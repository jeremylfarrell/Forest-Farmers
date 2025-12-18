"""
Overview Page Module
Displays high-level system overview and key metrics
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import config
from utils import find_column, get_vacuum_column


def calculate_overview_metrics(vacuum_df, personnel_df):
    """Calculate key metrics for overview"""
    metrics = {}
    today = datetime.now().date()

    # Vacuum metrics
    if not vacuum_df.empty:
        vacuum_col = get_vacuum_column(vacuum_df)
        sensor_col = find_column(vacuum_df, 'Sensor Name', 'sensor', 'mainline', 'location', 'name')

        if vacuum_col:
            metrics['avg_vacuum'] = vacuum_df[vacuum_col].mean()

            if sensor_col:
                metrics['active_sensors'] = vacuum_df[sensor_col].nunique()
                metrics['problem_areas'] = len(vacuum_df[vacuum_df[vacuum_col] < config.VACUUM_FAIR])
            else:
                metrics['active_sensors'] = 0
                metrics['problem_areas'] = 0
        else:
            metrics['avg_vacuum'] = 0
            metrics['active_sensors'] = 0
            metrics['problem_areas'] = 0
    else:
        metrics['avg_vacuum'] = 0
        metrics['active_sensors'] = 0
        metrics['problem_areas'] = 0

    # Personnel metrics
    if not personnel_df.empty:
        date_col = find_column(personnel_df, 'Date', 'date', 'timestamp')
        emp_name_col = find_column(personnel_df, 'Employee Name', 'employee', 'name')
        hours_col = find_column(personnel_df, 'Hours', 'hours', 'time')

        if date_col:
            today_personnel = personnel_df[pd.to_datetime(personnel_df[date_col]).dt.date == today]

            if emp_name_col:
                metrics['employees_today'] = today_personnel[emp_name_col].nunique()
            else:
                metrics['employees_today'] = 0

            if hours_col:
                metrics['total_hours_today'] = today_personnel[hours_col].sum()
            else:
                metrics['total_hours_today'] = 0
        else:
            metrics['employees_today'] = 0
            metrics['total_hours_today'] = 0
    else:
        metrics['employees_today'] = 0
        metrics['total_hours_today'] = 0

    return metrics


def render(vacuum_df, personnel_df):
    """Render the overview page"""

    st.title("🏠 System Overview")

    # Calculate metrics
    metrics = calculate_overview_metrics(vacuum_df, personnel_df)

    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg_vac = metrics['avg_vacuum']
        status = config.get_vacuum_status(avg_vac)
        st.metric("System Vacuum", f"{avg_vac:.1f}\"")
        st.markdown(f"**{status}**")

    with col2:
        st.metric("Active Sensors", metrics['active_sensors'])

    with col3:
        problem_count = metrics['problem_areas']
        st.metric("Problem Areas", problem_count)
        if problem_count > config.CRITICAL_SENSOR_COUNT:
            st.warning("⚠️ High number!")

    with col4:
        st.metric("Employees Today", metrics['employees_today'])

    st.divider()

    # Problem areas table
    st.subheader("⚠️ Areas Needing Attention")

    if not vacuum_df.empty:
        vacuum_col = get_vacuum_column(vacuum_df)
        sensor_col = find_column(vacuum_df, 'Sensor Name', 'sensor', 'mainline', 'location', 'name')

        if vacuum_col and sensor_col:
            # Get LATEST reading per sensor
            timestamp_col = find_column(
                vacuum_df,
                'Last communication', 'Last Communication', 'Timestamp', 'timestamp',
                'time', 'datetime', 'last_communication'
            )

            if timestamp_col:
                temp_df = vacuum_df.copy()
                temp_df[timestamp_col] = pd.to_datetime(temp_df[timestamp_col], errors='coerce')
                latest = temp_df.sort_values(timestamp_col, ascending=False).groupby(sensor_col).first().reset_index()
            else:
                latest = vacuum_df.groupby(sensor_col).first().reset_index()

            # Filter to problem areas only
            problems = latest[latest[vacuum_col] < config.VACUUM_FAIR].copy()

            if not problems.empty:
                problems = problems.sort_values(vacuum_col)
                display = problems[[sensor_col, vacuum_col]].head(15)
                display.columns = ['Location', 'Vacuum']
                display['Status'] = display['Vacuum'].apply(config.get_vacuum_emoji)
                display['Vacuum'] = display['Vacuum'].apply(lambda x: f"{x:.1f}\"")

                # Reorder to show status first
                display = display[['Status', 'Location', 'Vacuum']]

                st.dataframe(display, use_container_width=True, hide_index=True)
                st.caption(f"Showing {len(problems)} sensors below {config.VACUUM_FAIR}\"")
            else:
                st.success("🎉 All sensors are healthy!")
        else:
            st.info("Required columns not available for problem area analysis")
    else:
        st.info("No vacuum data available")