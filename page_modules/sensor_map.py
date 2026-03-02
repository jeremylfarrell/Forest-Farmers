"""
Interactive Map Page Module - MULTI-SITE POLISHED
Geographic visualization of sensor locations with performance overlay
Now with site color coding, legend, tap count display, and freeze alert mode
"""

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import config
from utils import find_column, get_vacuum_column
from utils.freeze_thaw import get_current_freeze_thaw_status, detect_freeze_event_drops
import re
import math


def match_mainline_to_sensor(mainline, sensor_names):
    """
    Match a mainline name to the closest sensor name.
    Uses progressive matching: exact → case-insensitive exact → same prefix+number.

    Args:
        mainline: Mainline name from personnel data (e.g., "RHAS13")
        sensor_names: List of sensor names from vacuum data

    Returns:
        Best matching sensor name or None
    """
    if pd.isna(mainline) or not mainline:
        return None

    mainline = str(mainline).strip().upper()

    # Try exact match first (case-insensitive)
    for sensor in sensor_names:
        if str(sensor).strip().upper() == mainline:
            return sensor

    # Try partial match — but only if one fully contains the other AND
    # the shorter string is at least 3 chars (avoids single-letter mismatches)
    for sensor in sensor_names:
        sensor_upper = str(sensor).strip().upper()
        if len(mainline) >= 3 and len(sensor_upper) >= 3:
            if mainline in sensor_upper or sensor_upper in mainline:
                return sensor

    # NOTE: We deliberately do NOT fall back to alpha-only matching (e.g.
    # matching "LHW" prefix to any "LHW*" sensor) because that causes taps
    # from LHW1, LHW2, etc. to all pile up on a single LHW0 sensor.

    return None


def get_taps_details_by_mainline(personnel_df):
    """
    Get detailed tap installation info per mainline from personnel data

    Args:
        personnel_df: Personnel DataFrame with mainline, Taps Put In, Date, Employee columns

    Returns:
        Dictionary mapping mainline names to dict with:
        - total_taps: total count
        - installations: list of {date, employee, taps} dicts
    """
    if personnel_df.empty:
        return {}

    # Find mainline column
    mainline_col = None
    for col in personnel_df.columns:
        if 'mainline' in col.lower():
            mainline_col = col
            break

    if not mainline_col:
        return {}

    # Find taps column
    taps_col = None
    for col in personnel_df.columns:
        if 'taps put in' in col.lower() or col == 'Taps Put In':
            taps_col = col
            break

    if not taps_col:
        return {}

    # Find employee column
    emp_col = None
    for col in ['Employee Name', 'Employee', 'EE First', 'Name']:
        if col in personnel_df.columns:
            emp_col = col
            break

    # Find date column
    date_col = 'Date' if 'Date' in personnel_df.columns else None

    # Build detailed info per mainline
    taps_details = {}

    for mainline in personnel_df[mainline_col].unique():
        if pd.isna(mainline) or not str(mainline).strip():
            continue

        mainline_data = personnel_df[personnel_df[mainline_col] == mainline]
        mainline_data = mainline_data[mainline_data[taps_col] > 0]  # Only rows with taps

        if mainline_data.empty:
            continue

        installations = []
        for _, row in mainline_data.iterrows():
            install = {
                'taps': int(row[taps_col]) if pd.notna(row[taps_col]) else 0
            }
            if date_col and pd.notna(row.get(date_col)):
                install['date'] = row[date_col]
            if emp_col and pd.notna(row.get(emp_col)):
                install['employee'] = row[emp_col]
            if install['taps'] > 0:
                installations.append(install)

        if installations:
            taps_details[mainline] = {
                'total_taps': sum(i['taps'] for i in installations),
                'installations': sorted(installations,
                    key=lambda x: x.get('date', pd.Timestamp.min) if pd.notna(x.get('date')) else pd.Timestamp.min,
                    reverse=True)[:10]  # Keep last 10 installations for popup
            }

    return taps_details


def render(vacuum_df, personnel_df, repairs_df=None):
    """Render interactive map with site-aware visualization"""

    st.title("🌍 Interactive Sensor Map")
    st.markdown("*Geographic visualization of sensor locations and performance*")

    # Compact weather status line
    freeze_status = get_current_freeze_thaw_status()
    _fs_label = freeze_status.get('status_label', 'UNKNOWN')
    _fs_temp = freeze_status.get('current_temp')
    _temp_str = f"{_fs_temp:.0f}°F" if _fs_temp is not None else "N/A"
    if _fs_label == 'CRITICAL':
        st.caption(f"🔴 **FREEZE/THAW ACTIVE** — {_temp_str} — Vacuum drops reveal open lines")
    elif _fs_label == 'UPCOMING':
        st.caption(f"🟡 **Freeze/thaw expected tomorrow** — Currently {_temp_str}")
    elif _fs_label == 'LOW PRIORITY':
        st.caption(f"🟢 No freeze cycle — Currently {_temp_str}")
    else:
        st.caption("Weather status unavailable")

    if vacuum_df.empty:
        st.warning("No vacuum data available for mapping")
        return

    # Check site context
    has_site = 'Site' in vacuum_df.columns
    viewing_site = None
    
    if has_site and len(vacuum_df['Site'].unique()) == 1:
        viewing_site = vacuum_df['Site'].iloc[0]
        site_emoji = "🟦" if viewing_site == "NY" else "🟩" if viewing_site == "VT" else "⚫"
        st.info(f"{site_emoji} **Mapping {viewing_site} site** - {vacuum_df['Site'].value_counts()[viewing_site]:,} sensor readings")
    elif has_site:
        site_counts = vacuum_df['Site'].value_counts()
        site_info = " | ".join([f"🟦 NY: {site_counts.get('NY', 0):,}" if s == 'NY' 
                               else f"🟩 VT: {site_counts.get('VT', 0):,}" 
                               for s in ['NY', 'VT'] if s in site_counts.index])
        st.info(f"🗺️ **Multi-site map** - {site_info} readings")

    # Find required columns
    sensor_col = find_column(vacuum_df, 'Name', 'name', 'mainline', 'Sensor Name', 'sensor', 'location')
    vacuum_col = get_vacuum_column(vacuum_df)
    lat_col = find_column(vacuum_df, 'Latitude', 'latitude', 'lat')
    lon_col = find_column(vacuum_df, 'Longitude', 'longitude', 'lon', 'long')

    # Check for required columns
    if not all([sensor_col, lat_col, lon_col]):
        st.error("Missing required columns for mapping")
        missing = []
        if not sensor_col:
            missing.append("Sensor name")
        if not lat_col:
            missing.append("Latitude")
        if not lon_col:
            missing.append("Longitude")
        st.write(f"Missing: {', '.join(missing)}")
        st.info("Available columns: " + ", ".join(vacuum_df.columns))
        return

    # Get latest reading per sensor
    timestamp_col = find_column(
        vacuum_df,
        'Last communication', 'Last Communication', 'Timestamp', 'timestamp'
    )

    if timestamp_col:
        temp_df = vacuum_df.copy()
        temp_df[timestamp_col] = pd.to_datetime(temp_df[timestamp_col], errors='coerce')
        latest = temp_df.sort_values(timestamp_col, ascending=False).groupby(sensor_col).first().reset_index()
    else:
        latest = vacuum_df.groupby(sensor_col).first().reset_index()

    # Filter out birch sensors (start with lowercase 'b') and relays/inactive
    # (sensors not matching pattern: 2-4 uppercase letters followed by a number)
    valid_sensor_pattern = r'^[A-Z]{2,4}\d'
    latest = latest[
        (~latest[sensor_col].str.startswith('b', na=False)) &
        (latest[sensor_col].str.match(valid_sensor_pattern, na=False))
    ]

    # Clean data
    map_data = latest[[sensor_col, lat_col, lon_col]].copy()
    if vacuum_col:
        map_data[vacuum_col] = latest[vacuum_col]
    if has_site:
        map_data['Site'] = latest['Site']
    
    map_data.columns = ['Sensor', 'Latitude', 'Longitude'] + ([vacuum_col] if vacuum_col else []) + (['Site'] if has_site else [])
    
    # Convert to numeric and clean
    map_data['Latitude'] = pd.to_numeric(map_data['Latitude'], errors='coerce')
    map_data['Longitude'] = pd.to_numeric(map_data['Longitude'], errors='coerce')
    if vacuum_col:
        map_data['Vacuum'] = pd.to_numeric(map_data[vacuum_col], errors='coerce')
    
    map_data = map_data.dropna(subset=['Latitude', 'Longitude'])

    if map_data.empty:
        st.warning("No sensors with valid coordinates found")
        return

    # Get detailed tap info from personnel data and match to sensors
    taps_details = get_taps_details_by_mainline(personnel_df)
    sensor_names = map_data['Sensor'].tolist()

    # Create mappings: sensor -> tap details, and track unmapped mainlines
    sensor_tap_info = {}  # sensor -> {total_taps, installations}
    unmapped_mainlines = {}  # mainline -> {total_taps, installations}

    for mainline, details in taps_details.items():
        matched_sensor = match_mainline_to_sensor(mainline, sensor_names)
        if matched_sensor:
            # Merge with existing if multiple mainlines match same sensor
            if matched_sensor in sensor_tap_info:
                sensor_tap_info[matched_sensor]['total_taps'] += details['total_taps']
                sensor_tap_info[matched_sensor]['installations'].extend(details['installations'])
            else:
                sensor_tap_info[matched_sensor] = {
                    'total_taps': details['total_taps'],
                    'installations': details['installations'].copy()
                }
        else:
            # Track unmapped mainlines
            unmapped_mainlines[mainline] = details

    # Add tap counts to map_data
    map_data['Taps'] = map_data['Sensor'].apply(
        lambda s: sensor_tap_info.get(s, {}).get('total_taps', 0)
    ).fillna(0).astype(int)

    # Map controls
    col1, col2, col3 = st.columns(3)

    with col1:
        map_style = st.selectbox(
            "Map Style",
            ["Street", "Terrain", "Satellite"],  # Street first as default (faster)
            help="Choose map background"
        )

    with col2:
        if vacuum_col:
            color_options = ["Vacuum Performance"]
            if has_site:
                color_options.append("Site")
            color_options.append("Freeze Alert")
            color_by = st.selectbox(
                "Color Markers By",
                color_options,
                help="How to color the sensor markers"
            )
        else:
            color_by = "Site" if has_site else None

    with col3:
        st.caption("Dot size reflects tap count")

    # Pre-compute freeze data for Freeze Alert mode and popups
    from utils.weather_api import get_temperature_data
    _freeze_temp_data = get_temperature_data(days=7)
    _freeze_drops = detect_freeze_event_drops(vacuum_df, _freeze_temp_data)
    _freeze_lookup = {}
    if not _freeze_drops.empty:
        for _, frow in _freeze_drops.iterrows():
            _freeze_lookup[frow['Sensor']] = {
                'status': frow['Freeze_Status'],
                'drop_rate': frow['Drop_Rate'],
                'days_with_drop': frow['Freeze_Days_With_Drop'],
                'total_days': frow['Total_Freeze_Days'],
            }

    # Collect all dates and employees from installations first
    all_employees = set()
    all_dates = []
    for details in list(sensor_tap_info.values()) + list(unmapped_mainlines.values()):
        for install in details.get('installations', []):
            if 'employee' in install and install['employee']:
                all_employees.add(install['employee'])
            if 'date' in install and pd.notna(install['date']):
                try:
                    all_dates.append(pd.to_datetime(install['date']).date())
                except Exception:
                    pass

    # Tapping overlay controls - all in one row
    st.markdown("**Tapping Overlay:**")
    tap_col1, tap_col2, tap_col3 = st.columns([1, 2, 3])

    with tap_col1:
        show_taps = st.checkbox("Show taps", value=True, help="Display tap installation counts on map")

    with tap_col2:
        if all_employees:
            employee_filter = st.multiselect(
                "Employee",
                options=sorted(all_employees),
                default=[],
                placeholder="All employees",
                help="Filter by employee"
            )
        else:
            employee_filter = []

    # Date range slider
    date_filter = None
    with tap_col3:
        if all_dates:
            min_date = min(all_dates)
            max_date = max(all_dates)

            if min_date < max_date:
                date_filter = st.slider(
                    "Date range",
                    min_value=min_date,
                    max_value=max_date,
                    value=(min_date, max_date),
                    format="MM/DD",
                    help="Filter by installation date"
                )

    # Helper function to filter installations
    def filter_installations(installs, emp_filter, date_range):
        filtered = installs
        if emp_filter:
            filtered = [i for i in filtered if i.get('employee') in emp_filter]
        if date_range:
            start_date, end_date = date_range
            def in_range(install):
                if 'date' not in install or pd.isna(install['date']):
                    return False
                try:
                    inst_date = pd.to_datetime(install['date']).date()
                    return start_date <= inst_date <= end_date
                except Exception:
                    return False
            filtered = [i for i in filtered if in_range(i)]
        return filtered

    # Re-calculate tap counts if filtering
    if (employee_filter or date_filter) and show_taps:
        # Filter the tap info
        filtered_sensor_tap_info = {}
        for sensor, details in sensor_tap_info.items():
            filtered_installs = filter_installations(details['installations'], employee_filter, date_filter)
            if filtered_installs:
                filtered_sensor_tap_info[sensor] = {
                    'total_taps': sum(i['taps'] for i in filtered_installs),
                    'installations': filtered_installs
                }
        sensor_tap_info = filtered_sensor_tap_info

        # Also filter unmapped mainlines for the summary
        filtered_unmapped = {}
        for mainline, details in unmapped_mainlines.items():
            filtered_installs = filter_installations(details['installations'], employee_filter, date_filter)
            if filtered_installs:
                filtered_unmapped[mainline] = {
                    'total_taps': sum(i['taps'] for i in filtered_installs),
                    'installations': filtered_installs
                }
        unmapped_mainlines = filtered_unmapped

        # Update map_data tap counts
        map_data['Taps'] = map_data['Sensor'].apply(
            lambda s: sensor_tap_info.get(s, {}).get('total_taps', 0)
        ).fillna(0).astype(int)

    st.divider()

    # Create map
    # Calculate center and zoom
    center_lat = map_data['Latitude'].mean()
    center_lon = map_data['Longitude'].mean()

    # Determine tile layer based on style
    if map_style == "Satellite":
        tiles = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
        attr = 'Esri'
    elif map_style == "Terrain":
        tiles = 'OpenTopoMap'
        attr = 'OpenTopoMap'
    else:
        tiles = 'OpenStreetMap'
        attr = 'OpenStreetMap'

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles=tiles,
        attr=attr
    )

    # Add legend based on color mode
    if has_site and color_by == "Site":
        legend_html = '''
        <div style="position: fixed;
                    top: 10px; right: 10px; width: 150px; height: auto;
                    background-color: white; border:2px solid grey; z-index:9999;
                    font-size:14px; padding: 10px; border-radius: 5px;">
        <p style="margin: 0; font-weight: bold; text-align: center;">Site Legend</p>
        <p style="margin: 5px 0;"><span style="color: #2196F3; font-size: 20px;">●</span> NY</p>
        <p style="margin: 5px 0;"><span style="color: #4CAF50; font-size: 20px;">●</span> VT</p>
        <p style="margin: 5px 0;"><span style="color: #9E9E9E; font-size: 20px;">●</span> UNK</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
    elif color_by == "Freeze Alert":
        legend_html = '''
        <div style="position: fixed;
                    top: 10px; right: 10px; width: 180px; height: auto;
                    background-color: white; border:2px solid grey; z-index:9999;
                    font-size:14px; padding: 10px; border-radius: 5px;">
        <p style="margin: 0; font-weight: bold; text-align: center;">Freeze Alert</p>
        <p style="margin: 5px 0;"><span style="color: #e74c3c; font-size: 20px;">&#9679;</span> Likely Leak</p>
        <p style="margin: 5px 0;"><span style="color: #f39c12; font-size: 20px;">&#9679;</span> Watch</p>
        <p style="margin: 5px 0;"><span style="color: #27ae60; font-size: 20px;">&#9679;</span> OK</p>
        <p style="margin: 5px 0;"><span style="color: #bdc3c7; font-size: 20px;">&#9679;</span> No Data</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))

    # Calculate max taps for dot scaling
    max_taps_value = map_data['Taps'].max() if map_data['Taps'].max() > 0 else 1

    # Add markers
    for idx, row in map_data.iterrows():
        # Determine marker color
        if color_by == "Vacuum Performance" and vacuum_col and 'Vacuum' in row:
            vacuum = row['Vacuum']
            if pd.notna(vacuum):
                if vacuum >= config.VACUUM_EXCELLENT:
                    color = 'green'
                    status = f"🟢 Excellent ({vacuum:.1f}\")"
                elif vacuum >= config.VACUUM_FAIR:
                    color = 'orange'
                    status = f"🟡 Fair ({vacuum:.1f}\")"
                else:
                    color = 'red'
                    status = f"🔴 Poor ({vacuum:.1f}\")"
            else:
                color = 'gray'
                status = "No reading"
        elif color_by == "Site" and has_site and 'Site' in row:
            site = row['Site']
            if site == 'NY':
                color = 'blue'
                status = "🟦 NY Site"
            elif site == 'VT':
                color = 'green'
                status = "🟩 VT Site"
            else:
                color = 'gray'
                status = "⚫ Unknown Site"
        elif color_by == "Freeze Alert":
            freeze_info = _freeze_lookup.get(row['Sensor'])
            if freeze_info:
                fz_status = freeze_info['status']
                if fz_status == 'LIKELY LEAK':
                    color = 'red'
                    status = f"🔴 Likely Leak ({freeze_info['drop_rate']:.0%})"
                elif fz_status == 'WATCH':
                    color = 'orange'
                    status = f"🟠 Watch ({freeze_info['drop_rate']:.0%})"
                else:
                    color = 'green'
                    status = "🟢 OK — Stable during freeze"
            else:
                color = 'gray'
                status = "No freeze data"
        else:
            color = 'blue'
            status = "Sensor"

        # Get tap info for this sensor
        tap_count = row.get('Taps', 0)
        tap_info = sensor_tap_info.get(row['Sensor'], {})
        installations = tap_info.get('installations', [])

        # Create popup
        popup_html = f"""
        <div style="font-family: Arial; min-width: 250px; max-width: 350px;">
            <h4 style="margin: 0 0 10px 0;">{row['Sensor']}</h4>
        """

        if has_site and 'Site' in row:
            site_emoji = "🟦" if row['Site'] == "NY" else "🟩" if row['Site'] == "VT" else "⚫"
            popup_html += f"<p style='margin: 5px 0;'><b>Site:</b> {site_emoji} {row['Site']}</p>"

        if vacuum_col and 'Vacuum' in row and pd.notna(row['Vacuum']):
            popup_html += f"<p style='margin: 5px 0;'><b>Vacuum:</b> {row['Vacuum']:.1f}\"</p>"
            popup_html += f"<p style='margin: 5px 0;'><b>Status:</b> {status}</p>"

        # Freeze event info line (shown in all color modes)
        _sensor_freeze = _freeze_lookup.get(row['Sensor'])
        if _sensor_freeze:
            _fz_days = _sensor_freeze['days_with_drop']
            _fz_total = _sensor_freeze['total_days']
            _fz_rate = _sensor_freeze['drop_rate']
            _fz_st = _sensor_freeze['status']
            if _fz_st == 'LIKELY LEAK':
                _fz_color = '#e74c3c'
                _fz_icon = '❄️🔴'
            elif _fz_st == 'WATCH':
                _fz_color = '#f39c12'
                _fz_icon = '❄️🟠'
            else:
                _fz_color = '#27ae60'
                _fz_icon = '❄️🟢'
            popup_html += f"<p style='margin: 5px 0; color: {_fz_color};'><b>{_fz_icon} Freeze Events:</b> Dropped {_fz_days}/{_fz_total} days ({_fz_rate:.0%})</p>"
        elif _freeze_drops is not None and not _freeze_drops.empty:
            popup_html += "<p style='margin: 5px 0; color: #27ae60;'><b>❄️ Freeze Events:</b> Stable</p>"

        if tap_count > 0:
            popup_html += f"<p style='margin: 5px 0;'><b>Total Taps Installed:</b> {int(tap_count):,}</p>"

            # Add installation history
            if installations:
                popup_html += "<div style='margin-top: 10px; border-top: 1px solid #ddd; padding-top: 8px;'>"
                popup_html += "<p style='margin: 0 0 5px 0; font-weight: bold; font-size: 12px;'>Recent Installations:</p>"
                popup_html += "<table style='font-size: 11px; width: 100%; border-collapse: collapse;'>"

                for install in installations[:5]:  # Show last 5
                    date_str = ""
                    if 'date' in install and pd.notna(install['date']):
                        try:
                            date_str = pd.to_datetime(install['date']).strftime('%m/%d/%y')
                        except Exception:
                            date_str = str(install['date'])[:10]

                    emp_str = install.get('employee', 'Unknown')
                    if isinstance(emp_str, str) and len(emp_str) > 15:
                        emp_str = emp_str[:15] + "..."

                    popup_html += f"<tr><td style='padding: 2px;'>{date_str}</td><td style='padding: 2px;'>{emp_str}</td><td style='padding: 2px; text-align: right;'>{install['taps']}</td></tr>"

                popup_html += "</table></div>"

        popup_html += f"""
            <p style='margin: 8px 0 0 0; font-size: 10px; color: gray;'>
                {row['Latitude']:.5f}, {row['Longitude']:.5f}
            </p>
        </div>
        """

        # Scale dot size by tap count: min 3 (0 taps) to max 22 (highest)
        # Use square root scaling for more visual separation between low/high
        tap_ratio = math.sqrt(tap_count / max_taps_value) if max_taps_value > 0 else 0
        dot_radius = 3 + tap_ratio * 19  # 3 to 22

        # Add circle marker with sensor name tooltip
        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=dot_radius,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=row['Sensor'],
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.7,
            weight=1
        ).add_to(m)

        # Add small black label with tap count (only if enabled and counts >= 20)
        if show_taps and tap_count >= 20:
            # Format the tap count
            if tap_count >= 1000:
                tap_label = f"{tap_count/1000:.1f}k"
            else:
                tap_label = str(int(tap_count))

            # Build hover tooltip text with recent installations
            tooltip_lines = [f"{row['Sensor']}: {int(tap_count)} taps"]
            if installations[:3]:  # Show last 3 in tooltip
                tooltip_lines.append("---")
                for install in installations[:3]:
                    date_str = ""
                    if 'date' in install and pd.notna(install['date']):
                        try:
                            date_str = pd.to_datetime(install['date']).strftime('%m/%d')
                        except Exception:
                            date_str = ""
                    emp = install.get('employee', '?')[:12]
                    tooltip_lines.append(f"{date_str} {emp}: {install['taps']}")
            tooltip_text = "&#10;".join(tooltip_lines)  # &#10; is newline in title attr

            # Create a small black label offset to upper-right of marker
            # title attribute shows on hover
            folium.Marker(
                location=[row['Latitude'], row['Longitude']],
                icon=folium.DivIcon(
                    html=f'''<div title="{tooltip_text}" style="
                        background-color: rgba(0,0,0,0.85);
                        color: white;
                        border-radius: 3px;
                        padding: 1px 4px;
                        font-size: 10px;
                        font-weight: bold;
                        white-space: nowrap;
                        transform: translate(8px, -20px);
                        box-shadow: 1px 1px 2px rgba(0,0,0,0.3);
                        cursor: default;
                    ">{tap_label}</div>''',
                    icon_size=(30, 15),
                    icon_anchor=(0, 0)
                )
            ).add_to(m)

    # Display map - use returned_objects=[] to prevent refreshes on every click
    st_folium(m, width=None, height=600, returned_objects=[])

    st.divider()

    # ========================================================================
    # REPAIRS NEEDING ATTENTION MAP
    # ========================================================================

    st.subheader("🔧 Repairs Needing Attention")
    st.markdown("*Lines with reported repairs that have no subsequent fix logged*")

    # Build repairs map from repairs tracker (or fall back to personnel data)
    _render_repairs_map(personnel_df, map_data, map_style, tiles, attr, center_lat, center_lon, repairs_df)

    st.divider()

    # Summary stats
    st.subheader("📊 Map Summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Sensors", len(map_data))

    with col2:
        if vacuum_col and 'Vacuum' in map_data.columns:
            avg_vacuum = map_data['Vacuum'].mean()
            st.metric("Avg Vacuum", f"{avg_vacuum:.1f}\"")

    with col3:
        lat_range = map_data['Latitude'].max() - map_data['Latitude'].min()
        st.metric("Latitude Range", f"{lat_range:.4f}°")

    with col4:
        lon_range = map_data['Longitude'].max() - map_data['Longitude'].min()
        st.metric("Longitude Range", f"{lon_range:.4f}°")

    # Site-specific stats if viewing all
    if has_site and not viewing_site:
        st.markdown("**Sensors by Site:**")
        
        site_stats = map_data.groupby('Site').agg({
            'Sensor': 'count',
            'Vacuum': 'mean' if 'Vacuum' in map_data.columns else 'count'
        }).reset_index()
        
        if 'Vacuum' in map_data.columns:
            site_stats.columns = ['Site', 'Count', 'Avg_Vacuum']
        else:
            site_stats.columns = ['Site', 'Count']
        
        cols = st.columns(len(site_stats))
        for idx, row in site_stats.iterrows():
            with cols[idx]:
                emoji = "🟦" if row['Site'] == "NY" else "🟩" if row['Site'] == "VT" else "⚫"
                st.metric(f"{emoji} {row['Site']}", f"{int(row['Count'])} sensors")
                if 'Avg_Vacuum' in row:
                    st.caption(f"Avg: {row['Avg_Vacuum']:.1f}\"")

    # Unmapped taps section
    if unmapped_mainlines:
        st.divider()
        total_unmapped_taps = sum(d['total_taps'] for d in unmapped_mainlines.values())

        with st.expander(f"⚠️ Unmapped Taps ({total_unmapped_taps:,} taps from {len(unmapped_mainlines)} mainlines)", expanded=False):
            st.markdown("""
            These mainlines from personnel data couldn't be matched to any vacuum sensor on the map.
            This could mean the mainline name doesn't match any sensor name, or the sensor isn't in the vacuum data.
            """)

            # Create a table of unmapped mainlines
            unmapped_data = []
            for mainline, details in sorted(unmapped_mainlines.items(), key=lambda x: x[1]['total_taps'], reverse=True):
                # Get most recent installation info
                recent = details['installations'][0] if details['installations'] else {}
                last_date = ""
                last_emp = ""
                if 'date' in recent and pd.notna(recent['date']):
                    try:
                        last_date = pd.to_datetime(recent['date']).strftime('%m/%d/%y')
                    except Exception:
                        last_date = str(recent['date'])[:10]
                if 'employee' in recent:
                    last_emp = recent['employee']

                unmapped_data.append({
                    'Mainline': mainline,
                    'Total Taps': details['total_taps'],
                    'Last Install': last_date,
                    'By': last_emp
                })

            unmapped_df = pd.DataFrame(unmapped_data)
            st.dataframe(unmapped_df, use_container_width=True, hide_index=True)

            st.info("💡 To fix: Check if mainline names match sensor names in the vacuum data, or add these sensors to the map.")

    st.divider()

    # Tips
    with st.expander("💡 Using the Interactive Map"):
        st.markdown("""
        **Map Features:**
        
        - **Click markers** for detailed sensor information
        - **Zoom/Pan** to explore specific areas
        - **Color coding** shows performance or site at a glance
        - **Site legend** (when viewing all sites) helps identify locations
        
        **Map Styles:**
        
        - **Terrain**: Shows elevation and topography (useful for planning routes)
        - **Satellite**: Aerial imagery (identify actual tree locations)
        - **Street**: Road network (useful for access planning)
        
        **Color Modes:**
        
        When coloring by **Vacuum Performance**:
        - 🟢 Green: Excellent (≥18")
        - 🟡 Orange: Fair (15-18")
        - 🔴 Red: Poor (<15")
        
        When coloring by **Site**:
        - 🟦 Blue: NY site
        - 🟩 Green: VT site
        - ⚫ Gray: Unknown site

        When coloring by **Freeze Alert**:
        - 🔴 Red: Likely Leak — vacuum dropped on 50%+ of freeze/thaw days
        - 🟠 Orange: Watch — vacuum dropped on 25-50% of freeze/thaw days
        - 🟢 Green: OK — stable during freeze events
        - ⚪ Gray: Insufficient freeze data

        **Multi-Site Viewing:**
        
        When viewing all sites:
        - See both NY and VT on same map
        - Site legend in top-right corner
        - Color by site to see site boundaries
        - Useful for understanding geographic separation
        
        When viewing single site:
        - Focused view of one location
        - Color by vacuum performance recommended
        - Easier to spot problem areas
        - Better for daily operations
        
        **Practical Uses:**
        
        - **Dispatch Planning**: Identify clusters of poor-performing sensors
        - **Route Planning**: Plan efficient maintenance routes
        - **Problem Areas**: Spot geographic patterns in issues
        - **Site Comparison**: See how sites differ geographically
        - **Crew Assignment**: Visualize which areas to assign to which crew
        - **Access Planning**: Identify difficult-to-reach sensors
        
        **Tips:**
        
        - Use terrain mode to plan walking routes
        - Color by vacuum to find problem areas quickly
        - Color by site when planning multi-site work
        - Click sensors to get exact coordinates
        - Screenshot map for crew navigation
        - Compare maps between sites for patterns
        """)


def _render_repairs_map(personnel_df, map_data, map_style, tiles, attr, center_lat, center_lon, repairs_df=None):
    """
    Render a second map showing mainlines with repair status.

    If repairs_df is provided (from the repairs_tracker Google Sheet), uses that
    for rich status/detail overlays. Otherwise falls back to scanning personnel
    data for repair text descriptions.

    Color coding (tracker mode):
        Red    = Open repairs
        Orange = Deferred repairs
        Green  = Completed repairs
        Gray   = No repairs reported
    """
    if map_data.empty:
        st.info("No sensor data available for repairs map")
        return

    # ── Use repairs_tracker data if available ──────────────────────────
    if repairs_df is not None and not repairs_df.empty:
        _render_repairs_map_from_tracker(repairs_df, map_data, map_style, tiles, attr, center_lat, center_lon)
        return

    # ── Fallback: derive repair info from personnel data ──────────────
    _render_repairs_map_from_personnel(personnel_df, map_data, map_style, tiles, attr, center_lat, center_lon)


def _render_repairs_map_from_tracker(repairs_df, map_data, map_style, tiles, attr, center_lat, center_lon):
    """Render repairs overlay using the repairs_tracker sheet data."""

    df = repairs_df.copy()

    # Normalise status
    if 'Status' in df.columns:
        df['Status'] = df['Status'].astype(str).str.strip().str.title()
    else:
        df['Status'] = 'Open'

    # Parse dates
    if 'Date Found' in df.columns:
        df['Date Found'] = pd.to_datetime(df['Date Found'], errors='coerce')
        df['Age (Days)'] = (pd.Timestamp.now() - df['Date Found']).dt.days
    else:
        df['Age (Days)'] = None

    if 'Date Resolved' in df.columns:
        df['Date Resolved'] = pd.to_datetime(df['Date Resolved'], errors='coerce')

    # ── Metrics ────────────────────────────────────────────────────────
    open_count = (df['Status'] == 'Open').sum()
    deferred_count = (df['Status'] == 'Deferred').sum()
    completed_count = (df['Status'] == 'Completed').sum()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Open", int(open_count))
    with col2:
        st.metric("Deferred", int(deferred_count))
    with col3:
        st.metric("Completed", int(completed_count))
    with col4:
        st.metric("Total Repairs", len(df))

    # ── Controls ───────────────────────────────────────────────────────
    show_completed = st.checkbox(
        "Show completed repairs on map",
        value=False,
        help="Toggle to show/hide completed (green) markers"
    )

    # Filter repairs for display
    if show_completed:
        display_df = df
    else:
        display_df = df[df['Status'] != 'Completed']

    if display_df.empty and not show_completed:
        st.success("No open or deferred repairs to display! Toggle 'Show completed' to see resolved items.")
        return

    # ── Match repairs to sensors ───────────────────────────────────────
    sensor_names = map_data['Sensor'].tolist()

    # Group repairs by the sensor they map to
    sensor_repairs = {}  # sensor_name -> list of repair dicts
    unmatched_repairs = []

    for _, repair in display_df.iterrows():
        mainline = repair.get('Mainline', '')
        if pd.isna(mainline) or not str(mainline).strip():
            unmatched_repairs.append(repair)
            continue

        matched_sensor = match_mainline_to_sensor(str(mainline).strip(), sensor_names)
        if matched_sensor:
            if matched_sensor not in sensor_repairs:
                sensor_repairs[matched_sensor] = []
            sensor_repairs[matched_sensor].append(repair)
        else:
            unmatched_repairs.append(repair)

    # ── Build map ──────────────────────────────────────────────────────
    m2 = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles=tiles,
        attr=attr
    )

    # Legend
    legend_html = '''
    <div style="position: fixed;
                top: 10px; right: 10px; width: 200px; height: auto;
                background-color: white; border:2px solid grey; z-index:9999;
                font-size:14px; padding: 10px; border-radius: 5px;">
    <p style="margin: 0; font-weight: bold; text-align: center;">Repair Status</p>
    <p style="margin: 5px 0;"><span style="color: #e74c3c; font-size: 20px;">&#9679;</span> Open</p>
    <p style="margin: 5px 0;"><span style="color: #f39c12; font-size: 20px;">&#9679;</span> Deferred</p>
    <p style="margin: 5px 0;"><span style="color: #27ae60; font-size: 20px;">&#9679;</span> Completed</p>
    <p style="margin: 5px 0;"><span style="color: #bdc3c7; font-size: 20px;">&#9679;</span> No Repairs</p>
    <p style="margin: 5px 0; border-top: 1px solid #ddd; padding-top: 5px; font-size: 12px; color: #555;">
      &#9898; White border = exact GPS pin<br>&#9679; Solid = sensor area</p>
    </div>
    '''
    m2.get_root().html.add_child(folium.Element(legend_html))

    # ── Place markers ──────────────────────────────────────────────────
    for _, row in map_data.iterrows():
        sensor = row['Sensor']
        repairs_list = sensor_repairs.get(sensor, [])

        if not repairs_list:
            # Gray — no repairs for this sensor
            color = '#bdc3c7'
            dot_radius = 6
            popup_html = f"""
            <div style="font-family: Arial;">
                <h4 style="margin: 0 0 5px 0;">{sensor}</h4>
                <p>No repairs reported</p>
            </div>
            """
        else:
            # Determine dominant status for marker color
            statuses = [str(r.get('Status', 'Open')).title() for r in repairs_list]
            open_here = statuses.count('Open')
            deferred_here = statuses.count('Deferred')
            completed_here = statuses.count('Completed')

            if open_here > 0:
                color = '#e74c3c'     # red — has open repairs
            elif deferred_here > 0:
                color = '#f39c12'     # orange — deferred only
            else:
                color = '#27ae60'     # green — all completed

            # Dot size: 8 base + 3 per open/deferred repair (cap at 20)
            active_count = open_here + deferred_here
            dot_radius = min(8 + active_count * 3, 20)

            # Build popup with repair list
            popup_html = f"""
            <div style="font-family: Arial; min-width: 280px; max-width: 400px;">
                <h4 style="margin: 0 0 8px 0;">{sensor}</h4>
                <p style="margin: 0 0 8px 0; font-size: 12px; color: #666;">
                    {open_here} open &middot; {deferred_here} deferred &middot; {completed_here} completed
                </p>
            """

            for repair in repairs_list:
                status = str(repair.get('Status', 'Open')).title()

                # Status badge color
                if status == 'Open':
                    badge_color = '#e74c3c'
                elif status == 'Deferred':
                    badge_color = '#f39c12'
                else:
                    badge_color = '#27ae60'

                # Date found
                date_found_str = ''
                if pd.notna(repair.get('Date Found')):
                    try:
                        date_found_str = repair['Date Found'].strftime('%m/%d/%y')
                    except Exception:
                        date_found_str = str(repair['Date Found'])[:10]

                # Age
                age_str = ''
                age_val = repair.get('Age (Days)')
                if pd.notna(age_val):
                    age_str = f" ({int(age_val)}d)"

                # Description
                desc = str(repair.get('Description', ''))[:120]

                # Found by
                found_by = str(repair.get('Found By', '')) if pd.notna(repair.get('Found By')) else ''

                popup_html += f"""
                <div style="border-top: 1px solid #eee; padding: 6px 0;">
                    <span style="background: {badge_color}; color: white; padding: 1px 6px;
                                 border-radius: 3px; font-size: 11px;">{status}</span>
                    <span style="font-size: 11px; color: #888; margin-left: 4px;">
                        {date_found_str}{age_str}
                    </span>
                """

                if desc:
                    popup_html += f"<p style='margin: 4px 0 2px 0; font-size: 12px;'>{desc}</p>"
                if found_by:
                    popup_html += f"<p style='margin: 2px 0; font-size: 11px; color: #666;'>Found by: {found_by}</p>"

                # Resolution info for completed
                if status == 'Completed':
                    resolved_by = str(repair.get('Resolved By', '')) if pd.notna(repair.get('Resolved By')) else ''
                    date_resolved_str = ''
                    if pd.notna(repair.get('Date Resolved')):
                        try:
                            date_resolved_str = repair['Date Resolved'].strftime('%m/%d/%y')
                        except Exception:
                            date_resolved_str = str(repair['Date Resolved'])[:10]
                    cost_str = ''
                    if pd.notna(repair.get('Repair Cost')) and str(repair.get('Repair Cost', '')).strip():
                        try:
                            cost_str = f"${float(repair['Repair Cost']):.2f}"
                        except (ValueError, TypeError):
                            cost_str = str(repair['Repair Cost'])
                    resolution_parts = []
                    if resolved_by:
                        resolution_parts.append(f"by {resolved_by}")
                    if date_resolved_str:
                        resolution_parts.append(f"on {date_resolved_str}")
                    if cost_str:
                        resolution_parts.append(f"cost {cost_str}")
                    if resolution_parts:
                        popup_html += f"<p style='margin: 2px 0; font-size: 11px; color: #27ae60;'>Resolved {' '.join(resolution_parts)}</p>"

                popup_html += "</div>"

            popup_html += "</div>"

        # Tooltip
        tooltip_text = sensor
        if repairs_list:
            active = sum(1 for r in repairs_list if str(r.get('Status', '')).title() in ('Open', 'Deferred'))
            if active:
                tooltip_text += f" ({active} open)"

        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=dot_radius,
            popup=folium.Popup(popup_html, max_width=400),
            tooltip=tooltip_text,
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.8,
            weight=2
        ).add_to(m2)

    # ── Exact GPS pins for AppSheet-logged repairs ──────────────────────
    # Repairs logged via AppSheet carry Latitude/Longitude from the Location
    # LatLong column (parsed in data_loader). Plot them at their precise field
    # location with a white border so they stand out from sensor-area pins.
    if 'Latitude' in display_df.columns and 'Longitude' in display_df.columns:
        gps_repairs = display_df.dropna(subset=['Latitude', 'Longitude'])
        gps_repairs = gps_repairs[gps_repairs['Latitude'].abs() > 0]
        for _, rep in gps_repairs.iterrows():
            _status = str(rep.get('Status', '')).title()
            _gps_color = ('#e74c3c' if _status == 'Open'
                          else '#f39c12' if _status == 'Deferred'
                          else '#27ae60')
            # Build popup
            _desc = str(rep.get('Description', ''))[:100]
            _found_by = str(rep.get('Found By', '')) if pd.notna(rep.get('Found By')) else ''
            _date_found = ''
            if pd.notna(rep.get('Date Found')):
                try:
                    _date_found = rep['Date Found'].strftime('%m/%d/%y')
                except Exception:
                    _date_found = str(rep.get('Date Found', ''))[:10]
            _photo_html = ''
            _photo_url = str(rep.get('Photo Found', '')).strip()
            if _photo_url and _photo_url not in ('', 'nan'):
                _photo_html = f'<br><a href="{_photo_url}" target="_blank">📷 View Photo</a>'
            _popup_body = (
                f"<b>{rep.get('Repair ID', '')}</b><br>"
                f"{_desc}<br>"
                f"Found: {_date_found}"
                + (f" by {_found_by}" if _found_by else "")
                + f"<br>Status: <b>{_status}</b>{_photo_html}"
            )
            folium.CircleMarker(
                location=[rep['Latitude'], rep['Longitude']],
                radius=8,
                color='white',
                weight=2,
                fill=True,
                fill_color=_gps_color,
                fill_opacity=0.9,
                popup=folium.Popup(_popup_body, max_width=250),
                tooltip=f"🔧 {rep.get('Mainline', '')} — {_status}",
            ).add_to(m2)

    st_folium(m2, width=None, height=600, returned_objects=[])

    # Show unmatched repairs
    if unmatched_repairs:
        with st.expander(f"⚠️ {len(unmatched_repairs)} repairs could not be placed on map", expanded=False):
            st.markdown("These repairs have mainline names that don't match any sensor with GPS coordinates.")
            unmatched_data = []
            for repair in unmatched_repairs:
                unmatched_data.append({
                    'Mainline': repair.get('Mainline', ''),
                    'Status': repair.get('Status', ''),
                    'Date Found': repair.get('Date Found', ''),
                    'Description': str(repair.get('Description', ''))[:80],
                })
            st.dataframe(pd.DataFrame(unmatched_data), use_container_width=True, hide_index=True)


def _render_repairs_map_from_personnel(personnel_df, map_data, map_style, tiles, attr, center_lat, center_lon):
    """
    Fallback: Render repairs map by scanning personnel data for repair text.
    Used when no repairs_tracker sheet is available.
    Red = repairs reported but no subsequent fix job logged.
    Green = repairs reported AND a fix was logged after.
    Gray = no repairs reported.
    """
    if personnel_df.empty:
        st.info("No personnel data available for repairs map")
        return

    # Find columns
    mainline_col = None
    for col in personnel_df.columns:
        if 'mainline' in col.lower():
            mainline_col = col
            break

    date_col = 'Date' if 'Date' in personnel_df.columns else None
    job_col = None
    for col in personnel_df.columns:
        if col.lower() in ('job', 'job code', 'jobcode'):
            job_col = col
            break

    repairs_col = None
    for col in personnel_df.columns:
        if 'repairs needed' in col.lower() or col == 'Repairs needed':
            repairs_col = col
            break

    if not all([mainline_col, date_col, repairs_col]):
        st.info("Required columns not found for repairs analysis")
        return

    df = personnel_df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df = df.dropna(subset=[date_col])

    # Find mainlines with text repair descriptions (not just numeric 0)
    def has_repair_text(val):
        if pd.isna(val) or val == '' or val is None:
            return False
        s = str(val).strip()
        if not s:
            return False
        try:
            float(s)
            return False  # Pure number, not a description
        except ValueError:
            return True

    repair_rows = df[df[repairs_col].apply(has_repair_text)].copy()

    if repair_rows.empty:
        st.info("No repair descriptions found in personnel data")
        return

    def is_fix_job(job_text):
        if pd.isna(job_text):
            return False
        j = str(job_text).lower()
        return any(kw in j for kw in [
            'fixing identified tubing',
            'already identified tubing',
            'tubing repair',
            'tubing issue',
            'fix identified',
        ])

    # Get the latest repair date per mainline
    mainline_repairs = repair_rows.groupby(mainline_col).agg({
        date_col: 'max',
        repairs_col: 'last'
    }).reset_index()
    mainline_repairs.columns = ['Mainline', 'Last_Repair_Date', 'Last_Repair_Desc']

    repair_status = {}

    for _, row in mainline_repairs.iterrows():
        mainline = row['Mainline']
        repair_date = row['Last_Repair_Date']
        desc = row['Last_Repair_Desc']

        if pd.isna(mainline) or not str(mainline).strip():
            continue

        if job_col:
            fix_entries = df[
                (df[mainline_col] == mainline) &
                (df[date_col] > repair_date) &
                (df[job_col].apply(is_fix_job))
            ]
            has_fix = not fix_entries.empty
        else:
            has_fix = False

        repair_status[mainline] = {
            'status': 'resolved' if has_fix else 'unresolved',
            'repair_date': repair_date,
            'description': str(desc)[:100],
        }

    if not repair_status:
        st.info("No repairs to map")
        return

    unresolved = sum(1 for v in repair_status.values() if v['status'] == 'unresolved')
    resolved = sum(1 for v in repair_status.values() if v['status'] == 'resolved')

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Unresolved", unresolved)
    with col2:
        st.metric("Resolved", resolved)
    with col3:
        st.metric("Total Lines with Repairs", len(repair_status))

    m2 = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles=tiles,
        attr=attr
    )

    legend_html = '''
    <div style="position: fixed;
                top: 10px; right: 10px; width: 180px; height: auto;
                background-color: white; border:2px solid grey; z-index:9999;
                font-size:14px; padding: 10px; border-radius: 5px;">
    <p style="margin: 0; font-weight: bold; text-align: center;">Repair Status</p>
    <p style="margin: 5px 0;"><span style="color: #e74c3c; font-size: 20px;">&#9679;</span> Needs Fix</p>
    <p style="margin: 5px 0;"><span style="color: #27ae60; font-size: 20px;">&#9679;</span> Fix Logged</p>
    <p style="margin: 5px 0;"><span style="color: #bdc3c7; font-size: 20px;">&#9679;</span> No Repairs</p>
    </div>
    '''
    m2.get_root().html.add_child(folium.Element(legend_html))

    for _, row in map_data.iterrows():
        sensor = row['Sensor']

        matched_mainline = None
        for mainline in repair_status:
            matched = match_mainline_to_sensor(mainline, [sensor])
            if matched:
                matched_mainline = mainline
                break

        if matched_mainline and matched_mainline in repair_status:
            info = repair_status[matched_mainline]
            if info['status'] == 'unresolved':
                color = '#e74c3c'
                status_text = 'Needs Fix'
            else:
                color = '#27ae60'
                status_text = 'Fix Logged'

            date_str = ''
            if pd.notna(info['repair_date']):
                try:
                    date_str = info['repair_date'].strftime('%Y-%m-%d')
                except Exception:
                    date_str = str(info['repair_date'])[:10]

            popup_html = f"""
            <div style="font-family: Arial; min-width: 200px;">
                <h4 style="margin: 0 0 5px 0;">{sensor}</h4>
                <p style="margin: 3px 0;"><b>Status:</b> {status_text}</p>
                <p style="margin: 3px 0;"><b>Repair Date:</b> {date_str}</p>
                <p style="margin: 3px 0;"><b>Description:</b> {info['description']}</p>
            </div>
            """
        else:
            color = '#bdc3c7'
            popup_html = f"""
            <div style="font-family: Arial;">
                <h4 style="margin: 0 0 5px 0;">{sensor}</h4>
                <p>No repairs reported</p>
            </div>
            """

        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=8,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=sensor,
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.8,
            weight=2
        ).add_to(m2)

    st_folium(m2, width=None, height=600, returned_objects=[])
