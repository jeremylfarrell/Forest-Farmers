"""
Repairs Analysis Page Module
Parses unstructured Notes and Repairs columns to extract actionable repair information
"""

import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
from schema import SchemaMapper


def parse_completion_status(text):
    """
    Extract completion status from text with robust pattern matching.

    Returns:
        'Complete', 'Not Complete', or None
    """
    if not text or pd.isna(text):
        return None

    # Validate input is string-like
    if not isinstance(text, (str, bytes)):
        return None

    try:
        text_upper = str(text).upper().strip()
    except (ValueError, TypeError):
        return None

    # Check for "NOT COMPLETE" patterns first (more specific)
    # Use word boundaries to avoid matching within words
    not_complete_patterns = [
        r'\bNOT\s+COMPLETE\b',
        r'\bNOTCOMPLETE\b',
        r'\bINCOMPLETE\b',
        r'\bUNFINISHED\b',
        r'\bNOT\s+DONE\b'
    ]

    for pattern in not_complete_patterns:
        if re.search(pattern, text_upper):
            return 'Not Complete'

    # Check for completion patterns (less specific, check after negatives)
    # Include common variations and typos
    complete_patterns = [
        r'\bCOMPLETE\b',
        r'\bREPAIR\s+COMPLETE\b',
        r'\bREPEAR\s+COMPLETE\b',  # Common typo
        r'\bLINE\s+COMPLETE\b',
        r'\bMAINLINE\s+COMPLETE\b',
        r'\bDONE\b',
        r'\bFINISHED\b',
        r'\bFIXED\b',
        r'\bRESOLVED\b',
        r'\bREPAIRED\b'
    ]

    for pattern in complete_patterns:
        if re.search(pattern, text_upper):
            return 'Complete'

    return None


def parse_issue_type(text):
    """
    Extract issue type(s) from text with improved pattern matching.

    Returns:
        List of issue types found (at least ['General Repair'] if no specific type detected)
    """
    if not text or pd.isna(text):
        return []

    # Validate input is string-like
    if not isinstance(text, (str, bytes)):
        return []

    try:
        text_upper = str(text).upper().strip()
    except (ValueError, TypeError):
        return []

    issues = []

    # Tree damage - use word boundaries
    if re.search(r'\b(TREE|CHAINSAW)\b', text_upper) or 'CUT OFF' in text_upper:
        issues.append('Tree Damage')

    # Spinseal issues - check variations with word boundaries
    spinseal_patterns = [r'\bSPINSEAL\b', r'\bSPENSEAL\b', r'\bSPIN\s+SEAL\b', r'\bSPN\s+SL\b']
    has_spinseal = any(re.search(pattern, text_upper) for pattern in spinseal_patterns)

    if has_spinseal:
        if re.search(r'\bREWELD\b', text_upper):
            issues.append('Spinseal Reweld')
        elif re.search(r'\bBROKEN\b', text_upper):
            issues.append('Spinseal Broken')
        else:
            issues.append('Spinseal Issue')

    # Stainless needs - word boundary
    if re.search(r'\bSTAINLESS\b', text_upper):
        issues.append('Needs Stainless')

    # Monitor/antenna issues - word boundary
    if re.search(r'\bANTENNA\b', text_upper):
        issues.append('Monitor Antenna')

    # Leak detection - word boundary
    if re.search(r'\b(LEAK|LEAKING|LEAKS)\b', text_upper):
        issues.append('Leak Detected')

    # Tubing issues - word boundary
    if re.search(r'\bTUBING\b', text_upper):
        issues.append('Tubing Issue')

    # General broken items - only if not spinseal
    if re.search(r'\bBROKEN\b', text_upper) and not has_spinseal:
        issues.append('Broken Equipment')

    return issues if issues else ['General Repair']


def parse_location(text):
    """
    Extract location information from text with improved pattern matching.

    Returns:
        Comma-separated string of locations or None
    """
    if not text or pd.isna(text):
        return None

    # Validate input is string-like
    if not isinstance(text, (str, bytes)):
        return None

    try:
        text_upper = str(text).upper().strip()
    except (ValueError, TypeError):
        return None

    locations = []

    # Position markers - use more specific patterns
    if re.search(r'@\s*MID\b|@ MID|\bMIDDLE\b|IN THE MIDDLE', text_upper):
        locations.append('Middle')
    if re.search(r'@\s*BTM\b|@ BTM|\bBOTTOM\b', text_upper):
        locations.append('Bottom')
    # TOP - only match as location reference, not in words like "STOP", "LAPTOP"
    if re.search(r'(AT|THE|@)\s*TOP\b|^\s*TOP\b', text_upper):
        locations.append('Top')

    # Component locations - use word boundaries
    if re.search(r'\bMONITOR\b', text_upper):
        locations.append('Monitor')
    if re.search(r'\bCONDUCTOR\b', text_upper):
        locations.append('Conductor')
    if re.search(r'\bMAINLINE\b', text_upper):
        locations.append('Mainline')

    # Distance descriptors
    if re.search(r'(CLOSE TO|AT THE)\s+END\b|END OF', text_upper):
        locations.append('Near End')
    if re.search(r'\bBEGINNING\b|AT THE BEGINNING|START OF', text_upper):
        locations.append('Beginning')

    return ', '.join(locations) if locations else None


def extract_repair_data(personnel_df):
    """
    Extract and structure repair information from personnel data.
    Uses SchemaMapper for flexible column lookups.

    Returns:
        DataFrame with parsed repair information, or empty DataFrame on error
    """
    if personnel_df.empty:
        return pd.DataFrame()

    try:
        # Use SchemaMapper for flexible column finding
        mapper = SchemaMapper(personnel_df)

        # Get relevant columns using schema mapper
        notes_col = mapper.get_column('notes')
        repairs_col = mapper.get_column('repairs_needed')

        if not notes_col and not repairs_col:
            # No repair-related columns found
            return pd.DataFrame()

        repairs = []
        parse_errors = 0
        total_rows = 0

        for idx, row in personnel_df.iterrows():
            total_rows += 1

            try:
                # Safely get text values
                notes_text = ''
                repairs_text = ''

                if notes_col:
                    val = row.get(notes_col, '')
                    if pd.notna(val) and isinstance(val, (str, bytes)):
                        notes_text = str(val).strip()

                if repairs_col:
                    val = row.get(repairs_col, '')
                    if pd.notna(val) and isinstance(val, (str, bytes)):
                        repairs_text = str(val).strip()

                # Skip if both are empty
                if not notes_text and not repairs_text:
                    continue

                # Combine text for parsing
                combined_text = f"{repairs_text} {notes_text}".strip()

                # Skip generic entries without repair keywords
                repair_keywords = ['complete', 'tree', 'spinseal', 'spenseal', 'stainless',
                                 'broken', 'reweld', 'antenna', 'repair', 'fix', 'need', 'leak',
                                 'tubing', 'issue', 'maintenance']

                if not any(keyword in combined_text.lower() for keyword in repair_keywords):
                    continue

                # Parse the data with error handling
                try:
                    completion = parse_completion_status(combined_text)
                    issues = parse_issue_type(combined_text)
                    location = parse_location(combined_text)
                except Exception as parse_err:
                    # Skip this row if parsing fails
                    parse_errors += 1
                    continue

                # Get metadata using SchemaMapper
                date = row.get(mapper.get_column('date') or 'Date', None)

                # Get employee name
                employee_name_col = mapper.get_column('employee_name')
                if employee_name_col:
                    employee = str(row.get(employee_name_col, '')).strip()
                else:
                    # Fall back to EE First/Last columns
                    first = str(row.get('EE First', '')).strip()
                    last = str(row.get('EE Last', '')).strip()
                    employee = f"{first} {last}".strip()

                # Get mainline using SchemaMapper
                mainline_col = mapper.get_column('mainline')
                mainline = str(row.get(mainline_col or 'mainline', '')).strip() if mainline_col else ''

                # Get job and site
                job = str(row.get('Job', '')).strip()
                site = str(row.get(mapper.get_column('site') or 'Site', 'Unknown')).strip()

                # Create entry for each issue type
                # NOTE: This creates multiple rows for repairs with multiple issues
                # (e.g., "TREE damage and BROKEN spinseal" creates 2 rows)
                # This allows filtering by issue type but inflates total counts
                for issue in issues:
                    repairs.append({
                        'Date': date,
                        'Site': site,
                        'Employee': employee if employee else 'Unknown',
                        'Mainline': mainline,
                        'Job': job,
                        'Issue Type': issue,
                        'Location': location,
                        'Status': completion,
                        'Repairs Noted': repairs_text,
                        'Notes': notes_text
                    })

            except Exception as row_err:
                # Skip rows that cause errors
                parse_errors += 1
                continue

        # Create DataFrame
        df = pd.DataFrame(repairs)

        if not df.empty and 'Date' in df.columns:
            try:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df = df.sort_values('Date', ascending=False)
            except Exception:
                pass  # Keep dataframe even if date sorting fails

        # Show warning if many parse errors
        if parse_errors > 0 and parse_errors / max(total_rows, 1) > 0.1:
            st.warning(f"⚠️ {parse_errors} of {total_rows} rows had parsing errors and were skipped")

        return df

    except Exception as e:
        st.error(f"Error extracting repair data: {str(e)}")
        return pd.DataFrame()

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
        st.info("📋 No repair notes found in the current data")
        with st.expander("ℹ️ What does this mean?"):
            st.markdown("""
            **Why might no repairs be found?**

            1. **Column names don't match** - Looking for columns containing "notes" or "repairs needed"
            2. **No repair keywords** - Need words like: complete, tree, spinseal, broken, leak, etc.
            3. **Wrong time period** - Adjust date range filter in sidebar
            4. **Site filter** - Check if you're viewing the correct site (NY/VT/All)

            **Expected column names:**
            - Notes column: "Notes", "Comments", "Employee Notes", etc.
            - Repairs column: "Repairs Needed", "Repairs", etc.

            **Repair keywords detected:**
            complete, tree, spinseal, broken, leak, tubing, stainless, antenna, reweld, fix, repair
            """)
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
    st.caption("ℹ️ Note: Repairs with multiple issue types appear as separate rows, so counts may exceed unique repair entries")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Issue Entries", len(filtered_df))

    with col2:
        complete = len(filtered_df[filtered_df['Status'] == 'Complete'])
        st.metric("Completed", complete)

    with col3:
        incomplete = len(filtered_df[filtered_df['Status'] == 'Not Complete'])
        st.metric("Not Complete", incomplete)

    with col4:
        unknown = len(filtered_df[filtered_df['Status'].isna()])
        st.metric("Unknown Status", unknown, help="No completion keywords found in repair notes")

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
