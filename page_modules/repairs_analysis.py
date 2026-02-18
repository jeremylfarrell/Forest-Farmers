"""
Repairs Needed Page Module
Interactive repairs management using st.data_editor.
Manager can update Status, Date Resolved, Resolved By, Repair Cost, and Notes.
Completed repairs move to a separate tab.
Cost summary splits by job code: Fixing Identified Issues vs Leak Checking.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from data_loader import save_repairs_updates
from metrics import calculate_repair_cost_breakdown
from utils import extract_conductor_system


def render(personnel_df, vacuum_df=None, repairs_df=None):
    """Render the Repairs Needed page with interactive editing"""

    st.title("Repairs Needed")
    st.markdown("*Track and manage identified tubing repairs. Mark repairs as completed when fixed.*")

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

    # Ensure Repair Cost column exists
    if 'Repair Cost' not in df.columns:
        df['Repair Cost'] = ''

    # --- Auto-complete repairs from TSheets ---
    # If someone clocked into a mainline with a "Fixing Identified Tubing Issues"
    # job code AFTER the repair was found, auto-mark it as Completed.
    auto_completed = _auto_complete_repairs(df, personnel_df)
    if auto_completed > 0:
        st.info(f"Auto-completed **{auto_completed}** repair(s) based on TSheets 'Fixing Identified Tubing Issues' entries.")

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

    # --- Cost Summary by Job Code ---
    cost_df = calculate_repair_cost_breakdown(personnel_df, df)
    if not cost_df.empty:
        st.subheader("Cost Summary")
        st.caption("Costs split by job code type. Cost/Tap uses **Fixing Issues** cost only.")

        total_fix = cost_df['Fix_Cost'].sum()
        total_leak = cost_df['LeakCheck_Cost'].sum()
        total_all = cost_df['Total_Cost'].sum()
        total_fix_hours = cost_df['Fix_Hours'].sum()
        total_leak_hours = cost_df['LeakCheck_Hours'].sum()

        # Taps for cost/tap calculation
        repairs_with_fix = cost_df[cost_df['Fix_Cost'] > 0]
        avg_cpt = repairs_with_fix['Cost_Per_Tap'].mean() if not repairs_with_fix.empty else 0

        cost_col1, cost_col2, cost_col3, cost_col4 = st.columns(4)
        with cost_col1:
            st.metric("Fixing Issues Cost", f"${total_fix:,.2f}",
                       help="Cost of 'Fixing Identified Tubing Issues' job code — going back to fix known problems")
        with cost_col2:
            st.metric("Leak Checking Cost", f"${total_leak:,.2f}",
                       help="Cost of 'Maple Tubing Inseason Repairs' job code — finding issues that cause low vacuum")
        with cost_col3:
            st.metric("Total Cost", f"${total_all:,.2f}")
        with cost_col4:
            st.metric("Avg Fix Cost/Tap", f"${avg_cpt:,.2f}",
                       help="Fixing cost only — does not include leak checking cost")

        with st.expander("Hours breakdown"):
            st.markdown(f"- **Fixing Issues:** {total_fix_hours:.1f}h (${total_fix:,.2f})")
            st.markdown(f"- **Leak Checking:** {total_leak_hours:.1f}h (${total_leak:,.2f})")

        # Merge cost data into main df for display
        df = df.merge(
            cost_df[['Repair ID', 'Fix_Cost', 'LeakCheck_Cost', 'Total_Cost', 'Cost_Per_Tap']],
            on='Repair ID', how='left'
        )
        for c in ['Fix_Cost', 'LeakCheck_Cost', 'Total_Cost', 'Cost_Per_Tap']:
            df[c] = df[c].fillna(0)

    st.divider()

    # --- Filters ---
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if 'Conductor System' in df.columns:
            systems = ['All'] + sorted([s for s in df['Conductor System'].unique() if s and s != 'Unknown'])
            selected_system = st.selectbox("Conductor System", systems, index=0)
        else:
            selected_system = 'All'

    with col2:
        mainlines = ['All'] + sorted([m for m in df['Mainline'].unique() if m and str(m) != 'nan' and str(m).strip()])
        selected_mainline = st.selectbox("Mainline", mainlines, index=0)

    with col3:
        reporters = ['All'] + sorted([r for r in df['Found By'].unique() if r and str(r) != 'nan' and str(r).strip()])
        selected_reporter = st.selectbox("Found By", reporters, index=0)

    with col4:
        st.write("")

    # Apply filters
    filtered = df.copy()
    if selected_system != 'All' and 'Conductor System' in filtered.columns:
        filtered = filtered[filtered['Conductor System'] == selected_system]
    if selected_mainline != 'All':
        filtered = filtered[filtered['Mainline'] == selected_mainline]
    if selected_reporter != 'All':
        filtered = filtered[filtered['Found By'] == selected_reporter]

    st.divider()

    # --- Tabbed View: Repairs Needed vs Completed ---
    tab1, tab2 = st.tabs(["🔧 Repairs Needed", "✅ Completed Repairs"])

    # ==========================================
    # TAB 1: OPEN / NEEDED REPAIRS (editable)
    # ==========================================
    with tab1:
        open_repairs = filtered[filtered['Status'] == 'Open'].copy()

        if not open_repairs.empty:
            st.subheader(f"Open Repairs ({len(open_repairs)})")
            st.caption("Edit Status, Date Resolved, Resolved By, Repair Cost, or Notes. Click **Save Changes** when done.")

            open_repairs = open_repairs.sort_values('Age (Days)', ascending=False)

            editor_cols = ['Repair ID', 'Date Found', 'Age (Days)', 'Mainline', 'Description',
                           'Found By', 'Status', 'Date Resolved', 'Resolved By', 'Repair Cost', 'Notes']
            editor_cols = [c for c in editor_cols if c in open_repairs.columns]

            edit_df = open_repairs[editor_cols].copy()

            if 'Date Found' in edit_df.columns:
                edit_df['Date Found'] = edit_df['Date Found'].dt.strftime('%Y-%m-%d').fillna('')
            if 'Date Resolved' in edit_df.columns:
                edit_df['Date Resolved'] = edit_df['Date Resolved'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and hasattr(x, 'strftime') else ''
                )

            for col in ['Resolved By', 'Notes', 'Repair Cost']:
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
                'Repair Cost': st.column_config.TextColumn('Repair Cost', help='Approx cost to fix (e.g. 45.50)'),
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

            if st.button("Save Changes", key="save_open", type="primary"):
                _save_edits(edited_open)

        else:
            st.success("No open repairs! All issues have been resolved.")

        st.divider()

        # Charts for open repairs
        open_all = df[df['Status'] == 'Open']
        if not open_all.empty:
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                st.subheader("By Conductor System")
                if 'Conductor System' in open_all.columns:
                    open_by_system = open_all.groupby('Conductor System').size().reset_index(name='Count')
                    if not open_by_system.empty:
                        open_by_system = open_by_system.sort_values('Count', ascending=True)
                        fig = px.bar(open_by_system, x='Count', y='Conductor System', orientation='h',
                                     color='Count', color_continuous_scale=['#4CAF50', '#ff6b6b'])
                        fig.update_layout(height=max(300, len(open_by_system) * 30 + 100),
                                          showlegend=False, coloraxis_showscale=False)
                        st.plotly_chart(fig, use_container_width=True)

            with chart_col2:
                st.subheader("By Reporter")
                by_reporter = open_all.groupby('Found By').size().reset_index(name='Count')
                if not by_reporter.empty:
                    by_reporter = by_reporter.sort_values('Count', ascending=True)
                    fig = px.bar(by_reporter, x='Count', y='Found By', orientation='h',
                                 color='Count', color_continuous_scale=['#2196F3', '#1565C0'])
                    fig.update_layout(height=max(300, len(by_reporter) * 30 + 100),
                                      showlegend=False, coloraxis_showscale=False)
                    st.plotly_chart(fig, use_container_width=True)

    # ==========================================
    # TAB 2: COMPLETED REPAIRS
    # ==========================================
    with tab2:
        completed = filtered[filtered['Status'] == 'Completed'].copy()

        if not completed.empty:
            st.subheader(f"Completed Repairs ({len(completed)})")

            if 'Date Resolved' in completed.columns and 'Date Found' in completed.columns:
                valid_resolved = completed.dropna(subset=['Date Resolved', 'Date Found'])
                if not valid_resolved.empty:
                    valid_resolved['Resolution Days'] = (valid_resolved['Date Resolved'] - valid_resolved['Date Found']).dt.days

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        avg_days = valid_resolved['Resolution Days'].mean()
                        st.metric("Avg Days to Resolve", f"{avg_days:.1f}")
                    with col2:
                        st.metric("Total Completed", len(completed))
                    with col3:
                        this_month = len(valid_resolved[valid_resolved['Date Resolved'] >= pd.Timestamp.now().replace(day=1)])
                        st.metric("Resolved This Month", this_month)

                    st.divider()

            detail_cols = ['Repair ID', 'Date Found', 'Mainline', 'Description', 'Found By',
                           'Date Resolved', 'Resolved By', 'Repair Cost', 'Notes']
            if 'Fix_Cost' in completed.columns:
                detail_cols.extend(['Fix_Cost', 'Cost_Per_Tap'])
            detail_cols = [c for c in detail_cols if c in completed.columns]

            comp_display = completed[detail_cols].copy()
            if 'Date Found' in comp_display.columns:
                comp_display['Date Found'] = comp_display['Date Found'].dt.strftime('%Y-%m-%d').fillna('')
            if 'Date Resolved' in comp_display.columns:
                comp_display['Date Resolved'] = comp_display['Date Resolved'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and hasattr(x, 'strftime') else ''
                )
            if 'Fix_Cost' in comp_display.columns:
                comp_display['Fix_Cost'] = comp_display['Fix_Cost'].apply(lambda x: f"${x:,.2f}" if x > 0 else "")
            if 'Cost_Per_Tap' in comp_display.columns:
                comp_display['Cost_Per_Tap'] = comp_display['Cost_Per_Tap'].apply(lambda x: f"${x:,.2f}" if x > 0 else "")

            comp_display = comp_display.sort_values('Date Resolved' if 'Date Resolved' in comp_display.columns else 'Date Found',
                                                     ascending=False)

            st.dataframe(comp_display, use_container_width=True, hide_index=True, height=500)

            with st.expander("Edit completed repairs (re-open, change details)"):
                comp_edit_cols = ['Repair ID', 'Date Found', 'Mainline', 'Description', 'Found By',
                                  'Status', 'Date Resolved', 'Resolved By', 'Repair Cost', 'Notes']
                comp_edit_cols = [c for c in comp_edit_cols if c in completed.columns]
                comp_edit = completed[comp_edit_cols].copy()

                if 'Date Found' in comp_edit.columns:
                    comp_edit['Date Found'] = comp_edit['Date Found'].dt.strftime('%Y-%m-%d').fillna('')
                if 'Date Resolved' in comp_edit.columns:
                    comp_edit['Date Resolved'] = comp_edit['Date Resolved'].apply(
                        lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and hasattr(x, 'strftime') else ''
                    )
                for col in ['Resolved By', 'Notes', 'Repair Cost']:
                    if col in comp_edit.columns:
                        comp_edit[col] = comp_edit[col].fillna('').astype(str)

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
                    'Repair Cost': st.column_config.TextColumn('Repair Cost', help='Approx cost to fix'),
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
        else:
            st.info("No completed repairs yet.")

    # --- Deferred Repairs ---
    deferred = filtered[filtered['Status'] == 'Deferred']
    if not deferred.empty:
        with st.expander(f"Deferred Repairs ({len(deferred)})"):
            def_cols = ['Repair ID', 'Date Found', 'Age (Days)', 'Mainline', 'Description',
                        'Found By', 'Status', 'Date Resolved', 'Resolved By', 'Repair Cost', 'Notes']
            def_cols = [c for c in def_cols if c in deferred.columns]
            def_edit = deferred[def_cols].copy()

            if 'Date Found' in def_edit.columns:
                def_edit['Date Found'] = def_edit['Date Found'].dt.strftime('%Y-%m-%d').fillna('')
            if 'Date Resolved' in def_edit.columns:
                def_edit['Date Resolved'] = def_edit['Date Resolved'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and hasattr(x, 'strftime') else ''
                )
            for col in ['Resolved By', 'Notes', 'Repair Cost']:
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
                'Repair Cost': st.column_config.TextColumn('Repair Cost', help='Approx cost to fix'),
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
    with st.expander("How to use Repairs Needed"):
        st.markdown("""
        **Repairs are auto-populated from TSheets** each day when workers log issues
        in the "Repairs needed" field.

        **To resolve a repair:**

        1. Change the `Status` dropdown from `Open` to `Completed`
        2. Fill in `Date Resolved` (YYYY-MM-DD) and `Resolved By`
        3. Optionally enter an approx `Repair Cost` (e.g. "45.50")
        4. Click **Save Changes** — the repair moves to the Completed tab

        **Cost Summary:**
        - **Fixing Issues Cost** = hours x rate for "Fixing Identified Tubing Issues" job code
          (going back to fix a known problem that was called out)
        - **Leak Checking Cost** = hours x rate for "Maple Tubing Inseason Repairs" job code
          (going out to find issues causing low vacuum)
        - **Cost/Tap** uses only the Fixing cost — not the leak checking cost

        **Tips:**
        - Changes are NOT saved until you click **Save Changes**
        - If a guy fixes something but doesn't make a TSheets entry, use `Repair Cost`
          to manually enter the approx cost
        - The dashboard refreshes data every hour or on manual refresh

        **Job Code Matching:**
        The dashboard matches TSheets job codes using keyword substrings (case-insensitive),
        so full job names like "Fixing Identified Tubing Issues - VT - 241114" are matched.

        Current keywords:
        - **Fixing:** "fixing identified tubing", "already identified tubing issue"
        - **Leak Checking:** "inseason tubing repair", "maple tubing inseason", "leak check"

        If additional job codes need to be recognized (e.g., clearing trees, etc.),
        update the keyword lists in `metrics.py → calculate_repair_cost_breakdown()`
        and `repairs_analysis.py → _auto_complete_repairs()`.
        """)


def _auto_complete_repairs(repairs_df, personnel_df):
    """
    Auto-complete open repairs when someone clocked into the same mainline
    with a 'Fixing Identified Tubing Issues' job code after the repair was found.

    Modifies repairs_df in-place. Returns count of auto-completed repairs.
    """
    from utils import find_column

    if personnel_df is None or personnel_df.empty:
        return 0

    mainline_col = find_column(personnel_df, 'mainline.', 'mainline', 'Mainline', 'location')
    job_col = find_column(personnel_df, 'Job', 'job', 'Job Code', 'jobcode')
    date_col = find_column(personnel_df, 'Date', 'date')
    emp_col = find_column(personnel_df, 'Employee Name', 'employee', 'name')

    if not all([mainline_col, job_col, date_col]):
        return 0

    # Get fixing job entries from personnel data
    fixing_keywords = ['fixing identified tubing', 'already identified tubing issue']
    p = personnel_df.copy()
    p['_job'] = p[job_col].astype(str).str.lower()
    p['_is_fixing'] = p['_job'].apply(lambda j: any(kw in j for kw in fixing_keywords))
    fixing_entries = p[p['_is_fixing']].copy()

    if fixing_entries.empty:
        return 0

    fixing_entries['_mainline'] = fixing_entries[mainline_col].astype(str).str.strip().str.upper()
    fixing_entries['_date'] = pd.to_datetime(fixing_entries[date_col], errors='coerce')
    fixing_entries['_emp'] = fixing_entries[emp_col] if emp_col else 'Unknown'

    auto_count = 0

    for idx, repair in repairs_df.iterrows():
        if repair.get('Status') != 'Open':
            continue

        mainline = str(repair.get('Mainline', '')).strip().upper()
        date_found = repair.get('Date Found')

        if pd.isna(date_found) or not mainline:
            continue

        # Find fixing entries on this mainline AFTER the repair was found
        matches = fixing_entries[
            (fixing_entries['_mainline'] == mainline) &
            (fixing_entries['_date'] >= date_found)
        ]

        if not matches.empty:
            # Use the first (earliest) fixing entry
            first_fix = matches.sort_values('_date').iloc[0]
            repairs_df.at[idx, 'Status'] = 'Completed'
            repairs_df.at[idx, 'Date Resolved'] = first_fix['_date']
            repairs_df.at[idx, 'Resolved By'] = str(first_fix.get('_emp', 'Auto'))
            if pd.isna(repairs_df.at[idx, 'Notes']) or str(repairs_df.at[idx, 'Notes']).strip() == '':
                repairs_df.at[idx, 'Notes'] = 'Auto-completed from TSheets'
            auto_count += 1

    return auto_count


def _save_edits(edited_df):
    """Save edits back to Google Sheets"""
    if 'Repair ID' not in edited_df.columns:
        st.error("Cannot save: Repair ID column missing")
        return

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
