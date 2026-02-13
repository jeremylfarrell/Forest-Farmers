"""
Repairs Tracker Page Module
Interactive repairs management using st.data_editor.
Manager can update Status, Date Resolved, Resolved By, and Notes directly in the dashboard.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from data_loader import save_repairs_updates
from utils import extract_conductor_system


def render(personnel_df, vacuum_df=None, repairs_df=None):
    """Render the repairs tracker page with interactive editing"""

    st.title("Repairs Tracker")
    st.markdown("*Edit repairs directly below — change Status, add resolution details, then click Save.*")

    if repairs_df is None or repairs_df.empty:
        st.info(
            "No repairs data yet. Repairs will appear here automatically after the next "
            "TSheets sync when workers log issues in the 'Repairs needed' field."
        )
        return

    df = repairs_df.copy()

    # Calculate age for open repairs
    if 'Date Found' in df.columns:
        df['Age (Days)'] = (pd.Timestamp.now() - df['Date Found']).dt.days
    else:
        df['Age (Days)'] = 0

    # Normalize status values
    if 'Status' in df.columns:
        df['Status'] = df['Status'].str.strip().str.title()
        df['Status'] = df['Status'].replace({'': 'Open'})
    else:
        df['Status'] = 'Open'

    # Add conductor system column
    if 'Mainline' in df.columns:
        df['Conductor System'] = df['Mainline'].apply(extract_conductor_system)

    # --- Summary Metrics ---
    st.subheader("Summary")

    open_count = len(df[df['Status'] == 'Open'])
    completed_count = len(df[df['Status'] == 'Completed'])
    deferred_count = len(df[df['Status'] == 'Deferred'])
    total_actionable = open_count + completed_count
    completion_rate = (completed_count / total_actionable * 100) if total_actionable > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Open", open_count)
    with col2:
        st.metric("Completed", completed_count)
    with col3:
        st.metric("Deferred", deferred_count)
    with col4:
        st.metric("Completion Rate", f"{completion_rate:.0f}%")

    st.divider()

    # --- Filters ---
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        status_options = ['All'] + sorted(df['Status'].unique().tolist())
        selected_status = st.selectbox("Status", status_options, index=0)

    with col2:
        if 'Conductor System' in df.columns:
            systems = ['All'] + sorted([s for s in df['Conductor System'].unique() if s and s != 'Unknown'])
            selected_system = st.selectbox("Conductor System", systems, index=0)
        else:
            selected_system = 'All'

    with col3:
        mainlines = ['All'] + sorted([m for m in df['Mainline'].unique() if m and str(m) != 'nan' and str(m).strip()])
        selected_mainline = st.selectbox("Mainline", mainlines, index=0)

    with col4:
        reporters = ['All'] + sorted([r for r in df['Found By'].unique() if r and str(r) != 'nan' and str(r).strip()])
        selected_reporter = st.selectbox("Found By", reporters, index=0)

    # Apply filters
    filtered = df.copy()
    if selected_status != 'All':
        filtered = filtered[filtered['Status'] == selected_status]
    if selected_system != 'All' and 'Conductor System' in filtered.columns:
        filtered = filtered[filtered['Conductor System'] == selected_system]
    if selected_mainline != 'All':
        filtered = filtered[filtered['Mainline'] == selected_mainline]
    if selected_reporter != 'All':
        filtered = filtered[filtered['Found By'] == selected_reporter]

    st.divider()

    # --- Interactive Editor for Open Repairs ---
    open_repairs = filtered[filtered['Status'] == 'Open'].copy()

    if not open_repairs.empty:
        st.subheader(f"Open Repairs ({len(open_repairs)})")
        st.caption("Edit Status, Date Resolved, Resolved By, or Notes directly in the table. Click **Save Changes** when done.")

        open_repairs = open_repairs.sort_values('Age (Days)', ascending=False)

        # Prepare editor columns
        editor_cols = ['Repair ID', 'Date Found', 'Age (Days)', 'Mainline', 'Description',
                       'Found By', 'Status', 'Date Resolved', 'Resolved By', 'Notes']
        editor_cols = [c for c in editor_cols if c in open_repairs.columns]

        edit_df = open_repairs[editor_cols].copy()

        # Format Date Found for display but keep as string for editor
        if 'Date Found' in edit_df.columns:
            edit_df['Date Found'] = edit_df['Date Found'].dt.strftime('%Y-%m-%d').fillna('')

        # Ensure Date Resolved is string for the editor
        if 'Date Resolved' in edit_df.columns:
            edit_df['Date Resolved'] = edit_df['Date Resolved'].apply(
                lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and hasattr(x, 'strftime') else ''
            )

        # Ensure text columns are strings
        for col in ['Resolved By', 'Notes']:
            if col in edit_df.columns:
                edit_df[col] = edit_df[col].fillna('').astype(str)

        column_config = {
            'Repair ID': st.column_config.TextColumn('Repair ID', disabled=True),
            'Date Found': st.column_config.TextColumn('Date Found', disabled=True),
            'Age (Days)': st.column_config.NumberColumn('Age (Days)', disabled=True),
            'Mainline': st.column_config.TextColumn('Mainline', disabled=True),
            'Description': st.column_config.TextColumn('Description', disabled=True, width='large'),
            'Found By': st.column_config.TextColumn('Found By', disabled=True),
            'Status': st.column_config.SelectboxColumn(
                'Status', options=['Open', 'Completed', 'Deferred'], required=True
            ),
            'Date Resolved': st.column_config.TextColumn('Date Resolved', help='YYYY-MM-DD'),
            'Resolved By': st.column_config.TextColumn('Resolved By'),
            'Notes': st.column_config.TextColumn('Notes', width='medium'),
        }

        edited_open = st.data_editor(
            edit_df,
            column_config=column_config,
            use_container_width=True,
            hide_index=True,
            height=min(400 + len(edit_df) * 10, 800),
            key="open_repairs_editor"
        )

        # Save button for open repairs
        if st.button("Save Changes", key="save_open", type="primary"):
            _save_edits(edited_open)

    else:
        if selected_status == 'All' or selected_status == 'Open':
            st.success("No open repairs!")

    st.divider()

    # --- Charts ---
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Repairs by Conductor System")
        if 'Conductor System' in df.columns:
            open_by_system = df[df['Status'] == 'Open'].groupby('Conductor System').size().reset_index(name='Count')
            if not open_by_system.empty:
                open_by_system = open_by_system.sort_values('Count', ascending=True)
                fig = px.bar(open_by_system, x='Count', y='Conductor System', orientation='h',
                             color='Count', color_continuous_scale=['#4CAF50', '#ff6b6b'])
                fig.update_layout(height=max(300, len(open_by_system) * 30 + 100),
                                  showlegend=False, coloraxis_showscale=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No open repairs to chart")
        else:
            st.info("Mainline data not available for grouping")

    with chart_col2:
        st.subheader("Repairs by Reporter")
        by_reporter = df[df['Status'] == 'Open'].groupby('Found By').size().reset_index(name='Count')
        if not by_reporter.empty:
            by_reporter = by_reporter.sort_values('Count', ascending=True)
            fig = px.bar(by_reporter, x='Count', y='Found By', orientation='h',
                         color='Count', color_continuous_scale=['#2196F3', '#1565C0'])
            fig.update_layout(height=max(300, len(by_reporter) * 30 + 100),
                              showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No open repairs to chart")

    st.divider()

    # --- Repair Detail Table ---
    st.subheader("📋 Repair Detail")

    detail_df = filtered.copy()
    detail_cols = []
    detail_names = []

    if 'Conductor System' in detail_df.columns:
        detail_cols.append('Conductor System')
        detail_names.append('System')
    if 'Mainline' in detail_df.columns:
        detail_cols.append('Mainline')
        detail_names.append('Mainline')
    if 'Description' in detail_df.columns:
        detail_cols.append('Description')
        detail_names.append('Issue')
    if 'Found By' in detail_df.columns:
        detail_cols.append('Found By')
        detail_names.append('Reported By')
    if 'Date Found' in detail_df.columns:
        detail_cols.append('Date Found')
        detail_names.append('Date Found')
    if 'Resolved By' in detail_df.columns:
        detail_cols.append('Resolved By')
        detail_names.append('Fixed By')

    # Calculate days to fix
    if 'Date Found' in detail_df.columns and 'Date Resolved' in detail_df.columns:
        detail_df['Days to Fix'] = (detail_df['Date Resolved'] - detail_df['Date Found']).dt.days
        detail_df['Days to Fix'] = detail_df['Days to Fix'].apply(
            lambda x: f"{int(x)}d" if pd.notna(x) and x >= 0 else "Open"
        )
        detail_cols.append('Days to Fix')
        detail_names.append('Days to Fix')

    if 'Status' in detail_df.columns:
        detail_cols.append('Status')
        detail_names.append('Status')

    if detail_cols:
        detail_display = detail_df[detail_cols].copy()
        if 'Date Found' in detail_display.columns:
            detail_display['Date Found'] = detail_display['Date Found'].dt.strftime('%Y-%m-%d').fillna('')
        detail_display.columns = detail_names
        detail_display = detail_display.sort_values('Date Found', ascending=False) if 'Date Found' in detail_names else detail_display
        st.dataframe(detail_display, use_container_width=True, hide_index=True)

    st.divider()

    # --- Resolution Metrics ---
    completed = df[df['Status'] == 'Completed'].copy()
    if not completed.empty and 'Date Resolved' in completed.columns and 'Date Found' in completed.columns:
        valid_resolved = completed.dropna(subset=['Date Resolved', 'Date Found'])
        if not valid_resolved.empty:
            valid_resolved['Resolution Days'] = (valid_resolved['Date Resolved'] - valid_resolved['Date Found']).dt.days

            st.subheader("Resolution Metrics")
            col1, col2, col3 = st.columns(3)
            with col1:
                avg_days = valid_resolved['Resolution Days'].mean()
                st.metric("Avg Days to Resolve", f"{avg_days:.1f}")
            with col2:
                oldest_open = df[df['Status'] == 'Open']['Age (Days)'].max() if open_count > 0 else 0
                st.metric("Oldest Open Repair", f"{oldest_open} days")
            with col3:
                st.metric("Resolved This Month",
                          len(valid_resolved[valid_resolved['Date Resolved'] >= pd.Timestamp.now().replace(day=1)]))

            st.divider()

    # --- Completed Repairs (editable) ---
    if not completed.empty:
        with st.expander(f"Completed Repairs ({len(completed)})"):
            comp_cols = ['Repair ID', 'Date Found', 'Mainline', 'Description', 'Found By',
                         'Status', 'Date Resolved', 'Resolved By', 'Notes']
            comp_cols = [c for c in comp_cols if c in completed.columns]
            comp_edit = completed[comp_cols].copy()

            if 'Date Found' in comp_edit.columns:
                comp_edit['Date Found'] = comp_edit['Date Found'].dt.strftime('%Y-%m-%d').fillna('')
            if 'Date Resolved' in comp_edit.columns:
                comp_edit['Date Resolved'] = comp_edit['Date Resolved'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and hasattr(x, 'strftime') else ''
                )
            for col in ['Resolved By', 'Notes']:
                if col in comp_edit.columns:
                    comp_edit[col] = comp_edit[col].fillna('').astype(str)

            comp_edit = comp_edit.sort_values('Date Found', ascending=False) if 'Date Found' in comp_edit.columns else comp_edit

            comp_config = {
                'Repair ID': st.column_config.TextColumn('Repair ID', disabled=True),
                'Date Found': st.column_config.TextColumn('Date Found', disabled=True),
                'Mainline': st.column_config.TextColumn('Mainline', disabled=True),
                'Description': st.column_config.TextColumn('Description', disabled=True, width='large'),
                'Found By': st.column_config.TextColumn('Found By', disabled=True),
                'Status': st.column_config.SelectboxColumn(
                    'Status', options=['Open', 'Completed', 'Deferred'], required=True
                ),
                'Date Resolved': st.column_config.TextColumn('Date Resolved', help='YYYY-MM-DD'),
                'Resolved By': st.column_config.TextColumn('Resolved By'),
                'Notes': st.column_config.TextColumn('Notes', width='medium'),
            }

            edited_comp = st.data_editor(
                comp_edit,
                column_config=comp_config,
                use_container_width=True,
                hide_index=True,
                key="completed_repairs_editor"
            )

            if st.button("Save Changes", key="save_completed", type="primary"):
                _save_edits(edited_comp)

    # --- Deferred Repairs (editable) ---
    deferred = filtered[filtered['Status'] == 'Deferred']
    if not deferred.empty:
        with st.expander(f"Deferred Repairs ({len(deferred)})"):
            def_cols = ['Repair ID', 'Date Found', 'Age (Days)', 'Mainline', 'Description',
                        'Found By', 'Status', 'Date Resolved', 'Resolved By', 'Notes']
            def_cols = [c for c in def_cols if c in deferred.columns]
            def_edit = deferred[def_cols].copy()

            if 'Date Found' in def_edit.columns:
                def_edit['Date Found'] = def_edit['Date Found'].dt.strftime('%Y-%m-%d').fillna('')
            if 'Date Resolved' in def_edit.columns:
                def_edit['Date Resolved'] = def_edit['Date Resolved'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and hasattr(x, 'strftime') else ''
                )
            for col in ['Resolved By', 'Notes']:
                if col in def_edit.columns:
                    def_edit[col] = def_edit[col].fillna('').astype(str)

            def_config = {
                'Repair ID': st.column_config.TextColumn('Repair ID', disabled=True),
                'Date Found': st.column_config.TextColumn('Date Found', disabled=True),
                'Age (Days)': st.column_config.NumberColumn('Age (Days)', disabled=True),
                'Mainline': st.column_config.TextColumn('Mainline', disabled=True),
                'Description': st.column_config.TextColumn('Description', disabled=True, width='large'),
                'Found By': st.column_config.TextColumn('Found By', disabled=True),
                'Status': st.column_config.SelectboxColumn(
                    'Status', options=['Open', 'Completed', 'Deferred'], required=True
                ),
                'Date Resolved': st.column_config.TextColumn('Date Resolved', help='YYYY-MM-DD'),
                'Resolved By': st.column_config.TextColumn('Resolved By'),
                'Notes': st.column_config.TextColumn('Notes', width='medium'),
            }

            edited_def = st.data_editor(
                def_edit,
                column_config=def_config,
                use_container_width=True,
                hide_index=True,
                key="deferred_repairs_editor"
            )

            if st.button("Save Changes", key="save_deferred", type="primary"):
                _save_edits(edited_def)

    # --- How to Use ---
    with st.expander("How to use the Repairs Tracker"):
        st.markdown("""
        **Repairs are auto-populated from TSheets** each day when workers log issues
        in the "Repairs needed" field.

        **To manage repairs directly in this dashboard:**

        1. **Mark as Completed:** Change the `Status` dropdown from `Open` to `Completed`,
           fill in `Date Resolved` (YYYY-MM-DD) and optionally `Resolved By`
        2. **Defer a repair:** Change `Status` to `Deferred` and add a note explaining why
        3. **Add context:** Use the `Notes` column for any additional information
        4. **Save:** Click the **Save Changes** button to write your updates to Google Sheets

        **Tips:**
        - Changes are NOT saved until you click **Save Changes**
        - The dashboard refreshes data every hour or on manual refresh
        - You can still edit directly in Google Sheets if preferred
        """)


def _save_edits(edited_df):
    """Save edits back to Google Sheets"""
    if 'Repair ID' not in edited_df.columns:
        st.error("Cannot save: Repair ID column missing")
        return

    # Get sheet config - try secrets first, then .env
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
        st.error("Could not find sheet URL in configuration")
        return

    with st.spinner("Saving changes to Google Sheets..."):
        success, message = save_repairs_updates(sheet_url, credentials_file, edited_df)

    if success:
        st.success(f"Saved! {message}")
        st.rerun()
    else:
        st.error(message)
