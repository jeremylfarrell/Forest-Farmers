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


def render(personnel_df, vacuum_df=None):
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
    # FILTERS
    # ------------------------------------------------------------------
    st.subheader("Filters")
    col1, col2, col3 = st.columns(3)

    # Figure out smart default date range: cover all pending data
    has_pending = ('Approval Status' in df.columns and
                   (df['Approval Status'].isin(['Pending', 'TSheets Updated'])).any())

    # Pre-compute counts for status labels (on full dataset before filtering)
    _all_count = len(df)
    if 'Approval Status' in df.columns:
        _pending_count = len(df[df['Approval Status'] == 'Pending'])
        _approved_count = len(df[df['Approval Status'] == 'Approved'])
        _updated_count = len(df[df['Approval Status'] == 'TSheets Updated'])
    else:
        _pending_count = _all_count
        _approved_count = 0
        _updated_count = 0

    with col1:
        # Date range filter
        if 'Date' in df.columns:
            min_date = df['Date'].min()
            max_date = df['Date'].max()
            if pd.isna(min_date):
                min_date = datetime.now() - timedelta(days=30)
            if pd.isna(max_date):
                max_date = datetime.now()

            # Smart default: always include at least last 14 days so recent
            # data is visible regardless of status.  If there is pending data,
            # extend back to cover the oldest pending row as well.
            default_start = datetime.now() - timedelta(days=14)
            if has_pending:
                pending_mask = df['Approval Status'].isin(['Pending', 'TSheets Updated'])
                pending_dates = df.loc[pending_mask, 'Date'].dropna()
                if not pending_dates.empty:
                    default_start = min(default_start, pending_dates.min())

            # Clamp to available data range
            default_start = max(min_date, default_start)
            if default_start > max_date:
                default_start = min_date

            date_range = st.date_input(
                "Date Range",
                value=(default_start, max_date),
                min_value=min_date,
                max_value=max_date,
                key="mgr_review_dates"
            )
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

    with col3:
        # Approval status filter — default to "All" so the manager can see
        # everything, including recently approved data.  Counts help spot
        # items needing attention at a glance.
        status_options = [
            f"All ({_all_count})",
            f"Pending Review ({_pending_count})",
            f"Approved ({_approved_count})",
        ]
        # Add TSheets Updated option if any exist
        if _updated_count > 0:
            status_options.insert(2, f"TSheets Updated ({_updated_count})")

        default_status_idx = 0  # Always show all statuses by default

        status_filter_raw = st.radio(
            "Status",
            status_options,
            index=default_status_idx,
            key="mgr_review_status"
        )
        # Strip the count suffix for filtering logic
        status_filter = status_filter_raw.split(" (")[0]

    # ------------------------------------------------------------------
    # APPLY FILTERS
    # ------------------------------------------------------------------
    filtered = df.copy()

    if date_range and 'Date' in filtered.columns:
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start, end = date_range
            filtered = filtered[
                (filtered['Date'] >= pd.Timestamp(start)) &
                (filtered['Date'] <= pd.Timestamp(end))
            ]
        elif isinstance(date_range, (list, tuple)) and len(date_range) == 1:
            filtered = filtered[filtered['Date'] == pd.Timestamp(date_range[0])]

    if selected_employees and 'Employee Name' in filtered.columns:
        filtered = filtered[filtered['Employee Name'].isin(selected_employees)]

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
        'Notes', 'Site', 'Clock In', 'Clock Out', 'Approval Status'
    ]
    # Also include any other columns the manager might want to see
    # (e.g., Vehicle Used if it exists in the data)
    for extra_col in filtered.columns:
        if extra_col not in display_cols and extra_col not in ('_merge_key',):
            display_cols.append(extra_col)
    # Only use columns that exist
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

    # Format dates for display (keep as strings for the editor)
    if 'Date' in edit_df.columns:
        edit_df['Date'] = edit_df['Date'].apply(
            lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and hasattr(x, 'strftime') else ''
        )
    for clock_col in ['Clock In', 'Clock Out']:
        if clock_col in edit_df.columns:
            edit_df[clock_col] = edit_df[clock_col].apply(
                lambda x: x.strftime('%Y-%m-%d %H:%M') if pd.notna(x) and hasattr(x, 'strftime') else ''
            )

    # Ensure string columns don't have NaN displayed
    for col in ['Notes', 'Job', 'Employee Name', 'Site']:
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
            except (KeyError, FileNotFoundError, AttributeError):
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
    # DATA EDITOR (authorized managers only)
    # ------------------------------------------------------------------
    st.subheader(f"Personnel Data ({len(edit_df)} rows)")
    st.caption(
        "Edit any cell below. When done reviewing, click **Approve Selected Data** "
        "to save your corrections."
    )

    # Column configuration
    column_config = {
        'Employee Name': st.column_config.TextColumn('Employee', width='medium'),
        'Date': st.column_config.TextColumn('Date', help='YYYY-MM-DD'),
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
        'Approval Status': st.column_config.TextColumn('Status', disabled=True,
                                                         help='Set automatically on approval'),
    }

    edited_data = st.data_editor(
        edit_df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        height=min(500 + len(edit_df) * 5, 900),
        key="manager_review_editor"
    )

    # ------------------------------------------------------------------
    # APPROVE BUTTON (with confirmation)
    # ------------------------------------------------------------------
    st.markdown("")  # spacer

    # Two-step approval: first click shows confirmation, second click saves
    if 'confirm_approve' not in st.session_state:
        st.session_state.confirm_approve = False

    col_btn, col_info = st.columns([1, 3])

    if not st.session_state.confirm_approve:
        with col_btn:
            if st.button(
                "✅ Approve Selected Data",
                type="primary",
                use_container_width=True,
                key="approve_btn"
            ):
                st.session_state.confirm_approve = True
                st.rerun()

        with col_info:
            st.caption(
                f"This will save **{len(edited_data)}** rows as manager-approved. "
                "Approved data will replace the raw TSheets data in all dashboard calculations."
            )
    else:
        # Confirmation step
        st.warning(
            f"**Are you sure?** This will approve **{len(edited_data)}** rows "
            "and update the dashboard data."
        )
        col_yes, col_no, col_spacer = st.columns([1, 1, 2])
        with col_yes:
            if st.button("Yes, Approve", type="primary", use_container_width=True, key="confirm_yes"):
                st.session_state.confirm_approve = False
                _save_approved(edited_data)
        with col_no:
            if st.button("Cancel", use_container_width=True, key="confirm_no"):
                st.session_state.confirm_approve = False
                st.rerun()

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
        5. Click **Approve Selected Data** — you'll get a confirmation prompt before it saves

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
    except (KeyError, FileNotFoundError):
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

    # Add approval metadata
    save_df['Approved Date'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    save_df['Approved By'] = 'Manager'

    # Remove the Approval Status display column (it's computed, not stored)
    if 'Approval Status' in save_df.columns:
        save_df = save_df.drop(columns=['Approval Status'])

    with st.spinner("Saving approved data to Google Sheets..."):
        success, message = save_approved_personnel(sheet_url, credentials_file, save_df)

    if success:
        st.success(f"✅ {message}")
        st.balloons()
        st.rerun()
    else:
        st.error(f"❌ {message}")
