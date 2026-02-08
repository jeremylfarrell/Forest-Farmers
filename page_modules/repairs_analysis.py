"""
Repairs Tracker Page Module
Displays repair items from the repairs_tracker Google Sheet tab.
Repairs are auto-populated from TSheets and managed by the operations manager.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime


def render(personnel_df, vacuum_df=None, repairs_df=None):
    """Render the repairs tracker page"""

    st.title("Repairs Tracker")
    st.markdown("*Repairs auto-populated from TSheets. Manager updates status in Google Sheets.*")

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
    col1, col2, col3 = st.columns(3)

    with col1:
        status_options = ['All'] + sorted(df['Status'].unique().tolist())
        selected_status = st.selectbox("Status", status_options, index=0)

    with col2:
        mainlines = ['All'] + sorted([m for m in df['Mainline'].unique() if m and str(m) != 'nan' and str(m).strip()])
        selected_mainline = st.selectbox("Mainline", mainlines, index=0)

    with col3:
        reporters = ['All'] + sorted([r for r in df['Found By'].unique() if r and str(r) != 'nan' and str(r).strip()])
        selected_reporter = st.selectbox("Found By", reporters, index=0)

    # Apply filters
    filtered = df.copy()
    if selected_status != 'All':
        filtered = filtered[filtered['Status'] == selected_status]
    if selected_mainline != 'All':
        filtered = filtered[filtered['Mainline'] == selected_mainline]
    if selected_reporter != 'All':
        filtered = filtered[filtered['Found By'] == selected_reporter]

    st.divider()

    # --- Open Repairs Table (main action list) ---
    open_repairs = filtered[filtered['Status'] == 'Open'].copy()

    if not open_repairs.empty:
        st.subheader(f"Open Repairs ({len(open_repairs)})")
        st.caption("Sorted by age — oldest items need attention first")

        open_repairs = open_repairs.sort_values('Age (Days)', ascending=False)

        # Color-code by age
        def age_color(age):
            if age > 14:
                return 'background-color: #ff6b6b22'
            elif age > 7:
                return 'background-color: #ffa50022'
            return ''

        display_cols = ['Repair ID', 'Date Found', 'Age (Days)', 'Mainline', 'Description', 'Found By']
        display_cols = [c for c in display_cols if c in open_repairs.columns]
        display_df = open_repairs[display_cols].copy()

        if 'Date Found' in display_df.columns:
            display_df['Date Found'] = display_df['Date Found'].dt.strftime('%Y-%m-%d').fillna('')

        styled = display_df.style.applymap(
            age_color, subset=['Age (Days)'] if 'Age (Days)' in display_df.columns else []
        )
        st.dataframe(styled, use_container_width=True, hide_index=True, height=400)
    else:
        if selected_status == 'All' or selected_status == 'Open':
            st.success("No open repairs!")

    st.divider()

    # --- Charts ---
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Repairs by Mainline")
        open_by_mainline = df[df['Status'] == 'Open'].groupby('Mainline').size().reset_index(name='Count')
        if not open_by_mainline.empty:
            open_by_mainline = open_by_mainline.sort_values('Count', ascending=True)
            fig = px.bar(open_by_mainline, x='Count', y='Mainline', orientation='h',
                         color='Count', color_continuous_scale=['#4CAF50', '#ff6b6b'])
            fig.update_layout(height=max(300, len(open_by_mainline) * 25 + 100),
                              showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No open repairs to chart")

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

    # --- Completed Repairs ---
    if not completed.empty:
        with st.expander(f"Completed Repairs ({len(completed)})"):
            comp_cols = ['Repair ID', 'Date Found', 'Mainline', 'Description', 'Found By',
                         'Date Resolved', 'Resolved By', 'Notes']
            comp_cols = [c for c in comp_cols if c in completed.columns]
            comp_display = completed[comp_cols].copy()
            if 'Date Found' in comp_display.columns:
                comp_display['Date Found'] = comp_display['Date Found'].dt.strftime('%Y-%m-%d').fillna('')
            if 'Date Resolved' in comp_display.columns:
                comp_display['Date Resolved'] = comp_display['Date Resolved'].dt.strftime('%Y-%m-%d').fillna('')
            comp_display = comp_display.sort_values('Date Found', ascending=False) if 'Date Found' in comp_display.columns else comp_display
            st.dataframe(comp_display, use_container_width=True, hide_index=True)

    # --- Deferred Repairs ---
    deferred = filtered[filtered['Status'] == 'Deferred']
    if not deferred.empty:
        with st.expander(f"Deferred Repairs ({len(deferred)})"):
            def_cols = ['Repair ID', 'Date Found', 'Age (Days)', 'Mainline', 'Description', 'Found By', 'Notes']
            def_cols = [c for c in def_cols if c in deferred.columns]
            def_display = deferred[def_cols].copy()
            if 'Date Found' in def_display.columns:
                def_display['Date Found'] = def_display['Date Found'].dt.strftime('%Y-%m-%d').fillna('')
            st.dataframe(def_display, use_container_width=True, hide_index=True)

    # --- How to Use ---
    with st.expander("How to use the Repairs Tracker"):
        st.markdown("""
        **Repairs are auto-populated from TSheets** each day when workers log issues
        in the "Repairs needed" field.

        **To manage repairs**, open the Google Sheet and go to the `repairs_tracker` tab:

        1. **Mark as Completed:** Change the `Status` column from `Open` to `Completed`,
           fill in `Date Resolved` and optionally `Resolved By`
        2. **Defer a repair:** Change `Status` to `Deferred` and add a note explaining why
        3. **Add context:** Use the `Notes` column for any additional information

        **Tips:**
        - Use Google Sheets Data Validation on the Status column for a dropdown
          (Data > Data validation > List: Open, Completed, Deferred)
        - Sort by Date Found to see the oldest issues first
        - The dashboard refreshes data every hour or on manual refresh
        """)
