"""
Leak Checking Page Module - MULTI-SITE ENHANCED
Analyzes vacuum improvements specifically from leak repair work
Tracks before/after vacuum levels for repair job codes
"""

import streamlit as st
import pandas as pd
from metrics import calculate_employee_effectiveness


def render(personnel_df, vacuum_df):
    """Render leak checking page showing vacuum improvements from repair work with site awareness"""

    st.title("⭐ Leak Checking")
    st.markdown("*Track vacuum improvements from inseason repairs and tubing issue fixes*")

    if personnel_df.empty or vacuum_df.empty:
        st.warning("Need both personnel and vacuum data for leak checking analysis")
        return

    # Check if we have site information
    has_personnel_site = 'Site' in personnel_df.columns
    has_vacuum_site = 'Site' in vacuum_df.columns

    # Find job code column
    from utils import find_column
    job_col = find_column(personnel_df, 'Job', 'job', 'Job Code', 'jobcode', 'task', 'work')
    
    if not job_col:
        st.error("❌ Job code column not found in personnel data")
        st.info("This page requires job code information to identify repair work. Available columns: " + ", ".join(personnel_df.columns))
        return
    
    # Filter to only repair-related job codes (no storm repair or road improvements)
    repair_keywords = ['inseason tubing repair', 'already identified tubing issue',
                       'fixing identified tubing', 'tubing repair', 'leak repair']

    # Create boolean mask for repair jobs (case insensitive), excluding storm/road
    repair_mask = personnel_df[job_col].str.lower().str.contains('|'.join(repair_keywords), na=False, case=False)
    exclude_mask = personnel_df[job_col].str.lower().str.contains('storm|road improvement', na=False, case=False)

    repair_df = personnel_df[repair_mask & ~exclude_mask].copy()

    # Show filtering info
    total_sessions = len(personnel_df)
    repair_sessions = len(repair_df)

    if repair_sessions == 0:
        st.warning(f"⚠️ No repair work found in {total_sessions:,} personnel records")
        st.info(f"""
        **Looking for job codes containing:**
        - "inseason tubing repair"
        - "already identified tubing issue"
        - "fixing identified tubing"
        - Other repair-related keywords (excluding storm repair and road improvements)

        **Job codes found in your data:**
        """)
        unique_jobs = personnel_df[job_col].dropna().unique()
        st.write(sorted(unique_jobs[:20]))
        if len(unique_jobs) > 20:
            st.caption(f"...and {len(unique_jobs) - 20} more")
        return
    
    st.info(f"🔍 **Analyzing {repair_sessions:,} repair sessions** from {total_sessions:,} total work sessions ({repair_sessions/total_sessions*100:.1f}%)")

    # Show which job codes are included
    repair_jobs = repair_df[job_col].unique()
    with st.expander("📋 Repair job codes included in analysis"):
        st.write(sorted(repair_jobs))

    # --- Filters ---
    from utils import extract_conductor_system

    # Add conductor system
    mainline_col = find_column(repair_df, 'mainline.', 'mainline', 'Mainline', 'location')
    if mainline_col:
        repair_df['Conductor System'] = repair_df[mainline_col].apply(extract_conductor_system)

    emp_col_name = find_column(repair_df, 'Employee Name', 'employee', 'name')
    date_col_name = find_column(repair_df, 'Date', 'date', 'timestamp')

    filter_col1, filter_col2, filter_col3 = st.columns(3)

    with filter_col1:
        if emp_col_name:
            employees = ['All'] + sorted([e for e in repair_df[emp_col_name].unique() if pd.notna(e)])
            selected_emp_filter = st.selectbox("Employee", employees, index=0, key="lc_emp_filter")
        else:
            selected_emp_filter = 'All'

    with filter_col2:
        if 'Conductor System' in repair_df.columns:
            systems = ['All'] + sorted([s for s in repair_df['Conductor System'].unique() if s and s != 'Unknown'])
            selected_system = st.selectbox("Conductor System", systems, index=0, key="lc_sys_filter")
        else:
            selected_system = 'All'

    with filter_col3:
        if date_col_name:
            repair_df[date_col_name] = pd.to_datetime(repair_df[date_col_name], errors='coerce')
            valid_dates = repair_df[date_col_name].dropna()
            if not valid_dates.empty:
                min_date = valid_dates.min().date()
                max_date = valid_dates.max().date()
                date_range = st.date_input("Date Range", value=(min_date, max_date), key="lc_date_filter")
            else:
                date_range = None
        else:
            date_range = None

    # Apply filters
    if selected_emp_filter != 'All' and emp_col_name:
        repair_df = repair_df[repair_df[emp_col_name] == selected_emp_filter]
    if selected_system != 'All' and 'Conductor System' in repair_df.columns:
        repair_df = repair_df[repair_df['Conductor System'] == selected_system]
    if date_range and date_col_name and len(date_range) == 2:
        repair_df = repair_df[
            (repair_df[date_col_name].dt.date >= date_range[0]) &
            (repair_df[date_col_name].dt.date <= date_range[1])
        ]

    repair_sessions = len(repair_df)
    if repair_sessions == 0:
        st.warning("No repair sessions match the selected filters")
        return

    st.divider()

    # Calculate effectiveness using only repair work
    with st.spinner("Analyzing leak repair effectiveness..."):
        effectiveness_df = calculate_employee_effectiveness(repair_df, vacuum_df)

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
                st.write("**Repair Work Mainlines:**")
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
                st.metric("Repair Sessions", debug['total_work_sessions'])

            with col2:
                st.metric("Matching Mainlines", len(debug['matching_mainlines']))

            with col3:
                st.metric("Successful Matches", debug['success_count'])

            if debug['matching_mainlines']:
                st.write("**Locations with repair work & vacuum data:**")
                st.write(sorted(list(debug['matching_mainlines'])))

            st.divider()

            st.write("**Why repair sessions didn't match:**")
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("No Mainline Match", debug['no_match_count'])
                st.caption("Location name doesn't exist in vacuum data")

            with col2:
                st.metric("No Before Reading", debug['no_before_count'])
                st.caption("No vacuum data 48h before repair")

            with col3:
                st.metric("No After Reading", debug['no_after_count'])
                st.caption("No vacuum data 48h after repair")

    if effectiveness_df.empty:
        st.warning("Could not match repair work with vacuum readings.")
        st.info("""
        **Common issues:**
        - Mainline names don't match between personnel and vacuum data
        - Not enough vacuum readings before/after repair work (need within 48 hours)
        - Date ranges don't overlap between datasets
        - No repair work logged with recognized job codes

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
            if 'Date' in repair_df.columns and 'Employee Name' in repair_df.columns:
                personnel_site = repair_df[['Date', 'Employee Name', 'Site']].copy()
                personnel_site.columns = ['Date', 'Employee', 'Site']
                
                # Merge to get site info
                effectiveness_df = effectiveness_df.merge(
                    personnel_site.drop_duplicates(),
                    on=['Date', 'Employee'],
                    how='left'
                )

    # Summary metrics
    st.subheader("📊 Leak Repair Impact")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Repair Sessions Analyzed", len(effectiveness_df))

    with col2:
        avg_improvement = effectiveness_df['Improvement'].mean()
        st.metric("Avg Vac Improvement", f"{avg_improvement:+.1f}\"",
                  delta=f"{avg_improvement:.1f}\"" if avg_improvement > 0 else None)

    with col3:
        positive_sessions = len(effectiveness_df[effectiveness_df['Improvement'] > 0])
        success_rate = (positive_sessions / len(effectiveness_df)) * 100
        st.metric("Successful Repairs", f"{success_rate:.0f}%")

    with col4:
        total_improvement = effectiveness_df['Improvement'].sum()
        st.metric("Total Vac Gained", f"{total_improvement:+.1f}\"")

    # Site-specific metrics if available
    if 'Site' in effectiveness_df.columns:
        st.markdown("---")
        st.subheader("🏢 Repair Performance by Site")
        
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
                    st.metric("Repairs", site_sessions)
                    
                    site_success = len(site_data[site_data['Improvement'] > 0]) / len(site_data) * 100
                    st.metric("Success Rate", f"{site_success:.0f}%")

    st.divider()

    # Employee Rankings
    st.subheader("🏆 Leak Repair Effectiveness by Employee")

    employee_stats = effectiveness_df.groupby('Employee').agg({
        'Improvement': ['mean', 'sum', 'count'],
        'Mainline': 'count',
        'Vacuum_Before': 'mean',
        'Vacuum_After': 'mean'
    }).reset_index()

    employee_stats.columns = ['Employee', 'Avg_Improvement', 'Total_Improvement',
                              'Repairs', 'Locations', 'Avg_Before', 'Avg_After']

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
        display_cols = ['Rank', 'Employee', 'Sites_Worked', 'Avg_Before', 'Avg_After', 'Avg_Improvement', 'Repairs', 'Total_Improvement']
        col_names = ['#', 'Employee', 'Sites', 'Vac Before', 'Vac After', 'Avg Δ', 'Repairs', 'Total Δ']
    else:
        display_cols = ['Rank', 'Employee', 'Avg_Before', 'Avg_After', 'Avg_Improvement', 'Repairs', 'Total_Improvement']
        col_names = ['#', 'Employee', 'Vac Before', 'Vac After', 'Avg Δ', 'Repairs', 'Total Δ']

    display_table = display[display_cols].copy()
    display_table.columns = col_names

    st.dataframe(display_table, use_container_width=True, hide_index=True, height=400)

    st.divider()

    # Site comparison chart if applicable
    if 'Site' in effectiveness_df.columns and len(effectiveness_df['Site'].unique()) > 1:
        st.subheader("📊 Cross-Site Repair Effectiveness")
        
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
        
        st.caption("📈 Compare leak repair effectiveness across sites")

    st.divider()

    # Individual employee detail
    st.subheader("📋 Individual Repair Sessions")

    selected_emp = st.selectbox("Select Employee", employee_stats['Employee'].tolist())

    if selected_emp:
        emp_sessions = effectiveness_df[effectiveness_df['Employee'] == selected_emp].copy()
        emp_sessions = emp_sessions.sort_values('Date', ascending=False)

        # Summary for this employee
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Repairs", len(emp_sessions))

        with col2:
            avg_imp = emp_sessions['Improvement'].mean()
            st.metric("Avg Improvement", f"{avg_imp:+.1f}\"")

        with col3:
            positive = len(emp_sessions[emp_sessions['Improvement'] > 0])
            pct = (positive / len(emp_sessions)) * 100
            st.metric("Successful Repairs", f"{positive}/{len(emp_sessions)} ({pct:.0f}%)")

        with col4:
            if 'Site' in emp_sessions.columns:
                sites_worked = ', '.join(sorted(emp_sessions['Site'].unique()))
                st.metric("Sites Worked", sites_worked)

        # Site breakdown if available
        if 'Site' in emp_sessions.columns and len(emp_sessions['Site'].unique()) > 1:
            st.markdown("**Repair Performance by Site:**")
            
            site_perf = emp_sessions.groupby('Site').agg({
                'Improvement': 'mean',
                'Mainline': 'count'
            }).reset_index()
            site_perf.columns = ['Site', 'Avg_Improvement', 'Repairs']
            
            cols = st.columns(len(site_perf))
            for idx, row in site_perf.iterrows():
                with cols[idx]:
                    emoji = "🟦" if row['Site'] == "NY" else "🟩" if row['Site'] == "VT" else "⚫"
                    st.metric(
                        f"{emoji} {row['Site']}", 
                        f"{row['Avg_Improvement']:+.1f}\"",
                        delta=f"{row['Repairs']} repairs"
                    )

        st.subheader("Repair History")

        # Display sessions
        display_sessions = emp_sessions.copy()
        display_sessions['Date'] = display_sessions['Date'].dt.strftime('%Y-%m-%d')
        display_sessions['Vacuum_Before'] = display_sessions['Vacuum_Before'].apply(lambda x: f"{x:.1f}\"")
        display_sessions['Vacuum_After'] = display_sessions['Vacuum_After'].apply(lambda x: f"{x:.1f}\"")
        display_sessions['Improvement'] = display_sessions['Improvement'].apply(
            lambda x: f"🟢 +{x:.1f}\"" if x > 0 else f"🔴 {x:.1f}\""
        )

        cols_to_show = ['Date', 'Mainline', 'Vacuum_Before', 'Vacuum_After', 'Improvement']
        col_labels = ['Date', 'Location', 'Vac Before', 'Vac After', 'Change']
        
        if 'Site' in display_sessions.columns:
            # Add site emoji to location
            display_sessions['Location_Display'] = display_sessions.apply(
                lambda row: f"{'🟦' if row['Site'] == 'NY' else '🟩' if row['Site'] == 'VT' else '⚫'} {row['Mainline']}",
                axis=1
            )
            cols_to_show = ['Date', 'Location_Display', 'Vacuum_Before', 'Vacuum_After', 'Improvement']
            col_labels = ['Date', 'Location', 'Vac Before', 'Vac After', 'Change']
        
        if 'Hours' in display_sessions.columns:
            cols_to_show.append('Hours')
            col_labels.append('Hours')

        display_sessions = display_sessions[cols_to_show]
        display_sessions.columns = col_labels

        st.dataframe(display_sessions, use_container_width=True, hide_index=True)

        # Chart of improvements over time
        st.subheader("Repair Improvement Trend")

        chart_data = emp_sessions[['Date', 'Improvement']].copy()
        chart_data = chart_data.sort_values('Date')
        chart_data = chart_data.set_index('Date')

        st.line_chart(chart_data, use_container_width=True)

    st.divider()

    # ========================================================================
    # MAINLINE HISTORY — chronological view of all entries for a selected line
    # ========================================================================
    st.subheader("📜 Mainline History")
    st.markdown("*All personnel entries for a selected mainline — chronological order*")

    # Use the original personnel_df (unfiltered by job code) for full history
    _mainline_col = find_column(personnel_df, 'mainline.', 'mainline', 'Mainline', 'location')
    _date_col = find_column(personnel_df, 'Date', 'date', 'timestamp')
    _emp_col = find_column(personnel_df, 'Employee Name', 'employee', 'name')
    _job_col = find_column(personnel_df, 'Job', 'job', 'Job Code', 'jobcode', 'task', 'work')
    _hours_col = find_column(personnel_df, 'Hours', 'hours', 'time')
    _taps_in = find_column(personnel_df, 'Taps Put In', 'taps_in', 'taps put in')
    _taps_out = find_column(personnel_df, 'Taps Removed', 'taps_removed', 'taps out')
    _taps_cap = find_column(personnel_df, 'taps capped', 'taps_capped')
    _repairs = find_column(personnel_df, 'Repairs needed', 'repairs', 'repairs_needed')
    _notes = find_column(personnel_df, 'Notes', 'notes', 'note')

    if _mainline_col:
        # Build conductor system -> mainline mapping for two-level selection
        all_mainlines = sorted([m for m in personnel_df[_mainline_col].unique()
                                if pd.notna(m) and str(m).strip()])

        hist_col1, hist_col2 = st.columns(2)

        with hist_col1:
            ml_systems = ['All'] + sorted(set(extract_conductor_system(m) for m in all_mainlines if extract_conductor_system(m) != 'Unknown'))
            hist_system = st.selectbox("Filter by Conductor System", ml_systems, index=0, key="hist_sys")

        filtered_mainlines = all_mainlines
        if hist_system != 'All':
            filtered_mainlines = [m for m in all_mainlines if extract_conductor_system(m) == hist_system]

        with hist_col2:
            selected_ml = st.selectbox("Select Mainline", filtered_mainlines, index=0 if filtered_mainlines else None, key="hist_ml")

        if selected_ml:
            ml_data = personnel_df[personnel_df[_mainline_col] == selected_ml].copy()
            if _date_col:
                ml_data[_date_col] = pd.to_datetime(ml_data[_date_col], errors='coerce')
                ml_data = ml_data.sort_values(_date_col, ascending=True)

            # Build display columns
            hist_cols = []
            hist_names = []

            for col, name in [(_date_col, 'Date'), (_emp_col, 'Employee'), (_job_col, 'Job Code'),
                               (_hours_col, 'Hours'), (_taps_in, 'Taps In'), (_taps_out, 'Taps Out'),
                               (_taps_cap, 'Taps Capped'), (_repairs, 'Repairs Needed'), (_notes, 'Notes')]:
                if col and col in ml_data.columns:
                    hist_cols.append(col)
                    hist_names.append(name)

            if hist_cols:
                hist_display = ml_data[hist_cols].copy()
                if _date_col in hist_cols:
                    hist_display[_date_col] = hist_display[_date_col].dt.strftime('%Y-%m-%d').fillna('')
                hist_display.columns = hist_names
                st.dataframe(hist_display, use_container_width=True, hide_index=True)
            else:
                st.info("No displayable columns found")
    else:
        st.info("Mainline column not found in personnel data")

    st.divider()

    # Tips with leak checking focus
    with st.expander("💡 Understanding Leak Checking Metrics"):
        st.markdown("""
        **How Leak Checking Works:**
        
        This page specifically tracks vacuum improvements from repair work:
        - **Filtered to repair jobs only**: "inseason tubing repairs" and "already identified tubing issues"
        - **Before vacuum**: Average vacuum 48 hours BEFORE repair work started
        - **After vacuum**: Average vacuum 48 hours AFTER repair work completed
        - **Improvement**: After - Before (positive = successful leak repair!)
        
        **Why This Matters:**
        - Identify which employees are most effective at finding and fixing leaks
        - Verify that repair work actually improves vacuum levels
        - Track repair effectiveness across sites
        - Prioritize difficult locations that need experienced repair crews
        
        **What Makes a Good Repair:**
        - **+5" or more**: Excellent repair, major leak fixed
        - **+2" to +5"**: Good repair, solid improvement
        - **0" to +2"**: Minor improvement, small leak fixed
        - **Negative**: Problem may not be fixed, or new issue occurred
        
        **Multi-Site Features:**
        - Compare repair effectiveness between NY and VT
        - Track which employees work at which sites
        - Identify site-specific leak patterns
        - Share successful repair techniques across locations
        
        **Tips for Analysis:**
        - High performers should train others on leak detection
        - Negative results might indicate systemic issues, not employee error
        - Some leaks are harder to find/fix than others
        - Track improvement over time as crew gains experience
        - Compare employees working similar locations
        
        **Using This Data:**
        - Recognize employees who excel at leak repairs
        - Assign challenging repairs to experienced crew
        - Provide training for leak detection techniques
        - Verify repairs are actually solving problems
        - Schedule follow-up on locations with poor improvement
        """)
