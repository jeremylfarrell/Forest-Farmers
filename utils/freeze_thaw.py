"""
Freeze/Thaw Detection Module
Shared logic for identifying freeze/thaw transition periods and
detecting sensors with vacuum drops during freeze events.

During freeze/thaw transitions (~32°F), open or leaking lines freeze
faster than sealed ones — vacuum drops during these events reveal
problem lines that need attention.
"""

import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

import config


@st.cache_data(ttl=900, show_spinner=False)
def get_current_freeze_thaw_status(latitude=None, longitude=None):
    """
    Fetch current weather and determine freeze/thaw status.

    Returns dict with:
        is_freeze_thaw, current_temp, today_high, today_low,
        tomorrow_high, tomorrow_low, tomorrow_freeze_thaw,
        sap_flow_score, status_label, status_description
    """
    default = {
        'is_freeze_thaw': False,
        'current_temp': None,
        'today_high': None,
        'today_low': None,
        'tomorrow_high': None,
        'tomorrow_low': None,
        'tomorrow_freeze_thaw': False,
        'sap_flow_score': 0,
        'status_label': 'UNKNOWN',
        'status_description': 'Weather data unavailable',
    }

    try:
        if latitude is None or longitude is None:
            _coords = config.SITE_COORDINATES['NY']
            latitude = _coords['lat']
            longitude = _coords['lon']

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": ["temperature_2m_max", "temperature_2m_min"],
            "hourly": ["temperature_2m"],
            "temperature_unit": "fahrenheit",
            "timezone": "America/New_York",
            "past_days": 0,
            "forecast_days": 2,
        }
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        daily = data.get('daily', {})
        hourly = data.get('hourly', {})

        # Today and tomorrow temps
        today_high = daily['temperature_2m_max'][0] if daily.get('temperature_2m_max') else None
        today_low = daily['temperature_2m_min'][0] if daily.get('temperature_2m_min') else None
        tomorrow_high = daily['temperature_2m_max'][1] if len(daily.get('temperature_2m_max', [])) > 1 else None
        tomorrow_low = daily['temperature_2m_min'][1] if len(daily.get('temperature_2m_min', [])) > 1 else None

        # Current temp: most recent hourly reading
        current_temp = None
        if hourly.get('temperature_2m'):
            now_hour = datetime.now().hour
            # hourly data has 48 entries (2 days), grab closest to current hour
            if now_hour < len(hourly['temperature_2m']):
                current_temp = hourly['temperature_2m'][now_hour]

        if today_high is None or today_low is None:
            return default

        freezing = config.FREEZING_POINT

        # Determine freeze/thaw status
        is_freeze_thaw = (today_low < freezing and today_high > freezing)
        tomorrow_ft = (tomorrow_low is not None and tomorrow_high is not None and
                       tomorrow_low < freezing and tomorrow_high > freezing)

        # Calculate sap flow score
        from utils.helpers import calculate_sap_flow_likelihood
        sap_score = int(calculate_sap_flow_likelihood(
            today_high, today_low, 0, 0  # no precip/wind for quick check
        ))

        # Status label
        if is_freeze_thaw:
            status_label = 'CRITICAL'
            status_description = (
                f"FREEZE/THAW TRANSITION — Low {today_low:.0f}°F / High {today_high:.0f}°F. "
                "Vacuum drops during freeze events reveal open/leaking lines."
            )
        elif tomorrow_ft:
            status_label = 'UPCOMING'
            status_description = (
                f"Freeze/thaw expected tomorrow (Low {tomorrow_low:.0f}°F / High {tomorrow_high:.0f}°F). "
                "Today is stable — prepare for critical monitoring tomorrow."
            )
        else:
            status_label = 'LOW PRIORITY'
            status_description = (
                f"No freeze/thaw cycle today or tomorrow. "
                f"Today: Low {today_low:.0f}°F / High {today_high:.0f}°F. "
                "Vacuum data is low priority — check Sap Flow Forecast for upcoming transitions."
            )

        return {
            'is_freeze_thaw': is_freeze_thaw,
            'current_temp': current_temp,
            'today_high': today_high,
            'today_low': today_low,
            'tomorrow_high': tomorrow_high,
            'tomorrow_low': tomorrow_low,
            'tomorrow_freeze_thaw': tomorrow_ft,
            'sap_flow_score': sap_score,
            'status_label': status_label,
            'status_description': status_description,
        }

    except Exception:
        return default


def detect_freeze_event_drops(vacuum_df, temp_data, threshold_drop=None):
    """
    Identify sensors whose vacuum dropped during freeze/thaw events.

    Args:
        vacuum_df: Vacuum DataFrame with Name, Vacuum, Last communication columns
        temp_data: Daily temperature DataFrame with Date, High, Low columns
                   (from vacuum.get_temperature_data())
        threshold_drop: Minimum vacuum drop (inches) to flag. Defaults to config value.

    Returns:
        DataFrame with columns: Sensor, Avg_Drop, Freeze_Days_With_Drop,
        Total_Freeze_Days, Drop_Rate, Latest_Vacuum, Freeze_Status
        Returns empty DataFrame if insufficient data.
    """
    if threshold_drop is None:
        threshold_drop = config.FREEZE_DROP_THRESHOLD

    empty_result = pd.DataFrame(columns=[
        'Sensor', 'Avg_Drop', 'Freeze_Days_With_Drop',
        'Total_Freeze_Days', 'Drop_Rate', 'Latest_Vacuum', 'Freeze_Status'
    ])

    if vacuum_df is None or vacuum_df.empty or temp_data is None or temp_data.empty:
        return empty_result

    # Find required columns
    from utils import find_column, get_vacuum_column

    sensor_col = find_column(vacuum_df, 'Name', 'name', 'Sensor Name', 'sensor')
    vacuum_col = get_vacuum_column(vacuum_df)
    timestamp_col = find_column(
        vacuum_df, 'Last communication', 'Last Communication',
        'Timestamp', 'timestamp'
    )

    if not all([sensor_col, vacuum_col, timestamp_col]):
        return empty_result

    # Prepare vacuum data
    vdf = vacuum_df[[sensor_col, vacuum_col, timestamp_col]].copy()
    vdf.columns = ['Sensor', 'Vacuum', 'Timestamp']
    vdf['Vacuum'] = pd.to_numeric(vdf['Vacuum'], errors='coerce')
    vdf['Timestamp'] = pd.to_datetime(vdf['Timestamp'], errors='coerce')
    vdf = vdf.dropna(subset=['Vacuum', 'Timestamp'])
    vdf['Date'] = vdf['Timestamp'].dt.date

    # Identify freeze/thaw days
    freezing = config.FREEZING_POINT
    tdf = temp_data.copy()
    if 'Date' in tdf.columns and not pd.api.types.is_datetime64_any_dtype(tdf['Date']):
        tdf['Date'] = pd.to_datetime(tdf['Date'], errors='coerce')
    if 'Date' in tdf.columns:
        tdf['DateKey'] = tdf['Date'].apply(
            lambda x: x.date() if hasattr(x, 'date') else x
        )
    else:
        return empty_result

    freeze_thaw_days = set()
    for _, row in tdf.iterrows():
        high = row.get('High')
        low = row.get('Low')
        if high is not None and low is not None:
            if low < freezing and high > freezing:
                freeze_thaw_days.add(row['DateKey'])

    if len(freeze_thaw_days) < 1:
        return empty_result

    # Calculate daily average vacuum per sensor
    daily_avg = vdf.groupby(['Sensor', 'Date'])['Vacuum'].mean().reset_index()
    daily_avg = daily_avg.sort_values(['Sensor', 'Date'])

    # For each sensor, compare vacuum on freeze/thaw days vs prior day
    results = []
    for sensor in daily_avg['Sensor'].unique():
        sensor_data = daily_avg[daily_avg['Sensor'] == sensor].sort_values('Date')
        if len(sensor_data) < 2:
            continue

        drops = []
        freeze_days_checked = 0

        for _, row in sensor_data.iterrows():
            if row['Date'] in freeze_thaw_days:
                freeze_days_checked += 1
                # Find prior day's reading
                prior_date = row['Date'] - timedelta(days=1)
                prior = sensor_data[sensor_data['Date'] == prior_date]
                if not prior.empty:
                    drop = prior.iloc[0]['Vacuum'] - row['Vacuum']
                    if drop >= threshold_drop:
                        drops.append(drop)

        if freeze_days_checked == 0:
            continue

        latest_vac = sensor_data.iloc[-1]['Vacuum']
        drop_rate = len(drops) / freeze_days_checked if freeze_days_checked > 0 else 0
        avg_drop = sum(drops) / len(drops) if drops else 0

        # Classify
        if drop_rate >= config.FREEZE_DROP_RATE_LIKELY:
            status = 'LIKELY LEAK'
        elif drop_rate >= config.FREEZE_DROP_RATE_WATCH:
            status = 'WATCH'
        else:
            status = 'OK'

        results.append({
            'Sensor': sensor,
            'Avg_Drop': round(avg_drop, 1),
            'Freeze_Days_With_Drop': len(drops),
            'Total_Freeze_Days': freeze_days_checked,
            'Drop_Rate': round(drop_rate, 2),
            'Latest_Vacuum': round(latest_vac, 1),
            'Freeze_Status': status,
        })

    if not results:
        return empty_result

    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values('Drop_Rate', ascending=False)
    return result_df


def add_freeze_bands_to_figure(fig, temp_data, annotate=False):
    """
    Add vertical shaded bands to a Plotly figure for each freeze/thaw day.

    A freeze/thaw day is one where Low < 32°F and High > 32°F.

    Args:
        fig: plotly.graph_objects.Figure to modify in-place
        temp_data: DataFrame with columns Date, High, Low (from get_temperature_data())
        annotate: If True, add a small "F/T" label on each band
    """
    if temp_data is None or 'Low' not in temp_data.columns:
        return

    import pandas as pd

    freezing = config.FREEZING_POINT
    for _, row in temp_data.iterrows():
        t_high = row.get('High')
        t_low = row.get('Low')
        if t_high is None or t_low is None:
            continue
        if t_low < freezing and t_high > freezing:
            d = row['Date']
            if hasattr(d, 'date'):
                d = d.date()
            kwargs = dict(
                x0=pd.Timestamp(d) - pd.Timedelta(hours=12),
                x1=pd.Timestamp(d) + pd.Timedelta(hours=12),
                fillcolor="rgba(100, 149, 237, 0.15)",
                line_width=0,
            )
            if annotate:
                kwargs.update(
                    annotation_text="F/T",
                    annotation_position="top left",
                    annotation_font_size=9,
                    annotation_font_color="cornflowerblue",
                )
            fig.add_vrect(**kwargs)


def render_freeze_thaw_banner(freeze_status):
    """
    Render a Streamlit banner showing current freeze/thaw status.

    Args:
        freeze_status: Dict from get_current_freeze_thaw_status()
    """
    label = freeze_status.get('status_label', 'UNKNOWN')
    desc = freeze_status.get('status_description', '')
    current = freeze_status.get('current_temp')
    score = freeze_status.get('sap_flow_score', 0)

    temp_str = f"Current: {current:.0f}°F | " if current is not None else ""
    score_str = f"Sap Flow Score: {score}%" if score > 0 else ""
    detail = f"{temp_str}{score_str}" if (temp_str or score_str) else ""

    if label == 'CRITICAL':
        st.error(f"**FREEZE/THAW — CRITICAL MONITORING PERIOD** {detail}\n\n{desc}")
    elif label == 'UPCOMING':
        st.warning(f"**FREEZE/THAW UPCOMING** {detail}\n\n{desc}")
    elif label == 'LOW PRIORITY':
        st.info(f"**LOW PRIORITY** {detail}\n\n{desc}")
    else:
        st.caption("Weather data unavailable — freeze/thaw status unknown")
