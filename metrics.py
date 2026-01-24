"""
Metrics Calculation Module
All metric calculations for the dashboard
Centralized for consistency and easy customization
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import config


def calculate_overview_metrics(vacuum_df, personnel_df):
    """
    Calculate key metrics for the overview page

    Args:
        vacuum_df: Vacuum data DataFrame
        personnel_df: Personnel data DataFrame

    Returns:
        Dictionary of metric values
    """
    metrics = {}

    # Get today's data
    today = datetime.now().date()

    # Vacuum metrics
    if not vacuum_df.empty:
        # Overall average vacuum
        metrics['avg_vacuum'] = vacuum_df['Vacuum Reading'].mean() if 'Vacuum Reading' in vacuum_df.columns else 0

        # Active sensors (sensors with readings today)
        if 'Date' in vacuum_df.columns:
            today_vacuum = vacuum_df[vacuum_df['Date'] == today]
            metrics['active_sensors'] = today_vacuum[
                'Sensor Name'].nunique() if 'Sensor Name' in today_vacuum.columns else 0
        else:
            metrics['active_sensors'] = vacuum_df['Sensor Name'].nunique() if 'Sensor Name' in vacuum_df.columns else 0

        # Problem areas (vacuum below threshold)
        if 'Vacuum Reading' in vacuum_df.columns:
            problem_sensors = vacuum_df[vacuum_df['Vacuum Reading'] < config.VACUUM_FAIR]
            metrics['problem_areas'] = problem_sensors[
                'Sensor Name'].nunique() if 'Sensor Name' in problem_sensors.columns else 0
        else:
            metrics['problem_areas'] = 0
    else:
        metrics['avg_vacuum'] = 0
        metrics['active_sensors'] = 0
        metrics['problem_areas'] = 0

    # Personnel metrics
    if not personnel_df.empty:
        # Employees active today
        if 'Date' in personnel_df.columns:
            today_personnel = personnel_df[pd.to_datetime(personnel_df['Date']).dt.date == today]
            metrics['employees_today'] = today_personnel[
                'Employee Name'].nunique() if 'Employee Name' in today_personnel.columns else 0
            metrics['total_hours_today'] = today_personnel['Hours'].sum() if 'Hours' in today_personnel.columns else 0
            metrics['repairs_today'] = today_personnel[
                'Repairs needed'].sum() if 'Repairs needed' in today_personnel.columns else 0
        else:
            metrics['employees_today'] = 0
            metrics['total_hours_today'] = 0
            metrics['repairs_today'] = 0
    else:
        metrics['employees_today'] = 0
        metrics['total_hours_today'] = 0
        metrics['repairs_today'] = 0

    return metrics


def calculate_mainline_summary(vacuum_df, personnel_df):
    """
    Calculate summary statistics for each mainline

    Args:
        vacuum_df: Vacuum data DataFrame
        personnel_df: Personnel data DataFrame

    Returns:
        DataFrame with mainline summary
    """
    if vacuum_df.empty:
        return pd.DataFrame()

    # Find sensor name column
    sensor_col = 'Sensor Name' if 'Sensor Name' in vacuum_df.columns else None
    if not sensor_col:
        return pd.DataFrame()

    # Aggregate vacuum data by mainline
    vacuum_summary = vacuum_df.groupby(sensor_col).agg({
        'Vacuum Reading': ['mean', 'min', 'max', 'count'],
        'Timestamp': 'max'
    }).reset_index()

    # Flatten column names
    vacuum_summary.columns = ['Mainline', 'Avg_Vacuum', 'Min_Vacuum', 'Max_Vacuum',
                              'Reading_Count', 'Last_Reading']

    # Add personnel data if available
    if not personnel_df.empty and 'mainline' in personnel_df.columns:
        personnel_summary = personnel_df.groupby('mainline').agg({
            'Hours': 'sum',
            'Employee Name': 'nunique',
            'Taps Put In': 'sum',
            'Taps Removed': 'sum',
            'Repairs needed': 'sum',
            'Date': 'max'
        }).reset_index()

        personnel_summary.columns = ['Mainline', 'Total_Hours', 'Employee_Count',
                                     'Taps_Installed', 'Taps_Removed', 'Repairs',
                                     'Last_Activity']

        # Merge summaries
        summary = pd.merge(vacuum_summary, personnel_summary, on='Mainline', how='left')
    else:
        summary = vacuum_summary
        summary['Total_Hours'] = 0
        summary['Employee_Count'] = 0
        summary['Taps_Installed'] = 0
        summary['Taps_Removed'] = 0
        summary['Repairs'] = 0
        summary['Last_Activity'] = None

    # Fill NaN values
    numeric_cols = ['Total_Hours', 'Employee_Count', 'Taps_Installed', 'Taps_Removed', 'Repairs']
    for col in numeric_cols:
        if col in summary.columns:
            summary[col] = summary[col].fillna(0)

    # Add status column
    summary['Status'] = summary['Avg_Vacuum'].apply(config.get_vacuum_status)
    summary['Status_Emoji'] = summary['Avg_Vacuum'].apply(config.get_vacuum_emoji)

    # Add needs attention flag
    summary['Needs_Attention'] = summary.apply(
        lambda row: 'Yes' if row['Avg_Vacuum'] < config.VACUUM_FAIR or row['Employee_Count'] == 0 else 'No',
        axis=1
    )

    # Sort by average vacuum (worst first)
    summary = summary.sort_values('Avg_Vacuum')

    return summary


def calculate_employee_performance(personnel_df, vacuum_df=None):
    """
    Calculate performance metrics for each employee

    Args:
        personnel_df: Personnel data DataFrame
        vacuum_df: Optional vacuum data for improvement calculations

    Returns:
        DataFrame with employee performance metrics
    """
    if personnel_df.empty:
        return pd.DataFrame()

    # Aggregate by employee
    employee_summary = personnel_df.groupby('Employee Name').agg({
        'Employee ID': 'first',
        'Hours': 'sum',
        'mainline': lambda x: x.nunique(),  # Distinct mainlines visited
        'Taps Put In': 'sum',
        'Taps Removed': 'sum',
        'Repairs needed': 'sum'
    }).reset_index()

    employee_summary.columns = ['Employee_Name', 'Employee_ID', 'Total_Hours',
                                'Mainlines_Visited', 'Taps_Installed',
                                'Taps_Removed', 'Repairs']

    # Calculate efficiency metrics (with zero-division protection)
    employee_summary['Hours_Per_Mainline'] = (
            employee_summary['Total_Hours'] / employee_summary['Mainlines_Visited'].replace(0, pd.NA)
    ).round(config.DECIMAL_PLACES['hours'])

    # Calculate efficiency score (placeholder - you can customize this)
    # Higher is better: more mainlines visited per hour
    employee_summary['Efficiency_Score'] = (
            employee_summary['Mainlines_Visited'] / employee_summary['Total_Hours'].replace(0, pd.NA) * config.EFFICIENCY_MULTIPLIER
    ).round(config.DECIMAL_PLACES['efficiency'])

    # Filter out employees with very few hours (to avoid skewed rankings)
    employee_summary = employee_summary[
        employee_summary['Total_Hours'] >= config.MIN_HOURS_FOR_RANKING
        ]

    # Sort by total hours (most active first)
    employee_summary = employee_summary.sort_values('Total_Hours', ascending=False)

    return employee_summary


def calculate_maintenance_effectiveness(personnel_df, vacuum_df):
    """
    Calculate effectiveness of maintenance activities

    Args:
        personnel_df: Personnel data DataFrame
        vacuum_df: Vacuum data DataFrame

    Returns:
        DataFrame with maintenance effectiveness metrics
    """
    # This is a simplified version
    # A more sophisticated version would track vacuum levels before/after specific visits

    if personnel_df.empty or vacuum_df.empty:
        return pd.DataFrame()

    # Get locations where repairs were done
    repairs = personnel_df[personnel_df['Repairs needed'] > 0].copy()

    if repairs.empty:
        return pd.DataFrame()

    # Group by mainline
    maintenance = repairs.groupby('mainline').agg({
        'Date': 'max',
        'Employee Name': 'first',
        'Hours': 'sum',
        'Repairs needed': 'sum'
    }).reset_index()

    maintenance.columns = ['Mainline', 'Last_Repair_Date', 'Employee',
                           'Hours_Spent', 'Repairs_Count']

    return maintenance


def calculate_problem_areas(vacuum_df, personnel_df):
    """
    Identify areas that need attention

    Args:
        vacuum_df: Vacuum data DataFrame
        personnel_df: Personnel data DataFrame

    Returns:
        DataFrame with problem areas ranked by urgency
    """
    if vacuum_df.empty:
        return pd.DataFrame()

    # Get mainline summary
    summary = calculate_mainline_summary(vacuum_df, personnel_df)

    if summary.empty:
        return pd.DataFrame()

    # Filter to problem areas only
    problems = summary[summary['Avg_Vacuum'] < config.VACUUM_FAIR].copy()

    # Calculate urgency score
    # Lower vacuum = more urgent
    # Longer since last activity = more urgent
    problems['Urgency_Score'] = (config.VACUUM_FAIR - problems['Avg_Vacuum']) * 10

    if 'Last_Activity' in problems.columns:
        # Add days since last activity to urgency
        problems['Days_Since_Activity'] = problems['Last_Activity'].apply(
            lambda x: (datetime.now() - pd.to_datetime(x)).days if pd.notna(x) else 999
        )
        problems['Urgency_Score'] += problems['Days_Since_Activity']

    # Sort by urgency (highest first)
    problems = problems.sort_values('Urgency_Score', ascending=False)

    return problems


def calculate_daily_trends(vacuum_df, days=7):
    """
    Calculate daily trend statistics

    Args:
        vacuum_df: Vacuum data DataFrame
        days: Number of days to analyze

    Returns:
        DataFrame with daily statistics
    """
    if vacuum_df.empty or 'Date' not in vacuum_df.columns:
        return pd.DataFrame()

    # Filter to recent days
    cutoff_date = datetime.now().date() - timedelta(days=days)
    recent = vacuum_df[vacuum_df['Date'] >= cutoff_date]

    if recent.empty:
        return pd.DataFrame()

    # Aggregate by date
    daily = recent.groupby('Date').agg({
        'Vacuum Reading': ['mean', 'min', 'max'],
        'Sensor Name': 'nunique'
    }).reset_index()

    daily.columns = ['Date', 'Avg_Vacuum', 'Min_Vacuum', 'Max_Vacuum', 'Active_Sensors']

    # Sort by date
    daily = daily.sort_values('Date')

    return daily


def get_top_performers(employee_df, n=None):
    """
    Get top performing employees

    Args:
        employee_df: Employee performance DataFrame
        n: Number of top performers to return (None = all)

    Returns:
        DataFrame with top N performers
    """
    if employee_df.empty:
        return pd.DataFrame()

    n = n or config.TOP_PERFORMERS_COUNT

    # Sort by efficiency score
    top = employee_df.sort_values('Efficiency_Score', ascending=False).head(n)

    return top


def get_bottom_performers(employee_df, n=None):
    """
    Get bottom performing employees (for coaching opportunities)

    Args:
        employee_df: Employee performance DataFrame
        n: Number of bottom performers to return (None = default)

    Returns:
        DataFrame with bottom N performers
    """
    if employee_df.empty:
        return pd.DataFrame()

    n = n or config.TOP_PERFORMERS_COUNT

    # Sort by efficiency score (lowest first)
    bottom = employee_df.sort_values('Efficiency_Score', ascending=True).head(n)

    return bottom


def calculate_employee_effectiveness(personnel_df, vacuum_df):
    """
    Calculate vacuum improvement for each employee's work

    UPDATED: Now uses daily averages and filters out invalid readings!
    - Compares average vacuum day before work vs day after work
    - Ignores vacuum readings of 0 (sensor offline/error)
    - More robust to timestamp issues

    Args:
        personnel_df: Personnel/timesheet data DataFrame
        vacuum_df: Vacuum sensor data DataFrame

    Returns:
        DataFrame with columns:
            - Employee: Employee name
            - Date: Work date
            - Mainline: Location worked
            - Vacuum_Before: Average vacuum day before work
            - Vacuum_After: Average vacuum day after work
            - Improvement: Change in vacuum (positive = improvement)
            - Hours: Hours worked (if available)

        DataFrame also includes 'debug_info' attribute with matching statistics
    """
    from utils import find_column, get_vacuum_column
    from datetime import timedelta

    if personnel_df.empty or vacuum_df.empty:
        return pd.DataFrame()

    # Find required columns
    emp_name_col = find_column(personnel_df, 'Employee Name', 'employee', 'EE First', 'EE Last')
    emp_date_col = find_column(personnel_df, 'Date', 'date', 'timestamp')
    # Personnel file uses "mainline." (with period!) for the location
    emp_mainline_col = find_column(personnel_df, 'mainline.', 'mainline', 'Mainline', 'location', 'sensor', 'Name')
    emp_hours_col = find_column(personnel_df, 'Hours', 'hours', 'time')

    # Vacuum file uses "Name" for the location
    vac_mainline_col = find_column(
        vacuum_df,
        'Name', 'name', 'mainline', 'Sensor Name', 'sensor', 'location', 'mainline.'
    )
    vac_reading_col = get_vacuum_column(vacuum_df)
    vac_timestamp_col = find_column(
        vacuum_df,
        'Last communication', 'Last Communication', 'Timestamp', 'timestamp', 'time', 'datetime'
    )

    # Debug: store column mapping
    debug_cols = {
        'personnel': {
            'employee': emp_name_col,
            'date': emp_date_col,
            'mainline': emp_mainline_col,
            'hours': emp_hours_col
        },
        'vacuum': {
            'mainline': vac_mainline_col,
            'reading': vac_reading_col,
            'timestamp': vac_timestamp_col
        }
    }

    if not all([emp_name_col, emp_date_col, emp_mainline_col, vac_mainline_col, vac_reading_col, vac_timestamp_col]):
        # Return empty with debug info about missing columns
        empty_df = pd.DataFrame()
        empty_df.attrs['debug_info'] = {
            'missing_columns': True,
            'column_mapping': debug_cols,
            'personnel_mainlines': set(),
            'vacuum_mainlines': set(),
            'matching_mainlines': set(),
            'no_match_count': 0,
            'no_before_count': 0,
            'no_after_count': 0,
            'success_count': 0,
            'total_work_sessions': 0
        }
        return empty_df

    # Prepare personnel data
    personnel = personnel_df[[emp_name_col, emp_date_col, emp_mainline_col]].copy()
    if emp_hours_col:
        personnel['Hours'] = personnel_df[emp_hours_col]

    personnel.columns = ['Employee', 'Work_Date', 'Mainline', 'Hours'] if emp_hours_col else ['Employee', 'Work_Date',
                                                                                              'Mainline']
    personnel['Work_Date'] = pd.to_datetime(personnel['Work_Date'], errors='coerce')
    personnel = personnel.dropna(subset=['Work_Date'])

    # Normalize mainline names (strip whitespace, consistent case)
    personnel['Mainline'] = personnel['Mainline'].astype(str).str.strip().str.upper()

    # Prepare vacuum data
    vacuum = vacuum_df[[vac_mainline_col, vac_reading_col, vac_timestamp_col]].copy()
    vacuum.columns = ['Mainline', 'Vacuum', 'Timestamp']
    vacuum['Timestamp'] = pd.to_datetime(vacuum['Timestamp'], errors='coerce')
    vacuum = vacuum.dropna(subset=['Timestamp'])

    # Normalize mainline names in vacuum data too
    vacuum['Mainline'] = vacuum['Mainline'].astype(str).str.strip().str.upper()

    # Convert vacuum to numeric
    vacuum['Vacuum'] = pd.to_numeric(vacuum['Vacuum'], errors='coerce')
    vacuum = vacuum.dropna(subset=['Vacuum'])

    # ⭐ FILTER OUT INVALID READINGS (sensor errors, offline sensors)
    # Remove readings of 0 or very low values that indicate sensor problems
    vacuum = vacuum[vacuum['Vacuum'] > 1.0]  # Keep only readings > 1"

    # Add date column for daily averaging
    vacuum['Date'] = vacuum['Timestamp'].dt.date

    # Get unique mainlines from both datasets for debugging
    personnel_mainlines = set(personnel['Mainline'].unique())
    vacuum_mainlines = set(vacuum['Mainline'].unique())
    matching_mainlines = personnel_mainlines & vacuum_mainlines

    # Calculate improvements
    results = []
    no_match_count = 0
    no_before_count = 0
    no_after_count = 0
    success_count = 0

    for idx, work in personnel.iterrows():
        employee = work['Employee']
        work_date = work['Work_Date']
        work_date_only = work_date.date()
        mainline = work['Mainline']

        # Get vacuum readings for this mainline
        mainline_vacuum = vacuum[vacuum['Mainline'] == mainline].copy()

        if mainline_vacuum.empty:
            no_match_count += 1
            continue

        # ⭐ USE DAILY AVERAGES instead of closest readings
        # Compare the day BEFORE work vs the day AFTER work

        # Get average vacuum for the day before work
        before_date = work_date_only - timedelta(days=1)
        before_readings = mainline_vacuum[mainline_vacuum['Date'] == before_date]

        # If no data on day before, try 2 days before
        if before_readings.empty:
            before_date = work_date_only - timedelta(days=2)
            before_readings = mainline_vacuum[mainline_vacuum['Date'] == before_date]

        if before_readings.empty:
            no_before_count += 1
            continue

        # Get average vacuum for the day after work
        after_date = work_date_only + timedelta(days=1)
        after_readings = mainline_vacuum[mainline_vacuum['Date'] == after_date]

        # If no data on day after, try 2 days after
        if after_readings.empty:
            after_date = work_date_only + timedelta(days=2)
            after_readings = mainline_vacuum[mainline_vacuum['Date'] == after_date]

        if after_readings.empty:
            no_after_count += 1
            continue

        # Calculate average vacuum for before and after periods
        vac_before = before_readings['Vacuum'].mean()
        vac_after = after_readings['Vacuum'].mean()

        improvement = vac_after - vac_before

        result = {
            'Employee': employee,
            'Date': work_date,
            'Mainline': mainline,
            'Vacuum_Before': vac_before,
            'Vacuum_After': vac_after,
            'Improvement': improvement
        }

        if 'Hours' in work:
            result['Hours'] = work['Hours']

        results.append(result)
        success_count += 1

    # Store debug info for display
    debug_info = {
        'personnel_mainlines': personnel_mainlines,
        'vacuum_mainlines': vacuum_mainlines,
        'matching_mainlines': matching_mainlines,
        'no_match_count': no_match_count,
        'no_before_count': no_before_count,
        'no_after_count': no_after_count,
        'success_count': success_count,
        'total_work_sessions': len(personnel)
    }

    if results:
        result_df = pd.DataFrame(results)
        # Store debug info in a way we can access it
        result_df.attrs['debug_info'] = debug_info
        return result_df
    else:
        # Return empty with debug info
        empty_df = pd.DataFrame()
        empty_df.attrs['debug_info'] = debug_info
        return empty_df


def format_metric_value(value, metric_type):
    """
    Format a metric value for display

    Args:
        value: The numeric value
        metric_type: Type of metric ('vacuum', 'hours', 'efficiency', etc.)

    Returns:
        Formatted string
    """
    if pd.isna(value):
        return "N/A"

    decimals = config.DECIMAL_PLACES.get(metric_type, 1)

    if metric_type == 'vacuum':
        return f"{value:.{decimals}f}\""
    elif metric_type == 'hours':
        return f"{value:.{decimals}f}h"
    elif metric_type in ['efficiency', 'improvement']:
        return f"{value:+.{decimals}f}"
    else:
        return f"{value:.{decimals}f}"