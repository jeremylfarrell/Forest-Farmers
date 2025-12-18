"""
Vacuum Performance Page Module
Shows performance metrics for each vacuum sensor and system trends
"""

import streamlit as st
import pandas as pd
import config
from utils import find_column, get_vacuum_column


def render(vacuum_df, personnel_df):
    """Render vacuum performance page"""

    st.title("🔧 Vacuum Performance")

    if vacuum_df.empty:
        st.warning("No vacuum data available")
        return

    # ============================================================================
    # VACUUM TRENDS SECTION
    # ============================================================================

    st.subheader("📈 Vacuum Trends (Last 7 Days)")

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
            # Create date column
            temp_df['Date'] = temp_df[timestamp_col].dt.date

            # Aggregate by date
            daily = temp_df.groupby('Date')[vacuum_col].mean().reset_index()
            daily = daily.sort_values('Date').tail(7)

            if len(daily) > 0:
                # Convert date to datetime for proper chart display
                daily['Date'] = pd.to_datetime(daily['Date'])

                st.line_chart(
                    daily.set_index('Date')[vacuum_col],
                    use_container_width=True
                )

                # Show data summary
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("7-Day Average", f"{daily[vacuum_col].mean():.1f}\"")
                with col2:
                    st.metric("Highest", f"{daily[vacuum_col].max():.1f}\"")
                with col3:
                    st.metric("Lowest", f"{daily[vacuum_col].min():.1f}\"")
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

    st.divider()

    # Display table
    st.subheader(f"Sensor Performance ({len(filtered)} locations)")

    display = filtered.copy()
    for col in ['Avg_Vacuum', 'Min_Vacuum', 'Max_Vacuum']:
        display[col] = display[col].apply(lambda x: f"{x:.1f}\"")

    # Format columns for display
    display_cols = ['Status', 'Sensor', 'Avg_Vacuum', 'Min_Vacuum', 'Max_Vacuum', 'Count']
    col_names = ['⚫', 'Sensor', 'Avg', 'Min', 'Max', 'Readings']

    if 'Last_Report' in display.columns:
        display['Last_Report_Display'] = display['Last_Report'].apply(
            lambda x: x.strftime('%Y-%m-%d %H:%M') if pd.notna(x) else "N/A"
        )
        display_cols.append('Last_Report_Display')
        col_names.append('Last Report')

    display = display[display_cols]
    display.columns = col_names

    st.dataframe(display, use_container_width=True, hide_index=True, height=400)