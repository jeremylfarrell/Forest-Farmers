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

## Recent Improvements (January 2026)

### Code Quality & Architecture (PR #1)
- ✅ Fixed all bare exception handlers with specific exception types
- ✅ Added division by zero protection in employee metrics
- ✅ Implemented safe secrets access with error handling
- ✅ Created SchemaMapper class for centralized column mapping
- ✅ Implemented PageRegistry pattern for dynamic page management
- ✅ Added site-level data filtering (~50% performance improvement)

### Repairs Analysis Robustness
- ✅ Added word boundary regex patterns to prevent false positives
- ✅ Improved completion status detection with proper negation handling
- ✅ Integrated SchemaMapper for flexible column lookups
- ✅ Added comprehensive exception handling throughout
- ✅ Added new issue types: Leak Detected, Tubing Issue
- ✅ Clarified duplicate row counting in UI

## Known Issues & Technical Debt

### Critical (Fix Immediately)
1. **No test coverage** - Zero unit or integration tests
2. **No structured logging** - Production debugging impossible
3. **Weather API failures** - Silent failures when Open-Meteo unavailable (vacuum.py:14-43)
4. **No error retry logic** - API calls fail permanently on transient errors

### High Priority
1. **Input validation gaps** - Date ranges, coordinates, numeric inputs not validated
2. **No RBAC** - Single shared password, no per-user accounts or role-based access
3. **Hardcoded assumptions** - Coordinates (geo_clustering.py:112-119), thresholds throughout
4. **Cache invalidation** - All-or-nothing cache clearing, no selective invalidation
5. **No data export** - Cannot export tables to CSV/Excel or generate PDF reports

### Medium Priority
1. **Monolithic page files** - sensor_map.py (697 lines), data_quality.py (794 lines)
2. **Code duplication** - Site emoji logic, credential loading, timestamp parsing
3. **Performance bottlenecks** - No pagination, no marker clustering on maps
4. **Missing documentation** - No API docs, user manual, or video tutorials

### Security & Compliance Gaps
1. **No audit logging** - Cannot track who accessed or modified data
2. **No RBAC** - All users see all data, no site-based restrictions
3. **No data retention policy** - Unbounded data growth
4. **No privacy policy** - May violate GDPR/CCPA for employee data

## Feature Assessment

### Production-Ready Pages (Main Section)
- 🏠 Overview - System health dashboard
- 🔧 Vacuum Performance - Deep dive with temperature correlation
- 🌳 Tapping Operations - Labor efficiency and productivity tracking
- ⭐ Employee Effectiveness - Vacuum improvement tracking
- 🔨 Maintenance Tracking - Automated leak detection

### Pages Needing Work (Other Section)
- 🌍 Interactive Map - Geographic sensor visualization (needs clustering)
- 🔧 Repairs Analysis - Text parsing (recently improved)
- ⚠️ Alerts - Data quality monitoring
- 📝 Daily Summary, 🗺️ Problem Clusters, 🌡️ Sap Forecast, 📊 Raw Data

### Missing Critical Capabilities
1. **Testing** - No unit tests, integration tests, or data validation tests
2. **Alerting** - No email/SMS/Slack notifications for critical issues
3. **Export** - No CSV/Excel export, PDF reports, or scheduled reports
4. **Historical** - No year-over-year comparison or baseline tracking
5. **Predictive** - No ML for leak prediction or performance forecasting
6. **Mobile** - Not optimized for mobile devices or offline use
7. **Workflow** - No automated work orders or crew dispatch

### Questions Users Can't Answer
- "Which sensors are likely to fail next week?" (no predictive analytics)
- "What's our ROI on maintenance spending?" (no financial tracking)
- "How does this season compare to last year?" (no historical comparison)
- "What's the optimal crew size?" (no optimization analysis)

## Development Priorities

### Immediate (This Week)
1. Add basic error logging (Python logging module)
2. Create .python-version file (specify Python 3.11)
3. Add requirements-lock.txt with pinned versions
4. Fix weather API error handling

### Short-Term (This Month)
5. Write unit tests for critical functions
6. Add CSV export for all data tables
7. Document column name expectations
8. Improve error messages with actionable guidance

### Medium-Term (This Quarter)
9. Implement role-based access control
10. Add email alerting for critical issues
11. Refactor monolithic page modules
12. Conduct security audit

### Long-Term (This Year)
13. Develop ML leak prediction model
14. Build mobile-optimized interface
15. Create comprehensive documentation
16. Implement automated testing pipeline

## Notes for AI Assistants

### Development Guidelines
- Always read relevant files before making changes
- Use existing helper functions and patterns for consistency
- Test column matching logic when modifying data processing
- Consider multi-site support (NY/VT) in all features
- Maintain the maple syrup production domain context
- Follow modular architecture - keep pages independent
- Use config.py for all thresholds and settings
- Preserve flexible column name matching throughout

### Testing Requirements
- Write unit tests for new features
- Test edge cases (empty dataframes, missing columns, invalid dates)
- Validate with realistic data samples
- Check performance with large datasets (10,000+ rows)

### Security Considerations
- Never log sensitive data (passwords, API keys, employee PII)
- Validate all user inputs
- Use SchemaMapper for column lookups (avoid hardcoded names)
- Handle missing data gracefully
- Add specific exception types (not bare except)

### Performance Guidelines
- Use vectorized pandas operations (avoid iterrows)
- Cache expensive computations
- Paginate large datasets
- Use efficient data structures
- Profile before optimizing
