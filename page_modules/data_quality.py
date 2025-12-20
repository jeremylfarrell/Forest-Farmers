"""
Data Validation Page Module
Detects anomalies and quality issues in timesheet and vacuum data

TIER 1 DETECTIONS:
- Location mismatches (timesheet location ≠ vacuum sensor location)
- Unmatched vacuum improvements (sensors improved but no timesheet entries)
- Zero-impact maintenance (timesheet claims work but no vacuum improvements)
- Date gaps (work logged on dates with no vacuum activity)
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from utils import find_column
import gspread
from google.oauth2.service_account import Credentials


def detect_location_mismatches(personnel_df, vacuum_df):
    """
    Detect cases where timesheet location doesn't match vacuum sensor locations
    
    Returns: DataFrame with alerts
    """
    alerts = []
    
    if personnel_df.empty or vacuum_df.empty:
        return pd.DataFrame(alerts)
    
    # Find columns
    emp_col = find_column(personnel_df, 'Employee Name', 'employee', 'name')
    date_col = find_column(personnel_df, 'Date', 'date')
    site_col = find_column(personnel_df, 'Site', 'site', 'location')
    job_desc_col = find_column(personnel_df, 'Job Description', 'job', 'description', 'job_description')
    sensor_col = find_column(vacuum_df, 'Sensor Name', 'sensor', 'mainline', 'location', 'name', 'Name')
    
    if not all([emp_col, date_col, site_col, sensor_col]):
        return pd.DataFrame(alerts)
    
    # Get maintenance-related personnel records (only if we have job description column)
    if job_desc_col:
        maintenance_df = personnel_df[
            personnel_df[job_desc_col].str.contains('maint|repair|fix|leak', case=False, na=False)
        ].copy()
    else:
        # If no job description column, use all personnel records
        maintenance_df = personnel_df.copy()
    
    for _, record in maintenance_df.iterrows():
        employee = record[emp_col]
        date = record[date_col]
        timesheet_site = record[site_col]
        
        # Skip if unknown site in timesheet
        if timesheet_site == 'UNK':
            continue
        
        # Find vacuum improvements on this date
        date_vacuum = vacuum_df[vacuum_df['Date'] == date].copy()
        
        if not date_vacuum.empty:
            # Check if sensors worked are from different site
            sensor_sites = date_vacuum['Site'].unique()
            
            # If timesheet says NY but only VT sensors improved (or vice versa)
            if timesheet_site not in sensor_sites and len(sensor_sites) > 0:
                other_site = sensor_sites[0]
                sensor_count = len(date_vacuum[date_vacuum['Site'] == other_site])
                
                alerts.append({
                    'Date': date,
                    'Employee': employee,
                    'Issue': 'Location Mismatch',
                    'Severity': 'HIGH',
                    'Details': f'Timesheet: {timesheet_site}, Sensors worked: {other_site} ({sensor_count} sensors)',
                    'Timesheet_Site': timesheet_site,
                    'Sensor_Site': other_site,
                    'Sensor_Count': sensor_count
                })
    
    return pd.DataFrame(alerts)


def detect_unmatched_improvements(vacuum_df, personnel_df):
    """
    Detect significant vacuum improvements with no corresponding timesheet entries
    
    Returns: DataFrame with alerts
    """
    alerts = []
    
    if vacuum_df.empty or personnel_df.empty:
        return pd.DataFrame(alerts)
    
    # Find columns
    date_col = find_column(vacuum_df, 'Date', 'date')
    sensor_col = find_column(vacuum_df, 'Sensor Name', 'sensor', 'mainline', 'location', 'name', 'Name')
    
    if not all([date_col, sensor_col]):
        return pd.DataFrame(alerts)
    
    # Group vacuum improvements by date and site
    for date in vacuum_df['Date'].unique():
        date_vacuum = vacuum_df[vacuum_df['Date'] == date]
        
        for site in ['NY', 'VT']:
            site_vacuum = date_vacuum[date_vacuum['Site'] == site]
            
            if len(site_vacuum) == 0:
                continue
            
            # Count significant improvements (let's say >5 inHg improvement)
            if 'Vacuum Improvement' in site_vacuum.columns:
                significant = site_vacuum[site_vacuum['Vacuum Improvement'] > 5]
                improvement_count = len(significant)
            else:
                improvement_count = len(site_vacuum)
            
            # Check if there are timesheet entries for this date/site
            date_personnel = personnel_df[
                (personnel_df['Date'] == date) & 
                (personnel_df['Site'] == site)
            ]
            
            # Alert if significant improvements but no timesheet
            if improvement_count >= 5 and len(date_personnel) == 0:
                avg_improvement = site_vacuum.get('Vacuum Improvement', pd.Series([0])).mean()
                
                severity = 'HIGH' if improvement_count >= 10 else 'MEDIUM'
                
                alerts.append({
                    'Date': date,
                    'Employee': 'Unknown',
                    'Issue': 'Unmatched Improvements',
                    'Severity': severity,
                    'Details': f'{improvement_count} sensors improved at {site}, no timesheet entries found',
                    'Site': site,
                    'Sensor_Count': improvement_count,
                    'Avg_Improvement': round(avg_improvement, 2) if not pd.isna(avg_improvement) else 0
                })
    
    return pd.DataFrame(alerts)


def detect_zero_impact_maintenance(personnel_df, vacuum_df):
    """
    Detect maintenance timesheet entries with no corresponding vacuum improvements
    
    Returns: DataFrame with alerts
    """
    alerts = []
    
    if personnel_df.empty or vacuum_df.empty:
        return pd.DataFrame(alerts)
    
    # Find columns
    emp_col = find_column(personnel_df, 'Employee Name', 'employee', 'name')
    date_col = find_column(personnel_df, 'Date', 'date')
    hours_col = find_column(personnel_df, 'Hours', 'hours', 'duration')
    job_desc_col = find_column(personnel_df, 'Job Description', 'job', 'description', 'job_description')
    
    if not all([emp_col, date_col, hours_col]):
        return pd.DataFrame(alerts)
    
    # Get maintenance-related personnel records (only if we have job description column)
    if job_desc_col:
        maintenance_df = personnel_df[
            personnel_df[job_desc_col].str.contains('maint|repair|fix|leak', case=False, na=False)
        ].copy()
    else:
        # If no job description column, use all personnel records
        maintenance_df = personnel_df.copy()
    
    for _, record in maintenance_df.iterrows():
        employee = record[emp_col]
        date = record[date_col]
        hours = record[hours_col]
        site = record.get('Site', 'UNK')
        
        # Find vacuum data for this date/site
        date_vacuum = vacuum_df[
            (vacuum_df['Date'] == date) & 
            (vacuum_df['Site'] == site)
        ]
        
        # Check for improvements
        if len(date_vacuum) == 0:
            # No vacuum data at all for this date/site
            if hours >= 4:  # Only flag if it's a half day or more
                alerts.append({
                    'Date': date,
                    'Employee': employee,
                    'Issue': 'Zero Impact',
                    'Severity': 'HIGH' if hours >= 8 else 'MEDIUM',
                    'Details': f'{hours} hours logged, no vacuum data found for {site}',
                    'Hours': hours,
                    'Site': site,
                    'Sensor_Count': 0
                })
        else:
            # Vacuum data exists - check if there are actual improvements
            if 'Vacuum Improvement' in date_vacuum.columns:
                improved = date_vacuum[date_vacuum['Vacuum Improvement'] > 2]
                improvement_count = len(improved)
                
                if improvement_count < 3 and hours >= 4:
                    alerts.append({
                        'Date': date,
                        'Employee': employee,
                        'Issue': 'Zero Impact',
                        'Severity': 'MEDIUM',
                        'Details': f'{hours} hours logged, only {improvement_count} sensors improved at {site}',
                        'Hours': hours,
                        'Site': site,
                        'Sensor_Count': improvement_count
                    })
    
    return pd.DataFrame(alerts)


def load_manager_notes(sheet_url, credentials_path):
    """
    Load manager notes from Google Sheets
    Creates the tab if it doesn't exist
    
    Returns: DataFrame with notes
    """
    try:
        # Set up credentials
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Try to load from Streamlit secrets first (for cloud deployment)
        try:
            credentials_dict = st.secrets["gcp_service_account"]
            creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        except:
            # Fall back to local credentials file
            creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        
        client = gspread.authorize(creds)
        
        # Open the personnel sheet (we'll add notes tab there)
        sheet = client.open_by_url(sheet_url)
        
        # Try to get Data_Quality_Notes worksheet
        try:
            worksheet = sheet.worksheet('Data_Quality_Notes')
        except:
            # Create it if it doesn't exist
            worksheet = sheet.add_worksheet(title='Data_Quality_Notes', rows=1000, cols=10)
            # Add headers
            worksheet.update('A1:H1', [[
                'Timestamp', 'Date', 'Employee', 'Issue', 'Severity', 
                'Manager', 'Note', 'Status'
            ]])
        
        # Get all data
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    
    except Exception as e:
        st.error(f"Error loading manager notes: {str(e)}")
        return pd.DataFrame()


def save_manager_note(sheet_url, credentials_path, note_data):
    """
    Save a manager note to Google Sheets
    
    Args:
        note_data: dict with keys: Date, Employee, Issue, Severity, Manager, Note, Status
    """
    try:
        # Set up credentials
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Try to load from Streamlit secrets first
        try:
            credentials_dict = st.secrets["gcp_service_account"]
            creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        except:
            creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        
        client = gspread.authorize(creds)
        sheet = client.open_by_url(sheet_url)
        worksheet = sheet.worksheet('Data_Quality_Notes')
        
        # Prepare row
        row = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            str(note_data.get('Date', '')),
            note_data.get('Employee', ''),
            note_data.get('Issue', ''),
            note_data.get('Severity', ''),
            note_data.get('Manager', ''),
            note_data.get('Note', ''),
            note_data.get('Status', 'Open')
        ]
        
        # Append row
        worksheet.append_row(row)
        return True
    
    except Exception as e:
        st.error(f"Error saving note: {str(e)}")
        return False


def render(personnel_df, vacuum_df):
    """
    Main render function for Data Validation page
    
    Args:
        personnel_df: Personnel timesheet data
        vacuum_df: Vacuum sensor data
    """
    st.title("⚠️ Data Validation")
    st.markdown("---")
    
    # Check for empty data
    if personnel_df.empty or vacuum_df.empty:
        st.warning("Insufficient data for validation analysis")
        st.info("Both personnel and vacuum data are required for data validation")
        return
    
    # Get configuration
    try:
        personnel_url = st.secrets["sheets"]["PERSONNEL_SHEET_URL"]
    except:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        personnel_url = os.getenv('PERSONNEL_SHEET_URL')
    
    credentials_path = 'credentials.json'
    
    # Description
    st.markdown("""
    This page automatically detects potential data quality issues by cross-analyzing 
    timesheet and vacuum data. Review flagged items and add manager notes as needed.
    """)
    
    # Date range filter
    col1, col2, col3 = st.columns(3)
    with col1:
        date_range = st.selectbox(
            "Date Range:",
            options=['Last 7 days', 'Last 14 days', 'Last 30 days', 'All data'],
            index=0
        )
    
    # Filter data by date range
    if date_range != 'All data':
        days = int(date_range.split()[1])
        cutoff_date = pd.Timestamp(datetime.now().date() - timedelta(days=days))
        
        # Ensure Date columns are datetime
        if 'Date' in personnel_df.columns:
            personnel_df = personnel_df.copy()
            personnel_df['Date'] = pd.to_datetime(personnel_df['Date'])
            personnel_df = personnel_df[personnel_df['Date'] >= cutoff_date]
        
        if 'Date' in vacuum_df.columns:
            vacuum_df = vacuum_df.copy()
            vacuum_df['Date'] = pd.to_datetime(vacuum_df['Date'])
            vacuum_df = vacuum_df[vacuum_df['Date'] >= cutoff_date]
    
    # Run detections
    with st.spinner('Analyzing data for quality issues...'):
        location_alerts = detect_location_mismatches(personnel_df, vacuum_df)
        unmatched_alerts = detect_unmatched_improvements(vacuum_df, personnel_df)
        zero_impact_alerts = detect_zero_impact_maintenance(personnel_df, vacuum_df)
        
        # Combine all alerts
        all_alerts = pd.concat([location_alerts, unmatched_alerts, zero_impact_alerts], 
                               ignore_index=True)
    
    # Display summary metrics
    st.markdown("### 📊 Alert Summary")
    
    if not all_alerts.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Alerts", len(all_alerts))
        
        with col2:
            high_count = len(all_alerts[all_alerts['Severity'] == 'HIGH'])
            st.metric("High Priority", high_count, delta=None, delta_color="inverse")
        
        with col3:
            medium_count = len(all_alerts[all_alerts['Severity'] == 'MEDIUM'])
            st.metric("Medium Priority", medium_count)
        
        with col4:
            low_count = len(all_alerts[all_alerts['Severity'] == 'LOW'])
            st.metric("Low Priority", low_count)
        
        st.markdown("---")
        
        # Filters
        st.markdown("### 🔍 Filter Alerts")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            severity_filter = st.multiselect(
                "Severity:",
                options=['HIGH', 'MEDIUM', 'LOW'],
                default=['HIGH', 'MEDIUM', 'LOW']
            )
        
        with col2:
            issue_filter = st.multiselect(
                "Issue Type:",
                options=all_alerts['Issue'].unique().tolist(),
                default=all_alerts['Issue'].unique().tolist()
            )
        
        with col3:
            if 'Employee' in all_alerts.columns:
                employees = all_alerts['Employee'].unique().tolist()
                employee_filter = st.multiselect(
                    "Employee:",
                    options=employees,
                    default=employees
                )
            else:
                employee_filter = []
        
        # Apply filters
        filtered_alerts = all_alerts[
            (all_alerts['Severity'].isin(severity_filter)) &
            (all_alerts['Issue'].isin(issue_filter))
        ]
        
        if employee_filter and 'Employee' in all_alerts.columns:
            filtered_alerts = filtered_alerts[filtered_alerts['Employee'].isin(employee_filter)]
        
        st.markdown("---")
        
        # Display alerts
        st.markdown(f"### 🚨 Alerts ({len(filtered_alerts)} items)")
        
        if not filtered_alerts.empty:
            # Sort by severity and date
            severity_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
            filtered_alerts['severity_order'] = filtered_alerts['Severity'].map(severity_order)
            filtered_alerts = filtered_alerts.sort_values(['severity_order', 'Date'], ascending=[True, False])
            filtered_alerts = filtered_alerts.drop('severity_order', axis=1)
            
            # Display each alert as an expandable card
            for idx, alert in filtered_alerts.iterrows():
                # Color code by severity
                if alert['Severity'] == 'HIGH':
                    color = "🔴"
                elif alert['Severity'] == 'MEDIUM':
                    color = "🟡"
                else:
                    color = "🟢"
                
                with st.expander(
                    f"{color} {alert['Issue']} - {alert['Employee']} - {alert['Date']}", 
                    expanded=False
                ):
                    st.markdown(f"**Details:** {alert['Details']}")
                    st.markdown(f"**Severity:** {alert['Severity']}")
                    
                    # Add manager note form
                    st.markdown("---")
                    st.markdown("**Manager Notes:**")
                    
                    with st.form(key=f"note_form_{idx}"):
                        manager_name = st.text_input("Your Name:", key=f"manager_{idx}")
                        note = st.text_area("Note:", key=f"note_{idx}", height=100)
                        status = st.selectbox(
                            "Status:", 
                            options=['Open', 'Investigating', 'Resolved', 'False Positive'],
                            key=f"status_{idx}"
                        )
                        
                        submitted = st.form_submit_button("Save Note")
                        
                        if submitted:
                            if manager_name and note:
                                note_data = {
                                    'Date': alert['Date'],
                                    'Employee': alert['Employee'],
                                    'Issue': alert['Issue'],
                                    'Severity': alert['Severity'],
                                    'Manager': manager_name,
                                    'Note': note,
                                    'Status': status
                                }
                                
                                if save_manager_note(personnel_url, credentials_path, note_data):
                                    st.success("✅ Note saved successfully!")
                                else:
                                    st.error("Failed to save note")
                            else:
                                st.warning("Please enter your name and a note")
        else:
            st.info("No alerts match the selected filters")
    
    else:
        st.success("✅ No data quality issues detected!")
        st.balloons()
    
    # Show existing manager notes
    st.markdown("---")
    st.markdown("### 📝 Manager Notes History")
    
    notes_df = load_manager_notes(personnel_url, credentials_path)
    
    if not notes_df.empty:
        # Filter to match current date range
        if date_range != 'All data':
            days = int(date_range.split()[1])
            cutoff_date = pd.Timestamp(datetime.now().date() - timedelta(days=days))
            notes_df = notes_df.copy()
            notes_df['Date'] = pd.to_datetime(notes_df['Date'], errors='coerce')
            notes_df = notes_df[notes_df['Date'] >= cutoff_date]
        
        if not notes_df.empty:
            st.dataframe(
                notes_df[['Timestamp', 'Date', 'Employee', 'Issue', 'Manager', 'Note', 'Status']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No manager notes in selected date range")
    else:
        st.info("No manager notes recorded yet")
