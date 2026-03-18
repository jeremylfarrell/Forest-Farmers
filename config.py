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

# Tapping targets by site
TAP_TARGETS = {"NY": 102000, "VT": 49000}

# Site coordinates for weather lookups
SITE_COORDINATES = {
    'NY': {'lat': 44.8939, 'lon': -73.8365, 'name': 'Ellenburg, NY'},
    'VT': {'lat': 44.3509, 'lon': -72.3540, 'name': 'Marshfield, VT'},
}

# Temperature ranges for productivity analysis (label, min_temp, max_temp in °F)
TEMP_RANGES = [
    ('Below 10°F', None, 10),
    ('10–20°F', 10, 20),
    ('20–32°F', 20, 32),
    ('Above 32°F', 32, None),
]

# Overtime threshold (hours per week)
OVERTIME_THRESHOLD = 52

# Tap history variance threshold (%) — flag mainlines with year-over-year change exceeding this
VARIANCE_THRESHOLD = 20

# Auto-refresh interval (seconds) - set to None to disable
AUTO_REFRESH_SECONDS = 300  # 5 minutes

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

# Freeze/thaw detection thresholds
FREEZING_POINT = 32.0              # Temperature threshold (Fahrenheit)
FREEZE_DROP_THRESHOLD = 2.0        # Vacuum drop (inches) during freeze to flag sensor
FREEZE_DROP_RATE_LIKELY = 0.50     # Drop rate > 50% = "LIKELY LEAK"
FREEZE_DROP_RATE_WATCH = 0.25      # Drop rate > 25% = "WATCH"

# Releaser differential color thresholds (inches)
# Uses absolute value of releaser diff for the scale.
# Data values are SIGNED: negative = normal loss, positive > 1 = sensor error.
# Rules (from manager meeting 2025-03-17):
#   abs(diff) < 2   → Good (green)
#   abs(diff) 2-5   → Low Priority (amber)
#   abs(diff) 5-10  → Critical (pink)
#   abs(diff) ≥ 10  → FROZEN (dark red)
#   positive > 1    → False Positive (sensor error) — clamped to 1 for display
#   vacuum ≈ 0 AND abs(diff) ≤ 1 → Pump OFF
RELEASER_DIFF_THRESHOLDS = [
    (2.0,  '#228B22', 'Good'),         # abs 0-2"  — green
    (5.0,  '#DAA520', 'Low Priority'), # abs 2-5"  — amber
    (10.0, '#FF69B4', 'Critical'),     # abs 5-10" — pink
    (99.0, '#8B0000', 'FROZEN'),       # abs ≥ 10" — dark red (line frozen)
]
RELEASER_FROZEN_COLOR = '#8B0000'     # Dark red — frozen line
RELEASER_OFF_COLOR = '#808080'        # Gray — pump off (vacuum=0 AND diff≈0)
RELEASER_FALSE_POS_COLOR = '#4682B4'  # Steel blue — sensor error (positive > 1)

# Stale sensor threshold: sensors not reporting within this many hours are
# separated into a "not reporting" list and excluded from main analysis.
STALE_SENSOR_HOURS = 24

# ============================================================================
# ADVANCED SETTINGS - For developers
# ============================================================================

# Enable debug mode (shows extra info)
DEBUG_MODE = False

# Cache timeout (seconds) - how long to cache data before reloading
CACHE_TIMEOUT = 3600  # 1 hour (matches @st.cache_data ttl in data_loader.py)

# Maximum number of rows to display in tables
MAX_TABLE_ROWS = 100

# Enable/disable features
FEATURES = {
    'show_trends': True,
    'show_predictions': False,  # Future feature
    'show_weather': True,       # Enabled for freeze/thaw analysis
    'enable_export': True,
    'show_raw_data': True,
    'show_freeze_analysis': True,  # Freeze/thaw leak detection
}

# ============================================================================
# SUGARBUSH & CONDUCTOR SYSTEM MAPPING
# ============================================================================

# Sensors with these prefixes should be EXCLUDED from analysis
# (birch lines, relays, typos, or other non-maple sensors)
EXCLUDED_SENSOR_PREFIXES = {'AB', 'BFB', 'BMMD', 'ZGAS', 'ZGAN', 'GDS'}

# Sugarbush → conductor system mapping
# Each sugarbush is a named location containing one or more conductor systems.
# A conductor system is identified by the letter prefix of the sensor name.
SUGARBUSH_MAP = {
    'Drew Mt': ['DMA', 'DMAS', 'DMB', 'DMC', 'DMD'],  # DM* sensors
    'Groton':  ['GA', 'GB', 'GC', 'GD'],             # G* sensors (GC includes GCE, GCW)
    'Devils East': ['DHE'],
    'Devils West': ['DHW'],
    'Lords':   ['LHW', 'LHE', 'LH'],
    'Matthews': ['M', 'MD'],
    'Ducharme': ['DU'],
}

# Reverse lookup: conductor prefix → sugarbush name
CONDUCTOR_TO_SUGARBUSH = {}
for _bush, _conductors in SUGARBUSH_MAP.items():
    for _cond in _conductors:
        CONDUCTOR_TO_SUGARBUSH[_cond] = _bush


def get_sugarbush(conductor_prefix):
    """
    Return the sugarbush name for a conductor system prefix.
    Uses longest-prefix match so 'DMA' matches before 'DM'.
    Falls back to 'Other' if no match.
    """
    if not conductor_prefix:
        return 'Other'
    # Try exact match first, then decreasing prefix length
    for length in range(len(conductor_prefix), 0, -1):
        prefix = conductor_prefix[:length].upper()
        if prefix in CONDUCTOR_TO_SUGARBUSH:
            return CONDUCTOR_TO_SUGARBUSH[prefix]
    return 'Other'


def is_excluded_sensor(sensor_name):
    """Check if a sensor name starts with an excluded prefix."""
    if not sensor_name:
        return True
    name = str(sensor_name).strip().upper()
    for prefix in EXCLUDED_SENSOR_PREFIXES:
        if name.startswith(prefix):
            return True
    return False


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


def get_releaser_diff_color(vacuum, releaser_diff):
    """
    Return (hex_color, label) for a sensor based on vacuum and releaser
    differential, using the graduated color scale.

    The releaser differential is SIGNED:
      - Negative values = normal (sensor reads less vacuum than releaser)
      - More negative = worse (bigger vacuum loss in the line)
      - Positive > 1 = sensor error / false reading

    Rules (from manager meeting 2025-03-17):
    - vacuum ≈ 0 AND abs(diff) ≤ 1 → gray (pump OFF)
    - vacuum ≈ 0 AND abs(diff) > 1  → dark red (FROZEN — pump on but line frozen)
    - positive diff > 1              → steel blue (False Positive — sensor error)
    - abs(diff) < 2                  → green (Good)
    - abs(diff) 2–5                  → amber (Low Priority)
    - abs(diff) 5–10                 → pink (Critical)
    - abs(diff) ≥ 10                 → dark red (FROZEN)
    """
    import math
    if vacuum is None or releaser_diff is None:
        return (RELEASER_OFF_COLOR, 'No Data')
    if (isinstance(vacuum, float) and math.isnan(vacuum)) or \
       (isinstance(releaser_diff, float) and math.isnan(releaser_diff)):
        return (RELEASER_OFF_COLOR, 'No Data')

    # Pump off: vacuum ≈ 0 AND releaser diff ≈ 0
    if vacuum <= 0.01 and abs(releaser_diff) <= 1.0:
        return (RELEASER_OFF_COLOR, 'OFF')

    # Vacuum is zero but releaser diff is significant → line is frozen
    if vacuum <= 0.01 and abs(releaser_diff) > 1.0:
        return (RELEASER_FROZEN_COLOR, 'FROZEN')

    # Positive diff > 1 = sensor error / false reading
    if releaser_diff > 1.0:
        return (RELEASER_FALSE_POS_COLOR, 'False Positive')

    # Graduated scale by absolute value of releaser differential
    abs_diff = abs(releaser_diff)
    for threshold, color, label in RELEASER_DIFF_THRESHOLDS:
        if abs_diff < threshold:
            return (color, label)

    # Fallback (abs_diff ≥ 99 — should not happen)
    return (RELEASER_FROZEN_COLOR, 'FROZEN')
