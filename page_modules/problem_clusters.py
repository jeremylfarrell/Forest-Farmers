"""
Problem Clusters Page Module - MULTI-SITE ENHANCED
Identifies geographic clusters of poorly performing sensors with site awareness
"""

import streamlit as st
import pandas as pd
import config
from geo_clustering import find_problem_clusters
from utils import find_column, get_vacuum_column


def render(vacuum_df):
    """Render geographic problem clusters page with site information"""

    st.title("🗺️ Problem Clusters")
    st.markdown("*Identify groups of nearby sensors that are all performing poorly*")

    if vacuum_df.empty:
        st.warning("No vacuum data available")
        return

    # Check if we have site information
    has_site = 'Site' in vacuum_df.columns

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
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Sensors", f"{total_sensors:,}")
        
        with col2:
            st.metric("Problem Sensors", f"{problem_sensors}",
                     delta=f"Below {vacuum_threshold}\"")
        
        with col3:
            if not clusters_df.empty:
                st.metric("Clusters Found", len(clusters_df))
            else:
                st.metric("Clusters Found", "0")
        
        # Show site breakdown if available
        if has_site:
            st.markdown("**Problem Sensors by Site:**")
            problem_data = vacuum_df[vacuum_df[vacuum_col] < vacuum_threshold]
            site_problems = problem_data.groupby('Site')[sensor_col].nunique().reset_index()
            site_problems.columns = ['Site', 'Problem_Count']
            
            cols = st.columns(len(site_problems))
            for idx, row in site_problems.iterrows():
                with cols[idx]:
                    emoji = "🟦" if row['Site'] == "NY" else "🟩" if row['Site'] == "VT" else "⚫"
                    st.metric(f"{emoji} {row['Site']}", f"{row['Problem_Count']} sensors")

    st.divider()

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

    # Add site information to clusters if available
    if has_site:
        # Determine site for each cluster based on its sensors
        for idx, cluster in clusters_df.iterrows():
            sites_in_cluster = set()
            for sensor_info in cluster['sensor_details']:
                sensor_name = sensor_info['sensor']
                # Find site for this sensor
                sensor_site = vacuum_df[vacuum_df[sensor_col] == sensor_name]['Site'].iloc[0] if sensor_col in vacuum_df.columns else 'UNK'
                sites_in_cluster.add(sensor_site)
            
            clusters_df.at[idx, 'sites'] = ', '.join(sorted(sites_in_cluster))
            # Primary site is the most common one
            site_list = [sensor_site for sensor_info in cluster['sensor_details'] 
                        for sensor_site in [vacuum_df[vacuum_df[sensor_col] == sensor_info['sensor']]['Site'].iloc[0] if sensor_col in vacuum_df.columns else 'UNK']]
            if site_list:
                clusters_df.at[idx, 'primary_site'] = max(set(site_list), key=site_list.count)

    # Summary table
    summary = clusters_df[['cluster_id', 'sensor_count', 'avg_vacuum', 'min_vacuum', 'max_vacuum']].copy()
    
    if has_site and 'primary_site' in clusters_df.columns:
        # Add site emoji
        clusters_df['site_display'] = clusters_df['primary_site'].apply(
            lambda x: f"🟦 {x}" if x == 'NY' else f"🟩 {x}" if x == 'VT' else f"⚫ {x}"
        )
        summary.insert(1, 'Site', clusters_df['site_display'])
    
    summary['avg_vacuum'] = summary['avg_vacuum'].apply(lambda x: f"{x:.1f}\"")
    summary['min_vacuum'] = summary['min_vacuum'].apply(lambda x: f"{x:.1f}\"")
    summary['max_vacuum'] = summary['max_vacuum'].apply(lambda x: f"{x:.1f}\"")
    
    if has_site:
        summary.columns = ['Cluster', 'Site', 'Sensors', 'Avg Vacuum', 'Min Vacuum', 'Max Vacuum']
    else:
        summary.columns = ['Cluster', 'Sensors', 'Avg Vacuum', 'Min Vacuum', 'Max Vacuum']

    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.divider()

    # Detailed view for each cluster
    st.subheader("Cluster Details")

    for idx, cluster_data in clusters_df.iterrows():
        # Build expander title with site
        cluster_title = f"Cluster {cluster_data['cluster_id']} - {cluster_data['sensor_count']} sensors"
        if has_site and 'site_display' in cluster_data:
            cluster_title = f"{cluster_data['site_display']} " + cluster_title
        
        with st.expander(f"🔴 {cluster_title}"):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Average Vacuum", f"{cluster_data['avg_vacuum']:.1f}\"")

            with col2:
                st.metric("Sensors in Cluster", cluster_data['sensor_count'])

            with col3:
                st.metric("Vacuum Range", 
                         f"{cluster_data['min_vacuum']:.1f}\" - {cluster_data['max_vacuum']:.1f}\"")
            
            # Show site info if available
            if has_site and 'sites' in cluster_data:
                if ',' in cluster_data['sites']:
                    st.warning(f"⚠️ **Multi-Site Cluster**: This cluster spans multiple sites: {cluster_data['sites']}")
                    st.caption("This may indicate a shared mainline or infrastructure issue")
                else:
                    emoji = "🟦" if cluster_data['primary_site'] == "NY" else "🟩" if cluster_data['primary_site'] == "VT" else "⚫"
                    st.info(f"{emoji} **Site:** {cluster_data['primary_site']}")

            st.subheader("Sensors in This Cluster:")

            # Show individual sensors with site if available
            sensor_details = []
            for sensor_data in cluster_data['sensor_details']:
                sensor_info = {
                    'Sensor': sensor_data['sensor'],
                    'Vacuum': f"{sensor_data['vacuum']:.1f}\"",
                    'Latitude': f"{sensor_data['lat']:.6f}",
                    'Longitude': f"{sensor_data['lon']:.6f}"
                }
                
                # Add site if available
                if has_site:
                    sensor_site = vacuum_df[vacuum_df[sensor_col] == sensor_data['sensor']]['Site'].iloc[0] if sensor_col in vacuum_df.columns else 'UNK'
                    emoji = "🟦" if sensor_site == "NY" else "🟩" if sensor_site == "VT" else "⚫"
                    sensor_info['Site'] = f"{emoji} {sensor_site}"
                
                sensor_details.append(sensor_info)

            sensor_df = pd.DataFrame(sensor_details)
            
            # Reorder columns to put Site first if it exists
            if 'Site' in sensor_df.columns:
                cols = ['Site', 'Sensor', 'Vacuum', 'Latitude', 'Longitude']
                sensor_df = sensor_df[cols]
            
            st.dataframe(sensor_df, use_container_width=True, hide_index=True)

            # Recommendations with site context
            st.info(f"""
            **Recommended Action:**
            This cluster has {cluster_data['sensor_count']} sensors averaging {cluster_data['avg_vacuum']:.1f}\" vacuum.
            
            {'**Site:** ' + cluster_data['site_display'] if has_site and 'site_display' in cluster_data else ''}
            
            Send a maintenance crew to this geographic area to:
            - Check for leaks in the mainline
            - Inspect releaser functionality
            - Look for damaged tubing
            - Check for obstructions

            All sensors are within {distance_threshold}m of each other, suggesting a localized problem.
            {"Consider coordinating with the " + cluster_data['primary_site'] + " site manager." if has_site and 'primary_site' in cluster_data else ""}
            """)

    st.divider()

    # Additional insights if multi-site
    if has_site and 'primary_site' in clusters_df.columns:
        st.subheader("📊 Cluster Distribution by Site")
        
        site_cluster_counts = clusters_df['primary_site'].value_counts().reset_index()
        site_cluster_counts.columns = ['Site', 'Clusters']
        
        cols = st.columns(len(site_cluster_counts))
        for idx, row in site_cluster_counts.iterrows():
            with cols[idx]:
                emoji = "🟦" if row['Site'] == "NY" else "🟩" if row['Site'] == "VT" else "⚫"
                st.metric(f"{emoji} {row['Site']}", f"{row['Clusters']} clusters")
        
        st.caption("💡 If one site has significantly more clusters, it may indicate site-wide issues or different terrain challenges")

    st.divider()

    # Tips with multi-site context
    with st.expander("💡 Understanding Problem Clusters"):
        st.markdown("""
        **What is a Problem Cluster?**
        
        A group of nearby sensors that are all performing poorly (below the vacuum threshold).
        This suggests a localized problem affecting that geographic area.
        
        **Why Clusters Matter:**
        
        - **Efficient Dispatch**: Send crew to one area instead of scattered locations
        - **Root Cause**: Indicates shared infrastructure problems
        - **Priority**: Multiple affected sensors = higher impact
        - **Site Context**: Know which site team to dispatch
        
        **Common Causes:**
        
        - **Mainline Leak**: Affects all downstream sensors
        - **Releaser Malfunction**: Impacts entire branch
        - **Shared Infrastructure**: Pump, lines, or connections
        - **Environmental**: Damage from weather, animals, etc.
        
        **Multi-Site Features:**
        
        - **Site Identification**: See which site each cluster is in
        - **Cross-Site Clusters**: Rare but indicates shared infrastructure
        - **Site Distribution**: Compare problem areas between sites
        - **Dispatch Planning**: Route crews to correct site
        
        **Using the Controls:**
        
        - **Distance**: Smaller = tighter clusters, Larger = broader areas
        - **Min Size**: Higher = only significant groups, Lower = catch small issues
        - **Threshold**: Lower = catch all problems, Higher = only critical
        
        **Best Practices:**
        
        1. **Review Daily**: Check for new clusters each morning
        2. **Site Assignment**: Dispatch appropriate site crew
        3. **Track Progress**: Revisit after maintenance to verify fixes
        4. **Share Learnings**: If one site solves a cluster type, share the solution
        5. **Seasonal Patterns**: Some cluster locations may be recurring
        
        **Site-Specific Considerations:**
        
        - Different terrain at each site may affect cluster patterns
        - NY and VT may have different infrastructure ages
        - Weather conditions may vary between sites
        - Crew familiarity with site-specific challenges
        """)
