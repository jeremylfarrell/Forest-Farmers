"""
Forest Farmers Vacuum Monitoring Dashboard - MULTI-SITE VERSION
Main application entry point - refactored and modular

This is the main dashboard file that orchestrates all pages and data loading.
All complex logic has been moved to separate modules for better maintainability.

MULTI-SITE: Supports NY and VT operations with site selection on login
UPDATED: Clean sidebar - removed filters, auto-loads 60 days
"""

import streamlit as st
import os
import requests
from datetime import datetime

# Import configuration
import config

# Import data loading
from data_loader import (
    load_all_vacuum_data, load_all_personnel_data, load_repairs_tracker,
    load_approved_personnel, merge_approved_data,
    process_vacuum_data, process_personnel_data
)

# Import utility functions
from utils import find_column

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
    data_quality,
    repairs_analysis,
    tap_history,
    manager_review,
    freezing_report,
    temperature_productivity
)

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
# AUTHENTICATION & SITE SELECTION
# ============================================================================

def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if "password" not in st.session_state:
            return
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


def site_selection_screen():
    """Show site selection screen after successful password entry"""
    
    # Apply custom styling
    apply_custom_css()
    
    # Center column for better presentation
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title("🍁 Forest Farmers Dashboard")
        st.markdown("---")
        st.subheader("🏢 Select Your Site")
        st.markdown("Choose which operation you'd like to view:")
        
        # Site selection buttons
        col_ny, col_vt, col_both = st.columns(3)
        
        with col_ny:
            if st.button("🟦 **New York**\n\nNY Operations", use_container_width=True, key="btn_ny"):
                st.session_state["selected_site"] = "NY"
                st.rerun()
        
        with col_vt:
            if st.button("🟩 **Vermont**\n\nVT Operations", use_container_width=True, key="btn_vt"):
                st.session_state["selected_site"] = "VT"
                st.rerun()
        
        with col_both:
            if st.button("📊 **Both Sites**\n\nAll Operations", use_container_width=True, key="btn_both"):
                st.session_state["selected_site"] = "All Sites"
                st.rerun()
        
        st.markdown("---")
        st.caption("💡 You can change sites anytime using the button in the sidebar")


# Check password before showing anything
if not check_password():
    st.stop()  # Don't continue if password is wrong

# Check if site has been selected
if "selected_site" not in st.session_state:
    site_selection_screen()
    st.stop()  # Don't continue until site is selected


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
# SIDEBAR - CLEAN & SIMPLE
# ============================================================================

def render_sidebar():
    """Render the sidebar with navigation only"""

    with st.sidebar:
        st.title("🍁 Forest Farmers Dashboard")
        
        # Show current site selection with visual indicator
        current_site = st.session_state.get("selected_site", "All Sites")
        
        if current_site == "NY":
            st.info("🟦 **Viewing: New York**")
        elif current_site == "VT":
            st.info("🟩 **Viewing: Vermont**")
        else:
            st.info("📊 **Viewing: Both Sites**")
        
        # Change site button
        if st.button("🔄 Change Site", use_container_width=True):
            del st.session_state["selected_site"]
            st.rerun()
        
        st.divider()

        # Page selection - PRIMARY NAVIGATION
        st.subheader("📄 Pages")

        # Main pages
        page = st.radio(
            "Select Page",
            [
                "🌳 Tapping Operations",
                "👥 Employee Hours",
                "🛠️ Repairs Needed",
                "🌍 Interactive Map",
                "📈 Tap History",
                "🌡️ Tapping by Temperature",
                "🧊 Freezing Report",
                "📋 Manager Data Review"
            ],
            label_visibility="collapsed",
            key="main_pages"
        )

        st.markdown("---")
        st.caption("⚠️ **Needs Work**")

        # Secondary pages that need work
        page2 = st.radio(
            "Other Pages",
            [
                "🔧 Vacuum Performance",
                "⭐ Leak Checking",
                "🔧 Maintenance & Leaks",
                "⚠️ Alerts",
                "🌡️ Sap Flow Forecast",
                "📊 Raw Data"
            ],
            label_visibility="collapsed",
            key="other_pages"
        )

        # Handle page selection from either radio group
        if "last_main_page" not in st.session_state:
            st.session_state.last_main_page = page
        if "last_other_page" not in st.session_state:
            st.session_state.last_other_page = page2

        # Determine which page changed
        if page != st.session_state.last_main_page:
            st.session_state.last_main_page = page
            st.session_state.active_page = page
        elif page2 != st.session_state.last_other_page:
            st.session_state.last_other_page = page2
            st.session_state.active_page = page2
        elif "active_page" not in st.session_state:
            st.session_state.active_page = page

        page = st.session_state.active_page

        st.divider()

        # Actions — separate refresh buttons for vacuum vs personnel
        col_ref1, col_ref2 = st.columns(2)
        with col_ref1:
            if st.button("🔄 Vacuum", use_container_width=True, help="Refresh vacuum sensor data only"):
                load_all_vacuum_data.clear()
                process_vacuum_data.clear()
                st.rerun()
        with col_ref2:
            if st.button("🔄 Personnel", use_container_width=True, help="Refresh personnel/TSheets data only"):
                load_all_personnel_data.clear()
                load_approved_personnel.clear()
                process_personnel_data.clear()
                load_repairs_tracker.clear()
                st.rerun()

        st.divider()

        if st.button("⬇️ Sync from TSheets", use_container_width=True):
            try:
                token = st.secrets["github"]["GITHUB_TOKEN"]
            except (KeyError, FileNotFoundError):
                st.error("GitHub token not configured. Add [github] GITHUB_TOKEN to Streamlit secrets.")
                token = None

            if token:
                with st.spinner("Triggering TSheets sync..."):
                    resp = requests.post(
                        "https://api.github.com/repos/jeremylfarrell/mike_personnel/actions/workflows/personnel_backup.yml/dispatches",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/vnd.github+json",
                        },
                        json={"ref": "main"},
                        timeout=15,
                    )
                if resp.status_code == 204:
                    st.success("Sync triggered! Data will update in ~30 seconds. Click **🔄 Personnel** after that.")
                    load_all_personnel_data.clear()
                    load_approved_personnel.clear()
                    process_personnel_data.clear()
                else:
                    st.error(f"Failed to trigger sync: {resp.status_code} — {resp.text}")

        st.divider()

        # Vacuum data range control
        if 'vacuum_days' not in st.session_state:
            st.session_state.vacuum_days = 3  # Fast default: last 3 days

        current_days = st.session_state.vacuum_days

        if current_days <= 3:
            if st.button("📅 Load More Vacuum Data (60 days)", use_container_width=True):
                st.session_state.vacuum_days = 60
                load_all_vacuum_data.clear()
                process_vacuum_data.clear()
                st.rerun()
            st.caption("📊 Showing last 3 days of vacuum data")
        else:
            if st.button("⚡ Quick Load (3 days)", use_container_width=True):
                st.session_state.vacuum_days = 3
                load_all_vacuum_data.clear()
                process_vacuum_data.clear()
                st.rerun()
            st.caption("📊 Showing last 60 days of vacuum data")

        st.divider()

        # Footer info
        st.caption(f"v9.36 | {datetime.now().strftime('%H:%M:%S')}")
        st.caption("💾 Data cached for 1 hour")

    # Get site filter from session state
    site_filter = st.session_state.get("selected_site", "All Sites")

    # Vacuum days from session state (default 3 for fast loading)
    days_to_load = st.session_state.get('vacuum_days', 3)

    return page, days_to_load, site_filter


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
            personnel_df = load_all_personnel_data(personnel_url, credentials)
            repairs_df = load_repairs_tracker(personnel_url, credentials)

            # Merge manager-approved overrides into personnel data.
            # Where the manager has corrected a row (same Employee+Date+Job),
            # use the corrected version.  All data is shown on all pages.
            approved_df = load_approved_personnel(personnel_url, credentials)
            personnel_df = merge_approved_data(personnel_df, approved_df)

        except Exception as e:
            st.error(f"Error loading data: {str(e)}")
            st.error("Make sure your Google Sheets credentials are properly configured in Streamlit secrets!")
            st.stop()

    return vacuum_df, personnel_df, repairs_df, approved_df


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


def filter_data_by_site(vacuum_df, personnel_df, repairs_df, site_filter):
    """
    Filter dataframes by selected site

    Args:
        vacuum_df: Vacuum data
        personnel_df: Personnel data
        repairs_df: Repairs tracker data
        site_filter: Selected site ("All Sites", "NY", "VT")

    Returns:
        Tuple of (filtered_vacuum_df, filtered_personnel_df, filtered_repairs_df)
    """
    if site_filter == "All Sites":
        return vacuum_df, personnel_df, repairs_df

    # Filter to specific site
    filtered_vacuum = vacuum_df[vacuum_df['Site'] == site_filter] if 'Site' in vacuum_df.columns else vacuum_df
    filtered_personnel = personnel_df[personnel_df['Site'] == site_filter] if 'Site' in personnel_df.columns else personnel_df
    filtered_repairs = repairs_df[repairs_df['Site'] == site_filter] if not repairs_df.empty and 'Site' in repairs_df.columns else repairs_df

    return filtered_vacuum, filtered_personnel, filtered_repairs


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application entry point"""

    # Render sidebar and get selections
    page, days_to_load, site_filter = render_sidebar()

    # Load data — personnel_df is the full merged dataset (raw + any approved corrections)
    vacuum_df, personnel_df, repairs_df, approved_df = load_data(days_to_load)

    # Show data loading info
    show_data_info(vacuum_df, personnel_df)

    # Filter by site (based on login selection)
    vacuum_df, personnel_df, repairs_df = filter_data_by_site(vacuum_df, personnel_df, repairs_df, site_filter)

    # Show filtering info at top of page
    sensor_col = find_column(vacuum_df, 'Sensor Name', 'sensor', 'mainline', 'location', 'name', 'Name')
    if not vacuum_df.empty and sensor_col:
        sensor_count = vacuum_df[sensor_col].nunique()
        if site_filter == "NY":
            st.success(f"🟦 **New York View** - {sensor_count} sensors | Last {days_to_load} days")
        elif site_filter == "VT":
            st.success(f"🟩 **Vermont View** - {sensor_count} sensors | Last {days_to_load} days")
        else:
            st.success(f"📊 **All Sites View** - {sensor_count} sensors combined | Last {days_to_load} days")

    # Route to selected page
    if page == "🔧 Vacuum Performance":
        vacuum.render(vacuum_df, personnel_df)
    elif page == "🌳 Tapping Operations":
        tapping.render(personnel_df, vacuum_df)
    elif page == "👥 Employee Hours":
        employees.render(personnel_df, site_filter)
    elif page == "⭐ Leak Checking":
        employee_effectiveness.render(personnel_df, vacuum_df)
    elif page == "🔧 Maintenance & Leaks":
        maintenance.render(vacuum_df, personnel_df)
    elif page == "🛠️ Repairs Needed":
        repairs_analysis.render(personnel_df, vacuum_df, repairs_df)
    elif page == "⚠️ Alerts":
        data_quality.render(personnel_df, vacuum_df)
    elif page == "🌍 Interactive Map":
        sensor_map.render(vacuum_df, personnel_df, repairs_df)
    elif page == "🌡️ Sap Flow Forecast":
        sap_forecast.render(vacuum_df, personnel_df)
    elif page == "📊 Raw Data":
        raw_data.render(vacuum_df, personnel_df)
    elif page == "📈 Tap History":
        tap_history.render(personnel_df, vacuum_df)
    elif page == "🌡️ Tapping by Temperature":
        temperature_productivity.render(personnel_df, vacuum_df)
    elif page == "🧊 Freezing Report":
        freezing_report.render(vacuum_df, personnel_df)
    elif page == "📋 Manager Data Review":
        manager_review.render(personnel_df, vacuum_df, approved_df)


if __name__ == "__main__":
    main()
