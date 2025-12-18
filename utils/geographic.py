"""
Geographic Utilities Module
Functions for geographic clustering and distance calculations
"""

import pandas as pd
import numpy as np
from math import radians, cos, sin, asin, sqrt
from sklearn.cluster import DBSCAN
import streamlit as st

from utils.helpers import find_column


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    
    Args:
        lat1, lon1: Coordinates of first point
        lat2, lon2: Coordinates of second point
        
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


def find_problem_clusters(vacuum_df, distance_threshold=500, min_sensors=2, vacuum_threshold=15.0):
    """
    Find geographic clusters of sensors with poor vacuum
    
    Args:
        vacuum_df: Vacuum data DataFrame with lat/lon and vacuum readings
        distance_threshold: Maximum distance (meters) between sensors in a cluster
        min_sensors: Minimum number of sensors to form a cluster
        vacuum_threshold: Vacuum level below which is considered "poor"
        
    Returns:
        List of dictionaries, each containing cluster information
    """
    if vacuum_df.empty:
        return []
    
    # Find necessary columns
    sensor_col = find_column(vacuum_df, 'Sensor Name', 'sensor', 'mainline', 'location', 'name')
    vacuum_col = find_column(vacuum_df, 'Vacuum Reading', 'vacuum', 'reading')
    lat_col = find_column(vacuum_df, 'Latitude', 'lat', 'latitude')
    lon_col = find_column(vacuum_df, 'Longitude', 'lon', 'longitude', 'long')
    
    if not all([sensor_col, vacuum_col, lat_col, lon_col]):
        return []
    
    # Calculate average vacuum per sensor
    sensor_avg = vacuum_df.groupby(sensor_col).agg({
        vacuum_col: 'mean',
        lat_col: 'first',
        lon_col: 'first'
    }).reset_index()
    
    sensor_avg.columns = ['sensor', 'avg_vacuum', 'lat', 'lon']
    
    # Filter to problem sensors only
    problem_sensors = sensor_avg[sensor_avg['avg_vacuum'] < vacuum_threshold].copy()
    
    if len(problem_sensors) < min_sensors:
        return []
    
    # Prepare coordinates for clustering
    coords = problem_sensors[['lat', 'lon']].values
    
    # Convert distance threshold to radians for DBSCAN
    # Earth radius in meters
    earth_radius = 6371000
    eps_radians = distance_threshold / earth_radius
    
    # Perform DBSCAN clustering
    clustering = DBSCAN(
        eps=eps_radians,
        min_samples=min_sensors,
        metric='haversine'
    ).fit(np.radians(coords))
    
    problem_sensors['cluster'] = clustering.labels_
    
    # Extract cluster information (ignore noise points, labeled as -1)
    clusters = []
    for cluster_id in problem_sensors['cluster'].unique():
        if cluster_id == -1:  # Skip noise points
            continue
        
        cluster_data = problem_sensors[problem_sensors['cluster'] == cluster_id]
        
        # Calculate cluster statistics
        cluster_info = {
            'cluster_id': cluster_id,
            'sensor_count': len(cluster_data),
            'avg_vacuum': cluster_data['avg_vacuum'].mean(),
            'min_vacuum': cluster_data['avg_vacuum'].min(),
            'max_vacuum': cluster_data['avg_vacuum'].max(),
            'center_lat': cluster_data['lat'].mean(),
            'center_lon': cluster_data['lon'].mean(),
            'sensor_details': cluster_data[['sensor', 'avg_vacuum', 'lat', 'lon']].to_dict('records')
        }
        
        clusters.append(cluster_info)
    
    # Sort clusters by severity (lowest average vacuum first)
    clusters.sort(key=lambda x: x['avg_vacuum'])
    
    return clusters


def calculate_cluster_spread(cluster_sensors):
    """
    Calculate the maximum distance between any two sensors in a cluster
    
    Args:
        cluster_sensors: List of sensor dictionaries with 'lat' and 'lon' keys
        
    Returns:
        Maximum distance in meters
    """
    if len(cluster_sensors) < 2:
        return 0
    
    max_distance = 0
    
    for i in range(len(cluster_sensors)):
        for j in range(i + 1, len(cluster_sensors)):
            distance = haversine_distance(
                cluster_sensors[i]['lat'],
                cluster_sensors[i]['lon'],
                cluster_sensors[j]['lat'],
                cluster_sensors[j]['lon']
            )
            max_distance = max(max_distance, distance)
    
    return max_distance


def get_map_bounds(sensors):
    """
    Calculate appropriate map bounds for a list of sensors
    
    Args:
        sensors: List of sensor dictionaries with 'lat' and 'lon' keys
        
    Returns:
        Dictionary with 'min_lat', 'max_lat', 'min_lon', 'max_lon'
    """
    if not sensors:
        return None
    
    lats = [s['lat'] for s in sensors]
    lons = [s['lon'] for s in sensors]
    
    # Add some padding (about 10%)
    lat_range = max(lats) - min(lats)
    lon_range = max(lons) - min(lons)
    padding_lat = lat_range * 0.1 if lat_range > 0 else 0.01
    padding_lon = lon_range * 0.1 if lon_range > 0 else 0.01
    
    return {
        'min_lat': min(lats) - padding_lat,
        'max_lat': max(lats) + padding_lat,
        'min_lon': min(lons) - padding_lon,
        'max_lon': max(lons) + padding_lon
    }


def create_cluster_map_data(clusters):
    """
    Prepare data for map visualization of clusters
    
    Args:
        clusters: List of cluster dictionaries from find_problem_clusters
        
    Returns:
        DataFrame suitable for mapping with pydeck or similar
    """
    if not clusters:
        return pd.DataFrame()
    
    map_data = []
    
    for cluster in clusters:
        for sensor in cluster['sensor_details']:
            map_data.append({
                'lat': sensor['lat'],
                'lon': sensor['lon'],
                'sensor': sensor['sensor'],
                'vacuum': sensor['vacuum'],
                'cluster_id': cluster['cluster_id'],
                'cluster_size': cluster['sensor_count']
            })
    
    return pd.DataFrame(map_data)
