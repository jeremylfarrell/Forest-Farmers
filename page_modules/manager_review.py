"""
Manager Data Review Page Module
Allows managers to review raw TSheets personnel data, make corrections,
and approve it before it flows into the rest of the dashboard.
Approved data is saved to the 'approved_personnel' tab in Google Sheets.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from data_loader import save_approved_personnel


def render(personnel_df, vacuum_df=None, approved_df=None):
    """Render the Manager Data Review page"""

    st.title("📋 Manager Data Review")
    st.markdown(
        "*Review raw TSheets data, correct any mistakes, and approve corrections. "
        "Manager corrections override the raw TSheets data across all dashboard pages.*"
    )

    if personnel_df is None or personnel_df.empty:
        st.info("No personnel data loaded. Check your data connection.")
        return

    df = personnel_df.copy()

    # ------------------------------------------------------------------
    # FILTERS — Phase 1: render date + employee inputs, capture values
    # ------------------------------------------------------------------
    st.subheader("Filters")
    col1, col2, col3 = st.columns(3)

    with col1:
        # Date range filter
        if 'Date' in df.columns:
            min_date = df['Date'].min()
            max_date = df['Date'].max()
            if pd.isna(min_date):
                min_date = datetime.now() - timedelta(days=30)
            if pd.isna(max_date):
                max_date = datetime.now()

            # Smart default: start from the day after the last approval
            # so the manager sees only NEW data.  Fall back to full range
            # if no approvals exist yet.
            smart_default = min_date
            last_approval_label = None
            if approved_df is not None and not approved_df.empty and 'Approved Date' in approved_df.columns:
                try:
                    last_approval = approved_df['Approved Date'].max()
                    # Guard against object-dtype strings returned by a failed
                    # type conversion — hasattr check ensures strftime exists.
                    if pd.notna(last_approval) and hasattr(last_approval, 'strftime'):
                        next_day = (last_approval + timedelta(days=1)).date()
                        mn = min_date.date() if hasattr(min_date, 'date') else min_date
                        mx = max_date.date() if hasattr(max_date, 'date') else max_date
                        if mn <= next_day <= mx:
                            smart_default = pd.Timestamp(next_day)
                            last_approval_label = last_approval.strftime('%Y-%m-%d')
                except Exception:
                    pass  # non-fatal — fall back to full date range

            default_start = smart_default

            show_all = st.checkbox("Show all dates", value=False, key="mgr_show_all_dates")

            # When show_all is toggled, force-update the date_input session
            # state.  st.date_input ignores its value= parameter once the key
            # exists in st.session_state (after the user first touches the
            # widget), so we must write directly to session_state on change.
            _prev_show_all = st.session_state.get("_mgr_show_all_prev", None)
            if _prev_show_all is not None and show_all != _prev_show_all:
                _sd = min_date if show_all else smart_default
                _sd = _sd.date() if hasattr(_sd, 'date') else _sd
                _ed = max_date.date() if hasattr(max_date, 'date') else max_date
                st.session_state["mgr_review_dates"] = (_sd, _ed)
            st.session_state["_mgr_show_all_prev"] = show_all

            if show_all:
                default_start = min_date

            date_range = st.date_input(
                "Date Range",
                value=(default_start, max_date),
                min_value=min_date,
                max_value=max_date,
                key="mgr_review_dates"
            )
            if last_approval_label and not show_all:
                st.caption(f"📅 Showing since last approval ({last_approval_label})")
        else:
            date_range = None

    with col2:
        # Employee filter
        if 'Employee Name' in df.columns:
            employees = sorted(
                [e for e in df['Employee Name'].unique()
                 if e and str(e) != 'nan' and str(e).strip()]
            )
            selected_employees = st.multiselect(
                "Employees",
                options=employees,
                default=[],
                placeholder="All employees",
                key="mgr_review_employees"
            )
        else:
            selected_employees = []

    # ------------------------------------------------------------------
    # APPLY DATE + EMPLOYEE FILTERS (before rendering status radio so
    # the counts in the radio labels match what is actually visible)
    # ------------------------------------------------------------------
    filtered = df.copy()

    # Separate NaT-date rows, apply date filter to the rest, then
    # always re-include NaT rows so they are never silently hidden.
    nat_rows = pd.DataFrame()
    if 'Date' in filtered.columns:
        nat_mask = filtered['Date'].isna()
        if nat_mask.any():
            nat_rows = filtered[nat_mask].copy()
            filtered = filtered[~nat_mask]

    if date_range and 'Date' in filtered.columns:
        # Normalize: date_input can return a plain date scalar (not a tuple) in
        # transient state while the user is mid-selection.  Without this guard
        # neither branch below would match and the filter would silently be
        # skipped — showing all rows regardless of the selected range.
        if not isinstance(date_range, (list, tuple)):
            date_range = (date_range,)
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start, end = date_range
            # Strip timezone info to avoid silent failures in pandas 2.x when
            # comparing tz-aware timestamps (Google Sheets) with tz-naive ones.
            _dates = filtered['Date']
            if hasattr(_dates.dtype, 'tz') and _dates.dtype.tz is not None:
                _dates = _dates.dt.tz_localize(None)
            filtered = filtered[
                (_dates >= pd.Timestamp(start)) &
                (_dates <= pd.Timestamp(end))
            ]
        elif isinstance(date_range, (list, tuple)) and len(date_range) == 1:
            _dates = filtered['Date']
            if hasattr(_dates.dtype, 'tz') and _dates.dtype.tz is not None:
                _dates = _dates.dt.tz_localize(None)
            filtered = filtered[_dates == pd.Timestamp(date_range[0])]

    # Always include NaT-date rows so they can be reviewed and approved
    if not nat_rows.empty:
        st.info(
            f"**{len(nat_rows)} row(s) have missing dates** — "
            "included below for review."
        )
        filtered = pd.concat([filtered, nat_rows], ignore_index=True)

    if selected_employees and 'Employee Name' in filtered.columns:
        filtered = filtered[filtered['Employee Name'].isin(selected_employees)]

    # ------------------------------------------------------------------
    # FILTERS — Phase 2: render status radio with counts from filtered data
    # (counts now accurately reflect the current date + employee selection)
    # ------------------------------------------------------------------
    _all_count = len(filtered)
    if 'Approval Status' in filtered.columns:
        _pending_count = len(filtered[filtered['Approval Status'] == 'Pending'])
        _approved_count = len(filtered[filtered['Approval Status'] == 'Approved'])
        _updated_count = len(filtered[filtered['Approval Status'] == 'TSheets Updated'])
    else:
        _pending_count = _all_count
        _approved_count = 0
        _updated_count = 0

    with col3:
        # Build label → canonical-value map so we never parse the label string.
        _status_opt_map = {
            f"All ({_all_count})": "All",
            f"Pending Review ({_pending_count})": "Pending Review",
            f"Approved ({_approved_count})": "Approved",
        }
        if _updated_count > 0:
            # Insert TSheets Updated between Pending Review and Approved
            _items = list(_status_opt_map.items())
            _status_opt_map = dict(
                _items[:2]
                + [(f"TSheets Updated ({_updated_count})", "TSheets Updated")]
                + _items[2:]
            )

        status_filter_raw = st.radio(
            "Status",
            list(_status_opt_map.keys()),
            index=0,
            key="mgr_review_status"
        )
        status_filter = _status_opt_map.get(status_filter_raw, "All")

    # Apply status filter
    if status_filter != "All" and 'Approval Status' in filtered.columns:
        if status_filter == "Pending Review":
            filtered = filtered[filtered['Approval Status'] == 'Pending']
        elif status_filter == "Approved":
            filtered = filtered[filtered['Approval Status'] == 'Approved']
        elif status_filter == "TSheets Updated":
            filtered = filtered[filtered['Approval Status'] == 'TSheets Updated']

    # ------------------------------------------------------------------
    # SUMMARY METRICS
    # ------------------------------------------------------------------
    total_rows = len(filtered)
    if 'Approval Status' in filtered.columns:
        approved_count = len(filtered[filtered['Approval Status'] == 'Approved'])
        updated_count = len(filtered[filtered['Approval Status'] == 'TSheets Updated'])
        pending_count = total_rows - approved_count - updated_count
    else:
        approved_count = 0
        updated_count = 0
        pending_count = total_rows

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Rows", f"{total_rows:,}")
    with m2:
        st.metric("Pending", f"{pending_count:,}")
    with m3:
        st.metric("Approved", f"{approved_count:,}")
    with m4:
        st.metric("TSheets Updated", f"{updated_count:,}",
                   help="Rows that were approved but TSheets data has since changed. Needs re-review.")

    if updated_count > 0:
        st.warning(
            f"**{updated_count} row(s) changed in TSheets since approval.** "
            "Use the **TSheets Updated** filter to review them. "
            "Re-approve after reviewing to clear the flag."
        )

    st.divider()

    if filtered.empty:
        # Give a helpful explanation rather than a generic message.
        # Check full dataset for rows matching the selected status so the
        # manager knows whether to expand the date range or there is truly
        # nothing to review.
        _status_map = {
            "Pending Review": "Pending",
            "Approved": "Approved",
            "TSheets Updated": "TSheets Updated",
        }
        if status_filter != "All" and status_filter in _status_map and 'Approval Status' in df.columns:
            _full_count = len(df[df['Approval Status'] == _status_map[status_filter]])
            if _full_count > 0:
                st.warning(
                    f"No **{status_filter}** rows in the selected date range — "
                    f"but there are **{_full_count}** across all dates. "
                    "Try checking **Show all dates** to see them."
                )
            else:
                st.info(f"No rows with status **{status_filter}**.")
        else:
            st.warning("No data matches the selected filters.")
        return

    # ------------------------------------------------------------------
    # PREPARE EDITABLE DATAFRAME
    # ------------------------------------------------------------------
    # Select and order columns for the editor — show ALL columns the
    # manager wants to see, through Notes.  Vehicle Used is optional.
    display_cols = [
        'Employee Name', 'Date', 'Hours', 'Rate', 'Job', 'mainline.',
        'Taps Put In', 'Taps Removed', 'taps capped', 'Repairs needed',
        'Notes', 'Site', 'Clock In', 'Clock Out',
        'Approved Date', 'Approved By',   # audit trail — shown read-only below
        'Approval Status'
    ]
    # Include any extra columns from the data (e.g. Vehicle Used).
    # Exclude internal/duplicate columns that would confuse the editor:
    #  - '_merge_key'  : internal join key
    #  - 'mainline'    : no-period duplicate created by process_personnel_data
    #  - 'Approved Date', 'Approved By' : already included above
    _EXCLUDE_FROM_EDITOR = {
        '_merge_key', 'mainline', 'Approved Date', 'Approved By',
    }
    for extra_col in filtered.columns:
        if extra_col not in display_cols and extra_col not in _EXCLUDE_FROM_EDITOR:
            display_cols.append(extra_col)
    # Only use columns that exist in the data
    display_cols = [c for c in display_cols if c in filtered.columns]

    edit_df = filtered[display_cols].copy()

    # Sort by date descending, then employee
    sort_cols = []
    if 'Date' in edit_df.columns:
        sort_cols.append('Date')
    if 'Employee Name' in edit_df.columns:
        sort_cols.append('Employee Name')
    if sort_cols:
        ascending = [False] + [True] * (len(sort_cols) - 1)
        edit_df = edit_df.sort_values(sort_cols, ascending=ascending)

    # Format dates for display (keep as strings for the editor).
    # Include the time component so the full datetime is preserved through
    # the save round-trip — the emp|datetime merge key depends on it.
    if 'Date' in edit_df.columns:
        edit_df['Date'] = edit_df['Date'].apply(
            lambda x: x.strftime('%Y-%m-%d %H:%M') if pd.notna(x) and hasattr(x, 'strftime') else ''
        )
    for clock_col in ['Clock In', 'Clock Out']:
        if clock_col in edit_df.columns:
            edit_df[clock_col] = edit_df[clock_col].apply(
                lambda x: x.strftime('%Y-%m-%d %H:%M') if pd.notna(x) and hasattr(x, 'strftime') else ''
            )

    # Ensure string columns don't have NaN displayed.
    # mainline. is included so that empty cells show as blank (not 'nan')
    # and produce clean '' values in edited_data → consistent with make_key().
    for col in ['Notes', 'Job', 'Employee Name', 'Site', 'mainline.']:
        if col in edit_df.columns:
            edit_df[col] = edit_df[col].fillna('').astype(str)

    # Ensure numeric columns are clean
    for col in ['Hours', 'Rate', 'Taps Put In', 'Taps Removed', 'taps capped', 'Repairs needed']:
        if col in edit_df.columns:
            edit_df[col] = pd.to_numeric(edit_df[col], errors='coerce').fillna(0)

    # Reset index for clean editing
    edit_df = edit_df.reset_index(drop=True)

    # ------------------------------------------------------------------
    # MANAGER EDIT PASSWORD GATE
    # ------------------------------------------------------------------
    manager_edit_authorized = st.session_state.get("manager_edit_authorized", False)

    if not manager_edit_authorized:
        st.subheader(f"Personnel Data ({len(edit_df)} rows)")
        st.caption("*Read-only view. Enter the manager password below to edit and approve data.*")

        # Read-only table
        st.dataframe(
            edit_df,
            use_container_width=True,
            hide_index=True,
            height=min(500 + len(edit_df) * 5, 900),
        )

        st.divider()

        # Password input to unlock editing
        st.markdown("🔒 **Manager Edit Access**")

        def _manager_password_entered():
            """Callback for manager password input"""
            if "manager_password_input" not in st.session_state:
                return
            entered = st.session_state["manager_password_input"]
            # Check against Streamlit secrets first, fall back to hardcoded default
            try:
                correct_pw = st.secrets["passwords"]["manager_password"]
            except (KeyError, AttributeError):
                correct_pw = "MapleBirch"
            if entered == correct_pw:
                st.session_state["manager_edit_authorized"] = True
                del st.session_state["manager_password_input"]
            else:
                st.session_state["manager_edit_pw_wrong"] = True

        st.text_input(
            "Enter manager password to edit & approve",
            type="password",
            on_change=_manager_password_entered,
            key="manager_password_input",
        )
        if st.session_state.get("manager_edit_pw_wrong"):
            st.error("Incorrect password")
            st.session_state["manager_edit_pw_wrong"] = False

        return  # Don't show editor or approve button until authorized

    # ------------------------------------------------------------------
    # EXCEL UPLOAD (authorized managers only)
    # ------------------------------------------------------------------
    with st.expander("📤 Upload Corrected Data (Excel)"):
        st.markdown(
            "Upload a corrected timecard Excel file. The data will be saved as "
            "manager-approved corrections, overriding raw TSheets data."
        )
        uploaded_file = st.file_uploader(
            "Choose an Excel file",
            type=['xlsx'],
            key="mgr_excel_upload"
        )
        if uploaded_file is not None:
            try:
                upload_df = pd.read_excel(uploaded_file)
                st.success(f"Read **{len(upload_df):,}** rows from `{uploaded_file.name}`")

                # Column mapping: Excel format → dashboard format
                col_map = {
                    'site': 'Site',
                    'mainline': 'mainline.',
                    'Taps Deleted': 'Taps Removed',
                }
                upload_df = upload_df.rename(columns=col_map)

                # Build Employee Name from EE First + EE Last if needed
                if 'Employee Name' not in upload_df.columns:
                    if 'EE First' in upload_df.columns and 'EE Last' in upload_df.columns:
                        upload_df['Employee Name'] = (
                            upload_df['EE First'].astype(str).str.strip() + ' ' +
                            upload_df['EE Last'].astype(str).str.strip()
                        )

                # Ensure Date is datetime
                if 'Date' in upload_df.columns:
                    upload_df['Date'] = pd.to_datetime(upload_df['Date'], errors='coerce')

                # Ensure numeric columns
                for col in ['Hours', 'Rate', 'Taps Put In', 'Taps Removed',
                            'taps capped', 'Repairs needed']:
                    if col in upload_df.columns:
                        upload_df[col] = pd.to_numeric(upload_df[col], errors='coerce').fillna(0)

                # Add approval metadata
                upload_df['Approved Date'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                upload_df['Approved By'] = 'Manager (Excel Upload)'

                # Remove raw-only columns not needed in approved tab
                for drop_col in ['Employee ID', 'Class', 'vehicle',
                                 'EE First', 'EE Last', 'Approval Status']:
                    if drop_col in upload_df.columns:
                        upload_df = upload_df.drop(columns=[drop_col])

                # Preview
                st.dataframe(upload_df.head(20), use_container_width=True, hide_index=True)
                st.caption(f"Showing first 20 of {len(upload_df):,} rows")

                # Upload button
                if st.button(
                    f"✅ Upload & Approve All ({len(upload_df):,} rows)",
                    type="primary",
                    key="excel_upload_btn"
                ):
                    _save_approved(upload_df)

            except Exception as e:
                st.error(f"Error reading Excel file: {e}")

    st.divider()

    # ------------------------------------------------------------------
    # DATA EDITOR (authorized managers only)
    # ------------------------------------------------------------------
    st.subheader(f"Personnel Data ({len(edit_df)} rows)")
    st.caption(
        "Edit any cell below. "
        "⚠️ **Press Enter or Tab after editing a cell** to commit the change before clicking Approve — "
        "edits in an active (highlighted) cell are not captured. "
        "When done reviewing, click **Approve All** to save your corrections."
    )

    # Column configuration
    # The merge key is now  Employee Name | DateTime  (two fields only).
    # That means ALL other columns — including Job, mainline., Hours, Notes —
    # are freely editable by the manager.  Employee Name and Date are disabled
    # because they form the key: changing them here would break the match to
    # the raw TSheets row.  Corrections to name or date must come from TSheets.
    column_config = {
        'Employee Name': st.column_config.TextColumn(
            'Employee', width='medium', disabled=True,
            help='Part of the row key — cannot be edited here; correct in TSheets'
        ),
        'Date': st.column_config.TextColumn(
            'Date / Time', disabled=True,
            help='Date and time from TSheets — part of the row key, cannot be edited here'
        ),
        'Hours': st.column_config.NumberColumn('Hours', min_value=0, max_value=24, step=0.25, format="%.2f"),
        'Rate': st.column_config.NumberColumn('Rate', min_value=0, step=0.5, format="%.2f"),
        'Job': st.column_config.TextColumn('Job', width='large'),
        'mainline.': st.column_config.TextColumn('Mainline', width='medium'),
        'Taps Put In': st.column_config.NumberColumn('Taps In', min_value=0, step=1, format="%d"),
        'Taps Removed': st.column_config.NumberColumn('Taps Out', min_value=0, step=1, format="%d"),
        'taps capped': st.column_config.NumberColumn('Capped', min_value=0, step=1, format="%d"),
        'Repairs needed': st.column_config.NumberColumn('Repairs', min_value=0, step=1, format="%d"),
        'Notes': st.column_config.TextColumn('Notes', width='large'),
        'Site': st.column_config.SelectboxColumn(
            'Site', options=['NY', 'VT', 'UNK'], required=True
        ),
        'Clock In': st.column_config.TextColumn('Clock In', help='YYYY-MM-DD HH:MM'),
        'Clock Out': st.column_config.TextColumn('Clock Out', help='YYYY-MM-DD HH:MM'),
        'Approved Date': st.column_config.TextColumn(
            'Approved', disabled=True,
            help='When this row was last reviewed and approved'
        ),
        'Approved By': st.column_config.TextColumn(
            'Approved By', disabled=True,
            help='Who approved this row'
        ),
        'Approval Status': st.column_config.TextColumn('Status', disabled=True,
                                                         help='Set automatically on approval'),
    }
    # Disable any column not explicitly configured above (e.g. extra raw-data
    # columns added by the extra-cols loop).  Prevents unintended edits to
    # system or TSheets-generated fields.
    for _col in display_cols:
        if _col not in column_config:
            column_config[_col] = st.column_config.TextColumn(_col, disabled=True)

    edited_data = st.data_editor(
        edit_df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        height=min(500 + len(edit_df) * 5, 900),
        key="manager_review_editor"
    )

    # ------------------------------------------------------------------
    # APPROVE BUTTON (single button — approves all filtered rows)
    # ------------------------------------------------------------------
    st.markdown("")  # spacer

    full_count = len(edit_df)

    # Two-step approval: first click shows confirmation, second click saves
    if 'confirm_approve_all' not in st.session_state:
        st.session_state.confirm_approve_all = False

    if not st.session_state.confirm_approve_all:
        col_btn, col_info = st.columns([1, 2])
        with col_btn:
            if st.button(
                f"✅ Approve All ({full_count})",
                type="primary",
                use_container_width=True,
                key="approve_all_btn"
            ):
                st.session_state.confirm_approve_all = True
                st.rerun()
        with col_info:
            st.caption(
                f"This will save **{full_count}** rows as manager-approved."
            )
    else:
        st.warning(
            f"**Are you sure?** This will approve **{full_count}** rows "
            "matching your current filters and update the dashboard data."
        )
        col_yes, col_no, col_spacer = st.columns([1, 1, 2])
        with col_yes:
            if st.button("Yes, Approve", type="primary", use_container_width=True, key="confirm_yes_all"):
                st.session_state.confirm_approve_all = False
                _save_approved(edited_data)
        with col_no:
            if st.button("Cancel", use_container_width=True, key="confirm_no_all"):
                st.session_state.confirm_approve_all = False
                st.rerun()

    # ------------------------------------------------------------------
    # APPROVAL DIAGNOSTICS (collapsed — for troubleshooting only)
    # ------------------------------------------------------------------
    with st.expander("🔍 Approval Diagnostics (troubleshooting)"):
        st.caption(
            "Use this panel to see the exact keys the merge comparison is generating. "
            "If raw 'Pending' keys and approved keys look identical but rows still show as "
            "Pending, report what you see here."
        )
        col_d1, col_d2 = st.columns(2)

        with col_d1:
            st.markdown("**📄 Approved data from Google Sheets**")
            if approved_df is not None and not approved_df.empty:
                st.write(f"Rows in approved_personnel tab: **{len(approved_df)}**")
                _ml_col_a = 'mainline.' if 'mainline.' in approved_df.columns else None
                if _ml_col_a:
                    _ml_vcounts = (
                        approved_df[_ml_col_a].fillna('‹NaN›').astype(str)
                        .value_counts().head(6).to_dict()
                    )
                    st.write(f"`mainline.` values: `{_ml_vcounts}`")
                else:
                    st.warning("⚠️ No `mainline.` column in approved data")
                # Show sample keys (repr reveals hidden whitespace/chars)
                st.markdown("**Sample keys (repr shows hidden chars):**")
                for _, _row in approved_df.head(5).iterrows():
                    _emp = str(_row.get('Employee Name', ''))
                    _dv  = _row.get('Date', '')
                    _ds  = _dv.strftime('%Y-%m-%d %H:%M') if (hasattr(_dv, 'strftime') and pd.notna(_dv)) else str(_dv)
                    _ml_val = str(_row.get(_ml_col_a, '')) if _ml_col_a else ''
                    st.code(f"{repr(_emp)}|{repr(_ds)}  [mainline.={repr(_ml_val)}]")
            else:
                st.info("No approved data found in Google Sheets tab")

        with col_d2:
            st.markdown("**📊 Personnel data (post-merge)**")
            if 'Approval Status' in df.columns:
                for _st_val, _cnt in df['Approval Status'].value_counts().items():
                    st.write(f"- {_st_val}: **{_cnt}**")
            else:
                st.warning("No `Approval Status` column — merge may not have run")

            _ml_col_r = (
                'mainline.' if 'mainline.' in df.columns
                else 'mainline' if 'mainline' in df.columns
                else None
            )
            if _ml_col_r:
                _ml_vcounts_r = (
                    df[_ml_col_r].fillna('‹NaN›').astype(str)
                    .value_counts().head(6).to_dict()
                )
                st.write(f"`{_ml_col_r}` values (top 6): `{_ml_vcounts_r}`")
            else:
                st.warning("⚠️ No mainline column in raw/merged data")

            # Per-status mainline. breakdown
            if _ml_col_r and 'Approval Status' in df.columns:
                st.markdown("**`mainline.` by status:**")
                for _status in ['Approved', 'TSheets Updated', 'Pending']:
                    _sub = df[df['Approval Status'] == _status]
                    if not _sub.empty:
                        _counts = (
                            _sub[_ml_col_r].fillna('‹NaN›').astype(str)
                            .value_counts().head(4).to_dict()
                        )
                        st.write(f"  *{_status}*: `{_counts}`")

            # Sample APPROVED keys
            _approved_sample = (
                df[df['Approval Status'].isin(['Approved', 'TSheets Updated'])].head(5)
                if 'Approval Status' in df.columns else pd.DataFrame()
            )
            if not _approved_sample.empty:
                st.markdown("**Sample APPROVED keys:**")
                for _, _row in _approved_sample.iterrows():
                    _emp = str(_row.get('Employee Name', ''))
                    _dv  = _row.get('Date', '')
                    _ds  = _dv.strftime('%Y-%m-%d %H:%M') if (hasattr(_dv, 'strftime') and pd.notna(_dv)) else str(_dv)
                    _ml_val = str(_row.get(_ml_col_r, '')) if _ml_col_r else ''
                    st.code(f"{repr(_emp)}|{repr(_ds)}  [mainline.={repr(_ml_val)}]")
            else:
                st.info("No Approved rows in merged data yet")

            # Sample PENDING keys (should NOT match any approved keys)
            _pending_sample = (
                df[df['Approval Status'] == 'Pending'].head(5)
                if 'Approval Status' in df.columns else pd.DataFrame()
            )
            if not _pending_sample.empty:
                st.markdown("**Sample PENDING keys:**")
                for _, _row in _pending_sample.iterrows():
                    _emp = str(_row.get('Employee Name', ''))
                    _dv  = _row.get('Date', '')
                    _ds  = _dv.strftime('%Y-%m-%d %H:%M') if (hasattr(_dv, 'strftime') and pd.notna(_dv)) else str(_dv)
                    st.code(f"{repr(_emp)}|{repr(_ds)}")

    # ------------------------------------------------------------------
    # HELP
    # ------------------------------------------------------------------
    with st.expander("ℹ️ How to use Manager Data Review"):
        st.markdown("""
        **Workflow:**

        1. **Filter** the data by date range and/or employee to focus on specific entries
        2. **Enter the manager password** to unlock editing (the table is read-only until you authenticate)
        3. **Review** each row — check hours, taps, mainlines, job codes, etc.
        4. **Edit** any cell that needs correction (click the cell to edit)
        5. Click **Approve All** — you'll get a confirmation prompt before it saves

        **What happens when you approve:**
        - All rows currently shown in the editor are saved to the
          `approved_personnel` tab in Google Sheets
        - For any row where the manager has made corrections (same
          Employee + Date + Job key), the corrected version is used
          across all dashboard pages
        - All data is always visible on all pages — approval is for
          corrections only, not a gate
        - If you re-approve the same row, it updates the existing
          entry — no duplicates

        **Status column:**
        - **Pending** — raw TSheets data, not yet reviewed
        - **Approved** — data has been reviewed and approved by a manager
        - **TSheets Updated** — was approved, but TSheets has since synced
          new data for this row (e.g. hours or taps changed). The dashboard
          still uses your approved version, but you should re-review and
          re-approve to pick up the changes.

        **What can be edited:**
        - ✅ **Editable:** Hours, Rate, Job, Mainline, Taps, Notes, Site, Clock In/Out
        - 🔒 **Read-only:** Employee Name and Date / Time — these form the row
          identity key. If TSheets has the wrong name or date, fix it in TSheets
          then click **🔄 Personnel** to re-sync.

        **Tips:**
        - Use the **Pending Review** filter to see only unapproved data
        - You can approve data in batches — filter by date range and approve a week at a time
        - Changes are NOT saved until you click the Approve button and confirm
        - After approving, the dashboard will refresh and all pages will use the corrected data
        """)


def _save_approved(edited_df):
    """Save approved data to Google Sheets"""

    # Get sheet URL from config (same pattern as repairs_analysis.py)
    sheet_url = None
    credentials_file = 'credentials.json'

    try:
        if hasattr(st, 'secrets') and 'sheets' in st.secrets:
            sheet_url = st.secrets['sheets']['PERSONNEL_SHEET_URL']
    except (KeyError, AttributeError):
        pass

    if not sheet_url:
        try:
            import os
            from dotenv import load_dotenv
            load_dotenv()
            sheet_url = os.getenv('PERSONNEL_SHEET_URL')
        except ImportError:
            pass

    if not sheet_url:
        st.error("Could not find sheet URL in configuration.")
        return

    # Prepare the dataframe for saving
    save_df = edited_df.copy()

    # Always stamp a fresh approval timestamp so that re-approvals of
    # TSheets-Updated rows correctly update the audit trail.
    save_df['Approved Date'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    # Set approver for any row that doesn't already have one.  The Excel
    # Upload path pre-sets 'Manager (Excel Upload)' — that value is preserved.
    if 'Approved By' not in save_df.columns:
        save_df['Approved By'] = 'Manager'
    else:
        save_df['Approved By'] = (
            save_df['Approved By'].fillna('Manager').replace('', 'Manager')
        )

    # Remove the Approval Status display column (it's computed, not stored)
    if 'Approval Status' in save_df.columns:
        save_df = save_df.drop(columns=['Approval Status'])

    with st.spinner("Saving approved data to Google Sheets..."):
        success, message = save_approved_personnel(sheet_url, credentials_file, save_df)

    if success:
        st.success(f"✅ {message}")
        st.balloons()
        # save_approved_personnel already cleared the personnel caches
        # (load_approved_personnel, load_all_personnel_data, process_personnel_data).
        # A full st.cache_data.clear() is intentionally avoided here — it would
        # also evict vacuum data and force expensive reloads on the next render.
        st.rerun()
    else:
        st.error(f"❌ {message}")
