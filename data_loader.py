"""
Data Loader Module
Handles loading and processing data from Google Sheets
All data loading logic is centralized here for easy maintenance

PERFORMANCE: Now includes caching for dramatic speed improvements!
- Data cached for 1 hour (auto-refresh)
- Manual refresh available via dashboard button

UPDATED: Now works with both local credentials AND Streamlit Cloud secrets!
"""

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import streamlit as st
import os
import json
import config


def connect_to_sheets(credentials_file):
    """
    Connect to Google Sheets with authentication
    Works with BOTH local credentials file AND Streamlit Cloud secrets!
    
    NOTE: No caching to avoid auth issues

    Args:
        credentials_file: Path to Google service account JSON file (for local development)

    Returns:
        Authorized gspread client
    """
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]

    credentials_dict = None
    
    # Try Streamlit secrets first (for Streamlit Cloud)
    try:
        if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
            credentials_dict = dict(st.secrets['gcp_service_account'])
            # Successfully got credentials from Streamlit secrets
    except (FileNotFoundError, KeyError, AttributeError):
        pass
    
    # Fall back to local credentials file (for local development)
    if credentials_dict is None:
        if not os.path.exists(credentials_file):
            raise FileNotFoundError(
                f"❌ Credentials not found!\n\n"
                f"For Streamlit Cloud: Add credentials to app secrets under [gcp_service_account]\n"
                f"For Local Development: Need '{credentials_file}' file in your project folder"
            )
        
        with open(credentials_file, 'r') as f:
            credentials_dict = json.load(f)
    
    # Create credentials and authorize (works with dict from either source)
    creds = Credentials.from_service_account_info(credentials_dict, scopes=scope)
    client = gspread.authorize(creds)
    
    return client


@st.cache_data(ttl=3600, show_spinner="Loading vacuum data from cache...")
def load_all_vacuum_data(sheet_url, credentials_file, days=None):
    """
    Load ALL vacuum data from all monthly tabs

    CACHED: Data is cached for 1 hour to dramatically improve performance.
    Switching between pages is instant after first load!

    Args:
        sheet_url: Google Sheet URL
        credentials_file: Path to credentials JSON
        days: If specified, only load last N days (None = all data)

    Returns:
        DataFrame with all vacuum readings
    """
    try:
        client = connect_to_sheets(credentials_file)
        sheet = client.open_by_url(sheet_url)

        # Get all worksheets (monthly tabs)
        all_worksheets = sheet.worksheets()

        all_data = []

        for worksheet in all_worksheets:
            # Skip any non-date worksheets (like instructions, etc.)
            if not is_month_tab(worksheet.title):
                continue

            try:
                # Get data from this worksheet
                data = worksheet.get_all_records()
                if data:
                    df = pd.DataFrame(data)
                    all_data.append(df)
            except Exception as e:
                if config.DEBUG_MODE:
                    st.warning(f"Skipped worksheet '{worksheet.title}': {str(e)}")
                continue

        if not all_data:
            return pd.DataFrame()

        # Combine all data
        combined_df = pd.concat(all_data, ignore_index=True)

        # Clean and process the data
        combined_df = process_vacuum_data(combined_df)

        # Filter by date if specified
        if days is not None:
            cutoff_date = datetime.now() - timedelta(days=days)
            combined_df = combined_df[combined_df['Timestamp'] >= cutoff_date]

        return combined_df

    except Exception as e:
        st.error(f"Error loading vacuum data: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner="Loading personnel data from cache...")
def load_all_personnel_data(sheet_url, credentials_file, days=None):
    """
    Load ALL personnel data from all monthly tabs

    CACHED: Data is cached for 1 hour to dramatically improve performance.
    Switching between pages is instant after first load!

    Args:
        sheet_url: Google Sheet URL
        credentials_file: Path to credentials JSON
        days: If specified, only load last N days (None = all data)

    Returns:
        DataFrame with all personnel timesheet data
    """
    try:
        client = connect_to_sheets(credentials_file)
        sheet = client.open_by_url(sheet_url)

        # Get all worksheets (monthly tabs)
        all_worksheets = sheet.worksheets()

        all_data = []

        for worksheet in all_worksheets:
            # Skip any non-date worksheets
            if not is_month_tab(worksheet.title):
                continue

            try:
                # Get data from this worksheet
                data = worksheet.get_all_records()
                if data:
                    df = pd.DataFrame(data)
                    all_data.append(df)
            except Exception as e:
                if config.DEBUG_MODE:
                    st.warning(f"Skipped worksheet '{worksheet.title}': {str(e)}")
                continue

        if not all_data:
            return pd.DataFrame()

        # Combine all data
        combined_df = pd.concat(all_data, ignore_index=True)

        # Clean and process the data
        combined_df = process_personnel_data(combined_df)

        # Filter by date if specified
        if days is not None:
            cutoff_date = datetime.now() - timedelta(days=days)
            combined_df = combined_df[combined_df['Date'] >= cutoff_date]

        return combined_df

    except Exception as e:
        st.error(f"Error loading personnel data: {str(e)}")
        return pd.DataFrame()


@st.cache_data
def process_vacuum_data(df):
    """
    Clean and process vacuum data

    CACHED: Processing is cached to avoid repeated computation

    Args:
        df: Raw DataFrame from Google Sheets

    Returns:
        Processed DataFrame with proper types and cleaned data
    """
    if df.empty:
        return df

    # Find timestamp/date column - try multiple possible names
    timestamp_col = None
    for possible_name in ['Timestamp', 'timestamp', 'Date', 'date', 'DateTime', 'datetime',
                          'Last Communication', 'Last communication', 'last communication',
                          'Time', 'time']:
        if possible_name in df.columns:
            timestamp_col = possible_name
            break

    # Convert timestamp to datetime if found
    if timestamp_col:
        df['Timestamp'] = pd.to_datetime(df[timestamp_col], errors='coerce')

        # Add derived columns
        df['Date'] = df['Timestamp'].dt.date
        df['Hour'] = df['Timestamp'].dt.hour

        # Remove rows with invalid timestamps
        df = df.dropna(subset=['Timestamp'])
    else:
        # No timestamp column found - create a default one with current time
        # This allows the dashboard to work even without timestamps
        df['Timestamp'] = pd.Timestamp.now()
        df['Date'] = datetime.now().date()

    # Convert vacuum reading to numeric
    vacuum_cols = [col for col in df.columns if 'vacuum' in col.lower() or 'reading' in col.lower()]
    for col in vacuum_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Fill missing vacuum values
    for col in vacuum_cols:
        df[col] = df[col].fillna(config.FILL_MISSING_VACUUM)

    return df


@st.cache_data
def process_personnel_data(df):
    """
    Clean and process personnel data

    CACHED: Processing is cached to avoid repeated computation

    Args:
        df: Raw DataFrame from Google Sheets

    Returns:
        Processed DataFrame with proper types and cleaned data
    """
    if df.empty:
        return df

    # Convert date to datetime
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

    # Convert hours to numeric
    if 'Hours' in df.columns:
        df['Hours'] = pd.to_numeric(df['Hours'], errors='coerce')
        df['Hours'] = df['Hours'].fillna(config.FILL_MISSING_HOURS)

    # Convert numeric fields
    numeric_fields = ['Taps Put In', 'Taps Removed', 'taps capped', 'Repairs needed']
    for field in numeric_fields:
        if field in df.columns:
            df[field] = pd.to_numeric(df[field], errors='coerce').fillna(0)

    # Create full employee name if needed
    if 'EE First' in df.columns and 'EE Last' in df.columns:
        df['Employee Name'] = df['EE First'] + ' ' + df['EE Last']

    # Clean mainline column name (handle potential variations)
    mainline_cols = [col for col in df.columns if 'mainline' in col.lower()]
    if mainline_cols:
        df['mainline'] = df[mainline_cols[0]]

    # Remove rows with invalid dates
    if 'Date' in df.columns:
        df = df.dropna(subset=['Date'])

    return df


def is_month_tab(tab_name):
    """
    Check if a worksheet tab name represents a month
    Supports multiple formats:
    - YYYY-MM (e.g., '2025-03')
    - Month_YYYY (e.g., 'Nov_2025', 'December_2025')
    - Any tab with year 2024, 2025, or 2026 in the name

    Args:
        tab_name: Name of the worksheet tab

    Returns:
        True if it looks like a month tab, False otherwise
    """
    import re

    # Pattern 1: YYYY-MM format (e.g., '2025-11')
    pattern_yyyy_mm = r'^\d{4}-\d{2}$'

    # Pattern 2: Month_YYYY format (e.g., 'Nov_2025', 'December_2025')
    # Matches 3+ letters followed by underscore and 4 digits
    pattern_month_year = r'^[A-Za-z]{3,}_\d{4}$'

    # Pattern 3: Simple check - does it contain a recent year?
    has_recent_year = any(year in tab_name for year in ['2024', '2025', '2026', '2027'])

    # Return True if any pattern matches
    return (bool(re.match(pattern_yyyy_mm, tab_name)) or
            bool(re.match(pattern_month_year, tab_name)) or
            has_recent_year)


def get_latest_data(vacuum_df, personnel_df, hours=24):
    """
    Get data from the last N hours

    Args:
        vacuum_df: Vacuum data DataFrame
        personnel_df: Personnel data DataFrame
        hours: Number of hours to look back

    Returns:
        Tuple of (filtered vacuum_df, filtered personnel_df)
    """
    cutoff = datetime.now() - timedelta(hours=hours)

    vacuum_recent = vacuum_df[vacuum_df['Timestamp'] >= cutoff] if not vacuum_df.empty else vacuum_df
    personnel_recent = personnel_df[personnel_df['Date'] >= cutoff] if not personnel_df.empty else personnel_df

    return vacuum_recent, personnel_recent


def merge_vacuum_personnel(vacuum_df, personnel_df):
    """
    Merge vacuum and personnel data on mainline location

    Args:
        vacuum_df: Vacuum data DataFrame
        personnel_df: Personnel data DataFrame

    Returns:
        Merged DataFrame with both vacuum and personnel information
    """
    if vacuum_df.empty or personnel_df.empty:
        return pd.DataFrame()

    # Find the sensor name column in vacuum data
    sensor_col = None
    for col in ['Sensor Name', 'sensor', 'mainline', 'location']:
        if col in vacuum_df.columns:
            sensor_col = col
            break

    if sensor_col is None:
        st.warning("Could not find sensor/mainline column in vacuum data")
        return pd.DataFrame()

    # Ensure mainline column exists in personnel data
    if 'mainline' not in personnel_df.columns:
        st.warning("Could not find mainline column in personnel data")
        return pd.DataFrame()

    # Merge on mainline
    merged = pd.merge(
        vacuum_df,
        personnel_df,
        left_on=sensor_col,
        right_on='mainline',
        how='left'
    )

    return merged


def calculate_vacuum_improvement(merged_df):
    """
    Calculate vacuum improvement based on before/after personnel activity

    Args:
        merged_df: Merged DataFrame with vacuum and personnel data

    Returns:
        DataFrame with improvement calculations added
    """
    # This is a simplified version - you can make it more sophisticated
    # by looking at vacuum readings before and after specific employee visits

    if merged_df.empty:
        return merged_df

    # Group by mainline and calculate change over time
    # This is a placeholder - actual implementation depends on your specific needs

    return merged_df
