"""
Helper Utilities Module
Common utility functions used across the dashboard
"""

import pandas as pd
from datetime import datetime, timedelta
import streamlit as st


def find_column(df, *possible_names):
    """
    Find a column in a DataFrame by trying multiple possible names (case-insensitive)
    
    Args:
        df: DataFrame to search
        *possible_names: Variable number of possible column names
        
    Returns:
        Column name if found, None otherwise
    """
    if df.empty:
        return None
    
    df_columns_lower = {col.lower(): col for col in df.columns}
    
    for name in possible_names:
        if name.lower() in df_columns_lower:
            return df_columns_lower[name.lower()]
    
    return None


def get_vacuum_column(df):
    """
    Find the vacuum reading column in dataframe
    
    Args:
        df: DataFrame to search
        
    Returns:
        Column name if found, None otherwise
    """
    return find_column(df, 'Vacuum Reading', 'vacuum', 'reading', 'Vacuum')


def filter_recent_sensors(vacuum_df, days=2):
    """
    Filter to only sensors that have reported in the last N days
    
    Args:
        vacuum_df: Vacuum data DataFrame
        days: Number of days to look back
        
    Returns:
        Filtered DataFrame
    """
    if vacuum_df.empty:
        return vacuum_df
    
    # Find the date/timestamp column
    date_col = find_column(vacuum_df, 'Date', 'Timestamp', 'date', 'timestamp')
    if not date_col:
        return vacuum_df
    
    # Convert to datetime if needed
    if not pd.api.types.is_datetime64_any_dtype(vacuum_df[date_col]):
        vacuum_df[date_col] = pd.to_datetime(vacuum_df[date_col], errors='coerce')
    
    # Calculate cutoff
    cutoff = datetime.now() - timedelta(days=days)
    
    # Find sensors that have recent readings
    if pd.api.types.is_datetime64_any_dtype(vacuum_df[date_col]):
        recent_data = vacuum_df[vacuum_df[date_col] >= cutoff]
    else:
        # If it's a date column
        recent_data = vacuum_df[pd.to_datetime(vacuum_df[date_col]) >= cutoff]
    
    sensor_col = find_column(vacuum_df, 'Sensor Name', 'sensor', 'mainline', 'location', 'name')
    if not sensor_col:
        return vacuum_df
    
    recent_sensors = recent_data[sensor_col].unique()
    
    # Filter original dataframe to only include these sensors
    filtered_df = vacuum_df[vacuum_df[sensor_col].isin(recent_sensors)]
    
    return filtered_df


def safe_divide(numerator, denominator, default=0):
    """
    Safely divide two numbers, returning default if denominator is 0
    
    Args:
        numerator: Number to divide
        denominator: Number to divide by
        default: Value to return if denominator is 0
        
    Returns:
        Division result or default
    """
    if denominator == 0 or pd.isna(denominator):
        return default
    return numerator / denominator


def format_hours(hours):
    """Format hours for display"""
    if pd.isna(hours):
        return "N/A"
    return f"{hours:.1f}h"


def format_vacuum(vacuum):
    """Format vacuum reading for display"""
    if pd.isna(vacuum):
        return "N/A"
    return f"{vacuum:.1f}\""


def format_percentage(value):
    """Format percentage for display"""
    if pd.isna(value):
        return "N/A"
    return f"{value:.1f}%"


def get_date_range_text(df, date_col='Date'):
    """
    Get human-readable date range from a DataFrame
    
    Args:
        df: DataFrame with date column
        date_col: Name of date column
        
    Returns:
        String describing date range
    """
    if df.empty or date_col not in df.columns:
        return "No data"
    
    min_date = df[date_col].min()
    max_date = df[date_col].max()
    
    if pd.isna(min_date) or pd.isna(max_date):
        return "No valid dates"
    
    # Format based on type
    if hasattr(min_date, 'strftime'):
        return f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"
    else:
        return f"{min_date} to {max_date}"


def create_status_badge(status_text, color):
    """
    Create a colored status badge using HTML
    
    Args:
        status_text: Text to display
        color: CSS color for badge
        
    Returns:
        HTML string
    """
    return f"""
    <span style="
        background-color: {color};
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 14px;
    ">{status_text}</span>
    """


def show_data_loading_info(vacuum_df, personnel_df):
    """
    Display data loading information in an expander
    
    Args:
        vacuum_df: Vacuum data DataFrame
        personnel_df: Personnel data DataFrame
    """
    with st.expander("📊 Data Loading Info", expanded=False):
        st.write("**Vacuum Data:**")
        if not vacuum_df.empty:
            st.write(f"- Total records: {len(vacuum_df):,}")
            if 'Date' in vacuum_df.columns:
                st.write(f"- Date range: {get_date_range_text(vacuum_df)}")
            sensor_col = find_column(vacuum_df, 'Sensor Name', 'sensor', 'mainline', 'location', 'name')
            if sensor_col:
                st.write(f"- Unique sensors: {vacuum_df[sensor_col].nunique()}")
        else:
            st.write("- No data loaded")
        
        st.write("**Personnel Data:**")
        if not personnel_df.empty:
            st.write(f"- Total records: {len(personnel_df):,}")
            if 'Date' in personnel_df.columns:
                st.write(f"- Date range: {get_date_range_text(personnel_df)}")
            emp_col = find_column(personnel_df, 'Employee Name', 'employee', 'name')
            if emp_col:
                st.write(f"- Unique employees: {personnel_df[emp_col].nunique()}")
            mainline_col = find_column(personnel_df, 'mainline', 'Mainline', 'location', 'sensor')
            if mainline_col:
                st.write(f"- Unique locations worked: {personnel_df[mainline_col].nunique()}")
        else:
            st.write("- No data loaded")


def show_empty_data_message(data_type="data"):
    """Show a friendly message when no data is available"""
    st.info(f"📊 No {data_type} available for the selected time period")
