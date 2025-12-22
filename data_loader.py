"""
Data Loader Module - MULTI-SITE VERSION
Handles loading and processing data from Google Sheets for NY and VT sites
All data loading logic is centralized here for easy maintenance

PERFORMANCE: Now includes caching for dramatic speed improvements!
- Data cached for 1 hour (auto-refresh)
- Manual refresh available via dashboard button

MULTI-SITE: Supports separate vacuum data for NY and VT sites
- Loads both sites and adds 'Site' column
- Parses personnel site from Job column
"""

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import streamlit as st
import os
import json
import re
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


def parse_site_from_job(job_text):
    """
    Parse site location from job description

    Args:
        job_text: Job description string (e.g., "Training/Meetings - VT Woods- 241121")

    Returns:
        "NY", "VT", or "UNK" (unknown)
    """
    if pd.isna(job_text):
        return "UNK"

    job_upper = str(job_text).upper()

    # Check for VT
    if "VT" in job_upper:
        return "VT"
    # Check for NY
    elif "NY" in job_upper:
        return "NY"
    else:
        return "UNK"


@st.cache_data(ttl=3600, show_spinner="Loading vacuum data from cache...")
def load_all_vacuum_data(ny_sheet_url, vt_sheet_url, credentials_file, days=None):
    """
    Load ALL vacuum data from both NY and VT sheets
    Combines data from both sites and adds 'Site' column

    CACHED: Data is cached for 1 hour to dramatically improve performance.
    Switching between pages is instant after first load!

    Args:
        ny_sheet_url: Google Sheet URL for NY vacuum data
        vt_sheet_url: Google Sheet URL for VT vacuum data
        credentials_file: Path to credentials JSON
        days: If specified, only load last N days (None = all data)

    Returns:
        DataFrame with all vacuum readings from both sites, with 'Site' column
    """
    all_sites_data = []

    # Load NY site data
    try:
        ny_data = _load_vacuum_from_single_site(ny_sheet_url, credentials_file, days, site_name="NY")
        if not ny_data.empty:
            all_sites_data.append(ny_data)
    except Exception as e:
        st.warning(f"Error loading NY vacuum data: {str(e)}")

    # Load VT site data
    try:
        vt_data = _load_vacuum_from_single_site(vt_sheet_url, credentials_file, days, site_name="VT")
        if not vt_data.empty:
            all_sites_data.append(vt_data)
    except Exception as e:
        st.warning(f"Error loading VT vacuum data: {str(e)}")

    # Combine all sites
    if not all_sites_data:
        return pd.DataFrame()

    combined_df = pd.concat(all_sites_data, ignore_index=True)
    return combined_df


def _load_vacuum_from_single_site(sheet_url, credentials_file, days=None, site_name="Unknown"):
    """
    Load vacuum data from a single site's Google Sheet

    Args:
        sheet_url: Google Sheet URL
        credentials_file: Path to credentials JSON
        days: If specified, only load last N days
        site_name: Name of the site (NY, VT, etc.)

    Returns:
        DataFrame with vacuum readings and 'Site' column added
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
                    st.warning(f"Skipped worksheet '{worksheet.title}' in {site_name}: {str(e)}")
                continue

        if not all_data:
            return pd.DataFrame()

        # Combine all data
        combined_df = pd.concat(all_data, ignore_index=True)

        # Clean and process the data
        combined_df = process_vacuum_data(combined_df)

        # Add site column
        combined_df['Site'] = site_name

        # Filter by date if specified
        if days is not None and 'Timestamp' in combined_df.columns:
            cutoff_date = datetime.now() - timedelta(days=days)
            combined_df = combined_df[combined_df['Timestamp'] >= cutoff_date]

        return combined_df

    except Exception as e:
        st.error(f"Error loading {site_name} vacuum data: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner="Loading personnel data from cache...")
def load_all_personnel_data(sheet_url, credentials_file, days=None):
    """
    Load ALL personnel data from all monthly tabs
    Adds 'Site' column based on Job description parsing

    CACHED: Data is cached for 1 hour to dramatically improve performance.
    Switching between pages is instant after first load!

    Args:
        sheet_url: Google Sheet URL
        credentials_file: Path to credentials JSON
        days: If specified, only load last N days (None = all data)

    Returns:
        DataFrame with all personnel timesheet data including 'Site' column
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
        if days is not None and 'Date' in combined_df.columns:
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

# Find ALL timestamp/date columns - process each one
    timestamp_columns = []
    for possible_name in ['Scrape_Timestamp', 'Timestamp', 'timestamp', 'Date', 'date', 'DateTime', 'datetime',
                          'Last Communication', 'Last communication', 'last communication',
                          'Time', 'time', 'Delay']:
        if possible_name in df.columns:
            timestamp_columns.append(possible_name)
    
    # Process each timestamp column found
    for timestamp_col in timestamp_columns:
        # Check if we have Excel serial dates (numeric values like 45991.06957)
        if pd.api.types.is_numeric_dtype(df[timestamp_col]):
            # Create a clean copy
            values = df[timestamp_col].copy()
            
            # Filter out invalid values (negative, zero, or unreasonably large)
            # Valid Excel dates are typically between 1 and 50000 (years 1900-2036)
            values = values.apply(lambda x: x if (pd.notna(x) and 0 < x < 100000) else None)
            
            # Convert Excel serial dates to datetime
            # Method: Add days to Excel's epoch (1899-12-30)
            from datetime import datetime as dt, timedelta
            
            def excel_to_datetime(excel_date):
                if pd.isna(excel_date):
                    return pd.NaT
                try:
                    # Excel epoch is December 30, 1899
                    epoch = dt(1899, 12, 30)
                    # Add the number of days
                    return epoch + timedelta(days=float(excel_date))
                except:
                    return pd.NaT
            
            df[timestamp_col] = values.apply(excel_to_datetime)
        else:
            # Regular string dates
            df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors='coerce')
    
    # Use the first valid timestamp column for primary Timestamp field
    if timestamp_columns:
        primary_timestamp = timestamp_columns[0]
        if primary_timestamp in df.columns:
            df['Timestamp'] = df[primary_timestamp]

            # Add derived columns
            df['Date'] = df['Timestamp'].dt.date
            df['Hour'] = df['Timestamp'].dt.hour

            # Remove rows with invalid timestamps
            df = df.dropna(subset=['Timestamp'])
    else:
        # No timestamp column found - create a default one with current time
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
    Adds 'Site' column based on Job description

    CACHED: Processing is cached to avoid repeated computation

    Args:
        df: Raw DataFrame from Google Sheets

    Returns:
        Processed DataFrame with proper types, cleaned data, and 'Site' column
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

    # Parse site from Job column
    if 'Job' in df.columns:
        df['Site'] = df['Job'].apply(parse_site_from_job)
    else:
        # If no Job column, default to UNK
        df['Site'] = 'UNK'

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
    - Any tab with year 2024, 2025, 2026, or 2027 in the name

    Args:
        tab_name: Name of the worksheet tab

    Returns:
        True if it looks like a month tab, False otherwise
    """
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
    for col in ['Sensor Name', 'sensor', 'mainline', 'location', 'Name']:
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
