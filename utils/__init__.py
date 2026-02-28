"""
Utilities Module
Reusable helper functions for the dashboard
"""

from .helpers import (
    find_column,
    filter_recent_sensors,
    format_hours,
    format_vacuum,
    format_percentage,
    get_vacuum_column,
    get_releaser_column,
    extract_conductor_system,
    is_tapping_job,
    calculate_sap_flow_likelihood
)

from .geographic import (
    haversine_distance,
    find_problem_clusters,
    calculate_cluster_spread,
    get_map_bounds,
    create_cluster_map_data
)

from .freeze_thaw import (
    get_current_freeze_thaw_status,
    detect_freeze_event_drops,
    render_freeze_thaw_banner,
    add_freeze_bands_to_figure
)

from .weather_api import (
    get_temperature_data,
    get_hourly_temperature
)

__all__ = [
    # helpers
    'find_column',
    'get_vacuum_column',
    'get_releaser_column',
    'filter_recent_sensors',
    'format_hours',
    'format_vacuum',
    'format_percentage',
    'extract_conductor_system',
    'is_tapping_job',
    'calculate_sap_flow_likelihood',
    # geographic
    'haversine_distance',
    'find_problem_clusters',
    'calculate_cluster_spread',
    'get_map_bounds',
    'create_cluster_map_data',
    # freeze_thaw
    'get_current_freeze_thaw_status',
    'detect_freeze_event_drops',
    'render_freeze_thaw_banner',
    'add_freeze_bands_to_figure',
    # weather_api
    'get_temperature_data',
    'get_hourly_temperature',
]
