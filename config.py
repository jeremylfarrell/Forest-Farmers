"""
Dashboard Configuration File
Customize your dashboard settings here - all in one place!
"""

# ============================================================================
# VISUAL SETTINGS - Customize colors, thresholds, and styling
# ============================================================================

# Vacuum thresholds (in inches of mercury)
VACUUM_EXCELLENT = 20.0  # Above this = excellent (green)
VACUUM_FAIR = 15.0       # Between fair and excellent = fair (yellow)
                         # Below fair = poor (red)

# Color scheme
COLORS = {
    'excellent': '#28a745',  # Green
    'fair': '#ffc107',       # Yellow
    'poor': '#dc3545',       # Red
    'primary': '#007bff',    # Blue
    'secondary': '#6c757d',  # Gray
}

# Chart colors for visualizations
CHART_COLORS = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
]

# ============================================================================
# DATA SETTINGS - Configure data loading behavior
# ============================================================================

# Number of days to show by default
DEFAULT_DAYS_TO_SHOW = 7

# How many top/bottom items to show in rankings
TOP_PERFORMERS_COUNT = 10
PROBLEM_AREAS_COUNT = 15

# Minimum hours threshold for employee performance calculation
MIN_HOURS_FOR_RANKING = 5.0

# Auto-refresh interval (seconds) - set to None to disable
AUTO_REFRESH_SECONDS = 300  # 5 minutes

# ============================================================================
# PAGE CONFIGURATION - Customize what appears on each page
# ============================================================================

# Pages to show in the dashboard
PAGES = {
    'overview': {
        'title': '🏠 Overview',
        'enabled': True,
        'icon': '🏠'
    },
    'mainlines': {
        'title': '📍 Mainline Details',
        'enabled': True,
        'icon': '📍'
    },
    'employees': {
        'title': '👥 Employee Performance',
        'enabled': True,
        'icon': '👥'
    },
    'maintenance': {
        'title': '🔧 Maintenance Tracking',
        'enabled': True,
        'icon': '🔧'
    },
    'raw_data': {
        'title': '📊 Raw Data Explorer',
        'enabled': True,
        'icon': '📊'
    }
}

# Metrics to show on overview page (in order)
OVERVIEW_METRICS = [
    'avg_vacuum',
    'active_sensors',
    'problem_areas',
    'employees_today',
    'total_hours_today',
    'repairs_today'
]

# ============================================================================
# GOOGLE SHEETS SETTINGS - Which sheets and how to load them
# ============================================================================

# Sheet URLs (will be loaded from .env file)
# These are just placeholders - actual values come from .env
VACUUM_SHEET_URL = None
PERSONNEL_SHEET_URL = None
CREDENTIALS_FILE = 'credentials.json'

# How to handle missing data
FILL_MISSING_VACUUM = 0.0
FILL_MISSING_HOURS = 0.0

# ============================================================================
# PERFORMANCE CALCULATION SETTINGS
# ============================================================================

# How to calculate employee efficiency score
# Formula: (Vacuum improvement) / (Hours worked) * EFFICIENCY_MULTIPLIER
EFFICIENCY_MULTIPLIER = 10.0

# Weights for overall employee score calculation
EMPLOYEE_SCORE_WEIGHTS = {
    'vacuum_improvement': 0.4,  # 40% weight
    'hours_worked': 0.2,        # 20% weight
    'locations_visited': 0.2,   # 20% weight
    'efficiency': 0.2           # 20% weight
}

# ============================================================================
# DISPLAY SETTINGS
# ============================================================================

# Date format for display
DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = '%Y-%m-%d %H:%M'

# Number of decimal places for metrics
DECIMAL_PLACES = {
    'vacuum': 1,
    'hours': 1,
    'efficiency': 2,
    'improvement': 1
}

# Page layout
PAGE_LAYOUT = 'wide'  # 'wide' or 'centered'
PAGE_ICON = '🍁'
PAGE_TITLE = 'Forest Farmers Vacuum Dashboard'

# ============================================================================
# ALERT THRESHOLDS - When to show warnings/alerts
# ============================================================================

# Alert when vacuum drops below this threshold
CRITICAL_VACUUM_THRESHOLD = 12.0

# Alert when this many sensors are in poor condition
CRITICAL_SENSOR_COUNT = 20

# Alert if no activity detected for this many days
DAYS_WITHOUT_ACTIVITY_ALERT = 3

# ============================================================================
# ADVANCED SETTINGS - For developers
# ============================================================================

# Enable debug mode (shows extra info)
DEBUG_MODE = False

# Cache timeout (seconds) - how long to cache data before reloading
CACHE_TIMEOUT = 300  # 5 minutes

# Maximum number of rows to display in tables
MAX_TABLE_ROWS = 100

# Enable/disable features
FEATURES = {
    'show_trends': True,
    'show_predictions': False,  # Future feature
    'show_weather': False,      # Future feature
    'enable_export': True,
    'show_raw_data': True
}

# ============================================================================
# HELPER FUNCTIONS - Don't modify unless you know what you're doing!
# ============================================================================

def get_vacuum_color(vacuum_value):
    """Return color based on vacuum level"""
    if vacuum_value >= VACUUM_EXCELLENT:
        return COLORS['excellent']
    elif vacuum_value >= VACUUM_FAIR:
        return COLORS['fair']
    else:
        return COLORS['poor']

def get_vacuum_status(vacuum_value):
    """Return status text based on vacuum level"""
    if vacuum_value >= VACUUM_EXCELLENT:
        return "🟢 Excellent"
    elif vacuum_value >= VACUUM_FAIR:
        return "🟡 Fair"
    else:
        return "🔴 Poor"

def get_vacuum_emoji(vacuum_value):
    """Return emoji based on vacuum level"""
    if vacuum_value >= VACUUM_EXCELLENT:
        return "🟢"
    elif vacuum_value >= VACUUM_FAIR:
        return "🟡"
    else:
        return "🔴"
