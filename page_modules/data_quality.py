"""
Alerts Page Module
Detects anomalies and quality issues in timesheet and vacuum data

ALERT TYPES:
- Repairs needed field entries
- Hours in excess of 12 per day
- Rapid vacuum drops (3"+ faster than average)
- Location mismatches (timesheet location ≠ vacuum sensor location)
- Unmatched vacuum improvements (sensors improved but no timesheet entries)
- Zero-impact maintenance (timesheet claims work but no vacuum improvements)
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from utils import find_column
import gspread
from google.oauth2.service_account import Credentials


def detect_repairs_needed(personnel_df):
    """
    Detect entries where "Repairs needed" field has content
    
    Returns: DataFrame with alerts
    """
    alerts = []
    
    if personnel_df.empty:
        return pd.DataFrame(alerts)
    
    # Find columns
    emp_col = find_column(personnel_df, 'Employee Name', 'employee', 'name')
    date_col = find_column(personnel_df, 'Date', 'date')
    repairs_col = find_column(personnel_df, 'Repairs needed', 'repairs', 'repair', 'repairs_needed')
    mainline_col = find_column(personnel_df, 'mainline', 'Mainline', 'mainline.', 'location')
    
    if not all([emp_col, date_col, repairs_col]):
        return pd.DataFrame(alerts)
    
    # Filter to records with repairs needed
    repairs_df = personnel_df[
        personnel_df[repairs_col].notna() & 
        (personnel_df[repairs_col].astype(str).str.strip() != '') &
        (personnel_df[repairs_col].astype(str).str.strip() != '0')
    ].copy()
    
    for _, record in repairs_df.iterrows():
        employee = record[emp_col]
        date = record[date_col]
        repair_note = str(record[repairs_col])
        site = record.get('Site', 'UNK')
        location = record.get(mainline_col, 'Unknown') if mainline_col else 'Unknown'
        
        alerts.append({
            'Date': date,
            'Employee': employee,
            'Issue': 'Repairs Needed',
            'Severity': 'HIGH',
            'Details': f'{site} - {location}: {repair_note}',
            'Site': site,
            'Location': location,
            'Repair_Note': repair_note
        })
    
    return pd.DataFrame(alerts)


def detect_excessive_hours(personnel_df):
    """
    Detect employees working more than 12 hours in a single day
    
    Returns: DataFrame with alerts
    """
    alerts = []
    
    if personnel_df.empty:
        return pd.DataFrame(alerts)
    
    # Find columns
    emp_col = find_column(personnel_df, 'Employee Name', 'employee', 'name')
    date_col = find_column(personnel_df, 'Date', 'date')
    hours_col = find_column(personnel_df, 'Hours', 'hours', 'time', 'duration')
    
    if not all([emp_col, date_col, hours_col]):
        return pd.DataFrame(alerts)
    
    # Group by employee and date, sum hours
    daily_hours = personnel_df.groupby([emp_col, date_col])[hours_col].sum().reset_index()
    daily_hours.columns = ['Employee', 'Date', 'Total_Hours']
    
    # Filter to excessive hours (>12)
    excessive = daily_hours[daily_hours['Total_Hours'] > 12].copy()
    
    for _, record in excessive.iterrows():
        employee = record['Employee']
        date = record['Date']
        hours = record['Total_Hours']
        
        # Get site info if available
        day_records = personnel_df[
            (personnel_df[emp_col] == employee) & 
            (personnel_df[date_col] == date)
        ]
        site = day_records['Site'].iloc[0] if 'Site' in day_records.columns and len(day_records) > 0 else 'UNK'
        
        # Determine severity
        if hours > 16:
            severity = 'HIGH'
        elif hours > 14:
            severity = 'MEDIUM'
        else:
            severity = 'MEDIUM'
        
        alerts.append({
            'Date': date,
            'Employee': employee,
            'Issue': 'Excessive Hours',
            'Severity': severity,
            'Details': f'{hours:.1f} hours worked in one day at {site}',
            'Site': site,
            'Hours': hours
        })
    
    return pd.DataFrame(alerts)


def detect_rapid_vac_drops(vacuum_df):
    """
    Detect systems with vacuum drops of 3"+ faster than average system drop
    
    Returns: DataFrame with alerts
    """
    alerts = []
    
    if vacuum_df.empty:
        return pd.DataFrame(alerts)
    
    # Find columns
    sensor_col = find_column(vacuum_df, 'Name', 'name', 'Sensor Name', 'sensor', 'mainline', 'location')
    vacuum_col = find_column(vacuum_df, 'Vacuum', 'vacuum', 'reading', 'value')
    timestamp_col = find_column(vacuum_df, 'Last communication', 'Last Communication', 'Timestamp', 'timestamp', 'time')
    
    if not all([sensor_col, vacuum_col, timestamp_col]):
        return pd.DataFrame(alerts)
    
    # Convert to datetime and numeric
    df = vacuum_df.copy()
    df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors='coerce')
    df[vacuum_col] = pd.to_numeric(df[vacuum_col], errors='coerce')
    df = df.dropna(subset=[timestamp_col, vacuum_col])
    
    if df.empty:
        return pd.DataFrame(alerts)
    
    # Sort by sensor and time
    df = df.sort_values([sensor_col, timestamp_col])
    
    # Calculate change from previous reading for each sensor
    df['Vac_Change'] = df.groupby(sensor_col)[vacuum_col].diff()
    df['Time_Diff_Hours'] = df.groupby(sensor_col)[timestamp_col].diff().dt.total_seconds() / 3600
    
    # Only look at readings within 24 hours of each other
    df = df[(df['Time_Diff_Hours'] > 0) & (df['Time_Diff_Hours'] <= 24)]
    
    if df.empty:
        return pd.DataFrame(alerts)
    
    # Calculate average drop across all systems (negative change = drop)
    avg_drop = df['Vac_Change'].mean()
    
    # Find systems dropping 3"+ more than average
    # If average drop is -2", then -5" would be 3" worse
    threshold_drop = avg_drop - 3
    
    rapid_drops = df[df['Vac_Change'] < threshold_drop].copy()
    
    for _, record in rapid_drops.iterrows():
        sensor = record[sensor_col]
        current_vac = record[vacuum_col]
        vac_change = record['Vac_Change']
        timestamp = record[timestamp_col]
        site = record.get('Site', 'UNK')
        
        # Calculate how much worse than average
        worse_than_avg = abs(vac_change - avg_drop)
        
        # Determine severity
        if worse_than_avg >= 5:
            severity = 'HIGH'
        elif worse_than_avg >= 4:
            severity = 'MEDIUM'
        else:
            severity = 'MEDIUM'
        
        alerts.append({
            'Date': timestamp.date() if pd.notna(timestamp) else None,
            'Employee': 'System',
            'Issue': 'Rapid Vac Drop',
            'Severity': severity,
            'Details': f'{site} - {sensor}: Dropped {abs(vac_change):.1f}" (avg drop: {abs(avg_drop):.1f}"), now at {current_vac:.1f}"',
            'Site': site,
            'Sensor': sensor,
            'Vac_Drop': abs(vac_change),
            'Current_Vac': current_vac,
            'Avg_Drop': abs(avg_drop)
        })
    
    return pd.DataFrame(alerts)


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
                    'Severity': 'MEDIUM',
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
                    'Severity': 'MEDIUM' if hours >= 8 else 'LOW',
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
                        'Severity': 'LOW',
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
        except (KeyError, FileNotFoundError):
            # Fall back to local credentials file
            creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        
        client = gspread.authorize(creds)
        
        # Open the personnel sheet (we'll add notes tab there)
        sheet = client.open_by_url(sheet_url)
        
        # Try to get Alerts_Notes worksheet
        try:
            worksheet = sheet.worksheet('Alerts_Notes')
        except gspread.exceptions.WorksheetNotFound:
            # Create it if it doesn't exist
            worksheet = sheet.add_worksheet(title='Alerts_Notes', rows=1000, cols=10)
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
        except (KeyError, FileNotFoundError):
            creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        
        client = gspread.authorize(creds)
        sheet = client.open_by_url(sheet_url)
        worksheet = sheet.worksheet('Alerts_Notes')
        
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
    Main render function for Alerts page
    
    Args:
        personnel_df: Personnel timesheet data
        vacuum_df: Vacuum sensor data
    """
    st.title("⚠️ Alerts")
    st.markdown("---")
    
    # Check for empty data
    if personnel_df.empty and vacuum_df.empty:
        st.warning("Insufficient data for alert analysis")
        st.info("Personnel and/or vacuum data required for alerts")
        return
    
    # Get configuration
    try:
        personnel_url = st.secrets["sheets"]["PERSONNEL_SHEET_URL"]
    except (KeyError, FileNotFoundError):
        import os
        from dotenv import load_dotenv
        load_dotenv()
        personnel_url = os.getenv('PERSONNEL_SHEET_URL')
    
    credentials_path = 'credentials.json'
    
    # Description
    st.markdown("""
    This page automatically detects issues requiring attention by analyzing 
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
        if 'Date' in personnel_df.columns and not personnel_df.empty:
            personnel_df = personnel_df.copy()
            personnel_df['Date'] = pd.to_datetime(personnel_df['Date'])
            personnel_df = personnel_df[personnel_df['Date'] >= cutoff_date]
        
        if 'Date' in vacuum_df.columns and not vacuum_df.empty:
            vacuum_df = vacuum_df.copy()
            vacuum_df['Date'] = pd.to_datetime(vacuum_df['Date'])
            vacuum_df = vacuum_df[vacuum_df['Date'] >= cutoff_date]
    
    # Run all detections
    with st.spinner('Analyzing data for alerts...'):
        # New alert types
        repairs_alerts = detect_repairs_needed(personnel_df) if not personnel_df.empty else pd.DataFrame()
        excessive_hours_alerts = detect_excessive_hours(personnel_df) if not personnel_df.empty else pd.DataFrame()
        rapid_drop_alerts = detect_rapid_vac_drops(vacuum_df) if not vacuum_df.empty else pd.DataFrame()
        
        # Original alert types
        location_alerts = detect_location_mismatches(personnel_df, vacuum_df) if not personnel_df.empty and not vacuum_df.empty else pd.DataFrame()
        unmatched_alerts = detect_unmatched_improvements(vacuum_df, personnel_df) if not personnel_df.empty and not vacuum_df.empty else pd.DataFrame()
        zero_impact_alerts = detect_zero_impact_maintenance(personnel_df, vacuum_df) if not personnel_df.empty and not vacuum_df.empty else pd.DataFrame()
        
        # Combine all alerts
        all_alerts = pd.concat([
            repairs_alerts, 
            excessive_hours_alerts,
            rapid_drop_alerts,
            location_alerts, 
            unmatched_alerts, 
            zero_impact_alerts
        ], ignore_index=True)
    
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
            
            # Convert Date to datetime for proper sorting, handling NaT values
            filtered_alerts['Date_Sort'] = pd.to_datetime(filtered_alerts['Date'], errors='coerce')
            
            # Sort by severity first, then date (nulls last)
            filtered_alerts = filtered_alerts.sort_values(
                ['severity_order', 'Date_Sort'], 
                ascending=[True, False],
                na_position='last'
            )
            
            # Clean up helper columns
            filtered_alerts = filtered_alerts.drop(['severity_order', 'Date_Sort'], axis=1)
            
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
        st.success("✅ No alerts detected!")
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
    
    # Tips
    st.markdown("---")
    with st.expander("💡 Understanding Alerts"):
        st.markdown("""
        **New Alert Types:**
        
        1. **Repairs Needed** 🔴 HIGH
           - Triggered when "Repairs needed" field has content
           - Shows location and repair description
           - Requires immediate attention
        
        2. **Excessive Hours** 🟡 MEDIUM/HIGH
           - Flags employees working >12 hours in one day
           - HIGH if >16 hours, MEDIUM if 12-16 hours
           - Check for data entry errors or overtime approval
        
        3. **Rapid Vac Drop** 🟡 MEDIUM/HIGH
           - Detects systems dropping 3"+ faster than average
           - HIGH if 5"+ worse than average
           - May indicate freeze-up, major leak, or system failure
        
        **Original Alert Types:**
        
        - **Location Mismatch**: Timesheet site doesn't match sensor locations worked
        - **Unmatched Improvements**: Sensors improved but no timesheet entries
        - **Zero Impact**: Maintenance logged but no vacuum improvements
        
        **Using This Page:**
        
        - Review HIGH priority alerts first
        - Add manager notes to document actions taken
        - Mark status as you investigate/resolve issues
        - Check "Repairs Needed" daily for maintenance requests
        - Monitor excessive hours for safety and compliance
        - Rapid vac drops may need emergency response
        """)
