"""
Utilities Module
Reusable helper functions for the dashboard
"""

from .helpers import (
    find_column,
    filter_recent_sensors,
    safe_divide,
    format_hours,
    format_vacuum,
    format_percentage,
    get_date_range_text,
    create_status_badge,
    show_data_loading_info,
    show_empty_data_message,
    get_vacuum_column,
    get_releaser_column,
    extract_conductor_system
)

from .geographic import (
    haversine_distance,
    find_problem_clusters,
    calculate_cluster_spread,
    get_map_bounds,
    create_cluster_map_data
)

from .ui_components import (
    display_metric_cards,
    display_vacuum_gauge,
    display_trend_chart,
    display_bar_chart,
    display_dataframe_with_filters,
    display_status_table,
    display_ranked_list,
    display_alert_banner,
    display_comparison_chart,
    create_two_column_layout,
    display_summary_statistics,
    display_heatmap
)

from .freeze_thaw import (
    get_current_freeze_thaw_status,
    detect_freeze_event_drops,
    render_freeze_thaw_banner
)

__all__ = [
    # helpers
    'find_column',
    'get_vacuum_column',
    'get_releaser_column',
    'filter_recent_sensors',
    'safe_divide',
    'format_hours',
    'format_vacuum',
    'format_percentage',
    'get_date_range_text',
    'create_status_badge',
    'show_data_loading_info',
    'show_empty_data_message',
    'extract_conductor_system',
    # geographic
    'haversine_distance',
    'find_problem_clusters',
    'calculate_cluster_spread',
    'get_map_bounds',
    'create_cluster_map_data',
    # ui_components
    'display_metric_cards',
    'display_vacuum_gauge',
    'display_trend_chart',
    'display_bar_chart',
    'display_dataframe_with_filters',
    'display_status_table',
    'display_ranked_list',
    'display_alert_banner',
    'display_comparison_chart',
    'create_two_column_layout',
    'display_summary_statistics',
    'display_heatmap',
    # freeze_thaw
    'get_current_freeze_thaw_status',
    'detect_freeze_event_drops',
    'render_freeze_thaw_banner'
]
