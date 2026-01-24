"""
Utility Functions Module
Helper functions used across the dashboard
"""

import pandas as pd
from datetime import datetime, timedelta
from schema import find_column, SchemaMapper


def get_vacuum_column(df):
    """
    Find the vacuum reading column in dataframe
    
    Args:
        df: DataFrame to search
        
    Returns:
        Column name if found, None otherwise
    """
    if df.empty:
        return None
    
    for col in df.columns:
        if 'vacuum' in col.lower() or 'reading' in col.lower():
            return col
    
    return None


def filter_recent_sensors(vacuum_df, days_threshold):
    """
    Filter vacuum data to only include sensors that reported recently
    
    Args:
        vacuum_df: Vacuum data DataFrame
        days_threshold: Number of days to look back (sensors must have reported within this)
        
    Returns:
        Filtered DataFrame with only recently active sensors
    """
    if vacuum_df.empty or days_threshold is None:
        return vacuum_df

    timestamp_col = find_column(
        vacuum_df, 
        'Last Communication', 'Timestamp', 'timestamp', 'time', 
        'datetime', 'Date', 'date', 'last_communication', 'last communication'
    )
    sensor_col = find_column(
        vacuum_df, 
        'Sensor Name', 'sensor', 'mainline', 'location', 'name'
    )

    if not timestamp_col or not sensor_col:
        return vacuum_df  # Can't filter without these columns

    # Convert to datetime if needed
    vacuum_df_copy = vacuum_df.copy()
    vacuum_df_copy[timestamp_col] = pd.to_datetime(vacuum_df_copy[timestamp_col], errors='coerce')

    # Get the last report time for each sensor
    latest_reports = vacuum_df_copy.groupby(sensor_col)[timestamp_col].max().reset_index()
    latest_reports.columns = [sensor_col, 'last_report']

    # Calculate cutoff date
    cutoff = datetime.now() - timedelta(days=days_threshold)

    # Find sensors that reported recently
    recent_sensors = latest_reports[latest_reports['last_report'] >= cutoff][sensor_col].tolist()

    # Filter to only recent sensors
    filtered_df = vacuum_df[vacuum_df[sensor_col].isin(recent_sensors)].copy()

    return filtered_df


def format_vacuum(value):
    """Format vacuum value for display"""
    if pd.isna(value):
        return "N/A"
    return f"{value:.1f}\""


def format_hours(value):
    """Format hours value for display"""
    if pd.isna(value):
        return "N/A"
    return f"{value:.1f}h"


def format_improvement(value):
    """Format improvement value for display with +/- sign"""
    if pd.isna(value):
        return "N/A"
    return f"{value:+.1f}\""
