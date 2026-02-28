"""
Weather API Utilities
Shared Open-Meteo API helpers used across the dashboard.
All functions use config.SITE_COORDINATES for coordinates.
"""

import pandas as pd
import requests
import streamlit as st

import config


@st.cache_data(ttl=3600, show_spinner=False)
def get_temperature_data(days=7, site='NY'):
    """
    Get historical daily High/Low temperature from Open-Meteo for a given site.

    Returns DataFrame with columns: Date, High, Low, Above_Freezing
    Returns None on error.
    """
    try:
        coords = config.SITE_COORDINATES.get(site, config.SITE_COORDINATES['NY'])
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": coords['lat'],
            "longitude": coords['lon'],
            "daily": ["temperature_2m_max", "temperature_2m_min"],
            "temperature_unit": "fahrenheit",
            "timezone": "America/New_York",
            "past_days": days,
            "forecast_days": 0,
        }
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()['daily']
        temp_df = pd.DataFrame({
            'Date': pd.to_datetime(data['time']),
            'High': data['temperature_2m_max'],
            'Low': data['temperature_2m_min'],
        })
        temp_df['Above_Freezing'] = (temp_df['High'] > 32) | (temp_df['Low'] > 32)
        return temp_df
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False)
def get_hourly_temperature(days=2, site='NY'):
    """
    Get hourly temperature data from Open-Meteo for a given site.

    Returns DataFrame with columns: time (datetime), temp (°F)
    Returns None on error.
    """
    try:
        coords = config.SITE_COORDINATES.get(site, config.SITE_COORDINATES['NY'])
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": coords['lat'],
            "longitude": coords['lon'],
            "hourly": "temperature_2m",
            "temperature_unit": "fahrenheit",
            "timezone": "America/New_York",
            "past_days": days,
            "forecast_days": 0,
        }
        resp = requests.get(url, params=params, timeout=3)
        resp.raise_for_status()
        td = resp.json()['hourly']
        return pd.DataFrame({
            'time': pd.to_datetime(td['time']),
            'temp': td['temperature_2m'],
        })
    except Exception:
        return None
