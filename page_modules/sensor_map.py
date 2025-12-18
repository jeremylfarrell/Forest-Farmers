"""
Interactive Sensor Map Page Module - FOLIUM VERSION
Uses Folium for better navigation and topographic maps
Includes OpenTopoMap with elevation contours and terrain details
"""

import streamlit as st
import pandas as pd
from streamlit_folium import st_folium
import folium
from folium import plugins
import config
from utils import find_column, get_vacuum_column


@st.cache_data(ttl=3600)
def prepare_map_data(vacuum_df):
    """
    Prepare sensor data for mapping (cached for performance)

    Args:
        vacuum_df: Raw vacuum data

    Returns:
        DataFrame ready for mapping
    """
    # Find required columns
    sensor_col = find_column(
        vacuum_df,
        'Name', 'name', 'mainline', 'Sensor Name', 'sensor', 'location'
    )
    vacuum_col = get_vacuum_column(vacuum_df)
    lat_col = find_column(vacuum_df, 'Latitude', 'latitude', 'lat')
    lon_col = find_column(vacuum_df, 'Longitude', 'longitude', 'lon', 'long')
    timestamp_col = find_column(
        vacuum_df,
        'Last communication', 'Last Communication', 'Timestamp', 'timestamp'
    )

    if not all([sensor_col, vacuum_col, lat_col, lon_col]):
        return None, None

    # Get latest reading per sensor
    if timestamp_col:
        temp_df = vacuum_df.copy()
        temp_df[timestamp_col] = pd.to_datetime(temp_df[timestamp_col], errors='coerce')
        latest = temp_df.sort_values(timestamp_col, ascending=False).groupby(sensor_col).first().reset_index()
    else:
        latest = vacuum_df.groupby(sensor_col).first().reset_index()

    # Prepare data for mapping
    map_data = latest[[sensor_col, vacuum_col, lat_col, lon_col]].copy()
    map_data.columns = ['Sensor', 'Vacuum', 'Latitude', 'Longitude']

    # Convert to numeric
    map_data['Latitude'] = pd.to_numeric(map_data['Latitude'], errors='coerce')
    map_data['Longitude'] = pd.to_numeric(map_data['Longitude'], errors='coerce')
    map_data['Vacuum'] = pd.to_numeric(map_data['Vacuum'], errors='coerce')

    # Filter out invalid coordinates
    original_count = len(map_data)
    map_data = map_data[
        (map_data['Latitude'].notna()) &
        (map_data['Longitude'].notna()) &
        (map_data['Latitude'] != 0) &
        (map_data['Longitude'] != 0) &
        (map_data['Latitude'].between(40, 45)) &
        (map_data['Longitude'].between(-80, -72))
        ]

    filtered_count = original_count - len(map_data)

    # Add status category for coloring
    def get_status_category(vacuum):
        if vacuum >= config.VACUUM_EXCELLENT:
            return "Excellent"
        elif vacuum >= config.VACUUM_FAIR:
            return "Fair"
        else:
            return "Poor"

    map_data['Status'] = map_data['Vacuum'].apply(get_status_category)

    return map_data, filtered_count


def get_marker_color(status):
    """Get marker color based on status"""
    if status == "Excellent":
        return "green"
    elif status == "Fair":
        return "orange"
    else:
        return "red"


def create_folium_map(data, map_style, show_clusters=False):
    """
    Create a Folium map with sensors

    Args:
        data: Filtered sensor data
        map_style: Selected map style
        show_clusters: Whether to cluster markers

    Returns:
        Folium map object
    """
    # Calculate center
    center_lat = data['Latitude'].mean()
    center_lon = data['Longitude'].mean()

    # Create base map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
        tiles=None  # We'll add tiles manually for more control
    )

    # Add different tile layers based on selection
    if map_style == "Topographic (OpenTopoMap)":
        folium.TileLayer(
            tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
            attr='Map data: © OpenStreetMap contributors, SRTM | Map style: © OpenTopoMap',
            name='OpenTopoMap',
            overlay=False,
            control=True,
            max_zoom=17
        ).add_to(m)
    elif map_style == "Street Map":
        folium.TileLayer(
            tiles='OpenStreetMap',
            name='Street Map',
            overlay=False,
            control=True
        ).add_to(m)
    elif map_style == "Terrain":
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
            attr='Tiles © Esri',
            name='Esri World Topo',
            overlay=False,
            control=True
        ).add_to(m)
    elif map_style == "Satellite (Esri)":
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Tiles © Esri',
            name='Esri Satellite',
            overlay=False,
            control=True
        ).add_to(m)

    # Add markers
    if show_clusters:
        # Use marker clustering for lots of sensors
        marker_cluster = plugins.MarkerCluster().add_to(m)

        for idx, row in data.iterrows():
            folium.Marker(
                location=[row['Latitude'], row['Longitude']],
                popup=folium.Popup(
                    f"""<b>{row['Sensor']}</b><br>
                    Vacuum: {row['Vacuum']:.1f}"<br>
                    Status: {row['Status']}""",
                    max_width=200
                ),
                tooltip=f"{row['Sensor']}: {row['Vacuum']:.1f}\"",
                icon=folium.Icon(color=get_marker_color(row['Status']), icon='info-sign')
            ).add_to(marker_cluster)
    else:
        # Add individual markers
        for idx, row in data.iterrows():
            folium.CircleMarker(
                location=[row['Latitude'], row['Longitude']],
                radius=8,
                popup=folium.Popup(
                    f"""<b>{row['Sensor']}</b><br>
                    Vacuum: {row['Vacuum']:.1f}"<br>
                    Status: {row['Status']}""",
                    max_width=200
                ),
                tooltip=f"{row['Sensor']}: {row['Vacuum']:.1f}\"",
                color='white',
                fillColor=get_marker_color(row['Status']),
                fillOpacity=0.7,
                weight=2
            ).add_to(m)

    # Add fullscreen button
    plugins.Fullscreen(
        position='topright',
        title='Fullscreen',
        title_cancel='Exit fullscreen',
        force_separate_button=True
    ).add_to(m)

    # Add measure control
    plugins.MeasureControl(position='topleft', primary_length_unit='miles').add_to(m)

    # Add minimap
    minimap = plugins.MiniMap(toggle_display=True)
    m.add_child(minimap)

    # Add layer control if multiple base maps
    folium.LayerControl().add_to(m)

    # Add legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; right: 50px; width: 150px; height: 110px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <p style="margin:0"><b>Vacuum Status</b></p>
    <p style="margin:5px 0"><span style="color:green">●</span> Excellent (≥{:.0f}")</p>
    <p style="margin:5px 0"><span style="color:orange">●</span> Fair ({:.0f}"-{:.0f}")</p>
    <p style="margin:5px 0"><span style="color:red">●</span> Poor (<{:.0f}")</p>
    </div>
    '''.format(config.VACUUM_EXCELLENT, config.VACUUM_FAIR, config.VACUUM_EXCELLENT, config.VACUUM_FAIR)

    m.get_root().html.add_child(folium.Element(legend_html))

    return m


def render(vacuum_df, personnel_df):
    """Render interactive sensor map page with Folium"""

    st.title("🗺️ Interactive Sensor Map")
    st.markdown("*Enhanced mapping with topographic detail*")

    if vacuum_df.empty:
        st.warning("No vacuum data available")
        return

    # Prepare data (cached)
    map_data, filtered_count = prepare_map_data(vacuum_df)

    if map_data is None:
        st.error("Required columns (sensor name, vacuum, latitude, longitude) not found")
        st.info("Available columns: " + ", ".join(vacuum_df.columns))
        return

    if filtered_count > 0:
        st.info(
            f"📊 Showing {len(map_data)} sensors with valid coordinates (filtered out {filtered_count} with missing/invalid coordinates)")

    if map_data.empty:
        st.warning("No sensors with valid coordinates found")
        st.info("""
        **Possible reasons:**
        - Latitude/Longitude columns are empty
        - Coordinates are 0,0 (invalid)
        - Coordinates outside NY state range (40-45°N, -80 to -72°W)

        Check your vacuum data sheet to ensure GPS coordinates are populated.
        """)
        return

    # Controls
    st.subheader("🔧 Map Controls")

    col1, col2, col3 = st.columns(3)

    with col1:
        map_style = st.selectbox(
            "Map Style",
            options=[
                "Topographic (OpenTopoMap)",  # Best option!
                "Terrain",
                "Satellite (Esri)",
                "Street Map"
            ],
            index=0,
            help="OpenTopoMap shows elevation contours and terrain features"
        )

    with col2:
        show_clusters = st.checkbox(
            "🎯 Cluster Markers",
            value=len(map_data) > 100,
            help="Group nearby sensors into clusters. Uncheck to see all individual markers."
        )
        if show_clusters:
            st.caption("✓ Clustering enabled - click clusters to expand")
        else:
            st.caption("⚠️ Showing all markers individually")

    with col3:
        status_filter = st.multiselect(
            "Filter by Status",
            options=["Excellent", "Fair", "Poor"],
            default=["Excellent", "Fair", "Poor"]
        )

    # Apply status filter
    filtered_data = map_data[map_data['Status'].isin(status_filter)].copy()

    st.divider()

    # Summary stats
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Sensors", len(filtered_data))

    with col2:
        excellent = len(filtered_data[filtered_data['Status'] == 'Excellent'])
        st.metric("🟢 Excellent", excellent)

    with col3:
        fair = len(filtered_data[filtered_data['Status'] == 'Fair'])
        st.metric("🟡 Fair", fair)

    with col4:
        poor = len(filtered_data[filtered_data['Status'] == 'Poor'])
        st.metric("🔴 Poor", poor)

    if filtered_data.empty:
        st.warning("No sensors match the current filters")
        return

    st.divider()

    # Create and display map
    st.subheader(f"📍 Sensor Locations ({len(filtered_data)} sensors)")

    # Map creation is actually fast - it's the data processing that's slow
    # Data is already cached by @st.cache_data decorator on prepare_map_data()
    with st.spinner("Rendering map..."):
        folium_map = create_folium_map(filtered_data, map_style, show_clusters)

    # Display map (height=650 for good visibility)
    # Note: st_folium needs a fresh map object each time
    st_folium(folium_map, width=None, height=650)

    # Map features info
    st.info("""
    🧭 **Map Features:**
    - **Pan**: Click and drag
    - **Zoom**: Mouse wheel or +/- buttons
    - **Fullscreen**: Button in top-right
    - **Measure**: Ruler tool in top-left (measure distances)
    - **Minimap**: Small overview map in bottom-left
    - **Marker Info**: Click any marker for details
    - **Layer Control**: Top-right to switch base maps

    🗻 **Topographic Map** (recommended) shows:
    - Elevation contour lines
    - Terrain shading
    - Hills and valleys
    - Forests and land use
    - All roads and paths

    ⚡ **Performance:**
    - Sensor data is cached for 1 hour (fast reloading!)
    - Map tiles cached by your browser
    - First load after data refresh: 3-5 seconds
    - Subsequent loads: Much faster!
    - Uncheck "Cluster Markers" to see all sensors individually
    """)

    st.divider()

    # Data table
    with st.expander("📊 View Sensor Data Table"):
        display = filtered_data.copy()
        display['Vacuum'] = display['Vacuum'].apply(lambda x: f"{x:.1f}\"")
        display = display.sort_values('Status', ascending=False)
        display = display[['Sensor', 'Status', 'Vacuum', 'Latitude', 'Longitude']]

        st.dataframe(display, use_container_width=True, hide_index=True, height=400)

        csv = display.to_csv(index=False)
        st.download_button(
            label="📥 Download Sensor Data as CSV",
            data=csv,
            file_name="sensor_locations.csv",
            mime="text/csv"
        )

    st.divider()

    # Geographic Analysis
    st.subheader("📐 Geographic Analysis")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Vacuum Statistics**")
        st.metric("Average Vacuum", f"{filtered_data['Vacuum'].mean():.1f}\"")
        st.metric("Highest Vacuum", f"{filtered_data['Vacuum'].max():.1f}\"")
        st.metric("Lowest Vacuum", f"{filtered_data['Vacuum'].min():.1f}\"")

    with col2:
        st.markdown("**Geographic Spread**")
        lat_range = filtered_data['Latitude'].max() - filtered_data['Latitude'].min()
        lon_range = filtered_data['Longitude'].max() - filtered_data['Longitude'].min()

        st.metric("Latitude Range", f"{lat_range:.4f}°")
        st.metric("Longitude Range", f"{lon_range:.4f}°")

        center_lat = filtered_data['Latitude'].mean()
        center_lon = filtered_data['Longitude'].mean()
        st.caption(f"**Center:** {center_lat:.6f}, {center_lon:.6f}")

        area_sq_miles = (lat_range * 69) * (lon_range * 53)
        st.metric("Approx. Coverage", f"{area_sq_miles:.1f} sq mi")

    # Problem areas
    poor_sensors = filtered_data[filtered_data['Status'] == 'Poor']

    if not poor_sensors.empty:
        st.divider()
        st.subheader("⚠️ Problem Areas Requiring Attention")

        st.markdown(f"**{len(poor_sensors)} sensors below {config.VACUUM_FAIR}\"**")

        worst = poor_sensors.nsmallest(10, 'Vacuum')
        display_worst = worst[['Sensor', 'Vacuum', 'Latitude', 'Longitude']].copy()
        display_worst['Vacuum'] = display_worst['Vacuum'].apply(lambda x: f"{x:.1f}\"")
        display_worst.insert(0, 'Priority', range(1, len(display_worst) + 1))

        st.dataframe(display_worst, use_container_width=True, hide_index=True)