"""
Repairs Analysis Page Module
Parses unstructured Notes and Repairs columns to extract actionable repair information
"""

import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta


def parse_completion_status(text):
    """Extract completion status from text"""
    if not text or pd.isna(text):
        return None

    text_upper = str(text).upper()

    # Check for completion indicators
    if 'NOT COMPLETE' in text_upper or 'NOTCOMPLETE' in text_upper:
        return 'Not Complete'
    elif 'COMPLETE' in text_upper or 'REPEAR COMPLETE' in text_upper or 'REPAIR COMPLETE' in text_upper:
        return 'Complete'
    elif 'LINE COMPLETE' in text_upper:
        return 'Complete'

    return None


def parse_issue_type(text):
    """Extract issue type(s) from text"""
    if not text or pd.isna(text):
        return []

    text_upper = str(text).upper()
    issues = []

    # Tree damage
    if any(word in text_upper for word in ['TREE', 'CHAINSAW', 'CUT OFF']):
        issues.append('Tree Damage')

    # Spinseal issues
    if any(word in text_upper for word in ['SPINSEAL', 'SPENSEAL', 'SPIN SEAL', 'SPIN SL', 'SPN SL']):
        if 'REWELD' in text_upper:
            issues.append('Spinseal Reweld')
        elif 'BROKEN' in text_upper:
            issues.append('Spinseal Broken')
        else:
            issues.append('Spinseal Issue')

    # Stainless needs
    if 'STAINLESS' in text_upper:
        issues.append('Needs Stainless')

    # Monitor/antenna issues
    if 'ANTENNA' in text_upper:
        issues.append('Monitor Antenna')

    # General broken items
    if 'BROKEN' in text_upper and 'SPINSEAL' not in text_upper and 'SPENSEAL' not in text_upper:
        issues.append('Broken Equipment')

    return issues if issues else ['General Repair']


def parse_location(text):
    """Extract location information from text"""
    if not text or pd.isna(text):
        return None

    text_upper = str(text).upper()
    locations = []

    # Position markers
    if '@MID' in text_upper or '@ MID' in text_upper or 'MIDDLE' in text_upper or 'IN THE MIDDLE' in text_upper:
        locations.append('Middle')
    if '@BTM' in text_upper or '@ BTM' in text_upper or 'BOTTOM' in text_upper:
        locations.append('Bottom')
    if 'TOP' in text_upper and 'STAINLESS' not in text_upper:  # Avoid "top need stainless"
        # Check if "top" is actually a location reference
        if 'AT TOP' in text_upper or 'THE TOP' in text_upper or '@TOP' in text_upper:
            locations.append('Top')

    # Component locations
    if 'MONITOR' in text_upper:
        locations.append('Monitor')
    if 'CONDUCTOR' in text_upper:
        locations.append('Conductor')
    if 'MAINLINE' in text_upper:
        locations.append('Mainline')

    # Distance descriptors
    if 'CLOSE TO END' in text_upper or 'AT THE END' in text_upper:
        locations.append('Near End')
    if 'BEGINNING' in text_upper or 'AT THE BEGINNING' in text_upper:
        locations.append('Beginning')

    return ', '.join(locations) if locations else None


def extract_repair_data(personnel_df):
    """
    Extract and structure repair information from personnel data

    Returns DataFrame with parsed repair information
    """
    if personnel_df.empty:
        return pd.DataFrame()

    # Filter to rows with repair-related jobs or notes
    repair_keywords = ['fix', 'repair', 'tubing', 'issue', 'maintenance']

    # Get relevant columns
    notes_col = None
    repairs_col = None

    for col in personnel_df.columns:
        col_lower = col.lower()
        if 'notes' in col_lower:
            notes_col = col
        if 'repair' in col_lower and 'needed' in col_lower:
            repairs_col = col

    if not notes_col and not repairs_col:
        return pd.DataFrame()

    repairs = []

    for idx, row in personnel_df.iterrows():
        notes_text = str(row.get(notes_col, '')) if notes_col else ''
        repairs_text = str(row.get(repairs_col, '')) if repairs_col else ''

        # Skip if both are empty or just nan
        if (not notes_text or notes_text == 'nan') and (not repairs_text or repairs_text == 'nan'):
            continue

        # Combine text for parsing
        combined_text = f"{repairs_text} {notes_text}".strip()

        # Skip generic entries without repair info
        if not any(keyword in combined_text.lower() for keyword in
                   ['complete', 'tree', 'spinseal', 'spenseal', 'stainless', 'broken',
                    'reweld', 'antenna', 'repair', 'fix', 'need', 'leak']):
            continue

        # Parse the data
        completion = parse_completion_status(combined_text)
        issues = parse_issue_type(combined_text)
        location = parse_location(combined_text)

        # Get metadata
        date = row.get('Date', None)
        employee = f"{row.get('EE First', '')} {row.get('EE Last', '')}".strip()
        mainline = row.get('mainline.', row.get('mainline', ''))
        job = row.get('Job', '')
        site = row.get('Site', 'Unknown')

        for issue in issues:
            repairs.append({
                'Date': date,
                'Site': site,
                'Employee': employee,
                'Mainline': mainline,
                'Job': job,
                'Issue Type': issue,
                'Location': location,
                'Status': completion,
                'Repairs Noted': repairs_text if repairs_text != 'nan' else '',
                'Notes': notes_text if notes_text != 'nan' else ''
            })

    df = pd.DataFrame(repairs)

    if not df.empty and 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.sort_values('Date', ascending=False)

    return df


def render(personnel_df, vacuum_df=None):
    """Render the repairs analysis page"""

    st.title("Repairs Analysis")
    st.markdown("*Parsed repair information from timesheet notes*")

    if personnel_df.empty:
        st.warning("No personnel data available")
        return

    # Extract repair data
    repairs_df = extract_repair_data(personnel_df)

    if repairs_df.empty:
        st.info("No repair notes found in the current data")
        return

    # Filters row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Issue type filter
        issue_types = ['All'] + sorted(repairs_df['Issue Type'].unique().tolist())
        selected_issue = st.selectbox("Issue Type", issue_types)

    with col2:
        # Status filter
        statuses = ['All', 'Complete', 'Not Complete', 'Unknown']
        selected_status = st.selectbox("Status", statuses)

    with col3:
        # Mainline filter
        mainlines = ['All'] + sorted([m for m in repairs_df['Mainline'].unique() if m and str(m) != 'nan'])
        selected_mainline = st.selectbox("Mainline", mainlines)

    with col4:
        # Employee filter
        employees = ['All'] + sorted([e for e in repairs_df['Employee'].unique() if e and str(e) != 'nan' and e.strip()])
        selected_employee = st.selectbox("Employee", employees)

    # Apply filters
    filtered_df = repairs_df.copy()

    if selected_issue != 'All':
        filtered_df = filtered_df[filtered_df['Issue Type'] == selected_issue]

    if selected_status != 'All':
        if selected_status == 'Unknown':
            filtered_df = filtered_df[filtered_df['Status'].isna()]
        else:
            filtered_df = filtered_df[filtered_df['Status'] == selected_status]

    if selected_mainline != 'All':
        filtered_df = filtered_df[filtered_df['Mainline'] == selected_mainline]

    if selected_employee != 'All':
        filtered_df = filtered_df[filtered_df['Employee'] == selected_employee]

    st.divider()

    # Summary metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Issues", len(filtered_df))

    with col2:
        complete = len(filtered_df[filtered_df['Status'] == 'Complete'])
        st.metric("Completed", complete)

    with col3:
        incomplete = len(filtered_df[filtered_df['Status'] == 'Not Complete'])
        st.metric("Not Complete", incomplete)

    with col4:
        unknown = len(filtered_df[filtered_df['Status'].isna()])
        st.metric("Unknown Status", unknown)

    with col5:
        mainlines_affected = filtered_df['Mainline'].nunique()
        st.metric("Mainlines", mainlines_affected)

    st.divider()

    # Two column layout for charts
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("Issues by Type")
        issue_counts = filtered_df['Issue Type'].value_counts()
        if not issue_counts.empty:
            st.bar_chart(issue_counts)

    with chart_col2:
        st.subheader("Completion Status")
        status_counts = filtered_df['Status'].fillna('Unknown').value_counts()
        if not status_counts.empty:
            st.bar_chart(status_counts)

    st.divider()

    # Outstanding repairs section
    st.subheader("Outstanding Repairs")
    outstanding = filtered_df[filtered_df['Status'] != 'Complete'].copy()

    if outstanding.empty:
        st.success("No outstanding repairs in filtered data!")
    else:
        # Group by mainline for actionable view
        st.markdown(f"**{len(outstanding)} repairs need attention:**")

        # Show by issue type
        for issue_type in outstanding['Issue Type'].unique():
            issue_items = outstanding[outstanding['Issue Type'] == issue_type]

            with st.expander(f"{issue_type} ({len(issue_items)} items)", expanded=True):
                display_df = issue_items[['Date', 'Mainline', 'Location', 'Employee', 'Repairs Noted', 'Notes']].copy()
                display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d') if 'Date' in display_df.columns else ''

                # Clean up display
                display_df = display_df.fillna('')
                display_df.columns = ['Date', 'Mainline', 'Location', 'Reported By', 'Repair Notes', 'Additional Notes']

                st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.divider()

    # Recent activity
    st.subheader("Recent Repair Activity")

    recent = filtered_df.head(20).copy()
    if not recent.empty:
        display_cols = ['Date', 'Site', 'Mainline', 'Issue Type', 'Location', 'Status', 'Employee']
        display_recent = recent[display_cols].copy()
        display_recent['Date'] = display_recent['Date'].dt.strftime('%Y-%m-%d %H:%M') if 'Date' in display_recent.columns else ''
        display_recent['Status'] = display_recent['Status'].fillna('Unknown')
        display_recent = display_recent.fillna('')

        st.dataframe(display_recent, use_container_width=True, hide_index=True)

    st.divider()

    # Detailed view with all data
    with st.expander("Full Repair Data"):
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    # Issue type guide
    with st.expander("Issue Type Guide"):
        st.markdown("""
        **Issue Categories:**

        - **Tree Damage** - Trees fallen on lines, need chainsaw work
        - **Spinseal Reweld** - Spinseal connections needing rewelding
        - **Spinseal Broken** - Broken spinseal components
        - **Spinseal Issue** - Other spinseal problems
        - **Needs Stainless** - Areas requiring stainless steel fittings
        - **Monitor Antenna** - Monitor antenna issues
        - **Broken Equipment** - Other broken equipment
        - **General Repair** - Other repairs mentioned

        **Location Markers:**

        - **@MID / Middle** - Middle section of mainline
        - **@BTM / Bottom** - Bottom section
        - **Top** - Top section
        - **Monitor** - At or near monitor location
        - **Conductor** - At conductor line
        - **Near End / Beginning** - Distance markers
        """)
