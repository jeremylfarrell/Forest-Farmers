"""
Forest Farmers Vacuum Monitoring Dashboard
Main application entry point - refactored and modular

This is the main dashboard file that orchestrates all pages and data loading.
All complex logic has been moved to separate modules for better maintainability.

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

# Import page modules
from page_modules import vacuum, employees, employee_effectiveness, problem_clusters, raw_data, sensor_map, sap_forecast, maintenance, daily_summary, tapping


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
    """
    vacuum_url = None
    personnel_url = None
    credentials_path = 'credentials.json'
    
    # Try Streamlit secrets first (for Streamlit Cloud)
    try:
        # Check if we have Streamlit secrets available
        if hasattr(st, 'secrets'):
            # Access root-level secrets directly (not with .get())
            if "VACUUM_SHEET_URL" in st.secrets:
                vacuum_url = st.secrets["VACUUM_SHEET_URL"]
            if "PERSONNEL_SHEET_URL" in st.secrets:
                personnel_url = st.secrets["PERSONNEL_SHEET_URL"]
            
            if vacuum_url and personnel_url:
                # Successfully got both URLs from secrets
                return vacuum_url, personnel_url, credentials_path
    except Exception as e:
        # Secrets not available or error accessing them
        pass
    
    # Fall back to .env file (for local development)
    try:
        from dotenv import load_dotenv
        load_dotenv()
        vacuum_url = os.getenv('VACUUM_SHEET_URL')
        personnel_url = os.getenv('PERSONNEL_SHEET_URL')
        
        if vacuum_url and personnel_url:
            # Running locally with .env file
            return vacuum_url, personnel_url, credentials_path
    except ImportError:
        # python-dotenv not installed (that's ok on Streamlit Cloud)
        pass
    
    # If we get here, configuration is missing
    return None, None, credentials_path


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
                "📱 Daily Summary",
                "🔧 Vacuum Performance",
                "🌳 Tapping Operations",
                "👥 Employee Performance",
                "⭐ Employee Effectiveness",
                "🔧 Maintenance & Leaks",
                "🗺️ Problem Clusters",
                "🌍 Interactive Map",
                "🌡️ Sap Flow Forecast",
                "📊 Raw Data"
            ],
            label_visibility="collapsed"
        )

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
        st.caption(f"v4.2 | {datetime.now().strftime('%H:%M:%S')}")
        st.caption("💾 Data cached for 1 hour")
        st.caption("Click 'Refresh Data' to reload")

    return page, days_to_load, recent_threshold


# ============================================================================
# DATA LOADING
# ============================================================================

def load_data(days_to_load):
    """Load data from Google Sheets"""

    # Load configuration (works for both local and cloud!)
    vacuum_url, personnel_url, credentials = load_config()

    # Validate configuration
    if not vacuum_url or not personnel_url:
        st.error("⚠️ Configuration Error")
        st.info("""
        **For Streamlit Cloud:** Add these to your app secrets:
        ```
        VACUUM_SHEET_URL = "your-vacuum-sheet-url"
        PERSONNEL_SHEET_URL = "your-personnel-sheet-url"
        ```
        
        **For Local Development:** Create a `.env` file with:
        ```
        VACUUM_SHEET_URL=your-vacuum-sheet-url
        PERSONNEL_SHEET_URL=your-personnel-sheet-url
        ```
        """)
        st.stop()

    # Check for credentials (local file check - on cloud this is handled by secrets)
    if not os.path.exists(credentials):
        # On Streamlit Cloud, credentials come from secrets, not a file
        # So this is only a warning for local development
        st.warning(f"⚠️ Note: Local credentials file '{credentials}' not found")
        st.info("On Streamlit Cloud, credentials should be in your app secrets under [gcp_service_account]")

    # Load data with progress indication
    with st.spinner('Loading data from Google Sheets...'):
        try:
            vacuum_df = load_all_vacuum_data(vacuum_url, credentials, days=days_to_load)
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
            sensor_col = find_column(vacuum_df, 'Sensor Name', 'sensor', 'mainline', 'location', 'name')
            if sensor_col:
                st.write(f"- Unique sensors: {vacuum_df[sensor_col].nunique()}")
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
            mainline_col = find_column(personnel_df, 'mainline', 'Mainline', 'location', 'sensor')
            if mainline_col:
                st.write(f"- Unique locations worked: {personnel_df[mainline_col].nunique()}")
        else:
            st.write("- No data loaded")


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application entry point"""

    # Render sidebar and get selections
    page, days_to_load, recent_threshold = render_sidebar()

    # Load data
    vacuum_df, personnel_df = load_data(days_to_load)

    # Show data loading info
    show_data_info(vacuum_df, personnel_df)

    # Apply recent sensor filter if enabled
    if recent_threshold is not None:
        original_sensors = 0
        if not vacuum_df.empty:
            sensor_col = find_column(vacuum_df, 'Sensor Name', 'sensor', 'mainline', 'location', 'name')
            if sensor_col:
                original_sensors = vacuum_df[sensor_col].nunique()

        vacuum_df = filter_recent_sensors(vacuum_df, recent_threshold)

        if original_sensors > 0 and not vacuum_df.empty:
            sensor_col = find_column(vacuum_df, 'Sensor Name', 'sensor', 'mainline', 'location', 'name')
            if sensor_col:
                filtered_sensors = vacuum_df[sensor_col].nunique()
                if filtered_sensors < original_sensors:
                    st.info(
                        f"📊 Showing {filtered_sensors} sensors active in last {recent_threshold} days "
                        f"(filtered out {original_sensors - filtered_sensors} inactive)"
                    )

    # Route to selected page
    if page == "📱 Daily Summary":
        daily_summary.render(vacuum_df, personnel_df)
    elif page == "🔧 Vacuum Performance":
        vacuum.render(vacuum_df, personnel_df)
    elif page == "🌳 Tapping Operations":
        tapping.render(personnel_df, vacuum_df)
    elif page == "👥 Employee Performance":
        employees.render(personnel_df)
    elif page == "⭐ Employee Effectiveness":
        employee_effectiveness.render(personnel_df, vacuum_df)
    elif page == "🔧 Maintenance & Leaks":
        maintenance.render(vacuum_df, personnel_df)
    elif page == "🗺️ Problem Clusters":
        problem_clusters.render(vacuum_df)
    elif page == "🌍 Interactive Map":
        sensor_map.render(vacuum_df, personnel_df)
    elif page == "🌡️ Sap Flow Forecast":
        sap_forecast.render(vacuum_df, personnel_df)
    elif page == "📊 Raw Data":
        raw_data.render(vacuum_df, personnel_df)


if __name__ == "__main__":
    main()
