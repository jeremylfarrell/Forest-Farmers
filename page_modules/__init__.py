"""
Page Modules Package
Contains all dashboard pages as separate modules
Each page has a render() function that takes vacuum_df and personnel_df

Note: This directory is named 'page_modules' (not 'pages') to avoid
Streamlit's automatic multi-page app detection.
"""

from . import vacuum, tapping, employees, employee_effectiveness, problem_clusters, raw_data, sensor_map, sap_forecast, maintenance, daily_summary

__all__ = [
    'vacuum',
    'employees',
    'employee_effectiveness',
    'problem_clusters',
    'raw_data',
    'sensor_map',
    'sap_forecast',
    'maintenance',
    'daily_summary'
    'tapping'
]