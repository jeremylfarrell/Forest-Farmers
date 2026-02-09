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
    st.subheader("⏱️ Site-Wide Efficiency")

    total_hours = df['Hours'].sum()
    total_taps = df['Taps_In'].sum()

    col1, col2, col3 = st.columns(3)

    with col1:
        avg_taps_per_hour = total_taps / total_hours if total_hours > 0 else 0
        st.metric("Avg Taps/Hour", f"{avg_taps_per_hour:.1f}")

    with col2:
        avg_mins_per_tap = (total_hours * 60) / total_taps if total_taps > 0 else 0
        st.metric("Avg Minutes/Tap", f"{avg_mins_per_tap:.1f}")

    with col3:
        st.metric("Total Hours", f"{total_hours:,.1f}")

    st.divider()

    # ========================================================================
    # TIME RANGE FILTER
    # ========================================================================

    col1, col2 = st.columns([2, 1])

    with col1:
        time_range = st.selectbox(
            "Time Range",
            ["This Season", "Previous Day", "Last 7 Days", "Last 30 Days", "Custom Range"]
        )

    # Apply time filter
    if time_range == "Previous Day":
        yesterday = (datetime.now() - timedelta(days=1)).date()
        filtered_df = df[df['Date'].dt.date == yesterday]
        st.info(f"Showing data for **{yesterday}** — review for data errors or performance issues")
    elif time_range == "Last 7 Days":
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

    st.markdown("**Tapping job codes only** — hours, taps/hr, and min/tap reflect only tapping work")

    # Normalize job codes to combine similar ones
    def normalize_job_code(job_code):
        """Extract the key part of job code, removing NY/VT numbers and normalizing case"""
        import re
        if pd.isna(job_code):
            return job_code
        name = str(job_code)
        # Remove state codes and numbers like "NY 240114", "- NY - 240114", "VT 240113"
        name = re.sub(r'\s*-?\s*-?\s*(NY|VT|ny|vt)\s*-?\s*\d+', '', name)
        # Extract text in parentheses if present, otherwise use cleaned name
        if '(' in name and ')' in name:
            paren_text = name[name.find('(')+1:name.find(')')]
            return paren_text.strip().lower()
        # Remove "Maple Tapping" prefix variations
        name = re.sub(r'^Maple\s*[Tt]apping\s*-?\s*', '', name)
        return name.strip().lower() if name.strip() else job_code.lower()

    def is_tapping_job(job_normalized):
        """Return True if this is a tapping job code (not storm repair, not general repair)"""
        if pd.isna(job_normalized):
            return False
        j = str(job_normalized).lower()
        # Exclude storm repair and non-tapping jobs
        if 'storm' in j:
            return False
        # Include tapping-related job codes
        return any(kw in j for kw in ['tap', 'spout', 'install'])

    # Create normalized job code column
    filtered_df = filtered_df.copy()
    filtered_df['Job_Code_Normalized'] = filtered_df['Job_Code'].apply(normalize_job_code)
    filtered_df['Is_Tapping'] = filtered_df['Job_Code_Normalized'].apply(is_tapping_job)

    # Filter to only tapping job codes for productivity metrics
    tapping_df = filtered_df[filtered_df['Is_Tapping']].copy()

    if not tapping_df.empty:
        # Aggregate by employee — only tapping hours
        emp_stats = tapping_df.groupby('Employee').agg({
            'Taps_In': 'sum',
            'Hours': 'sum',
        }).reset_index()

        # Calculate productivity metrics using only tapping hours
        emp_stats['Taps_Per_Hour'] = (emp_stats['Taps_In'] / emp_stats['Hours']).round(1)
        emp_stats['Taps_Per_Hour'] = emp_stats['Taps_Per_Hour'].replace([float('inf'), float('-inf')], 0)

        emp_stats['Min_Per_Tap'] = ((emp_stats['Hours'] * 60) / emp_stats['Taps_In']).round(1)
        emp_stats['Min_Per_Tap'] = emp_stats['Min_Per_Tap'].replace([float('inf'), float('-inf')], 0)

        # Sort by total taps, filter to employees who actually tapped
        emp_stats = emp_stats.sort_values('Taps_In', ascending=False)
        emp_stats = emp_stats[emp_stats['Taps_In'] > 0]

        if not emp_stats.empty:
            display = emp_stats[['Employee', 'Taps_In', 'Min_Per_Tap', 'Hours', 'Taps_Per_Hour']].copy()
            display.columns = ['Employee', 'Total Taps', 'Min/Tap', 'Tapping Hours', 'Taps/Hr']

            # Format hours
            display['Tapping Hours'] = display['Tapping Hours'].apply(lambda x: f"{x:.1f}")

            st.dataframe(display, use_container_width=True, hide_index=True, height=400)

            # Summary stats
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Employees Tracked", len(emp_stats))

            with col2:
                total_tapping_taps = emp_stats['Taps_In'].sum()
                total_tapping_hours = emp_stats['Hours'].sum()
                overall_taps_hr = total_tapping_taps / total_tapping_hours if total_tapping_hours > 0 else 0
                st.metric("Avg Taps/Hour", f"{overall_taps_hr:.1f}")

            with col3:
                overall_min = (total_tapping_hours * 60) / total_tapping_taps if total_tapping_taps > 0 else 0
                st.metric("Avg Min/Tap", f"{overall_min:.1f}")
        else:
            st.info("No tapping productivity data for selected time range")
    else:
        st.info("No tapping job codes found in selected time range")

    st.divider()

    # Tips with updated context
    with st.expander("💡 Understanding Tapping Metrics"):
        st.markdown("""
        **Key Metrics Explained:**

        - **Taps Installed**: New taps put into trees
        - **Taps Removed**: Old taps taken out
        - **Taps Capped**: Taps that were capped off (end of season or non-productive)
        - **Net Change**: Taps Installed - Taps Removed (overall system growth/shrinkage)
        - **Minutes Per Tap**: Time efficiency for tapping work only (lower = faster)
        - **Taps Per Hour**: Productivity metric for tapping work only (higher = more efficient)
        - **Tapping Hours**: Only hours spent in tapping job codes (excludes repairs, storm, etc.)

        **Good Productivity Rates:**
        - Beginner: 15-25 taps/hour (2.4-4 minutes/tap)
        - Experienced: 30-50 taps/hour (1.2-2 minutes/tap)
        - Expert: 50+ taps/hour (<1.2 minutes/tap)

        **Time Range Options:**
        - **This Season**: Full season overview (default)
        - **Previous Day**: Review yesterday's work for data errors or performance issues
        - **Last 7/30 Days**: Recent activity windows
        - **Custom Range**: Pick specific dates

        **Tips for Analysis:**
        - Track improvement over season as crew gains experience
        - Compare employees for training opportunities
        - Use "Previous Day" to catch data entry issues early
        """)
