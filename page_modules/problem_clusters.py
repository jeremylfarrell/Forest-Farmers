"""
Problem Clusters Page Module
Identifies geographic clusters of poorly performing sensors
"""

import streamlit as st
import pandas as pd
import config
from geo_clustering import find_problem_clusters
from utils import find_column, get_vacuum_column


def render(vacuum_df):
    """Render geographic problem clusters page"""

    st.title("🗺️ Problem Clusters")
    st.markdown("*Identify groups of nearby sensors that are all performing poorly*")

    if vacuum_df.empty:
        st.warning("No vacuum data available")
        return

    # Controls
    col1, col2, col3 = st.columns(3)

    with col1:
        distance_threshold = st.slider(
            "Cluster Distance (meters)",
            min_value=50,
            max_value=500,
            value=100,
            step=50,
            help="Sensors within this distance are considered part of the same cluster"
        )

    with col2:
        min_cluster_size = st.slider(
            "Minimum Cluster Size",
            min_value=2,
            max_value=10,
            value=3,
            help="Minimum number of sensors to form a cluster"
        )

    with col3:
        vacuum_threshold = st.slider(
            "Vacuum Threshold",
            min_value=10.0,
            max_value=20.0,
            value=float(config.VACUUM_FAIR),
            step=0.5,
            help="Sensors below this vacuum level are considered 'poor'"
        )

    st.divider()

    # Find clusters
    with st.spinner("Analyzing geographic clusters..."):
        clusters_df = find_problem_clusters(
            vacuum_df,
            distance_threshold_meters=distance_threshold,
            min_cluster_size=min_cluster_size,
            vacuum_threshold=vacuum_threshold
        )

    # Show info about filtering
    sensor_col = find_column(vacuum_df, 'Name', 'name', 'mainline', 'Sensor Name', 'sensor', 'location')
    vacuum_col = get_vacuum_column(vacuum_df)
    
    if sensor_col and vacuum_col:
        total_sensors = vacuum_df[sensor_col].nunique()
        problem_sensors = len(vacuum_df[vacuum_df[vacuum_col] < vacuum_threshold][sensor_col].unique())
        
        st.info(f"Found {problem_sensors} sensors below {vacuum_threshold}\" out of {total_sensors} total sensors")

    # Display results
    if clusters_df.empty:
        st.success("🎉 No problem clusters found!")
        st.info(f"""
        This means either:
        - There are no sensors performing poorly (below {vacuum_threshold}\")
        - Poor sensors are not clustered together geographically
        - No clusters meet the minimum size of {min_cluster_size} sensors

        Try adjusting the filters above to see different results.
        """)
        return

    st.subheader(f"Found {len(clusters_df)} Problem Cluster(s)")

    # Summary table
    summary = clusters_df[['cluster_id', 'sensor_count', 'avg_vacuum', 'min_vacuum', 'max_vacuum']].copy()
    summary['avg_vacuum'] = summary['avg_vacuum'].apply(lambda x: f"{x:.1f}\"")
    summary['min_vacuum'] = summary['min_vacuum'].apply(lambda x: f"{x:.1f}\"")
    summary['max_vacuum'] = summary['max_vacuum'].apply(lambda x: f"{x:.1f}\"")
    summary.columns = ['Cluster', 'Sensors', 'Avg Vacuum', 'Min Vacuum', 'Max Vacuum']

    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.divider()

    # Detailed view for each cluster
    st.subheader("Cluster Details")

    for idx, cluster_data in clusters_df.iterrows():
        with st.expander(f"🔴 Cluster {cluster_data['cluster_id']} - {cluster_data['sensor_count']} sensors"):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Average Vacuum", f"{cluster_data['avg_vacuum']:.1f}\"")

            with col2:
                st.metric("Sensors in Cluster", cluster_data['sensor_count'])

            with col3:
                st.metric("Vacuum Range", 
                         f"{cluster_data['min_vacuum']:.1f}\" - {cluster_data['max_vacuum']:.1f}\"")

            st.subheader("Sensors in This Cluster:")

            # Show individual sensors
            sensor_details = []
            for sensor_data in cluster_data['sensor_details']:
                sensor_details.append({
                    'Sensor': sensor_data['sensor'],
                    'Vacuum': f"{sensor_data['vacuum']:.1f}\"",
                    'Latitude': f"{sensor_data['lat']:.6f}",
                    'Longitude': f"{sensor_data['lon']:.6f}"
                })

            sensor_df = pd.DataFrame(sensor_details)
            st.dataframe(sensor_df, use_container_width=True, hide_index=True)

            st.info(f"""
            **Recommended Action:**
            This cluster has {cluster_data['sensor_count']} sensors averaging {cluster_data['avg_vacuum']:.1f}\" vacuum.
            Send a maintenance crew to this geographic area to:
            - Check for leaks in the mainline
            - Inspect releaser functionality
            - Look for damaged tubing
            - Check for obstructions

            All sensors are within {distance_threshold}m of each other, suggesting a localized problem.
            """)
