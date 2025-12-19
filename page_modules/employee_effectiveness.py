"""
Employee Effectiveness Page Module - MULTI-SITE ENHANCED
Analyzes vacuum improvements based on employee maintenance work
Now includes site tracking and cross-site comparison
"""

import streamlit as st
import pandas as pd
from metrics import calculate_employee_effectiveness


def render(personnel_df, vacuum_df):
    """Render employee effectiveness page showing vacuum improvements with site awareness"""

    st.title("⭐ Employee Effectiveness")
    st.markdown("*Track vacuum improvements based on who worked where*")

    if personnel_df.empty or vacuum_df.empty:
        st.warning("Need both personnel and vacuum data for effectiveness analysis")
        return

    # Check if we have site information
    has_personnel_site = 'Site' in personnel_df.columns
    has_vacuum_site = 'Site' in vacuum_df.columns

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

    # Add site information to effectiveness data if available
    if has_personnel_site:
        # Merge site info from personnel data
        if 'Date' in effectiveness_df.columns and 'Employee' in effectiveness_df.columns:
            # Create merge key from effectiveness_df
            eff_merge = effectiveness_df[['Date', 'Employee', 'Mainline']].copy()
            
            # Get site from personnel data
            if 'Date' in personnel_df.columns and 'Employee Name' in personnel_df.columns:
                personnel_site = personnel_df[['Date', 'Employee Name', 'Site']].copy()
                personnel_site.columns = ['Date', 'Employee', 'Site']
                
                # Merge to get site info
                effectiveness_df = effectiveness_df.merge(
                    personnel_site.drop_duplicates(),
                    on=['Date', 'Employee'],
                    how='left'
                )

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

    # Site-specific metrics if available
    if 'Site' in effectiveness_df.columns:
        st.markdown("---")
        st.subheader("🏢 Performance by Site")
        
        site_cols = st.columns(3)
        
        for idx, site in enumerate(['NY', 'VT', 'UNK']):
            site_data = effectiveness_df[effectiveness_df['Site'] == site]
            if not site_data.empty:
                with site_cols[idx]:
                    emoji = "🟦" if site == "NY" else "🟩" if site == "VT" else "⚫"
                    st.markdown(f"### {emoji} {site}")
                    
                    site_avg = site_data['Improvement'].mean()
                    st.metric("Avg Improvement", f"{site_avg:+.1f}\"")
                    
                    site_sessions = len(site_data)
                    st.metric("Sessions", site_sessions)
                    
                    site_success = len(site_data[site_data['Improvement'] > 0]) / len(site_data) * 100
                    st.metric("Success Rate", f"{site_success:.0f}%")

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

    # Add site information if available
    if 'Site' in effectiveness_df.columns:
        # Get sites each employee worked at
        emp_sites = effectiveness_df.groupby('Employee')['Site'].apply(
            lambda x: ', '.join(sorted(x.unique()))
        ).reset_index()
        emp_sites.columns = ['Employee', 'Sites_Worked']
        
        employee_stats = employee_stats.merge(emp_sites, on='Employee', how='left')

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

    # Select columns for display
    if 'Sites_Worked' in display.columns:
        display_cols = ['Rank', 'Employee', 'Sites_Worked', 'Avg_Improvement', 'Sessions', 'Total_Improvement']
        col_names = ['#', 'Employee', 'Sites', 'Avg Δ', 'Sessions', 'Total Δ']
    else:
        display_cols = ['Rank', 'Employee', 'Avg_Improvement', 'Sessions', 'Total_Improvement']
        col_names = ['#', 'Employee', 'Avg Δ', 'Sessions', 'Total Δ']

    display_table = display[display_cols].copy()
    display_table.columns = col_names

    st.dataframe(display_table, use_container_width=True, hide_index=True, height=400)

    st.divider()

    # Site comparison chart if applicable
    if 'Site' in effectiveness_df.columns and len(effectiveness_df['Site'].unique()) > 1:
        st.subheader("📊 Cross-Site Effectiveness Comparison")
        
        import plotly.graph_objects as go
        
        # Calculate average improvement by site
        site_avg = effectiveness_df.groupby('Site')['Improvement'].mean().reset_index()
        site_avg = site_avg.sort_values('Improvement', ascending=False)
        
        # Color code by site
        colors = []
        for site in site_avg['Site']:
            if site == 'NY':
                colors.append('#2196F3')  # Blue
            elif site == 'VT':
                colors.append('#4CAF50')  # Green
            else:
                colors.append('#9E9E9E')  # Gray
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=site_avg['Site'],
            y=site_avg['Improvement'],
            marker_color=colors,
            text=site_avg['Improvement'].apply(lambda x: f"{x:+.1f}\""),
            textposition='outside'
        ))
        
        fig.update_layout(
            yaxis_title="Average Vacuum Improvement (inches)",
            xaxis_title="Site",
            height=300,
            showlegend=False
        )
        
        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.caption("📈 Compare average vacuum improvement across sites to identify best practices")

    st.divider()

    # Individual employee detail
    st.subheader("📋 Individual Work Sessions")

    selected_emp = st.selectbox("Select Employee", employee_stats['Employee'].tolist())

    if selected_emp:
        emp_sessions = effectiveness_df[effectiveness_df['Employee'] == selected_emp].copy()
        emp_sessions = emp_sessions.sort_values('Date', ascending=False)

        # Summary for this employee
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Sessions", len(emp_sessions))

        with col2:
            avg_imp = emp_sessions['Improvement'].mean()
            st.metric("Average Improvement", f"{avg_imp:+.1f}\"")

        with col3:
            positive = len(emp_sessions[emp_sessions['Improvement'] > 0])
            pct = (positive / len(emp_sessions)) * 100
            st.metric("Positive Impact", f"{positive}/{len(emp_sessions)} ({pct:.0f}%)")

        with col4:
            if 'Site' in emp_sessions.columns:
                sites_worked = ', '.join(sorted(emp_sessions['Site'].unique()))
                st.metric("Sites Worked", sites_worked)

        # Site breakdown if available
        if 'Site' in emp_sessions.columns and len(emp_sessions['Site'].unique()) > 1:
            st.markdown("**Performance by Site:**")
            
            site_perf = emp_sessions.groupby('Site').agg({
                'Improvement': 'mean',
                'Mainline': 'count'
            }).reset_index()
            site_perf.columns = ['Site', 'Avg_Improvement', 'Sessions']
            
            cols = st.columns(len(site_perf))
            for idx, row in site_perf.iterrows():
                with cols[idx]:
                    emoji = "🟦" if row['Site'] == "NY" else "🟩" if row['Site'] == "VT" else "⚫"
                    st.metric(
                        f"{emoji} {row['Site']}", 
                        f"{row['Avg_Improvement']:+.1f}\"",
                        delta=f"{row['Sessions']} sessions"
                    )

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
        col_labels = ['Date', 'Location', 'Before', 'After', 'Change']
        
        if 'Site' in display_sessions.columns:
            # Add site emoji to location
            display_sessions['Location_Display'] = display_sessions.apply(
                lambda row: f"{'🟦' if row['Site'] == 'NY' else '🟩' if row['Site'] == 'VT' else '⚫'} {row['Mainline']}",
                axis=1
            )
            cols_to_show = ['Date', 'Location_Display', 'Vacuum_Before', 'Vacuum_After', 'Improvement']
            col_labels = ['Date', 'Location', 'Before', 'After', 'Change']
        
        if 'Hours' in display_sessions.columns:
            cols_to_show.append('Hours')
            col_labels.append('Hours')

        display_sessions = display_sessions[cols_to_show]
        display_sessions.columns = col_labels

        st.dataframe(display_sessions, use_container_width=True, hide_index=True)

        # Chart of improvements over time
        st.subheader("Improvement Trend")

        chart_data = emp_sessions[['Date', 'Improvement']].copy()
        chart_data = chart_data.sort_values('Date')
        chart_data = chart_data.set_index('Date')

        st.line_chart(chart_data, use_container_width=True)

    st.divider()

    # Tips with multi-site context
    with st.expander("💡 Understanding Employee Effectiveness"):
        st.markdown("""
        **How This Works:**
        
        For each work session, we compare vacuum readings:
        - **Before**: Average vacuum 48 hours before work
        - **After**: Average vacuum 48 hours after work
        - **Improvement**: After - Before (positive = good!)
        
        **Multi-Site Features:**
        - Track which employees work at which sites
        - Compare effectiveness across NY and VT
        - Identify site-specific best practices
        - Plan cross-site training opportunities
        
        **What Makes a Good Score:**
        - **+5" or more**: Excellent work, major improvement
        - **+2" to +5"**: Good work, solid improvement
        - **0" to +2"**: Minor improvement or maintenance
        - **Negative**: May indicate new problems or unrelated issues
        
        **Tips for Analysis:**
        - Compare employees working the same site
        - Look for patterns in high performers
        - Use for training and recognition
        - Consider site-specific challenges
        - Some locations are naturally harder to maintain
        
        **Using This Data:**
        - Recognize top performers publicly
        - Provide targeted training for specific techniques
        - Assign challenging locations to experienced crew
        - Track improvement over time as crew gains experience
        - Share best practices between sites
        """)
