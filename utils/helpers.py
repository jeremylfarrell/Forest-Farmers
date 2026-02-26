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


def get_releaser_column(df):
    """
    Find the releaser differential column in dataframe.
    The CDL export uses various names — search case-insensitively.

    Returns:
        Column name if found, None otherwise
    """
    if df.empty:
        return None
    for col in df.columns:
        cl = col.lower()
        if 'releaser' in cl or 'differential' in cl or 'rel diff' in cl:
            return col
    return None


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


def is_tapping_job(job_text):
    """
    Return True if the job code is a tapping-type code.

    Tapping jobs are: new spout install, dropline install, spout already on,
    maple tapping.  This is used by tapping.py, temperature_productivity.py,
    and any other module that needs to filter to tapping work.
    """
    if pd.isna(job_text):
        return False
    j = str(job_text).lower()
    return any(kw in j for kw in [
        'new spout install', 'dropline install', 'spout already on',
        'maple tapping',
    ])


def extract_conductor_system(mainline):
    """
    Extract the conductor system prefix from a mainline name.

    The conductor system is the letter prefix before the first digit.
    After extracting it, we try to match it against the known sugarbush
    conductor list (from config) to normalise sub-conductors into their
    parent.  E.g. GCE → GC, DMAN → DMA (closest match by prefix).
    """
    import re
    import config as _cfg

    if pd.isna(mainline) or not str(mainline).strip():
        return 'Unknown'

    name = str(mainline).strip().upper()

    # Extract all letters before the first digit
    m = re.match(r'^([A-Z]{1,6})', name)
    if not m:
        return 'Unknown'

    raw_prefix = m.group(1)

    # Try to match against known conductor prefixes (longest match first)
    known = set()
    for bush_conductors in _cfg.SUGARBUSH_MAP.values():
        known.update(bush_conductors)

    # Sort known conductors longest-first so DMA matches before DM, GC before G
    for known_cond in sorted(known, key=len, reverse=True):
        if raw_prefix.startswith(known_cond):
            return known_cond

    # Fallback: letters before first digit (original behaviour)
    m2 = re.match(r'^([A-Z]{1,4})', name)
    return m2.group(1) if m2 else 'Unknown'
