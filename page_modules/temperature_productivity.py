"""
Temperature & Tapping Productivity Page Module
Analyses how outdoor temperature affects tapping productivity by joining
daily weather data (Open-Meteo archive API) with TSheets tapping records.
Shows taps installed, hours worked, and taps/hour across temperature ranges.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
from datetime import datetime, timedelta

from utils import find_column
import config


# ---------------------------------------------------------------------------
# TEMPERATURE DATA
# ---------------------------------------------------------------------------

@st.cache_data(ttl=86400, show_spinner=False)
def get_historical_temperature(lat, lon, start_date, end_date):
    """
    Fetch daily high/low temperature from the Open-Meteo **archive** API.
    Cached for 24 hours because historical data does not change.

    Returns DataFrame with columns: Date, High, Low, Avg_Temp
    """
    try:
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "daily": ["temperature_2m_max", "temperature_2m_min"],
            "temperature_unit": "fahrenheit",
            "timezone": "America/New_York",
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()["daily"]

        temp_df = pd.DataFrame({
            "Date": pd.to_datetime(data["time"]),
            "High": data["temperature_2m_max"],
            "Low": data["temperature_2m_min"],
        })
        temp_df["Avg_Temp"] = ((temp_df["High"] + temp_df["Low"]) / 2).round(1)
        return temp_df
    except Exception as e:
        st.warning(f"Could not fetch temperature data: {e}")
        return None


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _is_tapping_job_code(job_text):
    """Return True if the job code is a tapping-type code."""
    if pd.isna(job_text):
        return False
    j = str(job_text).lower()
    return any(kw in j for kw in [
        'new spout install', 'dropline install', 'spout already on',
        'maple tapping',
    ])


def _assign_temp_bucket(avg_temp):
    """Assign a temperature bucket label based on config.TEMP_RANGES."""
    for label, lo, hi in config.TEMP_RANGES:
        if lo is None and hi is not None and avg_temp < hi:
            return label
        if lo is not None and hi is not None and lo <= avg_temp < hi:
            return label
        if lo is not None and hi is None and avg_temp >= lo:
            return label
    return "Unknown"


_BUCKET_COLORS = {
    config.TEMP_RANGES[0][0]: "#1f77b4",   # cold  — blue
    config.TEMP_RANGES[1][0]: "#ff7f0e",   # mild  — orange
    config.TEMP_RANGES[2][0]: "#2ca02c",   # warm  — green
}


# ---------------------------------------------------------------------------
# RENDER
# ---------------------------------------------------------------------------

def render(personnel_df, vacuum_df=None):
    """Render the Temperature & Tapping Productivity page."""

    st.title("🌡️ Tapping Productivity by Temperature")
    st.markdown(
        "*How does outdoor temperature affect tapping speed?  "
        "Each work day is matched to the daily average temperature, "
        "then grouped into ranges so you can compare taps installed, "
        "hours worked, and taps/hour across cold, mild, and warm days.*"
    )

    if personnel_df is None or personnel_df.empty:
        st.info("No personnel data loaded.")
        return

    # ------------------------------------------------------------------
    # 1. PREPARE TAPPING DATA
    # ------------------------------------------------------------------
    df = personnel_df.copy()

    date_col = find_column(df, 'Date', 'date')
    emp_col = find_column(df, 'Employee Name', 'employee')
    hours_col = find_column(df, 'Hours', 'hours')
    taps_in_col = find_column(df, 'Taps Put In', 'taps_in')
    job_col = find_column(df, 'Job', 'job', 'Job Code')
    mainline_col = find_column(df, 'mainline.', 'mainline', 'Mainline')

    if not all([date_col, emp_col, hours_col, taps_in_col, job_col]):
        st.error("Missing required columns in personnel data.")
        return

    df['Date'] = pd.to_datetime(df[date_col], errors='coerce')
    df = df.dropna(subset=['Date'])
    df['Employee'] = df[emp_col]
    df['Hours'] = pd.to_numeric(df[hours_col], errors='coerce').fillna(0)
    df['Taps_In'] = pd.to_numeric(df[taps_in_col], errors='coerce').fillna(0)
    df['Job_Code'] = df[job_col]
    if mainline_col:
        df['Mainline'] = df[mainline_col]

    # Filter to tapping job codes only
    df = df[df['Job_Code'].apply(_is_tapping_job_code)].copy()

    if df.empty:
        st.warning("No tapping job records found in the personnel data.")
        return

    # ------------------------------------------------------------------
    # 2. FETCH TEMPERATURE
    # ------------------------------------------------------------------
    start_date = df['Date'].min().strftime('%Y-%m-%d')
    end_date = df['Date'].max().strftime('%Y-%m-%d')

    # Determine site(s) being viewed
    has_site = 'Site' in df.columns
    sites = sorted(df['Site'].unique()) if has_site else ['VT']

    with st.spinner("Fetching historical temperature data..."):
        temp_frames = []
        for site in sites:
            coords = config.SITE_COORDINATES.get(site, config.SITE_COORDINATES.get('VT'))
            site_temp = get_historical_temperature(
                coords['lat'], coords['lon'], start_date, end_date
            )
            if site_temp is not None:
                site_temp = site_temp.copy()
                site_temp['Site'] = site
                temp_frames.append(site_temp)

    if not temp_frames:
        st.error("Could not fetch temperature data from Open-Meteo.")
        return

    temp_df = pd.concat(temp_frames, ignore_index=True)

    # ------------------------------------------------------------------
    # 3. JOIN TAPPING ← TEMPERATURE
    # ------------------------------------------------------------------
    df['_join_date'] = df['Date'].dt.normalize()
    temp_df['_join_date'] = temp_df['Date'].dt.normalize()

    if has_site and len(sites) > 1:
        merged = df.merge(
            temp_df[['_join_date', 'Site', 'High', 'Low', 'Avg_Temp']],
            on=['_join_date', 'Site'],
            how='left',
        )
    else:
        merged = df.merge(
            temp_df[['_join_date', 'High', 'Low', 'Avg_Temp']].drop_duplicates(subset='_join_date'),
            on='_join_date',
            how='left',
        )

    merged = merged.dropna(subset=['Avg_Temp'])
    merged['Temp_Range'] = merged['Avg_Temp'].apply(_assign_temp_bucket)

    if merged.empty:
        st.warning("No tapping records could be matched to temperature data.")
        return

    # Ordered bucket labels for consistent chart ordering
    bucket_order = [r[0] for r in config.TEMP_RANGES]

    # ------------------------------------------------------------------
    # 4. SUMMARY METRICS
    # ------------------------------------------------------------------
    st.subheader("📊 Summary by Temperature Range")

    total_taps_all = merged['Taps_In'].sum()

    cols = st.columns(len(config.TEMP_RANGES))
    for i, (label, _, _) in enumerate(config.TEMP_RANGES):
        bucket = merged[merged['Temp_Range'] == label]
        taps = bucket['Taps_In'].sum()
        hours = bucket['Hours'].sum()
        tph = taps / hours if hours > 0 else 0
        pct = taps / total_taps_all * 100 if total_taps_all > 0 else 0
        days = bucket['_join_date'].nunique()

        with cols[i]:
            st.markdown(f"**{label}**")
            st.metric("Taps Installed", f"{int(taps):,}")
            st.metric("Tapping Hours", f"{hours:,.1f}")
            st.metric("Taps/Hour", f"{tph:.1f}")
            st.metric("% of Total Taps", f"{pct:.1f}%")
            st.metric("Work Days", f"{days}")

    st.divider()

    # ------------------------------------------------------------------
    # 5. BAR CHART: TAPS BY TEMPERATURE RANGE
    # ------------------------------------------------------------------
    st.subheader("📊 Taps Installed by Temperature Range")

    range_agg = merged.groupby('Temp_Range').agg(
        Taps=('Taps_In', 'sum'),
        Hours=('Hours', 'sum'),
    ).reindex(bucket_order).reset_index()
    range_agg['Taps_Per_Hour'] = (range_agg['Taps'] / range_agg['Hours']).round(1)
    range_agg['Taps_Per_Hour'] = range_agg['Taps_Per_Hour'].fillna(0)

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        fig_taps = go.Figure(go.Bar(
            x=range_agg['Temp_Range'],
            y=range_agg['Taps'],
            marker_color=[_BUCKET_COLORS.get(r, '#999') for r in range_agg['Temp_Range']],
            text=range_agg['Taps'].apply(lambda x: f"{int(x):,}"),
            textposition='outside',
        ))
        fig_taps.update_layout(
            title="Total Taps by Temp Range",
            yaxis_title="Taps Put In",
            height=400,
            showlegend=False,
        )
        st.plotly_chart(fig_taps, use_container_width=True)

    # ------------------------------------------------------------------
    # 6. BAR CHART: PRODUCTIVITY BY TEMPERATURE RANGE
    # ------------------------------------------------------------------
    with col_chart2:
        fig_prod = go.Figure(go.Bar(
            x=range_agg['Temp_Range'],
            y=range_agg['Taps_Per_Hour'],
            marker_color=[_BUCKET_COLORS.get(r, '#999') for r in range_agg['Temp_Range']],
            text=range_agg['Taps_Per_Hour'].apply(lambda x: f"{x:.1f}"),
            textposition='outside',
        ))
        fig_prod.update_layout(
            title="Taps/Hour by Temp Range",
            yaxis_title="Taps per Hour",
            height=400,
            showlegend=False,
        )
        st.plotly_chart(fig_prod, use_container_width=True)

    st.divider()

    # ------------------------------------------------------------------
    # 7. SCATTER: DAILY AVG TEMP vs TAPS/HOUR
    # ------------------------------------------------------------------
    st.subheader("📈 Daily Temperature vs Productivity")

    # Aggregate by day (and site if multiple)
    group_cols = ['_join_date']
    if has_site and len(sites) > 1:
        group_cols.append('Site')

    daily = merged.groupby(group_cols).agg(
        Taps=('Taps_In', 'sum'),
        Hours=('Hours', 'sum'),
        Avg_Temp=('Avg_Temp', 'first'),
        High=('High', 'first'),
        Low=('Low', 'first'),
    ).reset_index()
    daily['Taps_Per_Hour'] = (daily['Taps'] / daily['Hours']).round(1)
    daily['Taps_Per_Hour'] = daily['Taps_Per_Hour'].replace(
        [float('inf'), float('-inf')], 0
    )
    daily = daily[daily['Taps'] > 0]  # Only days with actual tapping

    if not daily.empty:
        if has_site and len(sites) > 1:
            fig_scatter = px.scatter(
                daily, x='Avg_Temp', y='Taps_Per_Hour',
                color='Site',
                trendline='ols',
                labels={'Avg_Temp': 'Avg Temp (°F)', 'Taps_Per_Hour': 'Taps/Hour'},
                hover_data={'_join_date': '|%Y-%m-%d', 'High': True, 'Low': True, 'Taps': True},
            )
        else:
            fig_scatter = px.scatter(
                daily, x='Avg_Temp', y='Taps_Per_Hour',
                trendline='ols',
                labels={'Avg_Temp': 'Avg Temp (°F)', 'Taps_Per_Hour': 'Taps/Hour'},
                hover_data={'_join_date': '|%Y-%m-%d', 'High': True, 'Low': True, 'Taps': True},
            )

        fig_scatter.update_layout(
            title="Each dot = one work day",
            height=450,
        )
        fig_scatter.update_traces(marker=dict(size=8, opacity=0.7))
        st.plotly_chart(fig_scatter, use_container_width=True)

        # Correlation stat
        corr = daily['Avg_Temp'].corr(daily['Taps_Per_Hour'])
        if pd.notna(corr):
            direction = "positive" if corr > 0 else "negative"
            strength = "strong" if abs(corr) > 0.5 else "moderate" if abs(corr) > 0.3 else "weak"
            st.caption(
                f"Correlation: **r = {corr:.2f}** ({strength} {direction}) — "
                f"{'warmer days tend to have higher productivity' if corr > 0 else 'temperature has limited impact on productivity'}"
            )
    else:
        st.info("Not enough data for scatter plot.")

    st.divider()

    # ------------------------------------------------------------------
    # 8. TIMELINE: DAILY TAPS + TEMPERATURE
    # ------------------------------------------------------------------
    st.subheader("📅 Daily Taps & Temperature Over Time")

    # Use per-day totals (combine sites if multiple)
    timeline = merged.groupby('_join_date').agg(
        Taps=('Taps_In', 'sum'),
        Avg_Temp=('Avg_Temp', 'mean'),
    ).reset_index().sort_values('_join_date')

    if not timeline.empty:
        fig_timeline = go.Figure()

        fig_timeline.add_trace(go.Bar(
            x=timeline['_join_date'],
            y=timeline['Taps'],
            name='Taps Put In',
            marker_color='#2ca02c',
            opacity=0.7,
        ))

        fig_timeline.add_trace(go.Scatter(
            x=timeline['_join_date'],
            y=timeline['Avg_Temp'],
            name='Avg Temp (°F)',
            yaxis='y2',
            mode='lines+markers',
            marker=dict(size=4),
            line=dict(color='#d62728', width=2),
        ))

        # Add horizontal lines for temp range boundaries
        for _, lo, hi in config.TEMP_RANGES:
            if lo is not None:
                fig_timeline.add_hline(
                    y=lo, line_dash="dot", line_color="gray",
                    opacity=0.4, yref='y2',
                    annotation_text=f"{lo}°F", annotation_position="bottom right",
                )

        fig_timeline.update_layout(
            height=400,
            yaxis=dict(title='Taps Put In'),
            yaxis2=dict(title='Avg Temp (°F)', overlaying='y', side='right'),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            hovermode='x unified',
        )
        st.plotly_chart(fig_timeline, use_container_width=True)
    else:
        st.info("No data for timeline.")

    st.divider()

    # ------------------------------------------------------------------
    # 9. EMPLOYEE BREAKDOWN
    # ------------------------------------------------------------------
    st.subheader("👥 Employee Productivity by Temperature")

    emp_temp = merged.groupby(['Employee', 'Temp_Range']).agg(
        Taps=('Taps_In', 'sum'),
        Hours=('Hours', 'sum'),
    ).reset_index()
    emp_temp['Taps_Per_Hour'] = (emp_temp['Taps'] / emp_temp['Hours']).round(1)
    emp_temp['Taps_Per_Hour'] = emp_temp['Taps_Per_Hour'].replace(
        [float('inf'), float('-inf')], 0
    )
    emp_temp['Min_Per_Tap'] = ((emp_temp['Hours'] * 60) / emp_temp['Taps']).round(1)
    emp_temp['Min_Per_Tap'] = emp_temp['Min_Per_Tap'].replace(
        [float('inf'), float('-inf')], 0
    )

    # Filter to employees with at least some taps
    emp_temp = emp_temp[emp_temp['Taps'] > 0].copy()

    if not emp_temp.empty:
        # Pivot for compact view
        pivot = emp_temp.pivot_table(
            index='Employee',
            columns='Temp_Range',
            values='Taps_Per_Hour',
            aggfunc='first',
        ).reindex(columns=bucket_order)

        # Add total column
        emp_totals = merged.groupby('Employee').agg(
            Taps=('Taps_In', 'sum'),
            Hours=('Hours', 'sum'),
        )
        emp_totals['Overall Taps/Hr'] = (emp_totals['Taps'] / emp_totals['Hours']).round(1)
        pivot = pivot.join(emp_totals[['Taps', 'Overall Taps/Hr']])
        pivot = pivot.rename(columns={'Taps': 'Total Taps'})
        pivot = pivot.sort_values('Total Taps', ascending=False)
        pivot['Total Taps'] = pivot['Total Taps'].astype(int)

        st.dataframe(
            pivot.style.format({
                col: '{:.1f}' for col in pivot.columns
                if col not in ('Total Taps',)
            }).format({'Total Taps': '{:,.0f}'}),
            use_container_width=True,
        )
        st.caption(
            "Values show **Taps/Hour** for each employee in each temperature range. "
            "Blank cells mean the employee had no tapping days in that range."
        )
    else:
        st.info("No employee tapping data to display.")

    # ------------------------------------------------------------------
    # DETAIL TABLE
    # ------------------------------------------------------------------
    with st.expander("📋 Detailed Employee × Temperature Breakdown"):
        if not emp_temp.empty:
            detail = emp_temp[['Employee', 'Temp_Range', 'Taps', 'Hours', 'Taps_Per_Hour', 'Min_Per_Tap']].copy()
            detail.columns = ['Employee', 'Temp Range', 'Taps', 'Hours', 'Taps/Hr', 'Min/Tap']
            detail = detail.sort_values(['Employee', 'Temp Range'])
            st.dataframe(detail, use_container_width=True, hide_index=True)
