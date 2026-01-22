"""
Page Modules Package
Contains all dashboard pages as separate modules
Each page has a render() function that takes vacuum_df and personnel_df

Note: This directory is named 'page_modules' (not 'pages') to avoid
Streamlit's automatic multi-page app detection.
"""

from . import vacuum, tapping, employees, employee_effectiveness, raw_data, sensor_map, sap_forecast, maintenance, data_quality, repairs_analysis

__all__ = [
    'vacuum',
    'employees',
    'employee_effectiveness',
    'raw_data',
    'sensor_map',
    'data_quality',
    'sap_forecast',
    'maintenance',
    'tapping',
    'repairs_analysis'
]
