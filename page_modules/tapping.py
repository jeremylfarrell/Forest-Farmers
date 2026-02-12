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
import config


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

    # ========================================================================
    # TAPPING COMPLETION ESTIMATE
    # ========================================================================
    st.divider()
    st.subheader("🎯 Tapping Progress")

    def _render_tap_progress(tap_df, site_label, target):
        """Render progress bar and estimate for one site"""
        taps_installed = int(tap_df['Taps_In'].sum())
        pct = min(taps_installed / target, 1.0) if target > 0 else 0
        remaining = max(target - taps_installed, 0)

        # Calculate avg taps per day over last 7 calendar days (includes days off)
        seven_days_ago = (datetime.now() - timedelta(days=7)).date()
        recent = tap_df[tap_df['Date'].dt.date >= seven_days_ago]
        total_recent_taps = recent['Taps_In'].sum()
        avg_per_day = total_recent_taps / 7 if not recent.empty else 0

        # Estimate completion (every day is a possible tapping day)
        if avg_per_day > 0 and remaining > 0:
            days_left = int(remaining / avg_per_day)
            est_date = (datetime.now() + timedelta(days=days_left)).strftime('%b %d, %Y')
        elif remaining == 0:
            est_date = "Complete!"
        else:
            est_date = "N/A"

        st.markdown(f"**{site_label}**")
        st.progress(pct)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Installed / Target", f"{taps_installed:,} / {target:,}")
        with c2:
            st.metric("% Complete", f"{pct*100:.1f}%")
        with c3:
            st.metric("Avg Taps/Day (7d)", f"{avg_per_day:,.0f}" if avg_per_day > 0 else "N/A")
        with c4:
            st.metric("Est. Completion", est_date)

    tap_targets = config.TAP_TARGETS
    viewing_all = has_site and len(df['Site'].unique()) > 1

    if viewing_all:
        # Show both sites side by side
        col_ny, col_vt = st.columns(2)
        with col_ny:
            ny_df = df[df['Site'] == 'NY'] if 'Site' in df.columns else df
            _render_tap_progress(ny_df, "🟦 New York", tap_targets.get("NY", 0))
        with col_vt:
            vt_df = df[df['Site'] == 'VT'] if 'Site' in df.columns else df
            _render_tap_progress(vt_df, "🟩 Vermont", tap_targets.get("VT", 0))
    elif has_site and len(df['Site'].unique()) == 1:
        site_code = df['Site'].iloc[0]
        site_label = "🟦 New York" if site_code == "NY" else "🟩 Vermont" if site_code == "VT" else site_code
        _render_tap_progress(df, site_label, tap_targets.get(site_code, 0))
    else:
        # No site info — use combined target
        combined_target = sum(tap_targets.values())
        _render_tap_progress(df, "All Sites", combined_target)

    # SITE-WIDE EFFICIENCY METRICS (tapping job codes only)
    st.divider()
    st.subheader("⏱️ Site-Wide Efficiency")
    st.markdown("*Maple Tapping job codes only (new spout install, dropline install & tap, spout already on)*")

    # Helper to identify tapping job codes
    def _is_tapping_job_code(job_text):
        if pd.isna(job_text):
            return False
        j = str(job_text).lower()
        return any(kw in j for kw in [
            'new spout install', 'dropline install', 'spout already on',
            'maple tapping',
        ])

    tapping_only = df[df['Job_Code'].apply(_is_tapping_job_code)]
    total_tapping_hours = tapping_only['Hours'].sum()
    total_taps = tapping_only['Taps_In'].sum()

    col1, col2, col3 = st.columns(3)

    with col1:
        avg_taps_per_hour = total_taps / total_tapping_hours if total_tapping_hours > 0 else 0
        st.metric("Avg Taps/Hour", f"{avg_taps_per_hour:.1f}")

    with col2:
        avg_mins_per_tap = (total_tapping_hours * 60) / total_taps if total_taps > 0 else 0
        st.metric("Avg Minutes/Tap", f"{avg_mins_per_tap:.1f}")

    with col3:
        st.metric("Tapping Hours", f"{total_tapping_hours:,.1f}")

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
    # DAILY TAPS BY EMPLOYEE (pivot table for cross-checking)
    # ========================================================================

    st.subheader("📋 Daily Taps by Employee")
    st.markdown("*Taps Put In per employee per day — use to cross-check with TSheets/Excel*")

    if not filtered_df.empty and 'Taps_In' in filtered_df.columns:
        # Build pivot: rows = date, columns = employee, values = taps put in
        pivot_data = filtered_df[filtered_df['Taps_In'] > 0].copy()
        if not pivot_data.empty:
            pivot_data['Day'] = pivot_data['Date'].dt.date
            pivot = pivot_data.pivot_table(
                index='Day',
                columns='Employee',
                values='Taps_In',
                aggfunc='sum',
                fill_value=0,
                margins=True,
                margins_name='Total'
            )
            # Sort dates descending but keep Total row at top
            total_row = pivot.loc[['Total']]
            date_rows = pivot.drop('Total').sort_index(ascending=False)
            pivot = pd.concat([total_row, date_rows])

            # Convert to int for cleaner display
            pivot = pivot.astype(int)

            st.dataframe(pivot, use_container_width=True)
        else:
            st.info("No tapping entries in selected time range")
    else:
        st.info("No tapping data available")

    st.divider()

    # ========================================================================
    # EMPLOYEE PRODUCTIVITY - WITH JOB TYPE BREAKDOWN
    # ========================================================================

    st.subheader("👥 Employee Productivity")

    st.markdown("**Tapping job codes only** — new spout install, dropline install & tap, spout already on")

    # Filter to tapping job codes using same filter as efficiency section
    filtered_df = filtered_df.copy()
    filtered_df['Is_Tapping'] = filtered_df['Job_Code'].apply(_is_tapping_job_code)

    # Filter to only tapping job codes for productivity metrics
    tapping_df = filtered_df[filtered_df['Is_Tapping']].copy()

    if not tapping_df.empty:
        # Aggregate by employee — only tapping hours
        emp_stats = tapping_df.groupby('Employee').agg({
            'Taps_In': 'sum',
            'Taps_Out': 'sum',
            'Hours': 'sum',
        }).reset_index()

        # Calculate productivity metrics using only tapping hours
        emp_stats['Taps_Per_Hour'] = (emp_stats['Taps_In'] / emp_stats['Hours']).round(1)
        emp_stats['Taps_Per_Hour'] = emp_stats['Taps_Per_Hour'].replace([float('inf'), float('-inf')], 0)

        emp_stats['Min_Per_Tap'] = ((emp_stats['Hours'] * 60) / emp_stats['Taps_In']).round(1)
        emp_stats['Min_Per_Tap'] = emp_stats['Min_Per_Tap'].replace([float('inf'), float('-inf')], 0)

        # Calculate % deleted
        emp_stats['Pct_Deleted'] = ((emp_stats['Taps_Out'] / emp_stats['Taps_In']) * 100).round(1)
        emp_stats['Pct_Deleted'] = emp_stats['Pct_Deleted'].replace([float('inf'), float('-inf')], 0).fillna(0)

        # Sort by total taps, filter to employees who actually tapped
        emp_stats = emp_stats.sort_values('Taps_In', ascending=False)
        emp_stats = emp_stats[emp_stats['Taps_In'] > 0]

        if not emp_stats.empty:
            display = emp_stats[['Employee', 'Taps_In', 'Taps_Out', 'Pct_Deleted', 'Min_Per_Tap', 'Hours', 'Taps_Per_Hour']].copy()
            display.columns = ['Employee', 'Taps Put In', 'Taps Deleted', '% Deleted', 'Min/Tap', 'Tapping Hours', 'Taps/Hr']

            # Format
            display['Tapping Hours'] = display['Tapping Hours'].apply(lambda x: f"{x:.1f}")
            display['Taps Put In'] = display['Taps Put In'].astype(int)
            display['Taps Deleted'] = display['Taps Deleted'].astype(int)
            display['% Deleted'] = display['% Deleted'].apply(lambda x: f"{x:.1f}%")

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
