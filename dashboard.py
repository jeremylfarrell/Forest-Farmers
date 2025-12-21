"""
Forest Farmers Vacuum Monitoring Dashboard - MULTI-SITE VERSION
Main application entry point - refactored and modular

This is the main dashboard file that orchestrates all pages and data loading.
All complex logic has been moved to separate modules for better maintainability.

MULTI-SITE: Supports NY and VT operations with site filtering
UPDATED: Now works with both local .env files AND Streamlit Cloud secrets!
"""

import streamlit as st
import os
from datetime import datetime

# Import configuration
import config

# Import data loading
from data_loader import load_all_vacuum_data, load_all_personnel_data

# Import utility functions
from utils import filter_recent_sensors, find_column

# Import custom styling
from styling import apply_custom_css

from page_modules import (
    vacuum, 
    employees, 
    employee_effectiveness, 
    raw_data, 
    sensor_map, 
    sap_forecast, 
    maintenance, 
    tapping, 
    data_quality
)
#password
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["passwords"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password
        st.text_input(
            "🔒 Password",
            type="password",
            on_change=password_entered,
            key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error
        st.text_input(
            "🔒 Password",
            type="password",
            on_change=password_entered,
            key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct
        return True

# Check password before showing dashboard
if not check_password():
    st.stop()  # Don't continue if password is wrong


# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title=config.PAGE_TITLE,
    page_icon=config.PAGE_ICON,
    layout=config.PAGE_LAYOUT,
    initial_sidebar_state="expanded"
)


# ============================================================================
# CONFIGURATION LOADING (Works for both local and cloud!)
# ============================================================================

def load_config():
    """
    Load configuration from either Streamlit secrets (cloud) or .env file (local)
    Tries secrets first, falls back to .env

    Returns:
        Tuple of (ny_vacuum_url, vt_vacuum_url, personnel_url, credentials_path)
    """
    ny_vacuum_url = None
    vt_vacuum_url = None
    personnel_url = None
    credentials_path = 'credentials.json'

    # Try Streamlit secrets first (for Streamlit Cloud)
    try:
        # Check if we have Streamlit secrets available
        if hasattr(st, 'secrets') and 'sheets' in st.secrets:
            # Access sheet URLs from [sheets] section
            ny_vacuum_url = st.secrets["sheets"]["NY_VACUUM_SHEET_URL"]
            vt_vacuum_url = st.secrets["sheets"]["VT_VACUUM_SHEET_URL"]
            personnel_url = st.secrets["sheets"]["PERSONNEL_SHEET_URL"]

            if ny_vacuum_url and vt_vacuum_url and personnel_url:
                # Successfully got all URLs from secrets
                return ny_vacuum_url, vt_vacuum_url, personnel_url, credentials_path
    except Exception as e:
        # Secrets not available or error accessing them
        pass

    # Fall back to .env file (for local development)
    try:
        from dotenv import load_dotenv
        load_dotenv()
        ny_vacuum_url = os.getenv('NY_VACUUM_SHEET_URL')
        vt_vacuum_url = os.getenv('VT_VACUUM_SHEET_URL')
        personnel_url = os.getenv('PERSONNEL_SHEET_URL')

        if ny_vacuum_url and vt_vacuum_url and personnel_url:
            # Running locally with .env file
            return ny_vacuum_url, vt_vacuum_url, personnel_url, credentials_path
    except ImportError:
        # python-dotenv not installed (that's ok on Streamlit Cloud)
        pass

    # If we get here, configuration is missing
    return None, None, None, credentials_path


# Apply custom styling
apply_custom_css()


# ============================================================================
# SIDEBAR
# ============================================================================

def render_sidebar():
    """Render the sidebar with navigation and filters"""

    with st.sidebar:
        st.title("🍁 Forest Farmers Dashboard")

        # Page selection - PRIMARY NAVIGATION
        st.subheader("📄 Pages")
        page = st.radio(
            "Select Page",
            [
                "🔧 Vacuum Performance",
                "🌳 Tapping Operations",
                "👥 Employee Performance",
                "⭐ Leak Checking",
                "🔧 Maintenance & Leaks",
                "⚠️ Alerts",
                "🌍 Interactive Map",
                "🌡️ Sap Flow Forecast",
                "📊 Raw Data"
            ],
            label_visibility="collapsed"
        )

        st.divider()

        # SITE FILTER - NEW!
        st.subheader("🏢 Site Selection")
        site_filter = st.selectbox(
            "Select site:",
            options=["All Sites", "NY", "VT", "UNK"],
            index=0,
            help="Filter data by site location"
        )

        if site_filter == "All Sites":
            st.caption("📊 Showing combined NY + VT data")
        elif site_filter == "NY":
            st.caption("🟦 New York operations only")
        elif site_filter == "VT":
            st.caption("🟩 Vermont operations only")
        else:
            st.caption("⚫ Unknown/unclassified locations")

        st.divider()

        # Data range filter
        st.subheader("⏱️ Data Range")
        days_to_load = st.selectbox(
            "Show last:",
            options=[7, 14, 30, 60, 90],
            index=0,
            format_func=lambda x: f"{x} days"
        )

        st.caption(
            "💡 Employee Effectiveness always loads 30+ days for accurate comparisons"
        )

        st.divider()

        # Vacuum filters
        st.subheader("🔧 Vacuum Filters")
        only_recent_sensors = st.checkbox("Only recently active sensors", value=True)
        if only_recent_sensors:
            recent_threshold = st.slider(
                "Active within:",
                min_value=1,
                max_value=7,
                value=2,
                format="%d days"
            )
        else:
            recent_threshold = None

        st.divider()

        # Actions
        if st.button("🔄 Refresh Data", use_container_width=True):
            # Clear all cached data
            st.cache_data.clear()
            st.rerun()

        st.divider()

        # Footer info
        st.caption(f"v5.0 Multi-Site | {datetime.now().strftime('%H:%M:%S')}")
        st.caption("💾 Data cached for 1 hour")
        st.caption("Click 'Refresh Data' to reload")

    return page, days_to_load, recent_threshold, site_filter


# ============================================================================
# DATA LOADING
# ============================================================================

def load_data(days_to_load):
    """Load data from Google Sheets"""

    # Load configuration (works for both local and cloud!)
    ny_vacuum_url, vt_vacuum_url, personnel_url, credentials = load_config()

    # Validate configuration
    if not ny_vacuum_url or not vt_vacuum_url or not personnel_url:
        st.error("⚠️ Configuration Error")
        st.info("""
        **For Streamlit Cloud:** Add these to your app secrets:
        ```
        [sheets]
        NY_VACUUM_SHEET_URL = "your-ny-vacuum-sheet-url"
        VT_VACUUM_SHEET_URL = "your-vt-vacuum-sheet-url"
        PERSONNEL_SHEET_URL = "your-personnel-sheet-url"
        ```
        
        **For Local Development:** Create a `.env` file with:
        ```
        NY_VACUUM_SHEET_URL=your-ny-vacuum-sheet-url
        VT_VACUUM_SHEET_URL=your-vt-vacuum-sheet-url
        PERSONNEL_SHEET_URL=your-personnel-sheet-url
        ```
        """)
        st.stop()

    # Load data with progress indication
    with st.spinner('Loading data from Google Sheets...'):
        try:
            vacuum_df = load_all_vacuum_data(ny_vacuum_url, vt_vacuum_url, credentials, days=days_to_load)
            personnel_df = load_all_personnel_data(personnel_url, credentials, days=days_to_load)
        except Exception as e:
            st.error(f"Error loading data: {str(e)}")
            st.error("Make sure your Google Sheets credentials are properly configured in Streamlit secrets!")
            st.stop()

    return vacuum_df, personnel_df


def show_data_info(vacuum_df, personnel_df):
    """Display data loading information"""

    with st.expander("📊 Data Loading Info", expanded=False):
        st.write("**Vacuum Data:**")
        if not vacuum_df.empty:
            st.write(f"- Total records: {len(vacuum_df):,}")
            if 'Date' in vacuum_df.columns:
                date_range = vacuum_df['Date'].agg(['min', 'max'])
                st.write(f"- Date range: {date_range['min']} to {date_range['max']}")
            sensor_col = find_column(vacuum_df, 'Sensor Name', 'sensor', 'mainline', 'location', 'name', 'Name')
            if sensor_col:
                st.write(f"- Unique sensors: {vacuum_df[sensor_col].nunique()}")
            if 'Site' in vacuum_df.columns:
                st.write(f"- NY sensors: {len(vacuum_df[vacuum_df['Site'] == 'NY'][sensor_col].unique()) if sensor_col else 'N/A'}")
                st.write(f"- VT sensors: {len(vacuum_df[vacuum_df['Site'] == 'VT'][sensor_col].unique()) if sensor_col else 'N/A'}")
        else:
            st.write("- No data loaded")

        st.write("**Personnel Data:**")
        if not personnel_df.empty:
            st.write(f"- Total records: {len(personnel_df):,}")
            if 'Date' in personnel_df.columns:
                date_range = personnel_df['Date'].agg(['min', 'max'])
                st.write(
                    f"- Date range: {date_range['min'].strftime('%Y-%m-%d') if hasattr(date_range['min'], 'strftime') else date_range['min']} to "
                    f"{date_range['max'].strftime('%Y-%m-%d') if hasattr(date_range['max'], 'strftime') else date_range['max']}"
                )
            emp_col = find_column(personnel_df, 'Employee Name', 'employee', 'name')
            if emp_col:
                st.write(f"- Unique employees: {personnel_df[emp_col].nunique()}")
            if 'Site' in personnel_df.columns:
                site_counts = personnel_df['Site'].value_counts()
                st.write(f"- NY work sessions: {site_counts.get('NY', 0)}")
                st.write(f"- VT work sessions: {site_counts.get('VT', 0)}")
                st.write(f"- Unknown site: {site_counts.get('UNK', 0)}")
        else:
            st.write("- No data loaded")


def filter_data_by_site(vacuum_df, personnel_df, site_filter):
    """
    Filter dataframes by selected site

    Args:
        vacuum_df: Vacuum data
        personnel_df: Personnel data
        site_filter: Selected site ("All Sites", "NY", "VT", "UNK")

    Returns:
        Tuple of (filtered_vacuum_df, filtered_personnel_df)
    """
    if site_filter == "All Sites":
        # Return all data
        return vacuum_df, personnel_df

    # Filter to specific site
    filtered_vacuum = vacuum_df[vacuum_df['Site'] == site_filter] if 'Site' in vacuum_df.columns else vacuum_df
    filtered_personnel = personnel_df[personnel_df['Site'] == site_filter] if 'Site' in personnel_df.columns else personnel_df

    return filtered_vacuum, filtered_personnel


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application entry point"""

    # Render sidebar and get selections
    page, days_to_load, recent_threshold, site_filter = render_sidebar()

    # Load data
    vacuum_df, personnel_df = load_data(days_to_load)

    # Show data loading info
    show_data_info(vacuum_df, personnel_df)

    # Filter by site
    vacuum_df, personnel_df = filter_data_by_site(vacuum_df, personnel_df, site_filter)

    # Show filtering info
    if site_filter != "All Sites":
        sensor_col = find_column(vacuum_df, 'Sensor Name', 'sensor', 'mainline', 'location', 'name', 'Name')
        if not vacuum_df.empty and sensor_col:
            sensor_count = vacuum_df[sensor_col].nunique()
            st.info(f"🏢 Viewing {site_filter} site only - {sensor_count} sensors")

    # Apply recent sensor filter if enabled
    if recent_threshold is not None:
        original_sensors = 0
        if not vacuum_df.empty:
            sensor_col = find_column(vacuum_df, 'Sensor Name', 'sensor', 'mainline', 'location', 'name', 'Name')
            if sensor_col:
                original_sensors = vacuum_df[sensor_col].nunique()

        vacuum_df = filter_recent_sensors(vacuum_df, recent_threshold)

        if original_sensors > 0 and not vacuum_df.empty:
            sensor_col = find_column(vacuum_df, 'Sensor Name', 'sensor', 'mainline', 'location', 'name', 'Name')
            if sensor_col:
                filtered_sensors = vacuum_df[sensor_col].nunique()
                if filtered_sensors < original_sensors:
                    st.info(
                        f"📊 Showing {filtered_sensors} sensors active in last {recent_threshold} days "
                        f"(filtered out {original_sensors - filtered_sensors} inactive)"
                    )

    # Route to selected page
    if page == "🔧 Vacuum Performance":
        vacuum.render(vacuum_df, personnel_df)
    elif page == "🌳 Tapping Operations":
        tapping.render(personnel_df, vacuum_df)
    elif page == "👥 Employee Performance":
        employees.render(personnel_df)
    elif page == "⭐ Leak Checking":
        employee_effectiveness.render(personnel_df, vacuum_df)
    elif page == "🔧 Maintenance & Leaks":
        maintenance.render(vacuum_df, personnel_df)
    elif page == "⚠️ Alerts":
        data_quality.render(personnel_df, vacuum_df)
    elif page == "🌍 Interactive Map":
        sensor_map.render(vacuum_df, personnel_df)
    elif page == "🌡️ Sap Flow Forecast":
        sap_forecast.render(vacuum_df, personnel_df)
    elif page == "📊 Raw Data":
        raw_data.render(vacuum_df, personnel_df)


if __name__ == "__main__":
    main()
