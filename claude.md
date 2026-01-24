# Forest Farmers Dashboard - Claude Development Guide

## Project Overview

This is a **Streamlit-based web dashboard application** for monitoring and managing maple syrup production operations at Forest Farmers. It's a multi-site operational analytics platform that tracks vacuum pressure systems, employee productivity, tapping operations, and maintenance activities across geographically distributed locations (NY and VT).

## Technology Stack

- **Framework**: Streamlit (Python web framework)
- **Language**: Python 3.11
- **Data Processing**: pandas, numpy, scipy
- **Visualization**: plotly, folium (maps), streamlit-folium
- **Data Source**: Google Sheets integration (gspread, google-auth)
- **Geospatial**: scikit-learn (clustering), folium (mapping)

## Project Structure

```
/
├── dashboard.py              # Main application entry point (465 lines)
├── config.py                 # Configuration settings (205 lines)
├── data_loader.py            # Google Sheets data loading (519 lines)
├── styling.py                # Custom CSS styling (385 lines)
├── metrics.py                # Metric calculations (595 lines)
├── geo_clustering.py         # Geographic clustering (172 lines)
├── utils.py                  # Utility functions (122 lines)
│
├── page_modules/             # Dashboard pages (13 pages, 5,885 lines total)
│   ├── overview.py           # System overview & key metrics
│   ├── vacuum.py             # Vacuum pressure monitoring
│   ├── sensor_map.py         # Interactive geographic map
│   ├── tapping.py            # Tapping productivity tracking
│   ├── employees.py          # Employee performance metrics
│   ├── employee_effectiveness.py  # Detailed effectiveness analysis
│   ├── maintenance.py        # Maintenance tracking & leak detection
│   ├── repairs_analysis.py   # Parsing unstructured repair notes
│   ├── data_quality.py       # Data quality alerts
│   ├── sap_forecast.py       # SAP production forecasting
│   ├── raw_data.py           # Raw data explorer
│   ├── daily_summary.py      # Daily summary reports
│   └── problem_clusters.py   # Geographic problem clustering
│
└── utils/                    # Utility modules (824 lines total)
    ├── helpers.py            # General helper functions
    ├── ui_components.py      # Reusable UI components
    ├── geographic.py         # Geographic calculations
    └── __init__.py
```

## Key Features

### Monitoring & Analytics
- **Overview Dashboard**: System-wide metrics (avg vacuum, active sensors, problem areas, employees, hours)
- **Vacuum System**: Monitor vacuum pressure readings per sensor with status indicators (Excellent/Fair/Poor)
- **Sensor Map**: Interactive geographic visualization with color-coded performance

### Employee Management
- **Employee Performance**: Track hours worked, locations visited, productivity metrics
- **Employee Effectiveness**: Detailed scoring based on vacuum improvement, hours, locations, efficiency
- **Tapping Operations**: Monitor maple tapping productivity, track taps put in/removed/capped

### Maintenance & Quality
- **Maintenance Tracking**: Automatic leak detection (sudden drops >5", gradual degradation >3")
- **Repairs Analysis**: Parse unstructured repair notes from timesheets
- **Data Quality**: Alert system for anomalies (excess hours, rapid drops, location mismatches)

### Analysis & Forecasting
- **Problem Clusters**: Geographic clustering of problem sensors using DBSCAN
- **SAP Forecast**: Production forecasting capabilities
- **Daily Summary**: Daily reports and trend analysis

## Configuration (config.py)

### Vacuum Thresholds
- **Excellent**: ≥20 inches
- **Fair**: 15-20 inches
- **Poor**: <15 inches

### Color Schemes
- Status indicators: Green/Yellow/Red
- Maple theme: Brown/woodland colors

### Performance Settings
- Data caching: 5 minutes
- Auto-refresh: 5 minutes
- Column name matching: Case-insensitive with flexible matching

### Alert Thresholds
- Critical vacuum: 12 inches
- Leak detection: Sudden drops >5", gradual degradation >3"
- Data quality: Excess hours, location mismatches

## Data Pipeline

### Data Sources
- **Vacuum sensor readings**: Google Sheets
- **Personnel/timesheet data**: Google Sheets
- **Multi-site support**: NY and VT operations

### Authentication
- Google service account authentication
- Supports both local credentials.json and Streamlit Cloud secrets
- Password-protected dashboard access

### Data Processing
- Flexible column name matching (case-insensitive)
- Automatic data type conversion
- Missing data handling
- Column normalization for consistency

## Development Guidelines

### Code Organization
- **Modular architecture**: Each page is a separate module in `page_modules/`
- **Reusable components**: UI components in `utils/ui_components.py`
- **Centralized config**: All settings in `config.py`
- **Helper functions**: Common operations in `utils/helpers.py` and `utils.py`

### Common Patterns

#### Column Name Matching
Use the flexible column matching functions from `utils.py`:
- `find_column()`: Case-insensitive column lookup with aliases
- Always handle missing columns gracefully

#### Metric Cards
Use `ui_components.py` for consistent metric displays:
- `create_metric_card()`: Standard metric card with delta
- Color-coded status indicators

#### Data Loading
Use `data_loader.py` functions:
- `load_vacuum_data()`: Load vacuum sensor readings
- `load_personnel_data()`: Load timesheet data
- Cached with 5-minute TTL

### Styling
- Custom CSS in `styling.py`
- Maple theme colors: Browns, greens, woodland tones
- Responsive design for various screen sizes
- Status colors: Green (good), Yellow (warning), Red (critical)

### Geographic Features
- Folium maps for sensor locations
- DBSCAN clustering for problem identification
- Distance calculations using `utils/geographic.py`
- Color-coded markers based on performance

## Running the Application

### Local Development
```bash
streamlit run dashboard.py
```

### Dev Container
- Configured for VS Code/GitHub Codespaces
- Python 3.11 in Debian bookworm
- Automatic package installation

### Environment Setup
Required secrets (in `.streamlit/secrets.toml` or Streamlit Cloud):
```toml
password = "your_password"

[gcp_service_account]
# Google Cloud service account credentials
```

## Testing & Verification

- `verify_setup.py`: Setup verification script
- Selenium support for automated testing
- Data quality checks built into the application

## Recent Development Focus

Based on recent commits:
- Repairs analysis page with unstructured note parsing
- Interactive map enhancements (tap installations, hover tooltips)
- Tapping overlay UI improvements
- Date range filtering for tap installations
- Navigation reorganization with "Needs Work" section

## Common Tasks

### Adding a New Page
1. Create new file in `page_modules/`
2. Import in `page_modules/__init__.py`
3. Add page configuration in `dashboard.py`
4. Follow existing patterns for data loading and styling

### Modifying Metrics
1. Update calculation logic in `metrics.py`
2. Adjust thresholds in `config.py` if needed
3. Update UI components to display new metrics

### Adding New Data Sources
1. Add loading function in `data_loader.py`
2. Configure Google Sheets access
3. Add column mapping and normalization
4. Update relevant page modules

### Styling Changes
1. Modify CSS in `styling.py`
2. Update color constants in `config.py`
3. Test across different screen sizes

## Performance Considerations

- **Caching**: 5-minute TTL on data loading functions
- **Large datasets**: Use pagination or filtering for raw data displays
- **Map rendering**: Cluster markers for better performance with many sensors
- **Auto-refresh**: Optional 5-minute refresh to balance freshness and load

## Data Quality & Error Handling

- Flexible column matching to handle sheet changes
- Missing data handling with clear user feedback
- Alert system for data anomalies
- Comprehensive logging for debugging

## Git Workflow

- **Main branch**: `main` (production)
- **Feature branches**: Named branches for new features (like `romantic-carson`)
- **Worktree support**: Development in separate worktrees for parallel work

## Notes for AI Assistants

- Always read relevant files before making changes
- Use existing helper functions and patterns for consistency
- Test column matching logic when modifying data processing
- Consider multi-site support (NY/VT) in all features
- Maintain the maple syrup production domain context
- Follow modular architecture - keep pages independent
- Use config.py for all thresholds and settings
- Preserve flexible column name matching throughout
