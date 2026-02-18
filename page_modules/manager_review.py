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

    with col1:
        # Date range filter
        if 'Date' in df.columns:
            min_date = df['Date'].min()
            max_date = df['Date'].max()
            if pd.isna(min_date):
                min_date = datetime.now() - timedelta(days=30)
            if pd.isna(max_date):
                max_date = datetime.now()

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
        # Approval status filter
        status_filter = st.radio(
            "Status",
            ["All", "Pending Review", "Approved"],
            index=0,
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

    # ------------------------------------------------------------------
    # SUMMARY METRICS
    # ------------------------------------------------------------------
    total_rows = len(filtered)
    approved_count = len(filtered[filtered.get('Approval Status', pd.Series()) == 'Approved']) \
        if 'Approval Status' in filtered.columns else 0
    pending_count = total_rows - approved_count
    approval_rate = (approved_count / total_rows * 100) if total_rows > 0 else 0

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Rows", f"{total_rows:,}")
    with m2:
        st.metric("Approved", f"{approved_count:,}")
    with m3:
        st.metric("Pending", f"{pending_count:,}")
    with m4:
        st.metric("Approval Rate", f"{approval_rate:.0f}%")

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
    # APPROVE BUTTON
    # ------------------------------------------------------------------
    st.markdown("")  # spacer
    col_btn, col_info = st.columns([1, 3])

    with col_btn:
        approve_clicked = st.button(
            "✅ Approve Selected Data",
            type="primary",
            use_container_width=True,
            key="approve_btn"
        )

    with col_info:
        st.caption(
            f"This will save **{len(edited_data)}** rows as manager-approved. "
            "Approved data will replace the raw TSheets data in all dashboard calculations."
        )

    if approve_clicked:
        _save_approved(edited_data)

    # ------------------------------------------------------------------
    # HELP
    # ------------------------------------------------------------------
    with st.expander("ℹ️ How to use Manager Data Review"):
        st.markdown("""
        **Workflow:**

        1. **Filter** the data by date range and/or employee to focus on specific entries
        2. **Review** each row — check hours, taps, mainlines, job codes, etc.
        3. **Edit** any cell that needs correction (click the cell to edit)
        4. Click **✅ Approve Selected Data** when you're satisfied

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

        **Tips:**
        - Use the **Pending Review** filter to see only unapproved data
        - You can approve data in batches — filter by date range and approve a week at a time
        - Changes are NOT saved until you click the Approve button
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
