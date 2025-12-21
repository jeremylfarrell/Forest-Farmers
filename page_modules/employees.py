"""
Employee Performance Page Module - MULTI-SITE ENHANCED
Displays employee activity and productivity metrics with site awareness
UPDATED: Week starts Monday 12:01am, shows hours by state, job code analysis
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import config
from utils import find_column


def get_week_start():
    """Get Monday 12:01am of current week"""
    today = datetime.now()
    days_since_monday = today.weekday()  # Monday = 0
    monday = today - timedelta(days=days_since_monday)
    # Set to 12:01am
    return monday.replace(hour=0, minute=1, second=0, microsecond=0)


def render(personnel_df):
    """Render employee performance page with site tracking"""

    st.title("👥 Employee Performance")

    if personnel_df.empty:
        st.warning("No personnel data available")
        return

    # Check if we have site information
    has_site = 'Site' in personnel_df.columns

    # Find column names (case-insensitive)
    emp_name_col = find_column(personnel_df, 'Employee Name', 'employee', 'name')
    mainline_col = find_column(personnel_df, 'mainline', 'Mainline', 'location', 'sensor')
    hours_col = find_column(personnel_df, 'Hours', 'hours', 'time')
    date_col = find_column(personnel_df, 'Date', 'date', 'timestamp')
    job_col = find_column(personnel_df, 'Job', 'job', 'task', 'work', 'Job Code', 'jobcode')

    if not emp_name_col:
        st.warning("Employee Name column not found")
        st.info("Available columns: " + ", ".join(personnel_df.columns))
        return

    # Build aggregation dict dynamically
    agg_dict = {}

    if hours_col:
        agg_dict[hours_col] = 'sum'

    if mainline_col:
        agg_dict[mainline_col] = 'nunique'

    if date_col:
        agg_dict[date_col] = 'count'
    elif emp_name_col:
        agg_dict[emp_name_col] = 'count'

    if not agg_dict:
        st.warning("Required columns for analysis not found")
        return

    # Calculate employee summary
    emp_summary = personnel_df.groupby(emp_name_col).agg(agg_dict).reset_index()

    # Rename columns based on what we found
    col_mapping = {emp_name_col: 'Employee'}
    if hours_col:
        col_mapping[hours_col] = 'Total_Hours'
    if mainline_col:
        col_mapping[mainline_col] = 'Locations'
    if date_col:
        col_mapping[date_col] = 'Entries'
    elif emp_name_col in emp_summary.columns and emp_name_col != 'Employee':
        for col in emp_summary.columns:
            if col not in col_mapping:
                col_mapping[col] = 'Entries'

    emp_summary = emp_summary.rename(columns=col_mapping)

    # Add site information if available
    if has_site:
        # Calculate primary site (where they work most)
        emp_sites = personnel_df.groupby(emp_name_col)['Site'].agg([
            ('Primary_Site', lambda x: x.value_counts().index[0] if len(x) > 0 else 'UNK')
        ]).reset_index()
        
        emp_sites.columns = ['Employee', 'Primary_Site']
        
        # Merge with summary
        emp_summary = emp_summary.merge(emp_sites, on='Employee', how='left')

    # Filter by minimum hours if available
    if 'Total_Hours' in emp_summary.columns:
        emp_summary = emp_summary[emp_summary['Total_Hours'] >= config.MIN_HOURS_FOR_RANKING]
        emp_summary = emp_summary.sort_values('Total_Hours', ascending=False)

    # Calculate hours since Monday 12:01am
    week_start = get_week_start()
    week_data = None
    if date_col:
        personnel_df_copy = personnel_df.copy()
        personnel_df_copy[date_col] = pd.to_datetime(personnel_df_copy[date_col], errors='coerce')
        week_data = personnel_df_copy[personnel_df_copy[date_col] >= week_start]

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Employees", len(emp_summary))

    with col2:
        if 'Total_Hours' in emp_summary.columns:
            st.metric("Total Hours (All Time)", f"{emp_summary['Total_Hours'].sum():.1f}h")
        else:
            st.metric("Total Hours", "N/A")

    with col3:
        # Hours since Monday
        if week_data is not None and hours_col and not week_data.empty:
            week_hours = week_data[hours_col].sum()
            st.metric("Hours Since Monday", f"{week_hours:.1f}h")
        else:
            st.metric("Hours Since Monday", "N/A")

    with col4:
        if 'Total_Hours' in emp_summary.columns:
            st.metric("Avg Hours/Employee", f"{emp_summary['Total_Hours'].mean():.1f}h")
        else:
            st.metric("Avg Hours/Employee", "N/A")

    st.divider()

    # Employee Hours by State
    st.subheader("⏱️ Employee Hours")
    
    if has_site and 'Primary_Site' in emp_summary.columns:
        # Separate tables by state
        tab1, tab2 = st.tabs(["🟦 NY Employees", "🟩 VT Employees"])
        
        with tab1:
            ny_employees = emp_summary[emp_summary['Primary_Site'] == 'NY'].copy()
            if not ny_employees.empty:
                st.markdown(f"**{len(ny_employees)} employees based in NY**")
                
                # Build display
                display = ny_employees.copy()
                display_cols = ['Employee']
                col_names = ['Employee']

                if 'Total_Hours' in display.columns:
                    display['Total_Hours'] = display['Total_Hours'].apply(lambda x: f"{x:.1f}h")
                    display_cols.append('Total_Hours')
                    col_names.append('Total Hours')

                if 'Locations' in display.columns:
                    display_cols.append('Locations')
                    col_names.append('Locations')

                if 'Entries' in display.columns:
                    display_cols.append('Entries')
                    col_names.append('Days Worked')

                display = display[display_cols]
                display.columns = col_names
                st.dataframe(display, use_container_width=True, hide_index=True, height=400)
            else:
                st.info("No NY employees in data")
        
        with tab2:
            vt_employees = emp_summary[emp_summary['Primary_Site'] == 'VT'].copy()
            if not vt_employees.empty:
                st.markdown(f"**{len(vt_employees)} employees based in VT**")
                
                # Build display
                display = vt_employees.copy()
                display_cols = ['Employee']
                col_names = ['Employee']

                if 'Total_Hours' in display.columns:
                    display['Total_Hours'] = display['Total_Hours'].apply(lambda x: f"{x:.1f}h")
                    display_cols.append('Total_Hours')
                    col_names.append('Total Hours')

                if 'Locations' in display.columns:
                    display_cols.append('Locations')
                    col_names.append('Locations')

                if 'Entries' in display.columns:
                    display_cols.append('Entries')
                    col_names.append('Days Worked')

                display = display[display_cols]
                display.columns = col_names
                st.dataframe(display, use_container_width=True, hide_index=True, height=400)
            else:
                st.info("No VT employees in data")
    else:
        # No site data, show combined
        display = emp_summary.copy()
        display_cols = ['Employee']
        col_names = ['Employee']

        if 'Total_Hours' in display.columns:
            display['Total_Hours'] = display['Total_Hours'].apply(lambda x: f"{x:.1f}h")
            display_cols.append('Total_Hours')
            col_names.append('Total Hours')

        if 'Locations' in display.columns:
            display_cols.append('Locations')
            col_names.append('Locations')

        if 'Entries' in display.columns:
            display_cols.append('Entries')
            col_names.append('Days Worked')

        display = display[display_cols]
        display.columns = col_names
        st.dataframe(display, use_container_width=True, hide_index=True, height=400)

    st.divider()

    # Individual detail
    st.subheader("📊 Individual Detail")

    selected = st.selectbox("Select Employee", emp_summary['Employee'].tolist())

    if selected:
        emp_data = personnel_df[personnel_df[emp_name_col] == selected].copy()

        if date_col and date_col in emp_data.columns:
            emp_data[date_col] = pd.to_datetime(emp_data[date_col], errors='coerce')
            emp_data = emp_data.sort_values(date_col, ascending=False)

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if hours_col:
                st.metric("Total Hours", f"{emp_data[hours_col].sum():.1f}h")
            else:
                st.metric("Total Hours", "N/A")

        with col2:
            st.metric("Days Worked", len(emp_data))

        with col3:
            if hours_col:
                st.metric("Avg Hours/Day", f"{emp_data[hours_col].mean():.1f}h")
            else:
                st.metric("Avg Hours/Day", "N/A")
        
        with col4:
            if has_site:
                primary = emp_data['Site'].value_counts().index[0] if len(emp_data) > 0 else 'UNK'
                emoji = "🟦" if primary == "NY" else "🟩" if primary == "VT" else "⚫"
                st.metric("Primary Site", f"{emoji} {primary}")

        st.subheader("Recent Activity - Hours by Job Code by Day")

        # Create hours by job code by day view
        if job_col and date_col and hours_col:
            # Group by date and job code
            daily_jobs = emp_data.groupby([
                emp_data[date_col].dt.date,
                job_col
            ])[hours_col].sum().reset_index()
            
            daily_jobs.columns = ['Date', 'Job Code', 'Hours']
            daily_jobs = daily_jobs.sort_values('Date', ascending=False)
            
            # Format hours
            daily_jobs['Hours'] = daily_jobs['Hours'].apply(lambda x: f"{x:.1f}h")
            
            st.dataframe(daily_jobs.head(30), use_container_width=True, hide_index=True)
        elif date_col and hours_col:
            # No job code, just show by day
            daily = emp_data.groupby(emp_data[date_col].dt.date)[hours_col].sum().reset_index()
            daily.columns = ['Date', 'Hours']
            daily = daily.sort_values('Date', ascending=False)
            daily['Hours'] = daily['Hours'].apply(lambda x: f"{x:.1f}h")
            
            st.dataframe(daily.head(30), use_container_width=True, hide_index=True)
        else:
            st.info("Job code or date information not available")

    st.divider()

    # Tips
    with st.expander("💡 Understanding Employee Hours"):
        st.markdown("""
        **Metrics Explained:**
        
        - **Total Hours (All Time)**: All hours worked by all employees in loaded data
        - **Hours Since Monday**: Hours worked since Monday at 12:01am this week
        - **Total Hours (per employee)**: All hours worked by that employee
        - **Days Worked**: Number of separate work sessions
        - **Primary Site**: The site where employee works most often
        
        **Week Calculation:**
        
        - Week starts: Monday at 12:01am
        - Week ends: Sunday at 11:59pm
        - "Hours Since Monday" shows current week progress
        
        **Employee Hours by State:**
        
        - Employees are grouped by their primary work site
        - NY and VT tabs show separate rankings
        - Makes dispatch and planning easier
        
        **Recent Activity:**
        
        - Shows hours by job code by day
        - Helps identify what type of work was done
        - Useful for productivity analysis
        
        **Using This Page:**
        
        - **Weekly Planning**: Check "Hours Since Monday" to track weekly progress
        - **Site Assignment**: Use state tabs to see who works where
        - **Productivity**: Review job code breakdown to see task distribution
        - **Scheduling**: Balance workload across employees and sites
        """)</document_content></document>
