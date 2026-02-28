"""
Sap Flow Forecast Page Module - MULTI-SITE POLISHED
Predicts sap flow based on weather forecasts
Now with multi-site context and notes
"""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go
import config
from utils.helpers import calculate_sap_flow_likelihood


def get_weather_forecast(latitude=None, longitude=None, days=10):
    """Get weather forecast from Open-Meteo API"""
    if latitude is None or longitude is None:
        _coords = config.SITE_COORDINATES['NY']
        latitude = _coords['lat']
        longitude = _coords['lon']
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "windspeed_10m_max"
            ],
            "temperature_unit": "fahrenheit",
            "windspeed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "America/New_York",
            "forecast_days": days
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Convert to DataFrame
        df = pd.DataFrame({
            'date': pd.to_datetime(data['daily']['time']),
            'high_temp': data['daily']['temperature_2m_max'],
            'low_temp': data['daily']['temperature_2m_min'],
            'precipitation': data['daily']['precipitation_sum'],
            'wind_speed': data['daily']['windspeed_10m_max']
        })
        
        return df
        
    except Exception as e:
        st.error(f"Error fetching weather data: {str(e)}")
        return None


def render(vacuum_df, personnel_df):
    """Render sap flow forecast page with multi-site awareness"""
    
    st.title("🌡️ Sap Flow Forecast")
    st.markdown("*10-day weather forecast and sap flow predictions*")
    
    # Check site context
    has_site = 'Site' in vacuum_df.columns if not vacuum_df.empty else False
    viewing_site = None
    
    if has_site and not vacuum_df.empty and len(vacuum_df['Site'].unique()) == 1:
        viewing_site = vacuum_df['Site'].iloc[0]
        site_emoji = "🟦" if viewing_site == "NY" else "🟩" if viewing_site == "VT" else "⚫"
    
    # Location settings
    st.subheader("📍 Forecast Location")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if viewing_site:
            st.info(f"{site_emoji} **Forecasting for {viewing_site} site**")
        else:
            st.info("📊 **Weather forecast applies to both NY and VT sites** (similar regional conditions)")
    
    with col2:
        # Option to use custom coordinates
        use_custom = st.checkbox("Use custom coordinates", value=False)
    
    if use_custom:
        _default = config.SITE_COORDINATES['NY']
        col1, col2 = st.columns(2)
        with col1:
            latitude = st.number_input("Latitude", value=_default['lat'], format="%.4f")
        with col2:
            longitude = st.number_input("Longitude", value=_default['lon'], format="%.4f")
    else:
        # Default to NY site coordinates
        _coords = config.SITE_COORDINATES['NY']
        latitude = _coords['lat']
        longitude = _coords['lon']
        st.caption(f"Using default coordinates: {latitude:.4f}°N, {longitude:.4f}°W ({_coords['name']})")
    
    st.divider()
    
    # Get forecast
    with st.spinner("Fetching weather forecast..."):
        forecast_df = get_weather_forecast(latitude, longitude, days=10)
    
    if forecast_df is None or forecast_df.empty:
        st.error("Unable to fetch weather forecast. Please try again later.")
        return
    
    # Calculate sap flow likelihood
    forecast_df['sap_likelihood'] = forecast_df.apply(
        lambda row: calculate_sap_flow_likelihood(
            row['high_temp'], 
            row['low_temp'], 
            row['precipitation'], 
            row['wind_speed']
        ),
        axis=1
    )
    
    # Add freeze/thaw indicator
    forecast_df['freeze_thaw'] = (forecast_df['low_temp'] < 32) & (forecast_df['high_temp'] > 32)
    
    # Calculate temperature swing
    forecast_df['temp_swing'] = forecast_df['high_temp'] - forecast_df['low_temp']
    
    # ============================================================================
    # SUMMARY METRICS
    # ============================================================================
    
    st.subheader("📊 10-Day Outlook")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        excellent_days = len(forecast_df[forecast_df['sap_likelihood'] >= 70])
        st.metric("Excellent Days", excellent_days, delta="🟢" if excellent_days > 0 else None)
    
    with col2:
        good_days = len(forecast_df[(forecast_df['sap_likelihood'] >= 50) & (forecast_df['sap_likelihood'] < 70)])
        st.metric("Good Days", good_days, delta="🟡" if good_days > 0 else None)
    
    with col3:
        freeze_thaw_days = forecast_df['freeze_thaw'].sum()
        st.metric("Freeze/Thaw Days", freeze_thaw_days)
    
    with col4:
        avg_likelihood = forecast_df['sap_likelihood'].mean()
        st.metric("Avg Likelihood", f"{avg_likelihood:.0f}%")
    
    # Multi-site note
    if has_site and not viewing_site:
        st.info("""
        💡 **Multi-Site Note:** This weather forecast applies to both NY and VT sites as they experience 
        similar regional weather patterns. Expected sap flow conditions should be comparable at both locations, 
        though local microclimates may cause minor variations.
        """)
    
    st.divider()
    
    # ============================================================================
    # SAP FLOW LIKELIHOOD CHART
    # ============================================================================
    
    st.subheader("🌡️ Sap Flow Likelihood")
    
    fig = go.Figure()
    
    # Color code by likelihood
    colors = []
    for likelihood in forecast_df['sap_likelihood']:
        if likelihood >= 70:
            colors.append('#28a745')  # Green
        elif likelihood >= 50:
            colors.append('#ffc107')  # Yellow
        elif likelihood >= 30:
            colors.append('#fd7e14')  # Orange
        else:
            colors.append('#dc3545')  # Red
    
    fig.add_trace(go.Bar(
        x=forecast_df['date'],
        y=forecast_df['sap_likelihood'],
        marker_color=colors,
        text=forecast_df['sap_likelihood'].apply(lambda x: f"{x:.0f}%"),
        textposition='outside',
        hovertemplate='<b>%{x|%A, %b %d}</b><br>Likelihood: %{y:.0f}%<extra></extra>'
    ))
    
    # Add reference lines
    fig.add_hline(y=70, line_dash="dash", line_color="green", 
                  annotation_text="Excellent", annotation_position="right")
    fig.add_hline(y=50, line_dash="dash", line_color="orange",
                  annotation_text="Good", annotation_position="right")
    fig.add_hline(y=30, line_dash="dash", line_color="red",
                  annotation_text="Fair", annotation_position="right")
    
    fig.update_layout(
        yaxis_title="Sap Flow Likelihood (%)",
        xaxis_title="Date",
        yaxis=dict(range=[0, 110]),
        height=400,
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # ============================================================================
    # TEMPERATURE CHART
    # ============================================================================
    
    st.subheader("🌡️ Temperature Forecast")
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=forecast_df['date'],
        y=forecast_df['high_temp'],
        mode='lines+markers',
        name='High',
        line=dict(color='#dc3545', width=2),
        marker=dict(size=8)
    ))
    
    fig.add_trace(go.Scatter(
        x=forecast_df['date'],
        y=forecast_df['low_temp'],
        mode='lines+markers',
        name='Low',
        line=dict(color='#007bff', width=2),
        marker=dict(size=8)
    ))
    
    # Add freezing line
    fig.add_hline(y=32, line_dash="dash", line_color="gray",
                  annotation_text="Freezing (32°F)", annotation_position="left")
    
    fig.update_layout(
        yaxis_title="Temperature (°F)",
        xaxis_title="Date",
        height=350,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # ============================================================================
    # DETAILED FORECAST TABLE
    # ============================================================================
    
    st.subheader("📅 Detailed 10-Day Forecast")
    
    display = forecast_df.copy()
    
    # Format date
    display['Date'] = display['date'].dt.strftime('%a, %b %d')
    
    # Format temperatures
    display['High'] = display['high_temp'].apply(lambda x: f"{x:.0f}°F")
    display['Low'] = display['low_temp'].apply(lambda x: f"{x:.0f}°F")
    display['Swing'] = display['temp_swing'].apply(lambda x: f"{x:.0f}°F")
    
    # Format precipitation
    display['Precip'] = display['precipitation'].apply(lambda x: f"{x:.2f}\"" if x > 0 else "-")
    
    # Format wind
    display['Wind'] = display['wind_speed'].apply(lambda x: f"{x:.0f} mph")
    
    # Freeze/thaw indicator
    display['F/T'] = display['freeze_thaw'].apply(lambda x: "✓" if x else "-")
    
    # Sap flow status
    def get_status(likelihood):
        if likelihood >= 70:
            return "🟢 Excellent"
        elif likelihood >= 50:
            return "🟡 Good"
        elif likelihood >= 30:
            return "🟠 Fair"
        else:
            return "🔴 Poor"
    
    display['Status'] = display['sap_likelihood'].apply(get_status)
    display['Likelihood'] = display['sap_likelihood'].apply(lambda x: f"{x:.0f}%")
    
    # Select columns for display
    display_cols = ['Date', 'High', 'Low', 'Swing', 'F/T', 'Precip', 'Wind', 'Likelihood', 'Status']
    
    display_table = display[display_cols].copy()
    
    st.dataframe(display_table, use_container_width=True, hide_index=True, height=400)
    
    st.divider()
    
    # ============================================================================
    # RECOMMENDATIONS
    # ============================================================================
    
    st.subheader("✅ Planning Recommendations")
    
    # Find best days
    best_days = forecast_df.nlargest(3, 'sap_likelihood')
    
    if not best_days.empty:
        st.success(f"🌟 **Best days coming up:**")
        for idx, day in best_days.iterrows():
            date_str = day['date'].strftime('%A, %B %d')
            st.write(f"• **{date_str}**: {day['sap_likelihood']:.0f}% likelihood "
                    f"(High: {day['high_temp']:.0f}°F, Low: {day['low_temp']:.0f}°F)")
    
    # Warnings
    poor_days = forecast_df[forecast_df['sap_likelihood'] < 30]
    if not poor_days.empty:
        st.warning(f"⚠️ **Poor flow days:**")
        for idx, day in poor_days.iterrows():
            date_str = day['date'].strftime('%A, %B %d')
            reasons = []
            if day['high_temp'] < 32:
                reasons.append("too cold")
            if day['low_temp'] >= 32:
                reasons.append("no freeze")
            if day['precipitation'] > 0.5:
                reasons.append("heavy rain")
            reason_str = ", ".join(reasons) if reasons else "marginal conditions"
            st.write(f"• **{date_str}**: {day['sap_likelihood']:.0f}% likelihood ({reason_str})")
    
    # Multi-site operational notes
    if has_site and not viewing_site:
        st.info("""
        **Multi-Site Operations:**
        - Schedule both NY and VT crews similarly based on forecast
        - Expect comparable sap flow at both locations
        - Monitor actual production to catch local variations
        - Share daily observations between sites
        """)
    
    st.divider()
    
    # Tips
    with st.expander("💡 Understanding Sap Flow Predictions"):
        st.markdown("""
        **How Sap Flow Works:**
        
        Sap flows when:
        1. **Freeze/Thaw Cycle**: Nights below 32°F, days above 32°F
        2. **Temperature Swing**: Difference of 15-25°F is optimal
        3. **Moderate Temps**: Lows near 25°F, highs near 40-45°F
        
        **Likelihood Scale:**
        
        - **70-100%** (🟢): Excellent conditions - maximum collection expected
        - **50-70%** (🟡): Good conditions - solid flow expected
        - **30-50%** (🟠): Fair conditions - some flow possible
        - **0-30%** (🔴): Poor conditions - minimal/no flow expected
        
        **What Hurts Sap Flow:**
        
        - Heavy precipitation (dilutes sap)
        - High winds (drying effect)
        - Temperatures too warm (>50°F highs)
        - No freeze/thaw cycle (all above or below 32°F)
        
        **Multi-Site Considerations:**
        
        **Weather Similarity:**
        - NY and VT sites experience similar regional weather
        - Forecast applies to both locations
        - Both sites should see comparable sap flow
        
        **Local Variations:**
        - Microclimates may cause small differences
        - Elevation differences affect temperature
        - Tree exposure (sun/shade) varies
        - Monitor actual production at each site
        
        **Using This Forecast:**
        
        - **Daily Planning**: Check tonight's low and tomorrow's high
        - **Weekly Planning**: Schedule crew based on best days
        - **Capacity Planning**: Ensure collection capacity for excellent days
        - **Maintenance Scheduling**: Use poor days for repairs
        - **Multi-Site Coordination**: Plan crew schedules at both sites together
        
        **Best Practices:**
        
        - Check forecast daily
        - Prepare for excellent days (maximize collection)
        - Use poor days for maintenance and repairs
        - Track actual vs. predicted flow to improve planning
        - Share observations between NY and VT teams
        - Adjust based on local site differences over time
        
        **Data Source:**
        
        Weather data from Open-Meteo.com - updated daily
        Coordinates can be customized for precise local forecasts
        """)
