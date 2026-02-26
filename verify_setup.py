#!/usr/bin/env python3
"""
Dashboard Setup Verification Script
Run this to verify your dashboard is properly set up
"""

import os
import sys


def check_file(filepath, description):
    """Check if a file exists"""
    exists = os.path.exists(filepath)
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {filepath}")
    return exists


def check_directory(dirpath, description):
    """Check if a directory exists"""
    exists = os.path.isdir(dirpath)
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {dirpath}")
    return exists


def check_import(module_name, description):
    """Check if a module can be imported"""
    try:
        __import__(module_name)
        print(f"✓ {description}: {module_name}")
        return True
    except ImportError as e:
        print(f"✗ {description}: {module_name} - {e}")
        return False


def main():
    print("=" * 60)
    print("Forest Farmers Dashboard - Setup Verification")
    print("=" * 60)
    print()

    all_good = True

    # Check directory structure
    print("📁 Directory Structure:")
    print("-" * 60)
    all_good &= check_directory("page_modules", "Page modules directory")
    all_good &= check_directory("utils", "Utilities directory")
    print()

    # Check main files
    print("📄 Main Files:")
    print("-" * 60)
    all_good &= check_file("dashboard.py", "Dashboard main file")
    all_good &= check_file("config.py", "Configuration file")
    all_good &= check_file("data_loader.py", "Data loader")
    all_good &= check_file("metrics.py", "Metrics module")
    print()

    # Check page files
    print("📄 Page Modules:")
    print("-" * 60)
    all_good &= check_file("page_modules/__init__.py", "Page modules init file")
    all_good &= check_file("page_modules/vacuum.py", "Vacuum performance page")
    all_good &= check_file("page_modules/tapping.py", "Tapping operations page")
    all_good &= check_file("page_modules/employees.py", "Employees page")
    all_good &= check_file("page_modules/employee_effectiveness.py", "Employee effectiveness")
    all_good &= check_file("page_modules/sensor_map.py", "Interactive sensor map")
    all_good &= check_file("page_modules/sap_forecast.py", "Sap flow forecast")
    all_good &= check_file("page_modules/maintenance.py", "Maintenance tracking")
    all_good &= check_file("page_modules/raw_data.py", "Raw data page")
    all_good &= check_file("page_modules/data_quality.py", "Data quality / alerts page")
    all_good &= check_file("page_modules/repairs_analysis.py", "Repairs analysis page")
    all_good &= check_file("page_modules/tap_history.py", "Tap history page")
    all_good &= check_file("page_modules/manager_review.py", "Manager data review page")
    all_good &= check_file("page_modules/freezing_report.py", "Freezing report page")
    all_good &= check_file("page_modules/temperature_productivity.py", "Temperature productivity page")
    print()

    # Check utility files
    print("📄 Utility Modules:")
    print("-" * 60)
    all_good &= check_file("utils/__init__.py", "Utils init file")
    all_good &= check_file("utils/helpers.py", "Helper utilities")
    all_good &= check_file("utils/geographic.py", "Geographic utilities")
    all_good &= check_file("utils/freeze_thaw.py", "Freeze/thaw utilities")
    print()

    # Check configuration files
    print("⚙️  Configuration Files:")
    print("-" * 60)
    env_exists = check_file(".env", "Environment variables")
    creds_exists = check_file("credentials.json", "Google credentials")
    all_good &= env_exists and creds_exists
    print()

    # Check Python dependencies
    print("📦 Python Dependencies:")
    print("-" * 60)
    all_good &= check_import("streamlit", "Streamlit")
    all_good &= check_import("pandas", "Pandas")
    all_good &= check_import("gspread", "GSpread")
    all_good &= check_import("google.oauth2", "Google Auth")
    all_good &= check_import("numpy", "NumPy")
    all_good &= check_import("dotenv", "Python-dotenv")
    all_good &= check_import("plotly", "Plotly (for charts)")
    all_good &= check_import("folium", "Folium (for maps)")
    all_good &= check_import("requests", "Requests (for weather API)")
    all_good &= check_import("fpdf2", "FPDF2 (for PDF export)")
    print()

    # Try importing page modules
    print("🔌 Page Module Imports:")
    print("-" * 60)
    try:
        from page_modules import (
            vacuum, tapping, employees, employee_effectiveness,
            raw_data, sensor_map, sap_forecast, maintenance,
            data_quality, repairs_analysis, tap_history,
            manager_review, freezing_report, temperature_productivity
        )
        print("✓ All page modules imported successfully")

        # Check render functions
        modules = [
            (vacuum, 'vacuum'),
            (tapping, 'tapping'),
            (employees, 'employees'),
            (employee_effectiveness, 'employee_effectiveness'),
            (sensor_map, 'sensor_map'),
            (sap_forecast, 'sap_forecast'),
            (maintenance, 'maintenance'),
            (data_quality, 'data_quality'),
            (repairs_analysis, 'repairs_analysis'),
            (tap_history, 'tap_history'),
            (manager_review, 'manager_review'),
            (freezing_report, 'freezing_report'),
            (temperature_productivity, 'temperature_productivity'),
            (raw_data, 'raw_data'),
        ]

        for module, name in modules:
            has_render = hasattr(module, 'render')
            status = "✓" if has_render else "✗"
            print(f"{status} {name}.render() function exists")
            all_good &= has_render

    except ImportError as e:
        print(f"✗ Failed to import page modules: {e}")
        all_good = False
    print()

    # Final summary
    print("=" * 60)
    if all_good:
        print("✅ All checks passed! Your dashboard is ready to run.")
        print()
        print("To start the dashboard, run:")
        print("    streamlit run dashboard.py")
    else:
        print("⚠️  Some checks failed. Please review the output above.")
        print()
        print("Common fixes:")
        print("1. Make sure you're in the correct directory")
        print("2. Install missing dependencies: pip install -r requirements.txt")
        print("3. Create .env file with your Google Sheets URLs")
        print("4. Add credentials.json file from Google Cloud Console")
    print("=" * 60)

    return 0 if all_good else 1


if __name__ == "__main__":
    sys.exit(main())
