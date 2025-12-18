"""
Sap Flow Forecast Page Module
Predicts sap flow likelihood for the next 10 days based on weather forecasts
"""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px


def get_weather_forecast(latitude, longitude, days=10):
    """
    Get weather forecast from Open-Meteo API (free, no API key needed)

    Args:
        latitude: Location latitude
        longitude: Location longitude
        days: Number of forecast days (max 16)

    Returns:
        DataFrame with daily forecasts
    """
    try:
        # Open-Meteo API endpoint
        url = "https://api.open-meteo.com/v1/forecast"

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_probability_max"
            ],
            "temperature_unit": "fahrenheit",
            "timezone": "America/New_York",
            "forecast_days": days
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Parse the daily data
        daily = data['daily']

        df = pd.DataFrame({
            'Date': pd.to_datetime(daily['time']),
            'Max_Temp': daily['temperature_2m_max'],
            'Min_Temp': daily['temperature_2m_min'],
            'Precipitation': daily['precipitation_sum'],
            'Precip_Probability': daily['precipitation_probability_max']
        })

        return df

    except Exception as e:
        st.error(f"Error fetching weather forecast: {str(e)}")
        return None


def calculate_sap_flow_likelihood(weather_df):
    """
    Calculate likelihood of sap flow based on temperature patterns

    Ideal conditions:
    - Night temps below 32°F (freezing)
    - Day temps above 32°F (thawing)
    - Temperature swing of 15-25°F
    - Not too much precipitation

    Returns:
        DataFrame with sap flow predictions
    """
    df = weather_df.copy()

    # Calculate temperature swing
    df['Temp_Swing'] = df['Max_Temp'] - df['Min_Temp']

    # Check ideal conditions
    df['Freeze_at_Night'] = df['Min_Temp'] < 32.0
    df['Thaw_During_Day'] = df['Max_Temp'] > 32.0
    df['Good_Swing'] = df['Temp_Swing'].between(15, 25)
    df['Low_Precip'] = df['Precipitation'] < 0.5

    # Calculate likelihood score (0-100)
    df['Likelihood'] = 0.0

    # Base score from freeze/thaw cycle
    df.loc[df['Freeze_at_Night'] & df['Thaw_During_Day'], 'Likelihood'] += 40

    # Bonus for good temperature swing
    df.loc[df['Good_Swing'], 'Likelihood'] += 30

    # Additional points for optimal temps
    # Ideal: Min around 25°F, Max around 45°F
    df['Min_Temp_Score'] = 100 - abs(df['Min_Temp'] - 25) * 2
    df['Min_Temp_Score'] = df['Min_Temp_Score'].clip(0, 20)

    df['Max_Temp_Score'] = 100 - abs(df['Max_Temp'] - 45) * 2
    df['Max_Temp_Score'] = df['Max_Temp_Score'].clip(0, 20)

    df['Likelihood'] += (df['Min_Temp_Score'] + df['Max_Temp_Score']) / 2

    # Penalty for precipitation
    df.loc[~df['Low_Precip'], 'Likelihood'] -= 10

    # Ensure likelihood is 0-100
    df['Likelihood'] = df['Likelihood'].clip(0, 100)

    # Categorize
    def get_category(likelihood):
        if likelihood >= 70:
            return "Excellent"
        elif likelihood >= 50:
            return "Good"
        elif likelihood >= 30:
            return "Fair"
        else:
            return "Poor"

    df['Category'] = df['Likelihood'].apply(get_category)

    return df


def render(vacuum_df, personnel_df):
    """Render sap flow forecast page"""

    st.title("🌡️ Sap Flow Forecast")
    st.markdown("*10-day forecast based on temperature patterns*")

    # Location input
    st.subheader("📍 Location Settings")

    col1, col2 = st.columns(2)

    with col1:
        # Default to Ellenburg, NY area
        latitude = st.number_input(
            "Latitude",
            value=44.8997,
            min_value=40.0,
            max_value=45.0,
            step=0.0001,
            format="%.4f",
            help="Your operation's latitude"
        )

    with col2:
        longitude = st.number_input(
            "Longitude",
            value=-73.8331,
            min_value=-80.0,
            max_value=-72.0,
            step=0.0001,
            format="%.4f",
            help="Your operation's longitude"
        )

    st.caption("💡 Using Ellenburg, NY as default location. Update coordinates for your specific location.")

    st.divider()

    # Fetch weather data
    with st.spinner("Fetching weather forecast..."):
        weather_df = get_weather_forecast(latitude, longitude, days=10)

    if weather_df is None or weather_df.empty:
        st.error("Unable to load weather forecast. Please try again.")
        return

    # Calculate sap flow likelihood
    forecast_df = calculate_sap_flow_likelihood(weather_df)

    # Display forecast summary
    st.subheader("📊 Forecast Summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        excellent_days = len(forecast_df[forecast_df['Category'] == 'Excellent'])
        st.metric("Excellent Days", excellent_days,
                  help="Days with 70%+ likelihood of good sap flow")

    with col2:
        good_days = len(forecast_df[forecast_df['Category'] == 'Good'])
        st.metric("Good Days", good_days,
                  help="Days with 50-70% likelihood")

    with col3:
        avg_likelihood = forecast_df['Likelihood'].mean()
        st.metric("Avg Likelihood", f"{avg_likelihood:.0f}%",
                  help="Average across all forecast days")

    with col4:
        best_day = forecast_df.loc[forecast_df['Likelihood'].idxmax(), 'Date']
        st.metric("Best Day", best_day.strftime('%a, %b %d'),
                  help="Day with highest sap flow likelihood")

    st.divider()

    # Likelihood chart
    st.subheader("📈 10-Day Sap Flow Likelihood")

    # Create color scale
    colors = []
    for likelihood in forecast_df['Likelihood']:
        if likelihood >= 70:
            colors.append('#28a745')  # Green
        elif likelihood >= 50:
            colors.append('#5cb85c')  # Light green
        elif likelihood >= 30:
            colors.append('#ffc107')  # Yellow
        else:
            colors.append('#dc3545')  # Red

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=forecast_df['Date'],
        y=forecast_df['Likelihood'],
        marker_color=colors,
        text=forecast_df['Likelihood'].apply(lambda x: f"{x:.0f}%"),
        textposition='outside',
        hovertemplate='<b>%{x|%A, %B %d}</b><br>Likelihood: %{y:.0f}%<extra></extra>'
    ))

    fig.update_layout(
        yaxis_title="Sap Flow Likelihood (%)",
        yaxis_range=[0, 110],
        xaxis_title="Date",
        height=400,
        showlegend=False
    )

    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Temperature forecast
    st.subheader("🌡️ Temperature Forecast")

    fig2 = go.Figure()

    # Add temperature range (fill between min and max)
    fig2.add_trace(go.Scatter(
        x=forecast_df['Date'],
        y=forecast_df['Max_Temp'],
        mode='lines',
        name='High',
        line=dict(color='#dc3545', width=2),
        hovertemplate='High: %{y:.0f}°F<extra></extra>'
    ))

    fig2.add_trace(go.Scatter(
        x=forecast_df['Date'],
        y=forecast_df['Min_Temp'],
        mode='lines',
        name='Low',
        line=dict(color='#007bff', width=2),
        fill='tonexty',
        fillcolor='rgba(0,123,255,0.1)',
        hovertemplate='Low: %{y:.0f}°F<extra></extra>'
    ))

    # Add freezing line
    fig2.add_hline(
        y=32,
        line_dash="dash",
        line_color="gray",
        annotation_text="Freezing (32°F)",
        annotation_position="right"
    )

    fig2.update_layout(
        yaxis_title="Temperature (°F)",
        xaxis_title="Date",
        height=350,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # Detailed forecast table
    st.subheader("📋 Detailed Forecast")

    # Format the display
    display_df = forecast_df.copy()
    display_df['Date'] = display_df['Date'].dt.strftime('%a, %b %d')
    display_df['High'] = display_df['Max_Temp'].apply(lambda x: f"{x:.0f}°F")
    display_df['Low'] = display_df['Min_Temp'].apply(lambda x: f"{x:.0f}°F")
    display_df['Swing'] = display_df['Temp_Swing'].apply(lambda x: f"{x:.0f}°F")
    display_df['Likelihood %'] = display_df['Likelihood'].apply(lambda x: f"{x:.0f}%")
    display_df['Precip'] = display_df['Precipitation'].apply(lambda x: f"{x:.2f}\"")

    # Status emojis
    def get_emoji(category):
        if category == 'Excellent':
            return '🟢 Excellent'
        elif category == 'Good':
            return '🟡 Good'
        elif category == 'Fair':
            return '🟠 Fair'
        else:
            return '🔴 Poor'

    display_df['Status'] = display_df['Category'].apply(get_emoji)

    # Select columns for display
    display_cols = ['Date', 'Status', 'Likelihood %', 'High', 'Low', 'Swing', 'Precip']

    st.dataframe(
        display_df[display_cols],
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # Educational information
    st.subheader("📚 Understanding Sap Flow")

    with st.expander("🔍 What Makes Good Sap Flow?"):
        st.markdown("""
        **Ideal Conditions for Maple Sap Flow:**

        1. **Freeze-Thaw Cycle** ⭐ Most Important
           - Nighttime temperatures below 32°F (freezing)
           - Daytime temperatures above 32°F (thawing)
           - This creates pressure changes that drive sap flow

        2. **Temperature Swing**
           - Ideal: 15-25°F difference between day and night
           - Larger swings generally produce better flow
           - Best when low is ~25°F and high is ~40-45°F

        3. **Weather Conditions**
           - Clear to partly cloudy skies are best
           - Light wind is okay
           - Heavy rain or snow can reduce flow

        4. **Time of Season**
           - Early to mid-season typically best
           - Late season: warmer days may cause budding

        **This forecast considers:**
        - ✓ Freeze/thaw cycles (40% of score)
        - ✓ Temperature swing (30% of score)  
        - ✓ Optimal temperature ranges (20% of score)
        - ✓ Precipitation levels (10% of score)
        """)

    with st.expander("💡 How to Use This Forecast"):
        st.markdown("""
        **Planning Your Operations:**

        - **🟢 Excellent Days (70-100%)**: Prime sap flow expected
          - Plan for maximum collection capacity
          - Schedule extra staff if possible
          - Check vacuum systems before these days

        - **🟡 Good Days (50-70%)**: Decent flow likely
          - Normal operations expected
          - Monitor systems regularly

        - **🟠 Fair Days (30-50%)**: Marginal conditions
          - Some flow possible but not optimal
          - Good time for maintenance work

        - **🔴 Poor Days (0-30%)**: Minimal flow expected
          - Focus on maintenance and prep work
          - Check equipment and make repairs
          - Plan for better days ahead

        **Tips:**
        - Check forecast daily for updates
        - Local conditions may vary slightly
        - Update location coordinates for accuracy
        - Combine with your vacuum monitoring data
        """)

    st.info("🌐 Weather data provided by Open-Meteo.com (free weather API)")