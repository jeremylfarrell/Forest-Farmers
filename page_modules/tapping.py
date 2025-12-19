"""
Tapping Productivity Page Module - MULTI-SITE ENHANCED
Track tapping operations, employee productivity, and seasonal progress
Now includes site-specific metrics and cross-site comparisons
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
    # OVERALL SUMMARY WITH SITE BREAKDOWN
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

    # Site breakdown if available
    if has_site:
        st.markdown("---")
        st.subheader("🏢 Breakdown by Site")
        
        site_summary = df.groupby('Site').agg({
            'Taps_In': 'sum',
            'Taps_Out': 'sum',
            'Net_Taps': 'sum',
            'Labor_Cost': 'sum',
            'Hours': 'sum'
        }).reset_index()
        
        cols = st.columns(len(site_summary))
        
        for idx, row in site_summary.iterrows():
            with cols[idx]:
                emoji = "🟦" if row['Site'] == "NY" else "🟩" if row['Site'] == "VT" else "⚫"
                st.markdown(f"### {emoji} {row['Site']}")
                
                st.metric("Taps Installed", f"{int(row['Taps_In']):,}")
                st.metric("Net Change", f"{int(row['Net_Taps']):,}")
                
                # Calculate cost per tap for this site
                if row['Taps_In'] > 0:
                    cost_per_tap = row['Labor_Cost'] / row['Taps_In']
                    st.metric("Cost/Tap", f"${cost_per_tap:.2f}")

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

    # Site comparison chart if applicable
    if has_site and len(site_summary) > 1:
        st.divider()
        st.subheader("📊 Site Cost Comparison")
        
        # Prepare data for chart
        chart_data = site_summary[site_summary['Taps_In'] > 0].copy()
        chart_data['Cost_Per_Tap'] = chart_data['Labor_Cost'] / chart_data['Taps_In']
        
        # Color code
        colors = []
        for site in chart_data['Site']:
            if site == 'NY':
                colors.append('#2196F3')  # Blue
            elif site == 'VT':
                colors.append('#4CAF50')  # Green
            else:
                colors.append('#9E9E9E')  # Gray
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=chart_data['Site'],
            y=chart_data['Cost_Per_Tap'],
            marker_color=colors,
            text=chart_data['Cost_Per_Tap'].apply(lambda x: f"${x:.2f}"),
            textposition='outside'
        ))
        
        # Add company average line
        fig.add_hline(
            y=avg_cost_per_tap,
            line_dash="dash",
            line_color="gray",
            annotation_text=f"Company Avg: ${avg_cost_per_tap:.2f}",
            annotation_position="right"
        )
        
        fig.update_layout(
            yaxis_title="Cost Per Tap ($)",
            xaxis_title="Site",
            height=300,
            showlegend=False
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.caption("💡 Lower cost per tap indicates higher efficiency at that site")

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

    emp_stats['Minutes_Per_Tap'] = ((emp_stats['Hours'] * 60) / emp_stats['Taps_In']).round(1)
    emp_stats['Minutes_Per_Tap'] = emp_stats['Minutes_Per_Tap'].replace([float('inf'), float('-inf')], 0)

    emp_stats['Cost_Per_Tap'] = (emp_stats['Labor_Cost'] / emp_stats['Taps_In']).round(2)
    emp_stats['Cost_Per_Tap'] = emp_stats['Cost_Per_Tap'].replace([float('inf'), float('-inf')], 0)

    # Add site information
    if has_site:
        emp_sites = filtered_df.groupby('Employee')['Site'].apply(
            lambda x: ', '.join(sorted(x.unique()))
        ).reset_index()
        emp_sites.columns = ['Employee', 'Sites_Worked']
        emp_stats = emp_stats.merge(emp_sites, on='Employee', how='left')

    # Sort by taps installed
    emp_stats = emp_stats.sort_values('Taps_In', ascending=False)

    # Display ranking
    display = emp_stats.copy()
    display = display[display['Taps_In'] > 0]  # Only show employees who installed taps

    if not display.empty:
        display.insert(0, 'Rank', range(1, len(display) + 1))

        # Add efficiency indicator
        median_cost = display['Cost_Per_Tap'].median()
        display['Efficiency'] = display['Cost_Per_Tap'].apply(
            lambda x: '🟢 Low Cost' if x < median_cost else ('🟡 Average' if x == median_cost else '🔴 High Cost')
        )

        # Format for display
        if 'Sites_Worked' in display.columns:
            display_cols = ['Rank', 'Employee', 'Sites_Worked', 'Taps_In', 'Hours', 'Taps_Per_Hour',
                            'Minutes_Per_Tap', 'Cost_Per_Tap', 'Labor_Cost', 'Efficiency']
            col_names = ['#', 'Employee', 'Sites', 'Taps', 'Hours', 'Taps/Hr',
                         'Min/Tap', '$/Tap', 'Total $', '⚫']
        else:
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
            most_efficient = display.loc[display['Cost_Per_Tap'].idxmin(), 'Employee']
            st.metric("Most Efficient", most_efficient)

    else:
        st.info("No tapping activity in selected time range")

    st.divider()

    # Tips with multi-site context
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

        **Multi-Site Features:**
        - Compare efficiency between NY and VT operations
        - Identify site-specific challenges affecting productivity
        - Track which employees work at which sites
        - Share best practices across locations

        **Good Productivity Rates:**
        - Beginner: 15-25 taps/hour (2.4-4 minutes/tap)
        - Experienced: 30-50 taps/hour (1.2-2 minutes/tap)
        - Expert: 50+ taps/hour (<1.2 minutes/tap)

        **Cost Management:**
        - Lower cost per tap = better efficiency
        - Compare employees to find training opportunities
        - Track cost trends to optimize crew assignments
        - Consider terrain and site conditions when comparing

        **Tips for Analysis:**
        - Track improvement over season as crew gains experience
        - Compare rates between employees for training opportunities
        - Monitor cost per tap to control labor expenses
        - Use site breakdown to identify location-specific challenges
        - Share successful techniques between sites
        """)
