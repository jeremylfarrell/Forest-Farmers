"""
Vacuum Performance Page Module - MULTI-SITE POLISHED
Shows performance metrics for each vacuum sensor and system trends
UPDATED: Maple-only filtering, daily trends with hourly drill-down, temp-aware weekly view
"""

import streamlit as st
import pandas as pd
import requests
import config
from utils import find_column, get_vacuum_column


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

    if vacuum_df.empty:
        st.warning("No vacuum data available")
        return

    # ============================================================================
    # MAPLE-ONLY FILTERING
    # ============================================================================
    
    sensor_col = find_column(vacuum_df, 'Name', 'name', 'mainline', 'Sensor Name', 'sensor', 'location')
    
    if sensor_col:
        original_count = len(vacuum_df)
        
        # Filter to only sensors that start with "maple" (case-insensitive)
        vacuum_df = vacuum_df[
            vacuum_df[sensor_col].str.lower().str.startswith('maple', na=False)
        ].copy()
        
        filtered_count = len(vacuum_df)
        
        if filtered_count < original_count:
            st.info(f"🍁 **Showing maple systems only** - {filtered_count:,} readings from maple sensors (filtered out {original_count - filtered_count:,} non-maple readings)")
        else:
            st.info(f"🍁 **Maple systems** - {filtered_count:,} sensor readings")
    
    if vacuum_df.empty:
        st.warning("No maple sensor data available after filtering")
        return

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

    # Filters
    col1, col2 = st.columns(2)

    with col1:
        status_filter = st.selectbox("Filter by Status", ["All", "🟢 Excellent", "🟡 Fair", "🔴 Poor"])

    with col2:
        min_vacuum = st.number_input("Min Vacuum", 0.0, 30.0, 0.0, 0.5)

    # Apply filters
    filtered = summary.copy()

    if status_filter != "All":
        filtered = filtered[filtered['Avg_Vacuum'].apply(config.get_vacuum_status) == status_filter]

    if min_vacuum > 0:
        filtered = filtered[filtered['Avg_Vacuum'] >= min_vacuum]

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
        
        **Best Practices:**
        
        - Focus on above-freezing days for meaningful trends
        - Use hourly view to diagnose daily performance patterns
        - Compare similar sensors for patterns
        - Monitor maple systems specifically for sap quality
        """)</document_content>
