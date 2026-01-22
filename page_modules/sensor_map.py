"""
Interactive Map Page Module - MULTI-SITE POLISHED
Geographic visualization of sensor locations with performance overlay
Now with site color coding, legend, and tap count display
"""

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import config
from utils import find_column, get_vacuum_column
import re


def match_mainline_to_sensor(mainline, sensor_names):
    """
    Match a mainline name to the closest sensor name
    Uses fuzzy matching based on common patterns

    Args:
        mainline: Mainline name from personnel data (e.g., "RHAS13")
        sensor_names: List of sensor names from vacuum data

    Returns:
        Best matching sensor name or None
    """
    if pd.isna(mainline) or not mainline:
        return None

    mainline = str(mainline).strip().upper()

    # Try exact match first
    for sensor in sensor_names:
        if str(sensor).strip().upper() == mainline:
            return sensor

    # Try partial match - mainline contained in sensor name
    for sensor in sensor_names:
        sensor_upper = str(sensor).strip().upper()
        if mainline in sensor_upper or sensor_upper in mainline:
            return sensor

    # Try matching without numbers (e.g., "RHAS" matches "RHAS13")
    mainline_alpha = re.sub(r'\d+', '', mainline)
    for sensor in sensor_names:
        sensor_alpha = re.sub(r'\d+', '', str(sensor).upper())
        if mainline_alpha and sensor_alpha and mainline_alpha == sensor_alpha:
            return sensor

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


def render(vacuum_df, personnel_df):
    """Render interactive map with site-aware visualization"""

    st.title("🌍 Interactive Sensor Map")
    st.markdown("*Geographic visualization of sensor locations and performance*")

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
            ["Terrain", "Satellite", "Street"],
            help="Choose map background"
        )

    with col2:
        if vacuum_col:
            color_by = st.selectbox(
                "Color Markers By",
                ["Vacuum Performance", "Site"] if has_site else ["Vacuum Performance"],
                help="How to color the sensor markers"
            )
        else:
            color_by = "Site" if has_site else None

    with col3:
        marker_size = st.slider(
            "Marker Size",
            min_value=5,
            max_value=15,
            value=8,
            help="Size of markers on map"
        )

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

    # Add legend if multi-site
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
                        except:
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

        # Add smaller vacuum circle marker
        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=max(3, marker_size - 3),  # Smaller radius
            popup=folium.Popup(popup_html, max_width=300),
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.7,
            weight=1
        ).add_to(m)

        # Add small black label with tap count (only for counts >= 20 to reduce clutter)
        if tap_count >= 20:
            # Format the tap count
            if tap_count >= 1000:
                tap_label = f"{tap_count/1000:.1f}k"
            else:
                tap_label = str(int(tap_count))

            # Create a small black label offset to upper-right of marker
            folium.Marker(
                location=[row['Latitude'], row['Longitude']],
                icon=folium.DivIcon(
                    html=f'''<div style="
                        background-color: rgba(0,0,0,0.85);
                        color: white;
                        border-radius: 3px;
                        padding: 1px 4px;
                        font-size: 10px;
                        font-weight: bold;
                        white-space: nowrap;
                        transform: translate(8px, -20px);
                        box-shadow: 1px 1px 2px rgba(0,0,0,0.3);
                    ">{tap_label}</div>''',
                    icon_size=(30, 15),
                    icon_anchor=(0, 0)
                )
            ).add_to(m)

    # Display map
    st_folium(m, width=None, height=600)

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
                    except:
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
