"""
Vacuum Performance Page Module - MULTI-SITE POLISHED
Shows performance metrics for each vacuum sensor and system trends
UPDATED: Maple-only filtering, daily trends with hourly drill-down, temp-aware weekly view
UPDATED: Freeze/thaw smart display — highlights critical monitoring periods
"""

import streamlit as st
import pandas as pd
import requests
import config
from utils import find_column, get_vacuum_column
from utils.freeze_thaw import (
    get_current_freeze_thaw_status,
    detect_freeze_event_drops,
    render_freeze_thaw_banner
)


def get_temperature_data(days=7):
    """Get historical temperature data from Open-Meteo API"""
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": 43.4267,  # Lake George, NY
            "longitude": -73.7123,
            "daily": ["temperature_2m_max", "temperature_2m_min"],
            "temperature_unit": "fahrenheit",
            "timezone": "America/New_York",
            "past_days": days,
            "forecast_days": 0
        }
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()['daily']
        
        # Create dataframe
        temp_df = pd.DataFrame({
            'Date': pd.to_datetime(data['time']),
            'High': data['temperature_2m_max'],
            'Low': data['temperature_2m_min']
        })
        
        # Check if any temp was above freezing
        temp_df['Above_Freezing'] = (temp_df['High'] > 32) | (temp_df['Low'] > 32)
        
        return temp_df
    except:
        return None


def render(vacuum_df, personnel_df):
    """Render vacuum performance page with site context"""

    st.title("🔧 Vacuum Performance")

    # Freeze/thaw context banner — tells manager if this page is worth studying now
    freeze_status = get_current_freeze_thaw_status()
    render_freeze_thaw_banner(freeze_status)

    if vacuum_df.empty:
        st.warning("No vacuum data available")
        return

# ============================================================================
    # MAPLE-ONLY FILTERING
    # ============================================================================
    
    # Look for Station column (should be 4th column)
    station_col = find_column(vacuum_df, 'Station', 'station')
    
    if station_col:
        original_count = len(vacuum_df)
        
        # Filter to only stations that contain "maple" anywhere in the cell (case-insensitive)
        vacuum_df = vacuum_df[
            vacuum_df[station_col].str.lower().str.contains('maple', na=False, case=False)
        ].copy()
        
        filtered_count = len(vacuum_df)
    # Check if we have site information and if we're viewing a specific site
    has_site = 'Site' in vacuum_df.columns
    viewing_site = None
    
    if has_site and len(vacuum_df['Site'].unique()) == 1:
        viewing_site = vacuum_df['Site'].iloc[0]
        site_emoji = "🟦" if viewing_site == "NY" else "🟩" if viewing_site == "VT" else "⚫"
        st.caption(f"{site_emoji} {viewing_site} site only")
    elif has_site:
        # Viewing multiple sites
        site_counts = vacuum_df['Site'].value_counts()
        site_info = " | ".join([f"🟦 NY: {site_counts.get('NY', 0):,}" if s == 'NY' 
                               else f"🟩 VT: {site_counts.get('VT', 0):,}" 
                               for s in ['NY', 'VT'] if s in site_counts.index])
        st.caption(f"📊 All sites - {site_info}")

    # ============================================================================
    # VACUUM TRENDS SECTION - DAILY VIEW WITH TEMPERATURE AWARENESS
    # ============================================================================

    st.subheader("📈 Vacuum Trends - Daily View")

    vacuum_col = get_vacuum_column(vacuum_df)
    timestamp_col = find_column(
        vacuum_df,
        'Last communication', 'Last Communication', 'Timestamp', 'timestamp',
        'time', 'datetime', 'last_communication'
    )

    if vacuum_col and timestamp_col:
        # Make sure timestamp is datetime
        temp_df = vacuum_df.copy()
        temp_df[timestamp_col] = pd.to_datetime(temp_df[timestamp_col], errors='coerce')
        temp_df = temp_df.dropna(subset=[timestamp_col])

        if not temp_df.empty:
            # Get temperature data
            temp_data = get_temperature_data(days=7)
            
            # Create date column
            temp_df['Date'] = temp_df[timestamp_col].dt.date

            # Aggregate by date
            daily = temp_df.groupby('Date')[vacuum_col].mean().reset_index()
            daily = daily.sort_values('Date').tail(7)
            
            if temp_data is not None:
                # Merge with temperature data
                temp_data['Date'] = temp_data['Date'].dt.date
                daily = daily.merge(temp_data[['Date', 'High', 'Above_Freezing']], on='Date', how='left')
                
                # Filter to only days above freezing for weekly view
                daily_above_freezing = daily[daily['Above_Freezing'] == True].copy()
                
                if len(daily_above_freezing) > 0:
                    st.caption("📊 Showing only days with temps above freezing (optimal sap flow)")
                    display_daily = daily_above_freezing
                else:
                    st.caption("❄️ No days above freezing in past week - showing all days")
                    display_daily = daily
            else:
                display_daily = daily
                st.caption("📊 7-day vacuum trend (temperature data unavailable)")

            if len(display_daily) > 0:
                # Convert date to datetime for proper chart display
                display_daily['Date'] = pd.to_datetime(display_daily['Date'])

                # Create nice chart with plotly for better control
                import plotly.graph_objects as go
                
                fig = go.Figure()
                
                # Add vacuum trace
                fig.add_trace(go.Scatter(
                    x=display_daily['Date'],
                    y=display_daily[vacuum_col],
                    mode='lines+markers',
                    name='Avg Vacuum',
                    line=dict(color='#2196F3', width=3),
                    marker=dict(size=10),
                    hovertemplate='<b>%{x|%B %d}</b><br>Vacuum: %{y:.1f}"<extra></extra>'
                ))
                
                # Add temperature info if available
                if 'High' in display_daily.columns:
                    fig.add_trace(go.Scatter(
                        x=display_daily['Date'],
                        y=display_daily['High'],
                        mode='lines',
                        name='High Temp',
                        line=dict(color='#FF9800', width=2, dash='dot'),
                        yaxis='y2',
                        hovertemplate='<b>%{x|%B %d}</b><br>High: %{y:.0f}°F<extra></extra>'
                    ))
                
                # Add freeze/thaw day highlighting (blue bands)
                if temp_data is not None and 'Low' in temp_data.columns:
                    for _, trow in temp_data.iterrows():
                        t_high = trow.get('High')
                        t_low = trow.get('Low')
                        if t_high is not None and t_low is not None:
                            if t_low < config.FREEZING_POINT and t_high > config.FREEZING_POINT:
                                d = trow['Date']
                                if hasattr(d, 'date'):
                                    d = d.date()
                                fig.add_vrect(
                                    x0=pd.Timestamp(d) - pd.Timedelta(hours=12),
                                    x1=pd.Timestamp(d) + pd.Timedelta(hours=12),
                                    fillcolor="rgba(100, 149, 237, 0.15)",
                                    line_width=0,
                                    annotation_text="F/T",
                                    annotation_position="top left",
                                    annotation_font_size=9,
                                    annotation_font_color="cornflowerblue",
                                )

                # Add 32°F freeze reference line on temp axis
                if 'High' in display_daily.columns:
                    fig.add_hline(
                        y=config.FREEZING_POINT, line_dash="dash",
                        line_color="lightblue", line_width=1,
                        annotation_text="32°F",
                        annotation_font_color="lightblue",
                        yref="y2"
                    )

                # Update layout
                fig.update_layout(
                    yaxis=dict(
                        title="Average Vacuum (inches)",
                        side='left'
                    ),
                    yaxis2=dict(
                        title="Temperature (°F)",
                        overlaying='y',
                        side='right',
                        showgrid=False
                    ) if 'High' in display_daily.columns else None,
                    xaxis_title="Date",
                    height=400,
                    hovermode='x unified',
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )

                st.plotly_chart(fig, use_container_width=True)

                # Show data summary
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Days Shown", len(display_daily))
                with col2:
                    st.metric("Average", f"{display_daily[vacuum_col].mean():.1f}\"")
                with col3:
                    st.metric("Highest", f"{display_daily[vacuum_col].max():.1f}\"")
                with col4:
                    st.metric("Lowest", f"{display_daily[vacuum_col].min():.1f}\"")
            else:
                st.info("Not enough data for trend chart (need at least 1 day)")
        else:
            st.info("No valid timestamp data for trends")
    else:
        missing = []
        if not vacuum_col:
            missing.append("vacuum reading column")
        if not timestamp_col:
            missing.append("timestamp column")
        st.warning(f"Cannot create trend chart - missing: {', '.join(missing)}")

    st.divider()

    # ============================================================================
    # HOURLY DRILL-DOWN FOR SELECTED DAY
    # ============================================================================
    
    st.subheader("🕐 Hourly Detail - Select a Day")
    
    if vacuum_col and timestamp_col:
        temp_df = vacuum_df.copy()
        temp_df[timestamp_col] = pd.to_datetime(temp_df[timestamp_col], errors='coerce')
        temp_df = temp_df.dropna(subset=[timestamp_col])
        
        # Get available dates
        available_dates = sorted(temp_df[timestamp_col].dt.date.unique(), reverse=True)
        
        if len(available_dates) > 0:
            selected_date = st.selectbox(
                "Choose a date to see hourly breakdown:",
                options=available_dates,
                format_func=lambda x: x.strftime('%A, %B %d, %Y')
            )
            
            # Filter to selected date
            day_data = temp_df[temp_df[timestamp_col].dt.date == selected_date].copy()
            
            if not day_data.empty:
                # Create hour column
                day_data['Hour'] = day_data[timestamp_col].dt.hour
                
                # Aggregate by hour
                hourly = day_data.groupby('Hour')[vacuum_col].mean().reset_index()
                hourly = hourly.sort_values('Hour')
                
                # Create hourly chart
                import plotly.graph_objects as go
                
                fig = go.Figure()
                
                fig.add_trace(go.Bar(
                    x=hourly['Hour'],
                    y=hourly[vacuum_col],
                    marker_color='#4CAF50',
                    hovertemplate='<b>Hour %{x}:00</b><br>Vacuum: %{y:.1f}"<extra></extra>'
                ))
                
                fig.update_layout(
                    xaxis=dict(
                        title="Hour of Day",
                        tickmode='linear',
                        tick0=0,
                        dtick=1
                    ),
                    yaxis_title="Average Vacuum (inches)",
                    height=350,
                    hovermode='x'
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Summary stats
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Hours Recorded", len(hourly))
                with col2:
                    st.metric("Daily Average", f"{hourly[vacuum_col].mean():.1f}\"")
                with col3:
                    best_hour = hourly.loc[hourly[vacuum_col].idxmax(), 'Hour']
                    st.metric("Best Hour", f"{int(best_hour)}:00")
                with col4:
                    worst_hour = hourly.loc[hourly[vacuum_col].idxmin(), 'Hour']
                    st.metric("Worst Hour", f"{int(worst_hour)}:00")
            else:
                st.info(f"No data available for {selected_date}")
        else:
            st.info("No dates available for hourly analysis")
    
    st.divider()

    # ============================================================================
    # FREEZE EVENT ANALYSIS
    # ============================================================================

    # Get temperature data for freeze analysis (reuse if already fetched above)
    freeze_temp_data = get_temperature_data(days=7)
    freeze_drops_df = detect_freeze_event_drops(vacuum_df, freeze_temp_data)

    is_critical = freeze_status.get('status_label') in ('CRITICAL', 'UPCOMING')

    if is_critical and not freeze_drops_df.empty:
        # Prominent display during freeze events
        st.subheader("❄️ Freeze Event Leak Detection")
        st.caption("Sensors whose vacuum dropped during freeze/thaw days — potential open or leaking lines")

        likely_count = len(freeze_drops_df[freeze_drops_df['Freeze_Status'] == 'LIKELY LEAK'])
        watch_count = len(freeze_drops_df[freeze_drops_df['Freeze_Status'] == 'WATCH'])
        ok_count = len(freeze_drops_df[freeze_drops_df['Freeze_Status'] == 'OK'])

        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            st.metric("🔴 Likely Leak", likely_count)
        with fc2:
            st.metric("🟠 Watch", watch_count)
        with fc3:
            st.metric("🟢 OK", ok_count)

        # Show flagged sensors table
        flagged = freeze_drops_df[freeze_drops_df['Freeze_Status'] != 'OK'].copy()
        if not flagged.empty:
            display_freeze = flagged.copy()
            display_freeze['Drop_Rate'] = (display_freeze['Drop_Rate'] * 100).round(0).astype(int).astype(str) + '%'
            display_freeze['Avg_Drop'] = display_freeze['Avg_Drop'].apply(lambda x: f'{x:.1f}"')
            display_freeze['Latest_Vacuum'] = display_freeze['Latest_Vacuum'].apply(lambda x: f'{x:.1f}"')
            display_freeze.columns = ['Sensor', 'Avg Drop', 'Freeze Days w/ Drop',
                                       'Total Freeze Days', 'Drop Rate', 'Latest Vacuum', 'Status']
            st.dataframe(display_freeze, use_container_width=True, hide_index=True)

            # Chart: top 5 flagged sensors vacuum over time with freeze-day shading
            top_flagged = flagged.head(5)['Sensor'].tolist()
            _render_freeze_sensor_chart(vacuum_df, freeze_temp_data, top_flagged)
        else:
            st.success("No sensors flagged during recent freeze events.")

    elif not freeze_drops_df.empty:
        # Low priority — collapse into expander
        with st.expander("❄️ Freeze Event Analysis (not currently active)"):
            st.caption("No freeze/thaw transition today. Historical freeze analysis shown below.")
            likely_count = len(freeze_drops_df[freeze_drops_df['Freeze_Status'] == 'LIKELY LEAK'])
            watch_count = len(freeze_drops_df[freeze_drops_df['Freeze_Status'] == 'WATCH'])
            if likely_count > 0 or watch_count > 0:
                st.markdown(f"**{likely_count}** likely leak(s), **{watch_count}** watch sensor(s) from recent freeze events.")
                display_freeze = freeze_drops_df[freeze_drops_df['Freeze_Status'] != 'OK'].copy()
                if not display_freeze.empty:
                    display_freeze['Drop_Rate'] = (display_freeze['Drop_Rate'] * 100).round(0).astype(int).astype(str) + '%'
                    display_freeze['Avg_Drop'] = display_freeze['Avg_Drop'].apply(lambda x: f'{x:.1f}"')
                    display_freeze['Latest_Vacuum'] = display_freeze['Latest_Vacuum'].apply(lambda x: f'{x:.1f}"')
                    display_freeze.columns = ['Sensor', 'Avg Drop', 'Freeze Days w/ Drop',
                                               'Total Freeze Days', 'Drop Rate', 'Latest Vacuum', 'Status']
                    st.dataframe(display_freeze, use_container_width=True, hide_index=True)
            else:
                st.info("All sensors held vacuum well during recent freeze events.")
    else:
        with st.expander("❄️ Freeze Event Analysis"):
            st.info(
                "Not enough freeze/thaw data for analysis. "
                "Use **Load More Vacuum Data (60 days)** in the sidebar for a fuller picture."
            )

    st.divider()

    # ============================================================================
    # FREEZING REPORT — RELEASER DIFFERENTIAL COLOR-CODED DISPLAY
    # ============================================================================

    _render_freezing_report(vacuum_df)

    st.divider()

    # ============================================================================
    # PER-MAINLINE SENSOR DRILL-DOWN CHARTS
    # ============================================================================

    _render_sensor_drilldown(vacuum_df)

    st.divider()

    # ============================================================================
    # SENSOR DETAILS SECTION
    # ============================================================================

    st.subheader("📍 Sensor Details")

    # Use exact column names from your sheets
    sensor_col = 'Name'  # Your vacuum sheet uses 'Name' for sensor/mainline
    vacuum_col = 'Vacuum'  # Your vacuum sheet uses 'Vacuum' for reading
    timestamp_col = 'Last communication'  # Your vacuum sheet uses this for timestamp

    # Verify columns exist
    if sensor_col not in vacuum_df.columns:
        st.error(f"Column '{sensor_col}' not found in vacuum data")
        st.write("Available columns:", list(vacuum_df.columns))
        return

    if vacuum_col not in vacuum_df.columns:
        st.error(f"Column '{vacuum_col}' not found in vacuum data")
        st.write("Available columns:", list(vacuum_df.columns))
        return

    # Get latest reading per sensor
    if timestamp_col in vacuum_df.columns:
        temp_df = vacuum_df.copy()
        temp_df[timestamp_col] = pd.to_datetime(temp_df[timestamp_col], errors='coerce')
        latest = temp_df.sort_values(timestamp_col, ascending=False).groupby(sensor_col).first().reset_index()
    else:
        latest = vacuum_df.groupby(sensor_col).first().reset_index()

    # Calculate statistics
    summary = vacuum_df.groupby(sensor_col).agg({
        vacuum_col: ['mean', 'min', 'max', 'count']
    }).reset_index()

    summary.columns = ['Sensor', 'Avg_Vacuum', 'Min_Vacuum', 'Max_Vacuum', 'Count']
    summary['Status'] = summary['Avg_Vacuum'].apply(config.get_vacuum_emoji)

    # Add site if available
    if has_site:
        # Get site for each sensor from latest reading
        sensor_sites = latest[[sensor_col, 'Site']].copy()
        sensor_sites.columns = ['Sensor', 'Site']
        summary = summary.merge(sensor_sites, on='Sensor', how='left')

    # Add last report time if available
    if timestamp_col in vacuum_df.columns:
        temp_df = vacuum_df.copy()
        temp_df[timestamp_col] = pd.to_datetime(temp_df[timestamp_col], errors='coerce')
        last_report = temp_df.groupby(sensor_col)[timestamp_col].max().reset_index()
        last_report.columns = ['Sensor', 'Last_Report']
        summary = summary.merge(last_report, on='Sensor', how='left')

    # Add freeze alert info to sensor summary
    if not freeze_drops_df.empty:
        freeze_merge = freeze_drops_df[['Sensor', 'Freeze_Status', 'Drop_Rate']].copy()
        summary = summary.merge(freeze_merge, on='Sensor', how='left')
        summary['Freeze_Status'] = summary['Freeze_Status'].fillna('')
        summary['Drop_Rate'] = summary['Drop_Rate'].fillna(0)
    else:
        summary['Freeze_Status'] = ''
        summary['Drop_Rate'] = 0

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        status_filter = st.selectbox("Filter by Status", ["All", "🟢 Excellent", "🟡 Fair", "🔴 Poor"])

    with col2:
        min_vacuum = st.number_input("Min Vacuum", 0.0, 30.0, 0.0, 0.5)

    with col3:
        show_freeze_only = st.checkbox(
            "❄️ Freeze-flagged only",
            value=False,
            help="Show only sensors flagged during freeze events"
        )

    # Apply filters
    filtered = summary.copy()

    if status_filter != "All":
        filtered = filtered[filtered['Avg_Vacuum'].apply(config.get_vacuum_status) == status_filter]

    if min_vacuum > 0:
        filtered = filtered[filtered['Avg_Vacuum'] >= min_vacuum]

    if show_freeze_only:
        filtered = filtered[filtered['Freeze_Status'].isin(['LIKELY LEAK', 'WATCH'])]

    st.divider()

    # Summary stats
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Sensors", len(summary))

    with col2:
        excellent = len(summary[summary['Avg_Vacuum'] >= config.VACUUM_EXCELLENT])
        st.metric("🟢 Excellent", excellent)

    with col3:
        fair = len(
            summary[(summary['Avg_Vacuum'] >= config.VACUUM_FAIR) & (summary['Avg_Vacuum'] < config.VACUUM_EXCELLENT)])
        st.metric("🟡 Fair", fair)

    with col4:
        poor = len(summary[summary['Avg_Vacuum'] < config.VACUUM_FAIR])
        st.metric("🔴 Poor", poor)

    # Site breakdown if viewing all sites
    if has_site and not viewing_site:
        st.markdown("**Sensor Performance by Site:**")
        
        site_perf = summary.groupby('Site').agg({
            'Avg_Vacuum': 'mean',
            'Sensor': 'count'
        }).reset_index()
        
        cols = st.columns(len(site_perf))
        for idx, row in site_perf.iterrows():
            with cols[idx]:
                emoji = "🟦" if row['Site'] == "NY" else "🟩" if row['Site'] == "VT" else "⚫"
                st.metric(
                    f"{emoji} {row['Site']}", 
                    f"{row['Avg_Vacuum']:.1f}\"",
                    delta=f"{int(row['Sensor'])} sensors"
                )

    st.divider()

    # Display table
    st.subheader(f"Sensor Performance ({len(filtered)} locations)")

    display = filtered.copy()
    for col in ['Avg_Vacuum', 'Min_Vacuum', 'Max_Vacuum']:
        display[col] = display[col].apply(lambda x: f"{x:.1f}\"")

    # Format columns for display
    display_cols = ['Status', 'Sensor', 'Avg_Vacuum', 'Min_Vacuum', 'Max_Vacuum', 'Count']
    col_names = ['⚫', 'Sensor', 'Avg', 'Min', 'Max', 'Readings']

    # Add site if available and viewing all
    if has_site and 'Site' in display.columns:
        # Add emoji to site
        display['Site_Display'] = display['Site'].apply(
            lambda x: f"🟦 {x}" if x == 'NY' else f"🟩 {x}" if x == 'VT' else f"⚫ {x}"
        )
        display_cols.insert(1, 'Site_Display')
        col_names.insert(1, 'Site')

    if 'Last_Report' in display.columns:
        display['Last_Report_Display'] = display['Last_Report'].apply(
            lambda x: x.strftime('%Y-%m-%d %H:%M') if pd.notna(x) else "N/A"
        )
        display_cols.append('Last_Report_Display')
        col_names.append('Last Report')

    # Add freeze alert column
    if 'Freeze_Status' in display.columns:
        def _freeze_icon(val):
            if val == 'LIKELY LEAK':
                return '🔴 LEAK'
            elif val == 'WATCH':
                return '🟠 WATCH'
            elif val == 'OK':
                return '✅'
            return ''
        display['Freeze_Alert'] = display['Freeze_Status'].apply(_freeze_icon)
        display_cols.append('Freeze_Alert')
        col_names.append('❄️ Freeze')

    display = display[display_cols]
    display.columns = col_names

    st.dataframe(display, use_container_width=True, hide_index=True, height=400)

    st.divider()

    # Tips
    with st.expander("💡 Understanding Vacuum Performance"):
        st.markdown("""
        **What's New:**
        
        - 🍁 **Maple-Only View**: Automatically filters to show only maple systems
        - 📈 **Temperature-Aware Trends**: Weekly view shows only days above freezing
        - 🕐 **Hourly Drill-Down**: Select any day to see hour-by-hour vacuum levels
        - 📊 **Improved Charts**: Cleaner daily trends with temperature overlay
        
        **Metrics Explained:**
        
        - **Average**: Mean vacuum across all readings for this sensor
        - **Min/Max**: Range of vacuum values observed
        - **Readings**: Number of data points collected
        - **Last Report**: Most recent timestamp for this sensor
        
        **Status Categories:**
        
        - 🟢 **Excellent** (≥18"): Optimal performance, system healthy
        - 🟡 **Fair** (15-18"): Acceptable but monitor closely
        - 🔴 **Poor** (<15"): Needs attention, check for issues
        
        **Using the Daily Trends:**
        
        - Chart shows average vacuum by day
        - Only displays days with temps above 32°F (optimal sap flow conditions)
        - Temperature line helps correlate vacuum with weather
        - If no days above freezing, shows all days
        
        **Using the Hourly Detail:**
        
        - Select any date to see vacuum levels by hour
        - Helps identify daily patterns (morning freeze-up, afternoon improvement)
        - Useful for troubleshooting time-specific issues
        - See which hours have best/worst performance
        
        **Freeze Event Analysis:**

        - During freeze/thaw transitions (low < 32°F, high > 32°F), open or
          leaking lines freeze faster than sealed ones
        - The dashboard compares each sensor's vacuum on freeze days vs the prior day
        - **LIKELY LEAK**: Vacuum dropped on >50% of freeze days
        - **WATCH**: Vacuum dropped on >25% of freeze days
        - Use "❄️ Freeze-flagged only" checkbox to filter the sensor table
        - Load 60 days of data for the best freeze analysis

        **Best Practices:**

        - Focus on above-freezing days for meaningful trends
        - Use hourly view to diagnose daily performance patterns
        - During freeze events, check the Freeze Event Analysis section first
        - Compare similar sensors for patterns
        - Monitor maple systems specifically for sap quality
        """)


def _render_freeze_sensor_chart(vacuum_df, temp_data, sensor_list):
    """Render a plotly chart showing vacuum trends for flagged sensors with freeze-day shading."""
    import plotly.graph_objects as go
    from utils import find_column, get_vacuum_column

    sensor_col = find_column(vacuum_df, 'Name', 'name', 'Sensor Name', 'sensor')
    vacuum_col = get_vacuum_column(vacuum_df)
    timestamp_col = find_column(
        vacuum_df, 'Last communication', 'Last Communication',
        'Timestamp', 'timestamp'
    )

    if not all([sensor_col, vacuum_col, timestamp_col]):
        return

    vdf = vacuum_df.copy()
    vdf[timestamp_col] = pd.to_datetime(vdf[timestamp_col], errors='coerce')
    vdf = vdf.dropna(subset=[timestamp_col])
    vdf['Date'] = vdf[timestamp_col].dt.date

    fig = go.Figure()

    colors = ['#d62728', '#ff7f0e', '#e377c2', '#bcbd22', '#17becf']
    for i, sensor in enumerate(sensor_list):
        sdata = vdf[vdf[sensor_col] == sensor].copy()
        daily = sdata.groupby('Date')[vacuum_col].mean().reset_index()
        daily['Date'] = pd.to_datetime(daily['Date'])
        daily = daily.sort_values('Date')

        fig.add_trace(go.Scatter(
            x=daily['Date'], y=daily[vacuum_col],
            mode='lines+markers', name=sensor,
            line=dict(color=colors[i % len(colors)], width=2),
            marker=dict(size=6),
        ))

    # Add freeze-day shading
    if temp_data is not None and 'Low' in temp_data.columns:
        freezing = config.FREEZING_POINT
        for _, row in temp_data.iterrows():
            t_high = row.get('High')
            t_low = row.get('Low')
            if t_high is not None and t_low is not None:
                if t_low < freezing and t_high > freezing:
                    d = row['Date']
                    if hasattr(d, 'date'):
                        d = d.date()
                    fig.add_vrect(
                        x0=pd.Timestamp(d) - pd.Timedelta(hours=12),
                        x1=pd.Timestamp(d) + pd.Timedelta(hours=12),
                        fillcolor="rgba(100, 149, 237, 0.15)",
                        line_width=0,
                    )

    fig.update_layout(
        title="Flagged Sensors — Vacuum During Freeze Events",
        yaxis_title="Average Vacuum (inches)",
        xaxis_title="Date",
        height=350,
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# FREEZING REPORT — Releaser Differential Color-Coded Display
# ============================================================================

def _render_freezing_report(vacuum_df):
    """Render the freezing report section with graduated releaser differential colors."""
    import plotly.graph_objects as go
    from utils import find_column, get_vacuum_column, get_releaser_column, extract_conductor_system

    st.subheader("🧊 Freezing Report — Releaser Differential")
    st.caption(
        "Color-coded by releaser differential: "
        "dark green (<1\") to pink (>10\"). "
        "Dark red = frozen (vacuum 0 but releaser > 0). "
        "Gray = pump off (both 0)."
    )

    sensor_col = find_column(vacuum_df, 'Name', 'name', 'Sensor Name', 'sensor')
    vacuum_col = get_vacuum_column(vacuum_df)
    releaser_col = get_releaser_column(vacuum_df)
    timestamp_col = find_column(
        vacuum_df, 'Last communication', 'Last Communication',
        'Timestamp', 'timestamp'
    )

    if not releaser_col:
        st.info("No releaser differential column found in vacuum data. "
                "This report requires CDL sensor data with a releaser differential reading.")
        return

    if not all([sensor_col, vacuum_col, timestamp_col]):
        st.warning("Missing required columns for freezing report.")
        return

    # Get latest reading per sensor
    vdf = vacuum_df.copy()
    vdf[timestamp_col] = pd.to_datetime(vdf[timestamp_col], errors='coerce')
    vdf = vdf.dropna(subset=[timestamp_col])
    vdf[vacuum_col] = pd.to_numeric(vdf[vacuum_col], errors='coerce')
    vdf[releaser_col] = pd.to_numeric(vdf[releaser_col], errors='coerce')

    # Filter to valid maple sensors (2+ uppercase letters + number)
    import re
    valid_sensor = r'^[A-Z]{2,6}\d'
    vdf = vdf[vdf[sensor_col].str.match(valid_sensor, na=False)]

    # Exclude non-maple sensors (birch, relays, typos)
    vdf = vdf[~vdf[sensor_col].apply(config.is_excluded_sensor)]

    if vdf.empty:
        st.warning("No valid sensor data for freezing report.")
        return

    # Latest reading per sensor
    latest = vdf.sort_values(timestamp_col, ascending=False).groupby(sensor_col).first().reset_index()

    # Add conductor system grouping
    latest['Conductor'] = latest[sensor_col].apply(extract_conductor_system)

    # Add color and status using config helper
    latest['_color'], latest['_label'] = zip(
        *latest.apply(lambda r: config.get_releaser_diff_color(r[vacuum_col], r[releaser_col]), axis=1)
    )

    # Summary metrics
    frozen_count = len(latest[latest['_label'] == 'FROZEN'])
    off_count = len(latest[latest['_label'] == 'OFF'])
    critical_count = len(latest[latest['_label'] == 'Critical'])
    healthy_count = len(latest[latest['_label'].isin(['Excellent', 'Good', 'Acceptable'])])

    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        st.metric("🔴 FROZEN", frozen_count)
    with mc2:
        st.metric("🩷 Critical (>10\")", critical_count)
    with mc3:
        st.metric("🟢 Healthy (<3\")", healthy_count)
    with mc4:
        st.metric("⚫ Pump Off", off_count)

    # --- Conductor system selector ---
    conductors = sorted(latest['Conductor'].unique())
    if len(conductors) > 1:
        selected_conductor = st.selectbox(
            "Filter by Conductor System",
            ["All"] + conductors,
            key="freeze_report_conductor"
        )
        if selected_conductor != "All":
            latest = latest[latest['Conductor'] == selected_conductor]

    # --- Color-coded table ---
    # Build a Plotly heatmap-style bar chart showing each sensor's status
    # Sort: FROZEN first, then by releaser diff descending
    status_order = {'FROZEN': 0, 'Critical': 1, 'Elevated': 2, 'Moderate': 3,
                    'Acceptable': 4, 'Good': 5, 'Excellent': 6, 'OFF': 7, 'No Data': 8}
    latest['_sort'] = latest['_label'].map(status_order).fillna(9)
    latest = latest.sort_values(['_sort', releaser_col], ascending=[True, False])

    # Create horizontal bar chart (like CDL freezing report)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=latest[sensor_col],
        x=latest[releaser_col].fillna(0),
        orientation='h',
        marker=dict(color=latest['_color']),
        text=latest['_label'],
        textposition='auto',
        hovertemplate=(
            '<b>%{y}</b><br>'
            'Releaser Diff: %{x:.1f}"<br>'
            'Status: %{text}<extra></extra>'
        ),
    ))

    fig.update_layout(
        title="Sensors by Releaser Differential",
        xaxis_title='Releaser Differential (inches)',
        yaxis_title='',
        height=max(300, len(latest) * 22),
        yaxis=dict(autorange='reversed'),
        margin=dict(l=120),
    )

    st.plotly_chart(fig, use_container_width=True)

    # --- Color legend ---
    legend_cols = st.columns(8)
    legend_items = [
        ('#006400', '<1"'), ('#228B22', '1-2"'), ('#90EE90', '2-3"'),
        ('#DAA520', '3-5"'), ('#FFD700', '5-10"'), ('#FF69B4', '>10"'),
        ('#8B0000', 'FROZEN'), ('#808080', 'OFF'),
    ]
    for col_w, (color, label) in zip(legend_cols, legend_items):
        with col_w:
            st.markdown(
                f"<span style='color:{color}; font-size:20px;'>&#9679;</span> {label}",
                unsafe_allow_html=True
            )

    # --- Detailed table ---
    with st.expander("View Detailed Table"):
        detail = latest[[sensor_col, 'Conductor', vacuum_col, releaser_col, '_label', timestamp_col]].copy()
        detail.columns = ['Sensor', 'Conductor', 'Vacuum', 'Releaser Diff', 'Status', 'Last Reading']
        detail['Vacuum'] = detail['Vacuum'].apply(lambda x: f'{x:.1f}"' if pd.notna(x) else 'N/A')
        detail['Releaser Diff'] = detail['Releaser Diff'].apply(lambda x: f'{x:.1f}"' if pd.notna(x) else 'N/A')
        detail['Last Reading'] = detail['Last Reading'].apply(
            lambda x: x.strftime('%Y-%m-%d %H:%M') if pd.notna(x) and hasattr(x, 'strftime') else ''
        )
        st.dataframe(detail, use_container_width=True, hide_index=True, height=400)


# ============================================================================
# PER-MAINLINE SENSOR DRILL-DOWN CHARTS
# ============================================================================

def _render_sensor_drilldown(vacuum_df):
    """Render per-mainline time-series charts: Last 24H and Last 7 Days."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from utils import find_column, get_vacuum_column, get_releaser_column

    st.subheader("🔍 Sensor Detail — Vacuum Over Time")
    st.caption("Select a sensor to view its vacuum and releaser differential history")

    sensor_col = find_column(vacuum_df, 'Name', 'name', 'Sensor Name', 'sensor')
    vacuum_col = get_vacuum_column(vacuum_df)
    releaser_col = get_releaser_column(vacuum_df)
    timestamp_col = find_column(
        vacuum_df, 'Last communication', 'Last Communication',
        'Timestamp', 'timestamp'
    )

    if not all([sensor_col, vacuum_col, timestamp_col]):
        st.warning("Missing required columns for sensor drill-down.")
        return

    # Filter to valid sensors, excluding non-maple
    import re
    valid_sensor = r'^[A-Z]{2,6}\d'
    mask = (vacuum_df[sensor_col].str.match(valid_sensor, na=False) &
            ~vacuum_df[sensor_col].apply(config.is_excluded_sensor))
    sensors = sorted(vacuum_df[mask][sensor_col].unique())

    if not sensors:
        st.info("No valid sensors found.")
        return

    selected_sensor = st.selectbox("Select Sensor", sensors, key="drilldown_sensor")

    # Filter data for selected sensor
    sdf = vacuum_df[vacuum_df[sensor_col] == selected_sensor].copy()
    sdf[timestamp_col] = pd.to_datetime(sdf[timestamp_col], errors='coerce')
    sdf = sdf.dropna(subset=[timestamp_col]).sort_values(timestamp_col)
    sdf[vacuum_col] = pd.to_numeric(sdf[vacuum_col], errors='coerce')
    if releaser_col:
        sdf[releaser_col] = pd.to_numeric(sdf[releaser_col], errors='coerce')

    if sdf.empty:
        st.info(f"No data for {selected_sensor}")
        return

    # Split into Last 24H and Last 7 Days
    now = sdf[timestamp_col].max()
    last_24h = sdf[sdf[timestamp_col] >= now - pd.Timedelta(hours=24)]
    last_7d = sdf[sdf[timestamp_col] >= now - pd.Timedelta(days=7)]

    # Render two side-by-side charts
    tab1, tab2 = st.tabs(["Last 24 Hours", "Last 7 Days"])

    for tab, data, title in [(tab1, last_24h, "Last 24 Hours"), (tab2, last_7d, "Last 7 Days")]:
        with tab:
            if data.empty:
                st.info(f"No data for {title}")
                continue

            fig = make_subplots(specs=[[{"secondary_y": True}]])

            # Color vacuum dots by releaser differential
            if releaser_col and releaser_col in data.columns:
                colors = data.apply(
                    lambda r: config.get_releaser_diff_color(r[vacuum_col], r[releaser_col])[0], axis=1
                )
            else:
                colors = '#1f77b4'

            # Vacuum reading (primary y-axis)
            fig.add_trace(
                go.Scatter(
                    x=data[timestamp_col], y=data[vacuum_col],
                    mode='lines+markers',
                    name='Vacuum',
                    line=dict(color='#1f77b4', width=2),
                    marker=dict(color=colors, size=8, line=dict(width=1, color='white')),
                    hovertemplate='Vacuum: %{y:.1f}"<br>%{x}<extra></extra>',
                ),
                secondary_y=False,
            )

            # Releaser differential (secondary y-axis) — solid, darker, circles
            if releaser_col and releaser_col in data.columns:
                fig.add_trace(
                    go.Scatter(
                        x=data[timestamp_col], y=data[releaser_col],
                        mode='lines+markers',
                        name='Releaser Diff',
                        line=dict(color='#C43E00', width=2),
                        marker=dict(color='#C43E00', size=6, symbol='circle'),
                        hovertemplate='Rel Diff: %{y:.1f}"<br>%{x}<extra></extra>',
                    ),
                    secondary_y=True,
                )

            fig.update_layout(
                title=f"{selected_sensor} — {title}",
                height=400,
                hovermode='x unified',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                font=dict(size=13),
            )
            fig.update_yaxes(title_text="Vacuum (inches)", secondary_y=False)
            fig.update_yaxes(title_text="Releaser Diff (inches)", secondary_y=True)

            st.plotly_chart(fig, use_container_width=True)

            # Quick stats
            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                st.metric("Avg Vacuum", f"{data[vacuum_col].mean():.1f}\"")
            with sc2:
                st.metric("Min Vacuum", f"{data[vacuum_col].min():.1f}\"")
            with sc3:
                st.metric("Max Vacuum", f"{data[vacuum_col].max():.1f}\"")
            with sc4:
                st.metric("Readings", len(data))
