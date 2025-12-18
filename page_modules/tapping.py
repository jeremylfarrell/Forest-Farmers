"""
Tapping Productivity Page Module
Track tapping operations, employee productivity, and seasonal progress
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from utils import find_column


def render(personnel_df, vacuum_df):
    """Render tapping productivity page"""

    st.title("🌳 Tapping Operations")
    st.markdown("*Track tapping productivity and seasonal progress*")

    if personnel_df.empty:
        st.warning("No personnel data available for tapping analysis")
        return

    # Find relevant columns
    date_col = find_column(personnel_df, 'Date', 'date', 'timestamp')
    emp_col = find_column(personnel_df, 'Employee Name', 'employee', 'EE First', 'EE Last')
    hours_col = find_column(personnel_df, 'Hours', 'hours', 'time')
    rate_col = find_column(personnel_df, 'Rate', 'rate', 'pay_rate', 'hourly_rate')
    mainline_col = find_column(personnel_df, 'mainline.', 'mainline', 'Mainline', 'location')

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

    # Calculate net taps (taps added minus taps removed)
    df['Net_Taps'] = df['Taps_In'] - df['Taps_Out']

    # Calculate labor cost
    df['Labor_Cost'] = df['Hours'] * df['Rate']

    # ========================================================================
    # OVERALL SUMMARY
    # ========================================================================

    st.subheader("📊 Season Summary")

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

    # COMPANY-WIDE EFFICIENCY METRICS
    st.divider()
    st.subheader("💰 Company-Wide Efficiency")

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

    # Aggregate by date
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
        # Create stacked bar chart
        fig = go.Figure()

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

        fig.add_trace(go.Bar(
            x=daily['Date'],
            y=daily['Taps_Capped'],
            name='Capped',
            marker_color='#ffc107',
            hovertemplate='Capped: %{y}<extra></extra>'
        ))

        fig.update_layout(
            barmode='group',
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
    # EMPLOYEE PRODUCTIVITY
    # ========================================================================

    st.subheader("👥 Employee Productivity Rankings")

    # Aggregate by employee
    emp_stats = filtered_df.groupby('Employee').agg({
        'Taps_In': 'sum',
        'Taps_Out': 'sum',
        'Taps_Capped': 'sum',
        'Net_Taps': 'sum',
        'Hours': 'sum',
        'Labor_Cost': 'sum',
        'Repairs': 'sum'
    }).reset_index()

    # Calculate productivity metrics
    emp_stats['Taps_Per_Hour'] = (emp_stats['Taps_In'] / emp_stats['Hours']).round(1)
    emp_stats['Taps_Per_Hour'] = emp_stats['Taps_Per_Hour'].replace([float('inf'), float('-inf')], 0)

    # NEW METRICS
    emp_stats['Minutes_Per_Tap'] = ((emp_stats['Hours'] * 60) / emp_stats['Taps_In']).round(1)
    emp_stats['Minutes_Per_Tap'] = emp_stats['Minutes_Per_Tap'].replace([float('inf'), float('-inf')], 0)

    emp_stats['Cost_Per_Tap'] = (emp_stats['Labor_Cost'] / emp_stats['Taps_In']).round(2)
    emp_stats['Cost_Per_Tap'] = emp_stats['Cost_Per_Tap'].replace([float('inf'), float('-inf')], 0)

    # Sort by taps installed
    emp_stats = emp_stats.sort_values('Taps_In', ascending=False)

    # Display ranking
    display = emp_stats.copy()
    display = display[display['Taps_In'] > 0]  # Only show employees who installed taps

    if not display.empty:
        display.insert(0, 'Rank', range(1, len(display) + 1))

        # Add efficiency indicator based on cost per tap (lower is better)
        median_cost = display['Cost_Per_Tap'].median()
        display['Efficiency'] = display['Cost_Per_Tap'].apply(
            lambda x: '🟢 Low Cost' if x < median_cost else ('🟡 Average' if x == median_cost else '🔴 High Cost')
        )

        # Format for display
        display_cols = ['Rank', 'Employee', 'Taps_In', 'Hours', 'Taps_Per_Hour',
                        'Minutes_Per_Tap', 'Cost_Per_Tap', 'Labor_Cost', 'Efficiency']
        col_names = ['#', 'Employee', 'Taps', 'Hours', 'Taps/Hr',
                     'Min/Tap', '$/Tap', 'Total $', '⚫']

        display_table = display[display_cols].copy()
        display_table.columns = col_names

        # Format currency
        display_table['$/Tap'] = display_table['$/Tap'].apply(lambda x: f"${x:.2f}")
        display_table['Total $'] = display_table['Total $'].apply(lambda x: f"${x:,.2f}")

        st.dataframe(display_table, use_container_width=True, hide_index=True, height=400)

        # Summary stats
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Avg Taps/Hour", f"{display['Taps/Hr'].mean():.1f}")

        with col2:
            st.metric("Avg Minutes/Tap", f"{display['Min/Tap'].mean():.1f}")

        with col3:
            avg_cost = display_table['$/Tap'].str.replace('$', '').astype(float).mean()
            st.metric("Avg Cost/Tap", f"${avg_cost:.2f}")

        with col4:
            # Find most efficient (lowest cost per tap)
            most_efficient = display.loc[display['Cost_Per_Tap'].idxmin(), 'Employee']
            st.metric("Most Efficient", most_efficient)

    else:
        st.info("No tapping activity in selected time range")

    st.divider()

    # ========================================================================
    # COST COMPARISON CHART
    # ========================================================================

    if not display.empty and len(display) > 1:
        st.subheader("💵 Cost Per Tap Comparison")

        # Create bar chart comparing cost per tap
        fig = go.Figure()

        # Sort by cost per tap for better visualization
        chart_data = display.sort_values('Cost_Per_Tap', ascending=True)

        # Color bars based on efficiency
        colors = ['#28a745' if cost < median_cost else '#ffc107' if cost == median_cost else '#dc3545'
                  for cost in chart_data['Cost_Per_Tap']]

        fig.add_trace(go.Bar(
            x=chart_data['Employee'],
            y=chart_data['Cost_Per_Tap'],
            marker_color=colors,
            text=chart_data['Cost_Per_Tap'].apply(lambda x: f"${x:.2f}"),
            textposition='outside',
            hovertemplate='%{x}<br>Cost/Tap: $%{y:.2f}<extra></extra>'
        ))

        # Add median line
        fig.add_hline(
            y=median_cost,
            line_dash="dash",
            line_color="gray",
            annotation_text=f"Median: ${median_cost:.2f}",
            annotation_position="right"
        )

        fig.update_layout(
            xaxis_title="Employee",
            yaxis_title="Cost Per Tap ($)",
            height=400,
            showlegend=False
        )

        st.plotly_chart(fig, use_container_width=True)

        st.divider()

    # ========================================================================
    # LOCATION-BASED TAPPING
    # ========================================================================

    if mainline_col:
        st.subheader("📍 Tapping by Location")

        location_stats = filtered_df.groupby('Mainline').agg({
            'Taps_In': 'sum',
            'Taps_Out': 'sum',
            'Net_Taps': 'sum',
            'Taps_Capped': 'sum',
            'Hours': 'sum',
            'Labor_Cost': 'sum',
            'Employee': 'nunique'
        }).reset_index()

        location_stats.columns = ['Location', 'Installed', 'Removed', 'Net_Change', 'Capped',
                                  'Hours', 'Labor_Cost', 'Employees']

        # Calculate efficiency metrics by location
        location_stats['Cost_Per_Tap'] = (location_stats['Labor_Cost'] / location_stats['Installed']).round(2)
        location_stats['Minutes_Per_Tap'] = ((location_stats['Hours'] * 60) / location_stats['Installed']).round(1)

        location_stats = location_stats[location_stats['Installed'] > 0]
        location_stats = location_stats.sort_values('Installed', ascending=False)

        if not location_stats.empty:
            # Top 20 locations
            display_locs = location_stats.head(20).copy()

            # Format for display
            display_locs['Labor_Cost'] = display_locs['Labor_Cost'].apply(lambda x: f"${x:,.2f}")
            display_locs['Cost_Per_Tap'] = display_locs['Cost_Per_Tap'].apply(lambda x: f"${x:.2f}")

            st.dataframe(display_locs, use_container_width=True, hide_index=True)

            st.caption(f"Showing top 20 of {len(location_stats)} locations with tapping activity")
        else:
            st.info("No location data available")

    st.divider()

    # ========================================================================
    # INDIVIDUAL EMPLOYEE DETAIL
    # ========================================================================

    st.subheader("📋 Individual Employee Details")

    employees = sorted(filtered_df[filtered_df['Taps_In'] > 0]['Employee'].unique())

    if employees:
        selected_emp = st.selectbox("Select Employee", employees)

        emp_data = filtered_df[filtered_df['Employee'] == selected_emp].copy()
        emp_data = emp_data.sort_values('Date', ascending=False)

        # Summary for this employee
        total_taps = emp_data['Taps_In'].sum()
        total_hours = emp_data['Hours'].sum()
        total_cost = emp_data['Labor_Cost'].sum()

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric("Total Taps", f"{int(total_taps):,}")

        with col2:
            rate = total_taps / total_hours if total_hours > 0 else 0
            st.metric("Taps/Hour", f"{rate:.1f}")

        with col3:
            mins_per_tap = (total_hours * 60) / total_taps if total_taps > 0 else 0
            st.metric("Minutes/Tap", f"{mins_per_tap:.1f}")

        with col4:
            cost_per_tap = total_cost / total_taps if total_taps > 0 else 0
            st.metric("Cost/Tap", f"${cost_per_tap:.2f}")

        with col5:
            st.metric("Total Cost", f"${total_cost:,.2f}")

        st.subheader("Work History")

        # Display detailed sessions
        display_sessions = emp_data.copy()
        display_sessions['Date'] = display_sessions['Date'].dt.strftime('%Y-%m-%d')

        # Calculate per-session metrics
        display_sessions['Session_Cost'] = display_sessions['Labor_Cost']
        display_sessions['Cost_Per_Tap_Session'] = (display_sessions['Labor_Cost'] / display_sessions['Taps_In']).round(
            2)
        display_sessions['Minutes_Per_Tap_Session'] = (
                    (display_sessions['Hours'] * 60) / display_sessions['Taps_In']).round(1)

        cols_to_show = ['Date', 'Taps_In', 'Hours', 'Minutes_Per_Tap_Session',
                        'Cost_Per_Tap_Session', 'Session_Cost']
        if mainline_col:
            cols_to_show.insert(1, 'Mainline')

        display_sessions = display_sessions[cols_to_show]

        col_names = ['Date'] + (['Location'] if mainline_col else []) + \
                    ['Taps', 'Hours', 'Min/Tap', '$/Tap', 'Total $']
        display_sessions.columns = col_names

        # Format currency
        display_sessions['$/Tap'] = display_sessions['$/Tap'].apply(lambda x: f"${x:.2f}" if x > 0 else "$0.00")
        display_sessions['Total $'] = display_sessions['Total $'].apply(lambda x: f"${x:,.2f}")

        st.dataframe(display_sessions, use_container_width=True, hide_index=True)

        # Productivity trend chart
        st.subheader("Productivity Trend")

        daily_emp = emp_data.groupby(emp_data['Date'].dt.date).agg({
            'Taps_In': 'sum',
            'Hours': 'sum',
            'Labor_Cost': 'sum'
        }).reset_index()

        daily_emp['Rate'] = daily_emp['Taps_In'] / daily_emp['Hours']
        daily_emp['Rate'] = daily_emp['Rate'].replace([float('inf'), float('-inf')], 0)
        daily_emp['Cost_Per_Tap'] = daily_emp['Labor_Cost'] / daily_emp['Taps_In']
        daily_emp['Cost_Per_Tap'] = daily_emp['Cost_Per_Tap'].replace([float('inf'), float('-inf')], 0)
        daily_emp['Date'] = pd.to_datetime(daily_emp['Date'])
        daily_emp = daily_emp.sort_values('Date')

        if len(daily_emp) > 1:
            # Two charts: efficiency and cost
            col1, col2 = st.columns(2)

            with col1:
                fig1 = go.Figure()
                fig1.add_trace(go.Scatter(
                    x=daily_emp['Date'],
                    y=daily_emp['Rate'],
                    mode='lines+markers',
                    name='Taps/Hour',
                    line=dict(color='#007bff', width=2),
                    marker=dict(size=8)
                ))

                avg_rate = daily_emp['Rate'].mean()
                fig1.add_hline(
                    y=avg_rate,
                    line_dash="dash",
                    line_color="gray",
                    annotation_text=f"Avg: {avg_rate:.1f}",
                    annotation_position="right"
                )

                fig1.update_layout(
                    title="Efficiency Over Time",
                    xaxis_title="Date",
                    yaxis_title="Taps Per Hour",
                    height=300
                )
                st.plotly_chart(fig1, use_container_width=True)

            with col2:
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(
                    x=daily_emp['Date'],
                    y=daily_emp['Cost_Per_Tap'],
                    mode='lines+markers',
                    name='Cost/Tap',
                    line=dict(color='#28a745', width=2),
                    marker=dict(size=8)
                ))

                avg_cost = daily_emp['Cost_Per_Tap'].mean()
                fig2.add_hline(
                    y=avg_cost,
                    line_dash="dash",
                    line_color="gray",
                    annotation_text=f"Avg: ${avg_cost:.2f}",
                    annotation_position="right"
                )

                fig2.update_layout(
                    title="Cost Over Time",
                    xaxis_title="Date",
                    yaxis_title="Cost Per Tap ($)",
                    height=300
                )
                st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No employees with tapping activity in selected time range")

    st.divider()

    # ========================================================================
    # TIPS & INSIGHTS
    # ========================================================================

    with st.expander("💡 Understanding Tapping Metrics"):
        st.markdown("""
        **Key Metrics Explained:**

        - **Taps Installed**: New taps put into trees
        - **Taps Removed**: Old taps taken out
        - **Taps Capped**: Taps that were capped off (end of season or non-productive)
        - **Net Change**: Taps Installed - Taps Removed (overall system growth/shrinkage)
        - **Taps Per Hour**: Productivity metric (higher = more efficient)
        - **Minutes Per Tap**: Time efficiency (lower = faster work)
        - **Cost Per Tap**: Labor cost efficiency (lower = more cost-effective)

        **Good Productivity Rates:**
        - Beginner: 15-25 taps/hour (2.4-4 minutes/tap)
        - Experienced: 30-50 taps/hour (1.2-2 minutes/tap)
        - Expert: 50+ taps/hour (<1.2 minutes/tap)

        **Cost Management:**
        - Lower cost per tap = better efficiency
        - Compare employees to find training opportunities
        - Track cost trends to optimize crew assignments
        - Use location data to identify challenging areas

        **Tips for Analysis:**
        - Track improvement over season as crew gains experience
        - Compare rates between employees for training opportunities
        - Monitor cost per tap to control labor expenses
        - Use location data to plan future tapping zones and identify difficult areas
        """)