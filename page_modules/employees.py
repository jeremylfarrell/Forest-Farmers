"""
Employee Performance Page Module
Displays employee activity and productivity metrics
"""

import streamlit as st
import pandas as pd
import config
from utils import find_column


def render(personnel_df):
    """Render employee performance page"""

    st.title("👥 Employee Performance")

    if personnel_df.empty:
        st.warning("No personnel data available")
        return

    # Find column names (case-insensitive)
    emp_name_col = find_column(personnel_df, 'Employee Name', 'employee', 'name')
    mainline_col = find_column(personnel_df, 'mainline', 'Mainline', 'location', 'sensor')
    hours_col = find_column(personnel_df, 'Hours', 'hours', 'time')
    date_col = find_column(personnel_df, 'Date', 'date', 'timestamp')

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

    # Filter by minimum hours if available
    if 'Total_Hours' in emp_summary.columns:
        emp_summary = emp_summary[emp_summary['Total_Hours'] >= config.MIN_HOURS_FOR_RANKING]
        emp_summary = emp_summary.sort_values('Total_Hours', ascending=False)

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Employees", len(emp_summary))

    with col2:
        if 'Total_Hours' in emp_summary.columns:
            st.metric("Total Hours", f"{emp_summary['Total_Hours'].sum():.1f}h")
        else:
            st.metric("Total Hours", "N/A")

    with col3:
        if 'Locations' in emp_summary.columns:
            st.metric("Locations Worked", int(emp_summary['Locations'].sum()))
        else:
            st.metric("Locations Worked", "N/A")

    with col4:
        if 'Total_Hours' in emp_summary.columns:
            st.metric("Avg Hours/Employee", f"{emp_summary['Total_Hours'].mean():.1f}h")
        else:
            st.metric("Avg Hours/Employee", "N/A")

    st.divider()

    # Top performers
    st.subheader("🏆 Employee Rankings")

    display = emp_summary.copy()

    # Format display columns
    display_cols = ['Employee']
    col_names = ['Employee']

    if 'Total_Hours' in display.columns:
        display['Total_Hours'] = display['Total_Hours'].apply(lambda x: f"{x:.1f}h")
        display_cols.append('Total_Hours')
        col_names.append('Hours')

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
            emp_data = emp_data.sort_values(date_col, ascending=False)

        col1, col2, col3 = st.columns(3)

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

        st.subheader("Recent Activity")

        # Build display columns
        display_cols = []
        if date_col:
            display_cols.append(date_col)
        if mainline_col:
            display_cols.append(mainline_col)
        if hours_col:
            display_cols.append(hours_col)

        # Add any other interesting columns
        job_col = find_column(emp_data, 'Job', 'job', 'task', 'work')
        if job_col:
            display_cols.append(job_col)

        if display_cols:
            recent = emp_data[display_cols].head(20)
            st.dataframe(recent, use_container_width=True, hide_index=True)
        else:
            st.info("No detail columns available")
