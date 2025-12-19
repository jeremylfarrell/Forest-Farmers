"""
Interactive Map Page Module - MULTI-SITE POLISHED
Geographic visualization of sensor locations with performance overlay
Now with site color coding and legend
"""

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import config
from utils import find_column, get_vacuum_column


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

        # Create popup
        popup_html = f"""
        <div style="font-family: Arial; min-width: 200px;">
            <h4 style="margin: 0 0 10px 0;">{row['Sensor']}</h4>
        """
        
        if has_site and 'Site' in row:
            site_emoji = "🟦" if row['Site'] == "NY" else "🟩" if row['Site'] == "VT" else "⚫"
            popup_html += f"<p style='margin: 5px 0;'><b>Site:</b> {site_emoji} {row['Site']}</p>"
        
        if vacuum_col and 'Vacuum' in row and pd.notna(row['Vacuum']):
            popup_html += f"<p style='margin: 5px 0;'><b>Vacuum:</b> {row['Vacuum']:.1f}\"</p>"
            popup_html += f"<p style='margin: 5px 0;'><b>Status:</b> {status}</p>"
        
        popup_html += f"""
            <p style='margin: 5px 0; font-size: 11px; color: gray;'>
                Lat: {row['Latitude']:.6f}, Lon: {row['Longitude']:.6f}
            </p>
        </div>
        """

        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=marker_size,
            popup=folium.Popup(popup_html, max_width=300),
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.7,
            weight=2
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
