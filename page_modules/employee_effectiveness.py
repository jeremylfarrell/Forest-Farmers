"""
Employee Effectiveness Page Module
Analyzes vacuum improvements based on employee maintenance work
"""

import streamlit as st
import pandas as pd
from metrics import calculate_employee_effectiveness


def render(personnel_df, vacuum_df):
    """Render employee effectiveness page showing vacuum improvements"""

    st.title("⭐ Employee Effectiveness")
    st.markdown("*Track vacuum improvements based on who worked where*")

    if personnel_df.empty or vacuum_df.empty:
        st.warning("Need both personnel and vacuum data for effectiveness analysis")
        return

    # Calculate effectiveness
    with st.spinner("Analyzing employee effectiveness..."):
        effectiveness_df = calculate_employee_effectiveness(personnel_df, vacuum_df)

    # Show debug info
    if hasattr(effectiveness_df, 'attrs') and 'debug_info' in effectiveness_df.attrs:
        debug = effectiveness_df.attrs['debug_info']

        # Check if missing columns is the issue
        if debug.get('missing_columns', False):
            st.error("❌ Missing Required Columns")
            st.write("**Column Mapping Found:**")

            col1, col2 = st.columns(2)

            with col1:
                st.write("**Personnel Data:**")
                cols = debug['column_mapping']['personnel']
                st.write(f"- Employee: `{cols['employee']}`" if cols['employee'] else "- Employee: ❌ NOT FOUND")
                st.write(f"- Date: `{cols['date']}`" if cols['date'] else "- Date: ❌ NOT FOUND")
                st.write(f"- Mainline: `{cols['mainline']}`" if cols['mainline'] else "- Mainline: ❌ NOT FOUND")
                st.write(f"- Hours: `{cols['hours']}`" if cols['hours'] else "- Hours: (optional)")

            with col2:
                st.write("**Vacuum Data:**")
                cols = debug['column_mapping']['vacuum']
                st.write(f"- Mainline: `{cols['mainline']}`" if cols['mainline'] else "- Mainline: ❌ NOT FOUND")
                st.write(f"- Reading: `{cols['reading']}`" if cols['reading'] else "- Reading: ❌ NOT FOUND")
                st.write(f"- Timestamp: `{cols['timestamp']}`" if cols['timestamp'] else "- Timestamp: ❌ NOT FOUND")

            st.info("""
            **Expected Column Names:**
            - Personnel: Looking for "mainline." (with period) for location
            - Vacuum: Looking for "Name" for location

            Go to Raw Data tab to see actual column names in your data!
            """)
            return

        with st.expander("🔍 Debug: Mainline Matching", expanded=effectiveness_df.empty):
            col1, col2 = st.columns(2)

            with col1:
                st.write("**Personnel Mainlines:**")
                if debug['personnel_mainlines']:
                    st.write(sorted(list(debug['personnel_mainlines']))[:20])
                    if len(debug['personnel_mainlines']) > 20:
                        st.caption(f"...and {len(debug['personnel_mainlines']) - 20} more")
                else:
                    st.write("None found")

            with col2:
                st.write("**Vacuum Mainlines:**")
                if debug['vacuum_mainlines']:
                    st.write(sorted(list(debug['vacuum_mainlines']))[:20])
                    if len(debug['vacuum_mainlines']) > 20:
                        st.caption(f"...and {len(debug['vacuum_mainlines']) - 20} more")
                else:
                    st.write("None found")

            st.divider()

            st.write("**Matching Results:**")
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Total Work Sessions", debug['total_work_sessions'])

            with col2:
                st.metric("Matching Mainlines", len(debug['matching_mainlines']))

            with col3:
                st.metric("Successful Matches", debug['success_count'])

            if debug['matching_mainlines']:
                st.write("**Locations that match between datasets:**")
                st.write(sorted(list(debug['matching_mainlines'])))

            st.divider()

            st.write("**Why sessions didn't match:**")
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("No Mainline Match", debug['no_match_count'])
                st.caption("Location name doesn't exist in vacuum data")

            with col2:
                st.metric("No Before Reading", debug['no_before_count'])
                st.caption("No vacuum data 48h before work")

            with col3:
                st.metric("No After Reading", debug['no_after_count'])
                st.caption("No vacuum data 48h after work")

    if effectiveness_df.empty:
        st.warning("Could not match employee work with vacuum readings.")
        st.info("""
        **Common issues:**
        - Mainline names don't match between personnel and vacuum data
        - Not enough vacuum readings before/after work sessions (need within 48 hours)
        - Date ranges don't overlap between datasets

        **Check the debug info above to see specific issues!**
        """)
        return

    # Summary metrics
    st.subheader("📊 Overall Impact")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Work Sessions Analyzed", len(effectiveness_df))

    with col2:
        avg_improvement = effectiveness_df['Improvement'].mean()
        st.metric("Average Improvement", f"{avg_improvement:+.1f}\"",
                  delta=f"{avg_improvement:.1f}\"" if avg_improvement > 0 else None)

    with col3:
        positive_sessions = len(effectiveness_df[effectiveness_df['Improvement'] > 0])
        success_rate = (positive_sessions / len(effectiveness_df)) * 100
        st.metric("Success Rate", f"{success_rate:.0f}%")

    with col4:
        total_improvement = effectiveness_df['Improvement'].sum()
        st.metric("Total Improvement", f"{total_improvement:+.1f}\"")

    st.divider()

    # Employee Rankings
    st.subheader("🏆 Employee Rankings by Vacuum Improvement")

    employee_stats = effectiveness_df.groupby('Employee').agg({
        'Improvement': ['mean', 'sum', 'count'],
        'Mainline': 'count',
        'Vacuum_Before': 'mean',
        'Vacuum_After': 'mean'
    }).reset_index()

    employee_stats.columns = ['Employee', 'Avg_Improvement', 'Total_Improvement',
                              'Sessions', 'Locations', 'Avg_Before', 'Avg_After']

    # Sort by average improvement
    employee_stats = employee_stats.sort_values('Avg_Improvement', ascending=False)

    # Display rankings
    display = employee_stats.copy()
    display['Avg_Improvement'] = display['Avg_Improvement'].apply(lambda x: f"{x:+.1f}\"")
    display['Total_Improvement'] = display['Total_Improvement'].apply(lambda x: f"{x:+.1f}\"")
    display['Avg_Before'] = display['Avg_Before'].apply(lambda x: f"{x:.1f}\"")
    display['Avg_After'] = display['Avg_After'].apply(lambda x: f"{x:.1f}\"")

    # Add rank
    display.insert(0, 'Rank', range(1, len(display) + 1))

    st.dataframe(display, use_container_width=True, hide_index=True, height=400)

    st.divider()

    # Individual employee detail
    st.subheader("📋 Individual Work Sessions")

    selected_emp = st.selectbox("Select Employee", employee_stats['Employee'].tolist())

    if selected_emp:
        emp_sessions = effectiveness_df[effectiveness_df['Employee'] == selected_emp].copy()
        emp_sessions = emp_sessions.sort_values('Date', ascending=False)

        # Summary for this employee
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Sessions", len(emp_sessions))

        with col2:
            avg_imp = emp_sessions['Improvement'].mean()
            st.metric("Average Improvement", f"{avg_imp:+.1f}\"")

        with col3:
            positive = len(emp_sessions[emp_sessions['Improvement'] > 0])
            pct = (positive / len(emp_sessions)) * 100
            st.metric("Positive Impact", f"{positive}/{len(emp_sessions)} ({pct:.0f}%)")

        st.subheader("Work History")

        # Display sessions
        display_sessions = emp_sessions.copy()
        display_sessions['Date'] = display_sessions['Date'].dt.strftime('%Y-%m-%d')
        display_sessions['Vacuum_Before'] = display_sessions['Vacuum_Before'].apply(lambda x: f"{x:.1f}\"")
        display_sessions['Vacuum_After'] = display_sessions['Vacuum_After'].apply(lambda x: f"{x:.1f}\"")
        display_sessions['Improvement'] = display_sessions['Improvement'].apply(
            lambda x: f"🟢 +{x:.1f}\"" if x > 0 else f"🔴 {x:.1f}\""
        )

        cols_to_show = ['Date', 'Mainline', 'Vacuum_Before', 'Vacuum_After', 'Improvement']
        if 'Hours' in display_sessions.columns:
            cols_to_show.append('Hours')

        display_sessions = display_sessions[cols_to_show]
        display_sessions.columns = ['Date', 'Location', 'Before', 'After', 'Change'] + (
            ['Hours'] if 'Hours' in display_sessions.columns else [])

        st.dataframe(display_sessions, use_container_width=True, hide_index=True)

        # Chart of improvements over time
        st.subheader("Improvement Trend")

        chart_data = emp_sessions[['Date', 'Improvement']].copy()
        chart_data = chart_data.sort_values('Date')
        chart_data = chart_data.set_index('Date')

        st.line_chart(chart_data, use_container_width=True)
