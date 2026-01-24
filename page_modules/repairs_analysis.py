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


def link_repair_lifecycle(repairs_df, max_days_apart=14):
    """
    Link related repair entries to track lifecycle from reported → complete.
    Groups repairs by mainline + issue type within a time window.

    Args:
        repairs_df: DataFrame with individual repair entries
        max_days_apart: Maximum days between related entries (default 14)

    Returns:
        DataFrame with added columns: Repair_ID, Lifecycle_Status, Days_Open, Has_Update
    """
    if repairs_df.empty or 'Date' not in repairs_df.columns:
        return repairs_df

    try:
        # Sort by date (oldest first for linking)
        df = repairs_df.copy()
        df = df.sort_values('Date')

        # Create repair groups based on mainline + issue type
        df['Repair_Group'] = df['Mainline'].fillna('Unknown') + '|' + df['Issue Type']

        # Assign repair IDs and track lifecycle
        repair_id = 0
        repair_tracker = {}  # {group_key: [(repair_id, date, status)]}

        repair_ids = []
        lifecycle_statuses = []
        days_open_list = []
        has_updates = []

        for idx, row in df.iterrows():
            group_key = row['Repair_Group']
            current_date = row['Date']
            current_status = row['Status']

            # Find if this belongs to an existing repair
            matched_repair_id = None

            if group_key in repair_tracker:
                # Look for recent repairs in same group
                for tracked_id, tracked_date, tracked_status in repair_tracker[group_key]:
                    if pd.notna(current_date) and pd.notna(tracked_date):
                        days_apart = (current_date - tracked_date).days

                        # Link if within time window
                        if 0 <= days_apart <= max_days_apart:
                            # Link to this repair
                            matched_repair_id = tracked_id

                            # Update the tracker if this is a completion
                            if current_status == 'Complete' and tracked_status != 'Complete':
                                # Remove old entry and add updated one
                                repair_tracker[group_key] = [
                                    (tid, tdate, tstat) for tid, tdate, tstat in repair_tracker[group_key]
                                    if tid != tracked_id
                                ]
                                repair_tracker[group_key].append((tracked_id, current_date, 'Complete'))
                            break

            # If no match found, create new repair
            if matched_repair_id is None:
                repair_id += 1
                matched_repair_id = repair_id

                # Add to tracker
                if group_key not in repair_tracker:
                    repair_tracker[group_key] = []
                repair_tracker[group_key].append((matched_repair_id, current_date, current_status))

            # Determine lifecycle status
            if current_status == 'Complete':
                lifecycle_status = 'Completed'
            elif current_status == 'Not Complete':
                lifecycle_status = 'In Progress'
            else:
                lifecycle_status = 'Reported'

            # Calculate days open (from first mention to this entry)
            first_date = current_date
            for tracked_id, tracked_date, _ in repair_tracker.get(group_key, []):
                if tracked_id == matched_repair_id and pd.notna(tracked_date):
                    first_date = tracked_date
                    break

            days_open = None
            if pd.notna(current_date) and pd.notna(first_date):
                days_open = (current_date - first_date).days

            # Check if there are updates (multiple entries for same repair ID)
            has_update = sum(1 for tid, _, _ in repair_tracker.get(group_key, []) if tid == matched_repair_id) > 1

            repair_ids.append(matched_repair_id)
            lifecycle_statuses.append(lifecycle_status)
            days_open_list.append(days_open)
            has_updates.append(has_update)

        # Add new columns
        df['Repair_ID'] = repair_ids
        df['Lifecycle_Status'] = lifecycle_statuses
        df['Days_Open'] = days_open_list
        df['Has_Update'] = has_updates

        # Resort by date descending
        df = df.sort_values('Date', ascending=False)

        # Drop temporary column
        df = df.drop(columns=['Repair_Group'])

        return df

    except Exception as e:
        st.warning(f"Could not link repair lifecycle: {str(e)}")
        # Return original data if linking fails
        return repairs_df


def get_active_repairs(repairs_df):
    """
    Get currently active (unresolved) repairs.
    A repair is active if its most recent entry is not 'Completed'.

    Args:
        repairs_df: DataFrame with Repair_ID and Lifecycle_Status columns

    Returns:
        DataFrame with only active repairs (most recent entry per Repair_ID that isn't completed)
    """
    if repairs_df.empty or 'Repair_ID' not in repairs_df.columns:
        return repairs_df

    try:
        # Get the most recent entry for each Repair_ID
        latest_entries = repairs_df.sort_values('Date').groupby('Repair_ID').last().reset_index()

        # Filter to only non-completed repairs
        active = latest_entries[latest_entries['Lifecycle_Status'] != 'Completed'].copy()

        return active

    except Exception as e:
        st.warning(f"Could not filter active repairs: {str(e)}")
        return repairs_df


def render(personnel_df, vacuum_df=None):
    """Render the repairs analysis page"""

    st.title("Repairs Analysis")
    st.markdown("*Parsed repair information from timesheet notes*")

    if personnel_df.empty:
        st.warning("No personnel data available")
        return

    # Extract repair data
    repairs_df = extract_repair_data(personnel_df)

    # Link repairs to track lifecycle (needed → in progress → complete)
    if not repairs_df.empty:
        repairs_df = link_repair_lifecycle(repairs_df, max_days_apart=14)

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
    st.caption("ℹ️ Note: 'Unique Repairs' counts distinct issues; 'Entries' counts all timesheet records (same repair tracked over multiple days)")

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        unique_repairs = filtered_df['Repair_ID'].nunique() if 'Repair_ID' in filtered_df.columns else len(filtered_df)
        st.metric("Unique Repairs", unique_repairs, help="Distinct repair issues (same repair tracked across days counts as 1)")

    with col2:
        st.metric("Total Entries", len(filtered_df), help="All timesheet repair entries")

    with col3:
        # Count unique repairs that are completed (latest status = Complete)
        if 'Repair_ID' in filtered_df.columns and 'Lifecycle_Status' in filtered_df.columns:
            completed_repairs = filtered_df[filtered_df['Lifecycle_Status'] == 'Completed']['Repair_ID'].nunique()
        else:
            completed_repairs = len(filtered_df[filtered_df['Status'] == 'Complete'])
        st.metric("Completed", completed_repairs)

    with col4:
        # Count unique repairs that are in progress
        if 'Lifecycle_Status' in filtered_df.columns:
            in_progress_repairs = filtered_df[filtered_df['Lifecycle_Status'] == 'In Progress']['Repair_ID'].nunique()
            st.metric("In Progress", in_progress_repairs)
        else:
            incomplete = len(filtered_df[filtered_df['Status'] == 'Not Complete'])
            st.metric("Not Complete", incomplete)

    with col5:
        # Count unique repairs that are just reported
        if 'Lifecycle_Status' in filtered_df.columns:
            reported_repairs = filtered_df[filtered_df['Lifecycle_Status'] == 'Reported']['Repair_ID'].nunique()
            st.metric("Reported", reported_repairs)
        else:
            unknown = len(filtered_df[filtered_df['Status'].isna()])
            st.metric("Unknown Status", unknown, help="No completion keywords found in repair notes")

    with col6:
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

    # Get active (unresolved) repairs - shows most recent entry per repair, excludes completed
    outstanding = get_active_repairs(filtered_df)

    if outstanding.empty:
        st.success("✅ No outstanding repairs in filtered data!")
    else:
        # Count unique repairs
        unique_outstanding = outstanding['Repair_ID'].nunique() if 'Repair_ID' in outstanding.columns else len(outstanding)
        st.markdown(f"**{unique_outstanding} unique repairs need attention:**")

        # Show by issue type
        for issue_type in outstanding['Issue Type'].unique():
            issue_items = outstanding[outstanding['Issue Type'] == issue_type]

            with st.expander(f"{issue_type} ({len(issue_items)} items)", expanded=True):
                # Include lifecycle columns if available
                display_cols = ['Date', 'Mainline', 'Location', 'Employee', 'Repairs Noted', 'Notes']
                if 'Lifecycle_Status' in issue_items.columns:
                    display_cols.insert(1, 'Lifecycle_Status')
                if 'Days_Open' in issue_items.columns:
                    display_cols.insert(2, 'Days_Open')

                display_df = issue_items[display_cols].copy()
                display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d') if 'Date' in display_df.columns else ''

                # Clean up display
                display_df = display_df.fillna('')

                # Rename columns for clarity
                col_names = ['Date', 'Mainline', 'Location', 'Reported By', 'Repair Notes', 'Additional Notes']
                if 'Lifecycle_Status' in display_cols:
                    col_names.insert(1, 'Status')
                if 'Days_Open' in display_cols:
                    col_names.insert(2, 'Days Open')
                display_df.columns = col_names

                st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.divider()

    # Recent activity
    st.subheader("Recent Repair Activity")

    recent = filtered_df.head(20).copy()
    if not recent.empty:
        display_cols = ['Date', 'Site', 'Mainline', 'Issue Type', 'Location']
        if 'Lifecycle_Status' in recent.columns:
            display_cols.append('Lifecycle_Status')
        else:
            display_cols.append('Status')
        if 'Days_Open' in recent.columns:
            display_cols.append('Days_Open')
        display_cols.append('Employee')

        display_recent = recent[display_cols].copy()
        display_recent['Date'] = display_recent['Date'].dt.strftime('%Y-%m-%d %H:%M') if 'Date' in display_recent.columns else ''

        # Rename lifecycle columns for clarity
        rename_map = {
            'Lifecycle_Status': 'Lifecycle',
            'Days_Open': 'Days Open',
            'Status': 'Status'
        }
        display_recent = display_recent.rename(columns=rename_map)
        display_recent = display_recent.fillna('')

        st.dataframe(display_recent, use_container_width=True, hide_index=True)

    st.divider()

    # Repair History/Timeline - Show all entries for repairs with multiple entries
    if 'Repair_ID' in filtered_df.columns and 'Has_Update' in filtered_df.columns:
        repairs_with_updates = filtered_df[filtered_df['Has_Update'] == True]['Repair_ID'].unique()
        if len(repairs_with_updates) > 0:
            st.subheader("Repair Lifecycle Timeline")
            st.caption(f"📅 Showing {len(repairs_with_updates)} repairs with multiple entries (tracked over time)")

            # Let user select a repair to view its history
            repair_options = []
            for repair_id in sorted(repairs_with_updates):
                # Get info about this repair
                repair_entries = filtered_df[filtered_df['Repair_ID'] == repair_id]
                first_entry = repair_entries.iloc[0]
                mainline = first_entry['Mainline']
                issue_type = first_entry['Issue Type']
                entry_count = len(repair_entries)
                repair_options.append(f"{repair_id}: {mainline} - {issue_type} ({entry_count} entries)")

            if repair_options:
                selected_repair_str = st.selectbox("Select repair to view timeline:", repair_options)
                selected_repair_id = selected_repair_str.split(':')[0]

                # Show timeline for selected repair
                timeline_df = filtered_df[filtered_df['Repair_ID'] == selected_repair_id].copy()
                timeline_df = timeline_df.sort_values('Date')

                st.markdown(f"**Timeline for Repair {selected_repair_id}:**")

                # Display timeline
                timeline_display = timeline_df[['Date', 'Lifecycle_Status', 'Status', 'Employee', 'Repairs Noted', 'Notes']].copy()
                timeline_display['Date'] = timeline_display['Date'].dt.strftime('%Y-%m-%d %H:%M')
                timeline_display = timeline_display.rename(columns={
                    'Lifecycle_Status': 'Stage',
                    'Repairs Noted': 'Repair Description',
                    'Notes': 'Additional Notes'
                })
                timeline_display = timeline_display.fillna('')

                st.dataframe(timeline_display, use_container_width=True, hide_index=True)

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
