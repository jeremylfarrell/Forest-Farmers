"""
Data Loader Module - MULTI-SITE VERSION
Handles loading and processing data from Google Sheets for NY and VT sites
All data loading logic is centralized here for easy maintenance

PERFORMANCE: Now includes caching for dramatic speed improvements!
- Data cached for 1 hour (auto-refresh)
- Manual refresh available via dashboard button

MULTI-SITE: Supports separate vacuum data for NY and VT sites
- Loads both sites and adds 'Site' column
- Uses Site column from personnel sheet when available, falls back to Job parsing
"""

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import streamlit as st
import os
import json
import re
import config


def connect_to_sheets(credentials_file):
    """
    Connect to Google Sheets with authentication
    Works with BOTH local credentials file AND Streamlit Cloud secrets!

    NOTE: No caching to avoid auth issues

    Args:
        credentials_file: Path to Google service account JSON file (for local development)

    Returns:
        Authorized gspread client
    """
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]

    credentials_dict = None

    # Try Streamlit secrets first (for Streamlit Cloud)
    try:
        if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
            credentials_dict = dict(st.secrets['gcp_service_account'])
    except (FileNotFoundError, KeyError, AttributeError):
        pass

    # Fall back to local credentials file (for local development)
    if credentials_dict is None:
        if not os.path.exists(credentials_file):
            raise FileNotFoundError(
                f"❌ Credentials not found!\n\n"
                f"For Streamlit Cloud: Add credentials to app secrets under [gcp_service_account]\n"
                f"For Local Development: Need '{credentials_file}' file in your project folder"
            )

        with open(credentials_file, 'r') as f:
            credentials_dict = json.load(f)

    # Create credentials and authorize (works with dict from either source)
    creds = Credentials.from_service_account_info(credentials_dict, scopes=scope)
    client = gspread.authorize(creds)

    return client


def parse_site_from_job(job_text):
    """
    Parse site location from job description

    Args:
        job_text: Job description string (e.g., "Training/Meetings - VT Woods- 241121")

    Returns:
        "NY", "VT", or "UNK" (unknown)
    """
    if pd.isna(job_text):
        return "UNK"

    job_upper = str(job_text).upper()

    # Check for VT
    if "VT" in job_upper:
        return "VT"
    # Check for NY
    elif "NY" in job_upper:
        return "NY"
    else:
        return "UNK"


@st.cache_data(ttl=3600, show_spinner="Loading vacuum data from cache...")
def load_all_vacuum_data(ny_sheet_url, vt_sheet_url, credentials_file, days=None):
    """
    Load ALL vacuum data from both NY and VT sheets
    Combines data from both sites and adds 'Site' column

    CACHED: Data is cached for 1 hour to dramatically improve performance.
    Switching between pages is instant after first load!

    Args:
        ny_sheet_url: Google Sheet URL for NY vacuum data
        vt_sheet_url: Google Sheet URL for VT vacuum data
        credentials_file: Path to credentials JSON
        days: If specified, only load last N days (None = all data)

    Returns:
        DataFrame with all vacuum readings from both sites, with 'Site' column
    """
    all_sites_data = []

    # Load NY site data
    try:
        ny_data = _load_vacuum_from_single_site(ny_sheet_url, credentials_file, days, site_name="NY")
        if not ny_data.empty:
            all_sites_data.append(ny_data)
    except Exception as e:
        st.warning(f"Error loading NY vacuum data: {str(e)}")

    # Load VT site data
    try:
        vt_data = _load_vacuum_from_single_site(vt_sheet_url, credentials_file, days, site_name="VT")
        if not vt_data.empty:
            all_sites_data.append(vt_data)
    except Exception as e:
        st.warning(f"Error loading VT vacuum data: {str(e)}")

    # Combine all sites
    if not all_sites_data:
        return pd.DataFrame()

    combined_df = pd.concat(all_sites_data, ignore_index=True)
    return combined_df


def _load_vacuum_from_single_site(sheet_url, credentials_file, days=None, site_name="Unknown"):
    """
    Load vacuum data from a single site's Google Sheet

    Args:
        sheet_url: Google Sheet URL
        credentials_file: Path to credentials JSON
        days: If specified, only load last N days (also skips old tabs for speed)
        site_name: Name of the site (NY, VT, etc.)

    Returns:
        DataFrame with vacuum readings and 'Site' column added
    """
    try:
        client = connect_to_sheets(credentials_file)
        sheet = client.open_by_url(sheet_url)

        # Get all worksheets (monthly tabs)
        all_worksheets = sheet.worksheets()

        # If days is specified, figure out which month tabs we actually need.
        # This avoids downloading dozens of old tabs from Google Sheets.
        needed_months = None
        if days is not None:
            cutoff_date = datetime.now() - timedelta(days=days)
            needed_months = set()
            d = cutoff_date.replace(day=1)
            while d <= datetime.now():
                needed_months.add((d.year, d.month))
                # Advance to next month
                if d.month == 12:
                    d = d.replace(year=d.year + 1, month=1)
                else:
                    d = d.replace(month=d.month + 1)

        all_data = []

        for worksheet in all_worksheets:
            # Skip any non-date worksheets (like instructions, etc.)
            if not is_month_tab(worksheet.title):
                continue

            # Skip tabs for months outside our date range (big speed boost)
            if needed_months is not None:
                tab_month = _parse_tab_month(worksheet.title)
                if tab_month and tab_month not in needed_months:
                    continue

            try:
                # Get data from this worksheet
                data = worksheet.get_all_records()
                if data:
                    df = pd.DataFrame(data)
                    all_data.append(df)
            except Exception as e:
                if config.DEBUG_MODE:
                    st.warning(f"Skipped worksheet '{worksheet.title}' in {site_name}: {str(e)}")
                continue

        if not all_data:
            return pd.DataFrame()

        # Combine all data
        combined_df = pd.concat(all_data, ignore_index=True)

        # Clean and process the data
        combined_df = process_vacuum_data(combined_df)

        # Add site column
        combined_df['Site'] = site_name

        # Filter by date if specified (fine-grained filter after tab-level skip)
        if days is not None and 'Timestamp' in combined_df.columns:
            cutoff_date = datetime.now() - timedelta(days=days)
            combined_df = combined_df[combined_df['Timestamp'] >= cutoff_date]

        return combined_df

    except Exception as e:
        st.error(f"Error loading {site_name} vacuum data: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner="Loading personnel data from cache...")
def load_all_personnel_data(sheet_url, credentials_file, days=None):
    """
    Load ALL personnel data from all monthly tabs
    Adds 'Site' column based on Job description parsing

    CACHED: Data is cached for 1 hour to dramatically improve performance.
    Switching between pages is instant after first load!

    Args:
        sheet_url: Google Sheet URL
        credentials_file: Path to credentials JSON
        days: If specified, only load last N days (None = all data)

    Returns:
        DataFrame with all personnel timesheet data including 'Site' column
    """
    try:
        client = connect_to_sheets(credentials_file)
        sheet = client.open_by_url(sheet_url)

        all_data = []

        # Try the single 'all' tab first (case-insensitive search)
        all_tab = None
        for ws in sheet.worksheets():
            if ws.title.strip().lower() == 'all':
                all_tab = ws
                break

        if all_tab is not None:
            try:
                raw = all_tab.get_all_values()
                if raw and len(raw) > 1:
                    headers = raw[0]
                    rows = [r for r in raw[1:] if any(cell != '' for cell in r)]
                    df = pd.DataFrame(rows, columns=headers)
                    all_data.append(df)
            except Exception as e:
                if config.DEBUG_MODE:
                    st.warning(f"Error reading '{all_tab.title}' tab: {str(e)}")

        # Fallback: read monthly tabs if 'all' had no data
        if not all_data:
            for worksheet in sheet.worksheets():
                if not is_month_tab(worksheet.title):
                    continue
                try:
                    data = worksheet.get_all_records()
                    if data:
                        all_data.append(pd.DataFrame(data))
                except Exception as e:
                    if config.DEBUG_MODE:
                        st.warning(f"Skipped worksheet '{worksheet.title}': {str(e)}")
                    continue

        if not all_data:
            return pd.DataFrame()

        # Combine all data
        combined_df = pd.concat(all_data, ignore_index=True)

        # Clean and process the data
        combined_df = process_personnel_data(combined_df)

        # Filter by date if specified
        if days is not None and 'Date' in combined_df.columns:
            cutoff_date = datetime.now() - timedelta(days=days)
            combined_df = combined_df[combined_df['Date'] >= cutoff_date]

        return combined_df

    except Exception as e:
        st.error(f"Error loading personnel data: {str(e)}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner="Loading repairs tracker...")
def load_repairs_tracker(sheet_url, credentials_file):
    """Load repairs tracker data from the 'repairs_tracker' tab."""
    try:
        client = connect_to_sheets(credentials_file)
        sheet = client.open_by_url(sheet_url)

        tracker_ws = None
        for ws in sheet.worksheets():
            if ws.title.strip().lower() == 'repairs_tracker':
                tracker_ws = ws
                break

        if tracker_ws is None:
            return pd.DataFrame()

        raw = tracker_ws.get_all_values()
        if not raw or len(raw) <= 1:
            return pd.DataFrame()

        headers = raw[0]
        rows = [r for r in raw[1:] if any(cell != '' for cell in r)]
        df = pd.DataFrame(rows, columns=headers)

        if 'Date Found' in df.columns:
            df['Date Found'] = pd.to_datetime(df['Date Found'], errors='coerce')
        if 'Date Resolved' in df.columns:
            df['Date Resolved'] = pd.to_datetime(df['Date Resolved'], errors='coerce')

        return df

    except Exception as e:
        st.warning(f"Could not load repairs tracker: {e}")
        return pd.DataFrame()


def save_repairs_updates(sheet_url, credentials_file, updated_df):
    """
    Write updated repairs data back to the 'repairs_tracker' tab in Google Sheets.
    Matches rows by Repair ID and updates the editable columns only.
    """
    try:
        client = connect_to_sheets(credentials_file)
        sheet = client.open_by_url(sheet_url)

        tracker_ws = None
        for ws in sheet.worksheets():
            if ws.title.strip().lower() == 'repairs_tracker':
                tracker_ws = ws
                break

        if tracker_ws is None:
            return False, "repairs_tracker tab not found"

        raw = tracker_ws.get_all_values()
        if not raw:
            return False, "No data in repairs_tracker tab"

        headers = raw[0]

        # Build a map of Repair ID -> row number (1-indexed, header is row 1)
        repair_id_col = headers.index('Repair ID') if 'Repair ID' in headers else None
        if repair_id_col is None:
            return False, "Repair ID column not found"

        row_map = {}
        for i, row in enumerate(raw[1:], start=2):  # row 2 is first data row
            if repair_id_col < len(row):
                row_map[row[repair_id_col]] = i

        # Editable columns and their positions
        editable_cols = ['Status', 'Date Resolved', 'Resolved By', 'Repair Cost', 'Notes']
        col_indices = {}
        for col in editable_cols:
            if col in headers:
                col_indices[col] = headers.index(col)

        if not col_indices:
            return False, "No editable columns found"

        # Batch update cells
        cells_to_update = []
        for _, row in updated_df.iterrows():
            repair_id = row.get('Repair ID', '')
            if repair_id not in row_map:
                continue
            sheet_row = row_map[repair_id]

            for col_name, col_idx in col_indices.items():
                val = row.get(col_name, '')
                if pd.isna(val) or val is None:
                    val = ''
                elif isinstance(val, pd.Timestamp):
                    val = val.strftime('%Y-%m-%d') if not pd.isna(val) else ''
                else:
                    val = str(val)
                cells_to_update.append(gspread.Cell(sheet_row, col_idx + 1, val))

        if cells_to_update:
            tracker_ws.update_cells(cells_to_update, value_input_option='USER_ENTERED')

        # Clear cache so next load picks up changes
        st.cache_data.clear()

        return True, f"Updated {len(updated_df)} repairs"

    except Exception as e:
        return False, f"Error saving: {e}"


# ===========================================================================
# APPROVED PERSONNEL DATA (Manager Data Review workflow)
# ===========================================================================

@st.cache_data(ttl=3600, show_spinner="Loading approved personnel data...")
def load_approved_personnel(sheet_url, credentials_file):
    """
    Load manager-approved personnel data from the 'approved_personnel' tab.
    Returns empty DataFrame if the tab doesn't exist yet (graceful degradation).
    """
    try:
        client = connect_to_sheets(credentials_file)
        sheet = client.open_by_url(sheet_url)

        approved_ws = None
        for ws in sheet.worksheets():
            if ws.title.strip().lower() == 'approved_personnel':
                approved_ws = ws
                break

        if approved_ws is None:
            return pd.DataFrame()

        raw = approved_ws.get_all_values()
        if not raw or len(raw) <= 1:
            return pd.DataFrame()

        headers = raw[0]
        rows = [r for r in raw[1:] if any(cell != '' for cell in r)]
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=headers)

        # Type conversions (mirrors process_personnel_data but no dedup/site parsing)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        if 'Hours' in df.columns:
            df['Hours'] = pd.to_numeric(df['Hours'], errors='coerce').fillna(0)
        if 'Rate' in df.columns:
            df['Rate'] = pd.to_numeric(df['Rate'], errors='coerce').fillna(0)
        for field in ['Taps Put In', 'Taps Removed', 'taps capped', 'Repairs needed']:
            if field in df.columns:
                df[field] = pd.to_numeric(df[field], errors='coerce').fillna(0)
        for clock_col in ['Clock In', 'Clock Out']:
            if clock_col in df.columns:
                df[clock_col] = pd.to_datetime(df[clock_col], errors='coerce')
        if 'Approved Date' in df.columns:
            df['Approved Date'] = pd.to_datetime(df['Approved Date'], errors='coerce')

        return df

    except Exception as e:
        # Don't show warning on every page load — just return empty
        return pd.DataFrame()


def merge_approved_data(raw_df, approved_df):
    """
    Merge raw personnel data with manager-approved overrides.
    For rows where (Employee Name, Date, Job) exists in approved_df,
    use the approved version. Otherwise keep the raw version.
    Adds 'Approval Status' column:
      - 'Pending'         — raw data, not yet reviewed
      - 'Approved'        — data reviewed and approved by manager
      - 'TSheets Updated' — was approved, but TSheets has since changed
                             the underlying raw data (needs re-review)
    """
    if raw_df.empty:
        return raw_df

    if approved_df.empty:
        result = raw_df.copy()
        result['Approval Status'] = 'Pending'
        return result

    # Check required columns exist
    required = ['Employee Name', 'Date', 'Job']
    for col in required:
        if col not in raw_df.columns or col not in approved_df.columns:
            result = raw_df.copy()
            result['Approval Status'] = 'Pending'
            return result

    def make_key(df):
        emp = df['Employee Name'].astype(str)
        date = df['Date'].dt.strftime('%Y-%m-%d').fillna('')
        job = df['Job'].astype(str)
        return emp + '|' + date + '|' + job

    raw = raw_df.copy()
    approved = approved_df.copy()

    raw['_merge_key'] = make_key(raw)
    approved['_merge_key'] = make_key(approved)

    approved_keys = set(approved['_merge_key'].values)

    # --- Detect TSheets changes since approval ---
    # Compare key numeric fields between raw and approved.
    # If TSheets updated hours/taps after approval, flag for re-review.
    compare_cols = ['Hours', 'Taps Put In', 'Taps Removed', 'taps capped', 'Repairs needed']
    compare_cols = [c for c in compare_cols if c in raw.columns and c in approved.columns]

    tsheets_updated_keys = set()
    if compare_cols:
        raw_lookup = raw.set_index('_merge_key')[compare_cols]
        approved_lookup = approved.set_index('_merge_key')[compare_cols]

        common_keys = raw_lookup.index.intersection(approved_lookup.index)
        if len(common_keys) > 0:
            raw_vals = raw_lookup.loc[common_keys].fillna(0)
            appr_vals = approved_lookup.loc[common_keys].fillna(0)
            # Flag rows where any numeric field differs
            diffs = (raw_vals != appr_vals).any(axis=1)
            tsheets_updated_keys = set(diffs[diffs].index)

    # Raw rows NOT overridden by approved data
    pending_rows = raw[~raw['_merge_key'].isin(approved_keys)].copy()
    pending_rows['Approval Status'] = 'Pending'

    # Approved rows — mark those with TSheets changes
    approved['Approval Status'] = approved['_merge_key'].apply(
        lambda k: 'TSheets Updated' if k in tsheets_updated_keys else 'Approved'
    )

    # Combine: pending raw rows + approved rows
    merged = pd.concat([pending_rows, approved], ignore_index=True)
    merged = merged.drop(columns=['_merge_key'], errors='ignore')

    return merged


def save_approved_personnel(sheet_url, credentials_file, approved_df):
    """
    Save manager-approved personnel data to the 'approved_personnel' tab.
    Creates the tab if it doesn't exist. Updates existing rows by
    (Employee Name, Date, Job) key; appends new rows.
    Returns (success: bool, message: str).
    """
    try:
        client = connect_to_sheets(credentials_file)
        sheet = client.open_by_url(sheet_url)

        # Find or create the approved_personnel tab
        approved_ws = None
        for ws in sheet.worksheets():
            if ws.title.strip().lower() == 'approved_personnel':
                approved_ws = ws
                break

        # Define the columns for the approved tab
        approved_columns = [
            'Employee Name', 'Date', 'Hours', 'Rate', 'Job', 'mainline.',
            'Taps Put In', 'Taps Removed', 'taps capped', 'Repairs needed',
            'Notes', 'Site', 'Clock In', 'Clock Out', 'Approved Date', 'Approved By'
        ]

        if approved_ws is None:
            approved_ws = sheet.add_worksheet(
                title='approved_personnel', rows=1000, cols=len(approved_columns)
            )
            approved_ws.update('A1', [approved_columns], value_input_option='USER_ENTERED')
            existing_data = []
        else:
            existing_data = approved_ws.get_all_values()
            if not existing_data:
                approved_ws.update('A1', [approved_columns], value_input_option='USER_ENTERED')
                existing_data = [approved_columns]

        # Build key map for existing rows: (Employee Name|Date|Job) -> row number
        row_map = {}
        if existing_data and len(existing_data) > 1:
            headers = existing_data[0]
            try:
                emp_idx = headers.index('Employee Name')
                date_idx = headers.index('Date')
                job_idx = headers.index('Job')
            except ValueError:
                emp_idx = date_idx = job_idx = None

            if all(idx is not None for idx in [emp_idx, date_idx, job_idx]):
                for i, row in enumerate(existing_data[1:], start=2):
                    if len(row) > max(emp_idx, date_idx, job_idx):
                        key = f"{row[emp_idx]}|{row[date_idx]}|{row[job_idx]}"
                        row_map[key] = i

        # Prepare data for writing
        cells_to_update = []
        rows_to_append = []

        for _, row in approved_df.iterrows():
            # Build the key
            emp = str(row.get('Employee Name', ''))
            date_val = row.get('Date', '')
            if isinstance(date_val, pd.Timestamp) and not pd.isna(date_val):
                date_str = date_val.strftime('%Y-%m-%d')
            else:
                date_str = str(date_val) if date_val else ''
            job = str(row.get('Job', ''))
            key = f"{emp}|{date_str}|{job}"

            # Build the row values in column order
            row_values = []
            for col in approved_columns:
                val = row.get(col, '')
                if pd.isna(val) or val is None:
                    val = ''
                elif isinstance(val, pd.Timestamp):
                    if col in ('Clock In', 'Clock Out'):
                        val = val.strftime('%Y-%m-%d %H:%M') if not pd.isna(val) else ''
                    else:
                        val = val.strftime('%Y-%m-%d') if not pd.isna(val) else ''
                else:
                    val = str(val)
                row_values.append(val)

            if key in row_map:
                # Update existing row
                sheet_row = row_map[key]
                for col_idx, val in enumerate(row_values):
                    cells_to_update.append(
                        gspread.Cell(sheet_row, col_idx + 1, val)
                    )
            else:
                rows_to_append.append(row_values)

        # Execute batch update for existing rows
        if cells_to_update:
            approved_ws.update_cells(cells_to_update, value_input_option='USER_ENTERED')

        # Append new rows
        if rows_to_append:
            approved_ws.append_rows(rows_to_append, value_input_option='USER_ENTERED')

        # Clear cache so next load picks up changes
        st.cache_data.clear()

        total = len(approved_df)
        appended = len(rows_to_append)
        updated = total - appended
        return True, f"Approved {total} rows ({appended} new, {updated} updated)"

    except Exception as e:
        return False, f"Error saving approved data: {e}"


@st.cache_data
def process_vacuum_data(df):
    """
    Clean and process vacuum data

    CACHED: Processing is cached to avoid repeated computation

    Args:
        df: Raw DataFrame from Google Sheets

    Returns:
        Processed DataFrame with proper types and cleaned data
    """
    if df.empty:
        return df

# Find ALL timestamp/date columns - process each one
    timestamp_columns = []
    for possible_name in ['Scrape_Timestamp', 'Timestamp', 'timestamp', 'Date', 'date', 'DateTime', 'datetime',
                          'Last Communication', 'Last communication', 'last communication',
                          'Time', 'time', 'Delay']:
        if possible_name in df.columns:
            timestamp_columns.append(possible_name)
    
    # Process each timestamp column found
    for timestamp_col in timestamp_columns:
        from datetime import datetime as dt, timedelta

        def parse_mixed_timestamp(val):
            """Handle mixed columns: numeric Excel serial dates AND string datetimes."""
            if pd.isna(val) or val == '':
                return pd.NaT
            # Try numeric (Excel serial date) first
            try:
                num = float(val)
                if 0 < num < 100000:
                    epoch = dt(1899, 12, 30)
                    return epoch + timedelta(days=num)
            except (ValueError, TypeError):
                pass
            # Fall back to string datetime parsing
            try:
                return pd.to_datetime(val)
            except Exception:
                return pd.NaT

        df[timestamp_col] = df[timestamp_col].apply(parse_mixed_timestamp)
    
    # Use the first valid timestamp column for primary Timestamp field
    if timestamp_columns:
        primary_timestamp = timestamp_columns[0]
        if primary_timestamp in df.columns:
            df['Timestamp'] = df[primary_timestamp]

            # Add derived columns
            df['Date'] = df['Timestamp'].dt.date
            df['Hour'] = df['Timestamp'].dt.hour

            # Remove rows with invalid timestamps
            df = df.dropna(subset=['Timestamp'])
    else:
        # No timestamp column found - create a default one with current time
        df['Timestamp'] = pd.Timestamp.now()
        df['Date'] = datetime.now().date()

    
    # Convert vacuum reading to numeric
    vacuum_cols = [col for col in df.columns if 'vacuum' in col.lower() or 'reading' in col.lower()]
    for col in vacuum_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Fill missing vacuum values
    for col in vacuum_cols:
        df[col] = df[col].fillna(config.FILL_MISSING_VACUUM)

    # Detect and process releaser differential column
    releaser_col = None
    for col in df.columns:
        if 'releaser' in col.lower() or 'differential' in col.lower():
            releaser_col = col
            break
    if releaser_col:
        df[releaser_col] = pd.to_numeric(df[releaser_col], errors='coerce')

    return df


@st.cache_data
def process_personnel_data(df):
    """
    Clean and process personnel data
    Adds 'Site' column based on Job description

    CACHED: Processing is cached to avoid repeated computation

    Args:
        df: Raw DataFrame from Google Sheets

    Returns:
        Processed DataFrame with proper types, cleaned data, and 'Site' column
    """
    if df.empty:
        return df

    # Convert date to datetime
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

    # Convert hours to numeric
    if 'Hours' in df.columns:
        df['Hours'] = pd.to_numeric(df['Hours'], errors='coerce')
        df['Hours'] = df['Hours'].fillna(config.FILL_MISSING_HOURS)

    # Convert numeric fields
    numeric_fields = ['Taps Put In', 'Taps Removed', 'taps capped', 'Repairs needed']
    for field in numeric_fields:
        if field in df.columns:
            df[field] = pd.to_numeric(df[field], errors='coerce').fillna(0)

    # Create full employee name if needed
    if 'EE First' in df.columns and 'EE Last' in df.columns:
        df['Employee Name'] = df['EE First'].astype(str).str.strip() + ' ' + df['EE Last'].astype(str).str.strip()

    # Clean mainline column name (handle potential variations)
    mainline_cols = [col for col in df.columns if 'mainline' in col.lower()]
    if mainline_cols:
        df['mainline'] = df[mainline_cols[0]]

    # Use the Site column written by the backup script if available,
    # otherwise fall back to parsing from the Job column.
    if 'Site' in df.columns:
        # Normalize: backup script uses 'Unknown', dashboard expects 'UNK'
        df['Site'] = df['Site'].replace({'Unknown': 'UNK'})
        # Fill any blanks by parsing from Job
        mask = df['Site'].isna() | (df['Site'] == '') | (df['Site'] == 'UNK')
        if mask.any() and 'Job' in df.columns:
            df.loc[mask, 'Site'] = df.loc[mask, 'Job'].apply(parse_site_from_job)
    elif 'Job' in df.columns:
        df['Site'] = df['Job'].apply(parse_site_from_job)
    else:
        df['Site'] = 'UNK'

    # Parse Clock In / Clock Out columns as datetime (for timestamp-based vacuum matching)
    for clock_col in ['Clock In', 'Clock Out']:
        if clock_col in df.columns:
            df[clock_col] = pd.to_datetime(df[clock_col], errors='coerce')

    # Remove rows with invalid dates
    if 'Date' in df.columns:
        df = df.dropna(subset=['Date'])

    # Deduplicate: TSheets sync can append updated versions of the same entry.
    # Key on Employee Name + Date + Job; keep the last occurrence (most recent sync).
    dedup_cols = []
    if 'Employee Name' in df.columns:
        dedup_cols.append('Employee Name')
    if 'Date' in df.columns:
        dedup_cols.append('Date')
    if 'Job' in df.columns:
        dedup_cols.append('Job')
    if len(dedup_cols) >= 2:
        before = len(df)
        df = df.drop_duplicates(subset=dedup_cols, keep='last')
        dropped = before - len(df)
        if dropped > 0 and config.DEBUG_MODE:
            import streamlit as _st
            _st.info(f"Dedup: removed {dropped} duplicate personnel rows")

    return df


def _parse_tab_month(tab_name):
    """
    Parse a worksheet tab name into a (year, month) tuple.
    Returns None if the tab name cannot be parsed.
    Supports: 'YYYY-MM', 'Month_YYYY', 'Month YYYY'
    """
    import calendar
    tab_name = tab_name.strip()

    # Pattern 1: YYYY-MM
    m = re.match(r'^(\d{4})-(\d{2})$', tab_name)
    if m:
        return (int(m.group(1)), int(m.group(2)))

    # Pattern 2: Month_YYYY or Month YYYY
    m = re.match(r'^([A-Za-z]{3,})[\s_](\d{4})$', tab_name)
    if m:
        month_str = m.group(1).capitalize()
        year = int(m.group(2))
        # Try full month names and abbreviations
        for i, name in enumerate(calendar.month_name):
            if name and name.lower().startswith(month_str.lower()):
                return (year, i)
        for i, name in enumerate(calendar.month_abbr):
            if name and name.lower() == month_str[:3].lower():
                return (year, i)

    return None


def is_month_tab(tab_name):
    """
    Check if a worksheet tab name represents a month
    Supports multiple formats:
    - YYYY-MM (e.g., '2025-03')
    - Month_YYYY (e.g., 'Nov_2025', 'December_2025')
    - Month YYYY with space (e.g., 'Jan 2026', 'December 2025')

    Args:
        tab_name: Name of the worksheet tab

    Returns:
        True if it looks like a month tab, False otherwise
    """
    # Pattern 1: YYYY-MM format (e.g., '2025-11')
    pattern_yyyy_mm = r'^\d{4}-\d{2}$'

    # Pattern 2: Month_YYYY or Month YYYY format (e.g., 'Nov_2025', 'December 2025')
    pattern_month_year = r'^[A-Za-z]{3,}[\s_]\d{4}$'

    # Return True if any pattern matches
    return (bool(re.match(pattern_yyyy_mm, tab_name)) or
            bool(re.match(pattern_month_year, tab_name)))


def get_latest_data(vacuum_df, personnel_df, hours=24):
    """
    Get data from the last N hours

    Args:
        vacuum_df: Vacuum data DataFrame
        personnel_df: Personnel data DataFrame
        hours: Number of hours to look back

    Returns:
        Tuple of (filtered vacuum_df, filtered personnel_df)
    """
    cutoff = datetime.now() - timedelta(hours=hours)

    vacuum_recent = vacuum_df[vacuum_df['Timestamp'] >= cutoff] if not vacuum_df.empty else vacuum_df
    personnel_recent = personnel_df[personnel_df['Date'] >= cutoff] if not personnel_df.empty else personnel_df

    return vacuum_recent, personnel_recent


def merge_vacuum_personnel(vacuum_df, personnel_df):
    """
    Merge vacuum and personnel data on mainline location

    Args:
        vacuum_df: Vacuum data DataFrame
        personnel_df: Personnel data DataFrame

    Returns:
        Merged DataFrame with both vacuum and personnel information
    """
    if vacuum_df.empty or personnel_df.empty:
        return pd.DataFrame()

    # Find the sensor name column in vacuum data
    sensor_col = None
    for col in ['Sensor Name', 'sensor', 'mainline', 'location', 'Name']:
        if col in vacuum_df.columns:
            sensor_col = col
            break

    if sensor_col is None:
        st.warning("Could not find sensor/mainline column in vacuum data")
        return pd.DataFrame()

    # Ensure mainline column exists in personnel data
    if 'mainline' not in personnel_df.columns:
        st.warning("Could not find mainline column in personnel data")
        return pd.DataFrame()

    # Merge on mainline
    merged = pd.merge(
        vacuum_df,
        personnel_df,
        left_on=sensor_col,
        right_on='mainline',
        how='left'
    )

    return merged


def calculate_vacuum_improvement(merged_df):
    """
    Calculate vacuum improvement based on before/after personnel activity

    Args:
        merged_df: Merged DataFrame with vacuum and personnel data

    Returns:
        DataFrame with improvement calculations added
    """
    # This is a simplified version - you can make it more sophisticated
    # by looking at vacuum readings before and after specific employee visits

    if merged_df.empty:
        return merged_df

    # Group by mainline and calculate change over time
    # This is a placeholder - actual implementation depends on your specific needs

    return merged_df
