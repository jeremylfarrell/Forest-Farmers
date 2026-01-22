"""
Tapping Productivity Page Module - MULTI-SITE ENHANCED
Track tapping operations, employee productivity, and seasonal progress
UPDATED: Site-wide efficiency, minutes per tap by job type
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from utils import find_column


def render(personnel_df, vacuum_df):
    """Render tapping productivity page with site awareness"""

    st.title("🌳 Tapping Operations")
    st.markdown("*Track tapping productivity and seasonal progress across sites*")

    if personnel_df.empty:
        st.warning("No personnel data available for tapping analysis")
        return

    # Check if we have site information
    has_site = 'Site' in personnel_df.columns

    # Find relevant columns
    date_col = find_column(personnel_df, 'Date', 'date', 'timestamp')
    emp_col = find_column(personnel_df, 'Employee Name', 'employee', 'EE First', 'EE Last')
    hours_col = find_column(personnel_df, 'Hours', 'hours', 'time')
    rate_col = find_column(personnel_df, 'Rate', 'rate', 'pay_rate', 'hourly_rate')
    mainline_col = find_column(personnel_df, 'mainline.', 'mainline', 'Mainline', 'location')
    job_col = find_column(personnel_df, 'Job', 'job', 'Job Code', 'jobcode', 'task', 'work')

    # Tapping columns
    taps_in_col = find_column(personnel_df, 'Taps Put In', 'taps_in', 'taps put in')
    taps_out_col = find_column(personnel_df, 'Taps Removed', 'taps_removed', 'taps out')
    taps_capped_col = find_column(personnel_df, 'taps capped', 'taps_capped')
    repairs_col = find_column(personnel_df, 'Repairs needed', 'repairs', 'repairs_needed')

    if not all([date_col, emp_col]):
        st.error("Missing required columns in personnel data")
        return

    # Prepare data
    df = personnel_df.copy()
    df['Date'] = pd.to_datetime(df[date_col], errors='coerce')
    df = df.dropna(subset=['Date'])

    # Ensure numeric columns
    for col, name in [(taps_in_col, 'Taps_In'), (taps_out_col, 'Taps_Out'),
                      (taps_capped_col, 'Taps_Capped'), (repairs_col, 'Repairs')]:
        if col and col in df.columns:
            df[name] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[name] = 0

    if hours_col:
        df['Hours'] = pd.to_numeric(df[hours_col], errors='coerce').fillna(0)
    else:
        df['Hours'] = 0

    if rate_col:
        df['Rate'] = pd.to_numeric(df[rate_col], errors='coerce').fillna(0)
    else:
        df['Rate'] = 0

    df['Employee'] = df[emp_col]
    if mainline_col:
        df['Mainline'] = df[mainline_col]
    
    if job_col:
        df['Job_Code'] = df[job_col]
    else:
        df['Job_Code'] = 'Unknown'

    # Calculate net taps (taps added minus taps removed)
    df['Net_Taps'] = df['Taps_In'] - df['Taps_Out']

    # Calculate labor cost
    df['Labor_Cost'] = df['Hours'] * df['Rate']

    # ========================================================================
    # OVERALL SUMMARY (NO SITE BREAKDOWN)
    # ========================================================================

    st.subheader("📊 Season Summary")

    # Main metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        total_in = df['Taps_In'].sum()
        st.metric("Total Taps Installed", f"{int(total_in):,}")

    with col2:
        total_out = df['Taps_Out'].sum()
        st.metric("Total Taps Removed", f"{int(total_out):,}")

    with col3:
        net_change = df['Net_Taps'].sum()
        st.metric("Net Change", f"{int(net_change):,}",
                  delta=f"{int(net_change):,}")

    with col4:
        total_capped = df['Taps_Capped'].sum()
        st.metric("Taps Capped", f"{int(total_capped):,}")

    with col5:
        total_repairs = df['Repairs'].sum()
        st.metric("Repairs Needed", f"{int(total_repairs):,}")

    # SITE-WIDE EFFICIENCY METRICS
    st.divider()
    st.subheader("💰 Site-Wide Efficiency")

    total_hours = df['Hours'].sum()
    total_labor_cost = df['Labor_Cost'].sum()
    total_taps = df['Taps_In'].sum()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg_taps_per_hour = total_taps / total_hours if total_hours > 0 else 0
        st.metric("Avg Taps/Hour", f"{avg_taps_per_hour:.1f}")

    with col2:
        avg_mins_per_tap = (total_hours * 60) / total_taps if total_taps > 0 else 0
        st.metric("Avg Minutes/Tap", f"{avg_mins_per_tap:.1f}")

    with col3:
        avg_cost_per_tap = total_labor_cost / total_taps if total_taps > 0 else 0
        st.metric("Avg Cost/Tap", f"${avg_cost_per_tap:.2f}")

    with col4:
        st.metric("Total Labor Cost", f"${total_labor_cost:,.2f}")

    st.divider()

    # ========================================================================
    # TIME RANGE FILTER
    # ========================================================================

    col1, col2 = st.columns([2, 1])

    with col1:
        time_range = st.selectbox(
            "Time Range",
            ["Last 7 Days", "Last 30 Days", "This Season", "Custom Range"]
        )

    # Apply time filter
    if time_range == "Last 7 Days":
        cutoff = datetime.now() - timedelta(days=7)
        filtered_df = df[df['Date'] >= cutoff]
    elif time_range == "Last 30 Days":
        cutoff = datetime.now() - timedelta(days=30)
        filtered_df = df[df['Date'] >= cutoff]
    elif time_range == "Custom Range":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End Date", value=datetime.now())
        filtered_df = df[(df['Date'] >= pd.to_datetime(start_date)) &
                         (df['Date'] <= pd.to_datetime(end_date))]
    else:  # This Season
        filtered_df = df

    st.divider()

    # ========================================================================
    # DAILY TAPPING ACTIVITY
    # ========================================================================

    st.subheader("📈 Daily Tapping Activity")

    # Aggregate by date (and site if available)
    if has_site:
        daily = filtered_df.groupby([filtered_df['Date'].dt.date, 'Site']).agg({
            'Taps_In': 'sum',
            'Taps_Out': 'sum',
            'Net_Taps': 'sum',
            'Taps_Capped': 'sum',
            'Employee': 'nunique'
        }).reset_index()
        daily.columns = ['Date', 'Site', 'Taps_In', 'Taps_Out', 'Net_Taps', 'Taps_Capped', 'Employees']
    else:
        daily = filtered_df.groupby(filtered_df['Date'].dt.date).agg({
            'Taps_In': 'sum',
            'Taps_Out': 'sum',
            'Net_Taps': 'sum',
            'Taps_Capped': 'sum',
            'Employee': 'nunique'
        }).reset_index()
        daily.columns = ['Date', 'Taps_In', 'Taps_Out', 'Net_Taps', 'Taps_Capped', 'Employees']
    
    daily['Date'] = pd.to_datetime(daily['Date'])
    daily = daily.sort_values('Date')

    if not daily.empty:
        # Create chart with site colors if applicable
        fig = go.Figure()

        if has_site:
            # Stacked bars by site
            for site in sorted(daily['Site'].unique()):
                site_data = daily[daily['Site'] == site]
                color = '#2196F3' if site == 'NY' else '#4CAF50' if site == 'VT' else '#9E9E9E'
                
                fig.add_trace(go.Bar(
                    x=site_data['Date'],
                    y=site_data['Taps_In'],
                    name=f"{site} - Installed",
                    marker_color=color,
                    opacity=0.8,
                    hovertemplate=f'{site} Installed: %{{y}}<extra></extra>'
                ))
        else:
            # Simple grouped bars
            fig.add_trace(go.Bar(
                x=daily['Date'],
                y=daily['Taps_In'],
                name='Installed',
                marker_color='#28a745',
                hovertemplate='Installed: %{y}<extra></extra>'
            ))

            fig.add_trace(go.Bar(
                x=daily['Date'],
                y=daily['Taps_Out'],
                name='Removed',
                marker_color='#dc3545',
                hovertemplate='Removed: %{y}<extra></extra>'
            ))

        fig.update_layout(
            barmode='stack' if has_site else 'group',
            xaxis_title="Date",
            yaxis_title="Number of Taps",
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No tapping data for selected time range")

    st.divider()

    # ========================================================================
    # EMPLOYEE PRODUCTIVITY - WITH JOB TYPE BREAKDOWN
    # ========================================================================

    st.subheader("👥 Employee Productivity")
    
    st.markdown("**Minutes per tap by job type:**")
    st.caption("Shows time efficiency for tapping and repair work")

    # Normalize job codes to combine similar ones
    def normalize_job_code(job_code):
        """Extract the key part of job code, removing NY/VT numbers and normalizing case"""
        import re
        if pd.isna(job_code):
            return job_code
        name = str(job_code)
        # Remove state codes and numbers like "NY 240114", "- NY - 240114", "VT 240113"
        name = re.sub(r'\s*-?\s*(NY|VT|ny|vt)\s*-?\s*\d+', '', name)
        # Extract text in parentheses if present, otherwise use cleaned name
        if '(' in name and ')' in name:
            paren_text = name[name.find('(')+1:name.find(')')]
            return paren_text.strip().lower()
        # Remove "Maple Tapping" prefix variations
        name = re.sub(r'^Maple\s*[Tt]apping\s*-?\s*', '', name)
        return name.strip().lower() if name.strip() else job_code.lower()

    # Create normalized job code column
    filtered_df = filtered_df.copy()
    filtered_df['Job_Code_Normalized'] = filtered_df['Job_Code'].apply(normalize_job_code)

    # Calculate minutes per tap by NORMALIZED job type for each employee
    emp_job_stats = filtered_df.groupby(['Employee', 'Job_Code_Normalized']).agg({
        'Hours': 'sum',
        'Taps_In': 'sum'
    }).reset_index()

    # Calculate minutes per tap
    emp_job_stats['Minutes_Per_Tap'] = ((emp_job_stats['Hours'] * 60) / emp_job_stats['Taps_In']).round(1)
    emp_job_stats['Minutes_Per_Tap'] = emp_job_stats['Minutes_Per_Tap'].replace([float('inf'), float('-inf')], 0)

    # Filter to relevant job codes
    job_codes_to_show = []

    # Find tapping job codes (case insensitive)
    tapping_jobs = emp_job_stats[
        emp_job_stats['Job_Code_Normalized'].str.lower().str.contains('tap|spout|install', na=False, case=False)
    ]['Job_Code_Normalized'].unique()
    job_codes_to_show.extend(tapping_jobs)

    # Find repair job codes
    repair_jobs = emp_job_stats[
        emp_job_stats['Job_Code_Normalized'].str.lower().str.contains('repair|tubing|fixing', na=False, case=False)
    ]['Job_Code_Normalized'].unique()
    job_codes_to_show.extend(repair_jobs)
    
    # Remove duplicates from job_codes_to_show
    job_codes_to_show = list(dict.fromkeys(job_codes_to_show))

    if len(job_codes_to_show) > 0:
        # Pivot to show job codes as columns (using normalized names)
        pivot = emp_job_stats[emp_job_stats['Job_Code_Normalized'].isin(job_codes_to_show)].pivot(
            index='Employee',
            columns='Job_Code_Normalized',
            values='Minutes_Per_Tap'
        ).reset_index()
        
        # Add total taps and hours
        emp_totals = filtered_df.groupby('Employee').agg({
            'Taps_In': 'sum',
            'Hours': 'sum',
            'Labor_Cost': 'sum'
        }).reset_index()
        
        # Merge
        productivity = pivot.merge(emp_totals, on='Employee', how='left')
        
        # Calculate overall metrics
        productivity['Overall_Taps_Per_Hour'] = (productivity['Taps_In'] / productivity['Hours']).round(1)
        productivity['Overall_Taps_Per_Hour'] = productivity['Overall_Taps_Per_Hour'].replace([float('inf'), float('-inf')], 0)
        
        productivity['Cost_Per_Tap'] = (productivity['Labor_Cost'] / productivity['Taps_In']).round(2)
        productivity['Cost_Per_Tap'] = productivity['Cost_Per_Tap'].replace([float('inf'), float('-inf')], 0)
        
        # Sort by total taps
        productivity = productivity.sort_values('Taps_In', ascending=False)
        productivity = productivity[productivity['Taps_In'] > 0]
        
        if not productivity.empty:
            # Build display columns
            display_cols = ['Employee']
            col_names = ['Employee']
            
            # Add job code columns - names are already normalized
            for job_code in job_codes_to_show:
                if job_code in productivity.columns:
                    display_cols.append(job_code)
                    # Capitalize for display
                    display_name = job_code.title() if job_code else job_code
                    col_names.append(display_name)
            
            # Add totals
            display_cols.extend(['Taps_In', 'Hours', 'Overall_Taps_Per_Hour', 'Cost_Per_Tap', 'Labor_Cost'])
            col_names.extend(['Total Taps', 'Hours', 'Overall Taps/Hr', '$/Tap', 'Total Cost'])
            
            display = productivity[display_cols].copy()
            display.columns = col_names
            
            # Format currency
            if '$/Tap' in display.columns:
                display['$/Tap'] = display['$/Tap'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "N/A")
            if 'Total Cost' in display.columns:
                display['Total Cost'] = display['Total Cost'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A")
            
            st.dataframe(display, use_container_width=True, hide_index=True, height=400)
            
            # Summary stats
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Employees Tracked", len(productivity))
            
            with col2:
                avg_taps_hr = productivity['Overall_Taps_Per_Hour'].mean()
                st.metric("Avg Taps/Hour", f"{avg_taps_hr:.1f}")
            
            with col3:
                # Get average for first job code shown
                if len(job_codes_to_show) > 0 and job_codes_to_show[0] in productivity.columns:
                    avg_mins = productivity[job_codes_to_show[0]].mean()
                    st.metric(f"Avg Min/Tap ({job_codes_to_show[0][:15]})", f"{avg_mins:.1f}")
            
            with col4:
                avg_cost = productivity['Cost_Per_Tap'].mean()
                st.metric("Avg Cost/Tap", f"${avg_cost:.2f}")
        else:
            st.info("No productivity data for selected time range")
    else:
        # Fallback to simple view if no job codes found
        st.info("Job code information not available - showing basic productivity metrics")
        
        # Aggregate by employee
        emp_stats = filtered_df.groupby('Employee').agg({
            'Taps_In': 'sum',
            'Hours': 'sum',
            'Labor_Cost': 'sum'
        }).reset_index()
        
        # Calculate productivity metrics
        emp_stats['Taps_Per_Hour'] = (emp_stats['Taps_In'] / emp_stats['Hours']).round(1)
        emp_stats['Taps_Per_Hour'] = emp_stats['Taps_Per_Hour'].replace([float('inf'), float('-inf')], 0)
        
        emp_stats['Minutes_Per_Tap'] = ((emp_stats['Hours'] * 60) / emp_stats['Taps_In']).round(1)
        emp_stats['Minutes_Per_Tap'] = emp_stats['Minutes_Per_Tap'].replace([float('inf'), float('-inf')], 0)
        
        emp_stats['Cost_Per_Tap'] = (emp_stats['Labor_Cost'] / emp_stats['Taps_In']).round(2)
        emp_stats['Cost_Per_Tap'] = emp_stats['Cost_Per_Tap'].replace([float('inf'), float('-inf')], 0)
        
        emp_stats = emp_stats.sort_values('Taps_In', ascending=False)
        emp_stats = emp_stats[emp_stats['Taps_In'] > 0]
        
        if not emp_stats.empty:
            display = emp_stats[['Employee', 'Taps_In', 'Hours', 'Taps_Per_Hour', 'Minutes_Per_Tap', 'Cost_Per_Tap', 'Labor_Cost']].copy()
            display.columns = ['Employee', 'Taps', 'Hours', 'Taps/Hr', 'Min/Tap', '$/Tap', 'Total Cost']
            
            display['$/Tap'] = display['$/Tap'].apply(lambda x: f"${x:.2f}")
            display['Total Cost'] = display['Total Cost'].apply(lambda x: f"${x:,.2f}")
            
            st.dataframe(display, use_container_width=True, hide_index=True, height=400)

    st.divider()

    # Tips with updated context
    with st.expander("💡 Understanding Tapping Metrics"):
        st.markdown("""
        **What's New:**
        
        - **Site-Wide Efficiency**: Renamed from "Company-Wide" to better reflect overall operation metrics
        - **Minutes/Tap by Job Type**: Now shows time efficiency for different types of work:
          - Tapping (new tap installation)
          - Inseason Repairs (fixing issues during season)
          - Already Identified Tubing Issues (known problem repairs)
        - **Removed Site Breakdown**: Simplified view focuses on overall efficiency
        
        **Key Metrics Explained:**

        - **Taps Installed**: New taps put into trees
        - **Taps Removed**: Old taps taken out
        - **Taps Capped**: Taps that were capped off (end of season or non-productive)
        - **Net Change**: Taps Installed - Taps Removed (overall system growth/shrinkage)
        - **Minutes Per Tap**: Time efficiency by job type (lower = faster work)
        - **Taps Per Hour**: Overall productivity metric (higher = more efficient)
        - **Cost Per Tap**: Labor cost efficiency (lower = more cost-effective)

        **Good Productivity Rates:**
        - Beginner: 15-25 taps/hour (2.4-4 minutes/tap)
        - Experienced: 30-50 taps/hour (1.2-2 minutes/tap)
        - Expert: 50+ taps/hour (<1.2 minutes/tap)
        
        **Note:** Repair work typically takes longer per tap than new installations

        **Using Job Type Breakdown:**
        - Compare tapping efficiency vs repair efficiency
        - Identify employees who excel at specific tasks
        - Plan crew assignments based on skill sets
        - Track if repair times improve with experience

        **Tips for Analysis:**
        - Track improvement over season as crew gains experience
        - Compare employees for training opportunities
        - Monitor cost per tap to control labor expenses
        - Different job types naturally have different time requirements
        """)
