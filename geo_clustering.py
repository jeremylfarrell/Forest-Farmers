"""
Geographic Clustering Module
Functions for analyzing geographic patterns in vacuum sensor data
"""

import pandas as pd
import numpy as np
from math import radians, cos, sin, asin, sqrt
import config
from utils import find_column, get_vacuum_column


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    
    Args:
        lat1, lon1: Latitude and longitude of first point
        lat2, lon2: Latitude and longitude of second point
        
    Returns:
        Distance in meters
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))

    # Radius of earth in meters
    r = 6371000

    return c * r


def find_problem_clusters(vacuum_df, distance_threshold_meters=100, min_cluster_size=3, vacuum_threshold=None):
    """
    Find clusters of nearby sensors that are all performing poorly
    
    This function identifies geographic clusters of sensors that are:
    1. Close together (within distance_threshold_meters)
    2. All reading below the vacuum_threshold
    3. Form a group of at least min_cluster_size sensors
    
    Args:
        vacuum_df: DataFrame with vacuum sensor data
        distance_threshold_meters: How close sensors must be to be in same cluster (default 100m)
        min_cluster_size: Minimum number of sensors to be considered a cluster (default 3)
        vacuum_threshold: Vacuum level below which sensor is "poor" (default config.VACUUM_FAIR)
        
    Returns:
        DataFrame with cluster information, or empty DataFrame if no clusters found
        
    Cluster DataFrame columns:
        - cluster_id: Unique identifier for the cluster
        - sensor_count: Number of sensors in cluster
        - sensors: List of sensor names
        - avg_vacuum: Average vacuum reading across cluster
        - min_vacuum: Lowest vacuum reading in cluster
        - max_vacuum: Highest vacuum reading in cluster
        - center_lat: Geographic center latitude
        - center_lon: Geographic center longitude
        - sensor_details: List of detailed sensor information
    """
    if vacuum_df.empty:
        return pd.DataFrame()

    if vacuum_threshold is None:
        vacuum_threshold = config.VACUUM_FAIR

    # Find required columns
    sensor_col = find_column(
        vacuum_df, 
        'Name', 'name', 'mainline', 'Sensor Name', 'sensor', 'location', 'mainline.'
    )
    vacuum_col = get_vacuum_column(vacuum_df)
    lat_col = find_column(vacuum_df, 'Latitude', 'latitude', 'lat')
    lon_col = find_column(vacuum_df, 'Longitude', 'longitude', 'lon', 'long')
    timestamp_col = find_column(
        vacuum_df, 
        'Last communication', 'Last Communication', 'Timestamp', 'timestamp'
    )

    if not all([sensor_col, vacuum_col, lat_col, lon_col]):
        return pd.DataFrame()

    # Get latest reading per sensor
    if timestamp_col:
        latest = vacuum_df.sort_values(timestamp_col, ascending=False).groupby(sensor_col).first().reset_index()
    else:
        latest = vacuum_df.groupby(sensor_col).first().reset_index()

    # Filter to problem sensors only
    problem_sensors = latest[latest[vacuum_col] < vacuum_threshold].copy()

    if len(problem_sensors) < min_cluster_size:
        return pd.DataFrame()

    # Convert to numeric and rename for easier access
    problem_sensors['lat'] = pd.to_numeric(problem_sensors[lat_col], errors='coerce')
    problem_sensors['lon'] = pd.to_numeric(problem_sensors[lon_col], errors='coerce')
    problem_sensors['vacuum'] = pd.to_numeric(problem_sensors[vacuum_col], errors='coerce')
    problem_sensors['sensor'] = problem_sensors[sensor_col]

    # Drop sensors without valid coordinates
    problem_sensors = problem_sensors.dropna(subset=['lat', 'lon', 'vacuum'])

    # Filter out invalid coordinates (0,0 or outside reasonable range)
    # Reasonable range for New York State: lat 40-45, lon -80 to -72
    problem_sensors = problem_sensors[
        (problem_sensors['lat'] != 0) &
        (problem_sensors['lon'] != 0) &
        (problem_sensors['lat'].between(40, 45)) &
        (problem_sensors['lon'].between(-80, -72))
    ]

    if len(problem_sensors) < min_cluster_size:
        return pd.DataFrame()

    # Simple clustering: find groups of sensors within distance threshold
    clusters = []
    used_indices = set()

    for idx, sensor in problem_sensors.iterrows():
        if idx in used_indices:
            continue

        # Start a new cluster
        cluster = [idx]
        cluster_sensors = [sensor]

        # Find all nearby sensors
        for idx2, sensor2 in problem_sensors.iterrows():
            if idx2 in used_indices or idx2 == idx:
                continue

            # Calculate distance
            dist = haversine_distance(
                sensor['lat'], sensor['lon'],
                sensor2['lat'], sensor2['lon']
            )

            if dist <= distance_threshold_meters:
                cluster.append(idx2)
                cluster_sensors.append(sensor2)
                used_indices.add(idx2)

        # If cluster is big enough, save it
        if len(cluster) >= min_cluster_size:
            used_indices.update(cluster)

            cluster_data = {
                'cluster_id': len(clusters) + 1,
                'sensor_count': len(cluster),
                'sensors': [s['sensor'] for s in cluster_sensors],
                'avg_vacuum': np.mean([s['vacuum'] for s in cluster_sensors]),
                'min_vacuum': np.min([s['vacuum'] for s in cluster_sensors]),
                'max_vacuum': np.max([s['vacuum'] for s in cluster_sensors]),
                'center_lat': np.mean([s['lat'] for s in cluster_sensors]),
                'center_lon': np.mean([s['lon'] for s in cluster_sensors]),
                'sensor_details': cluster_sensors
            }
            clusters.append(cluster_data)

    if clusters:
        return pd.DataFrame(clusters)
    else:
        return pd.DataFrame()
