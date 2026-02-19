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
        "*Review raw TSheets data, correct any mistakes, and approve it. "
        "Approved data replaces the raw data across all dashboard pages.*"
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

    with col1:
        # Date range filter
        if 'Date' in df.columns:
            min_date = df['Date'].min()
            max_date = df['Date'].max()
            if pd.isna(min_date):
                min_date = datetime.now() - timedelta(days=30)
            if pd.isna(max_date):
                max_date = datetime.now()

            # Smart default: if there's pending data, start from the oldest
            # pending row so the manager sees everything that needs review.
            # Otherwise fall back to last 7 days.
            if has_pending:
                pending_mask = df['Approval Status'].isin(['Pending', 'TSheets Updated'])
                pending_dates = df.loc[pending_mask, 'Date'].dropna()
                if not pending_dates.empty:
                    default_start = pending_dates.min()
                else:
                    default_start = max(min_date, datetime.now() - timedelta(days=7))
            else:
                default_start = max(min_date, datetime.now() - timedelta(days=7))

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
        # Approval status filter — default to "Pending Review" if there's
        # pending data so the manager immediately sees what needs attention
        status_options = ["All", "Pending Review", "Approved"]
        # Add TSheets Updated option if any exist
        if 'Approval Status' in df.columns and (df['Approval Status'] == 'TSheets Updated').any():
            status_options.insert(2, "TSheets Updated")

        default_status_idx = 1 if has_pending else 0  # Default to Pending Review

        status_filter = st.radio(
            "Status",
            status_options,
            index=default_status_idx,
            key="mgr_review_status"
        )

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
    # Select and order columns for the editor
    display_cols = [
        'Employee Name', 'Date', 'Hours', 'Rate', 'Job', 'mainline.',
        'Taps Put In', 'Taps Removed', 'taps capped', 'Repairs needed',
        'Notes', 'Site', 'Clock In', 'Clock Out', 'Approval Status'
    ]
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
    # DATA EDITOR
    # ------------------------------------------------------------------
    st.subheader(f"Personnel Data ({len(edit_df)} rows)")
    st.caption(
        "Edit any cell below. When done reviewing, click **✅ Approve Selected Data** "
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
        2. **Review** each row — check hours, taps, mainlines, job codes, etc.
        3. **Edit** any cell that needs correction (click the cell to edit)
        4. Click **Approve Selected Data** — you'll get a confirmation prompt before it saves

        **What happens when you approve:**
        - All rows currently shown in the editor are saved to the
          `approved_personnel` tab in Google Sheets
        - Approved data automatically overrides the raw TSheets data
          for all dashboard pages (Tapping Operations, Employee Performance, etc.)
        - If you re-approve the same row (same Employee + Date + Job),
          it updates the existing entry — no duplicates

        **Status column:**
        - **Pending** — raw TSheets data, not yet reviewed
        - **Approved** — data has been reviewed and approved by a manager
        - **TSheets Updated** — was approved, but TSheets has since synced
          new data for this row (e.g. hours or taps changed). The dashboard
          still uses your approved version, but you should re-review and
          re-approve to pick up the changes.

        **TSheets change detection:**
        When TSheets syncs updated data for a row you already approved
        (e.g. someone corrected their hours in TSheets), the dashboard
        detects the difference and flags it as **TSheets Updated**. Use
        the filter to find these rows, review the changes, and re-approve.

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
