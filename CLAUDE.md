# Forest Farmers Dashboard — CLAUDE.md

## What This Is

Streamlit dashboard for a maple syrup operation. Monitors vacuum systems, tracks employee productivity, and manages tapping operations across two sites: **New York (NY)** and **Vermont (VT)**. Deployed on Streamlit Cloud, auto-deploys from `main` branch.

**Current version: v9.41** (shown in sidebar footer of `dashboard.py`)

## Architecture

```
Google Sheets (NY Vacuum, VT Vacuum, Personnel)
    → data_loader.py (gspread + 1hr cache)
    → dashboard.py (auth → site selection → filter → route)
    → page_modules/*.py render() functions
    → Streamlit UI (Plotly, Folium maps, metrics)
```

Each page module has a `render()` function called by `dashboard.py`. Data is filtered by site before being passed to pages.

## File Map

| File | Purpose |
|------|---------|
| `dashboard.py` | Entry point: auth, site picker, sidebar nav, page routing |
| `config.py` | All thresholds, colors, site coords, sugarbush mapping (edit here, not in page modules) |
| `data_loader.py` | Google Sheets loading with `@st.cache_data(ttl=3600)`; `save_repairs_updates()`, `save_repair_locations()` (~970 lines) |
| `metrics.py` | Metric calculation helpers |
| `styling.py` | Custom CSS (maple/brown theme) |
| `verify_setup.py` | Setup verification script |

### Utilities (`utils/`)

| Module | Purpose |
|--------|---------|
| `helpers.py` | `find_column()`, `is_tapping_job()`, `extract_conductor_system()`, `calculate_sap_flow_likelihood()`, `match_mainline_to_sensor()`, formatters |
| `geographic.py` | Haversine distance, clustering helpers |
| `freeze_thaw.py` | `get_current_freeze_thaw_status()`, `detect_freeze_event_drops()`, `render_freeze_thaw_banner()`, `add_freeze_bands_to_figure()` |
| `weather_api.py` | `get_temperature_data()`, `get_hourly_temperature()` — centralized Open-Meteo API calls |
| `__init__.py` | Re-exports all utils for `from utils import ...` |

### Page Modules (`page_modules/`)

**Primary pages** (sidebar top):
| Module | Dashboard Name | What It Does |
|--------|---------------|-------------|
| `tapping.py` | Tapping Operations | Season progress, daily taps by employee pivot, site-wide efficiency |
| `employees.py` | Employee Performance | Overtime watch (52h), hours by state, individual detail |
| `repairs_analysis.py` | Repairs Needed | `st.data_editor` repairs tracker; AppSheet photo/video `LinkColumn`s; GPS backfill expander writes `Location` to Google Sheets |
| `sensor_map.py` | Interactive Map | Folium map with tap-count-scaled sensor dots + exact-GPS AppSheet repair pins (white border); M-line sensors supported (~1,280 lines) |
| `tap_history.py` | Tap History | Year-over-year tap comparisons |
| `temperature_productivity.py` | Tapping by Temperature | Tapping productivity vs temperature (Open-Meteo API) |
| `freezing_report.py` | Freezing Report | Per-conductor freeze analysis + PDF export (~660 lines) |
| `manager_review.py` | Manager Data Review | Approve/edit personnel data, upload Excel corrections |

**Secondary pages** (sidebar "Needs Work"):
| Module | Dashboard Name | What It Does |
|--------|---------------|-------------|
| `vacuum.py` | Vacuum Performance | Sensor performance trends + freeze analysis (~995 lines) |
| `employee_effectiveness.py` | Leak Checking | Vacuum before/after for repair work |
| `maintenance.py` | Maintenance & Leaks | Proactive leak detection alerts |
| `data_quality.py` | Alerts | Anomaly detection, manager notes to Google Sheets |
| `sap_forecast.py` | Sap Flow Forecast | Weather-based sap prediction |
| `raw_data.py` | Raw Data | Direct data inspection |

## Domain Knowledge

### Sites
- **NY** = New York / Ellenburg operation (larger, ~102k tap target)
- **VT** = Vermont / Marshfield operation (~49k tap target)
- Site coordinates in `config.SITE_COORDINATES` — used for weather API calls
- Site is determined from the `Site` column in personnel data, or parsed from Job Code text

### Conductor Systems
The 2-4 letter prefix before the number in a mainline name. E.g., `DMA5` → conductor `DMA` → sugarbush "Drew Mt". Mapping lives in `config.SUGARBUSH_MAP` with longest-prefix matching via `config.get_sugarbush()`.

### Sensor Filtering
- `config.EXCLUDED_SENSOR_PREFIXES` = `{'AB', 'BFB', 'BMMD', 'ZGAS', 'ZGAN', 'GDS'}` — birch, relays, non-maple
- Use `config.is_excluded_sensor()` to filter

### Job Codes (from TSheets)
**Tapping job codes** (detected by `utils.helpers.is_tapping_job()`):
- "new spout install", "dropline install", "spout already on", "maple tapping"

**Repair job codes:**
- "inseason tubing repair", "already identified tubing issue", "fixing identified tubing"
- Excluded: "storm repair" (weather damage), "road improvement" (infrastructure)

### Google Sheets Structure
- **Vacuum sheets** (separate for NY and VT): Monthly tabs named like "January 2025", plus an `all` tab
- **Personnel sheet**: Tabs: `all` (TSheets data), `approved_personnel` (manager-reviewed), `repairs_tracker`, `Alerts_Notes`
  - **repairs_tracker** columns: `Repair ID`, `Mainline`, `Status`, `Location` (lat,lon string — written by dashboard GPS backfill or AppSheet `HERE()`), photo/video URL columns

### Personnel Data Columns
- `Employee Name`, `Date`, `Hours`, `Rate`
- `mainline.` (note the trailing period — use `find_column()` to match it)
- `Job` or `Job Code`
- `Taps Put In`, `Taps Removed`, `taps capped`
- `Repairs needed` (free-text field, not numeric)
- `Notes`, `Site` (NY/VT/UNK)

### Vacuum Data Columns
- `Name` — sensor name (matches mainline naming)
- `Vacuum` or `Vacuum Reading` — inches of mercury
- `Last Communication` or `Timestamp`
- `Latitude`, `Longitude`, `Site` (NY/VT)

### Key Thresholds (all in config.py)
- Vacuum: Excellent ≥ 20", Fair ≥ 15", Poor < 15", Critical < 12"
- Overtime: 52 hours/week
- Tap targets: NY = 102,000, VT = 49,000
- Freeze: LIKELY LEAK > 50% drop rate, WATCH > 25%
- Releaser diff colors: graduated green → yellow → pink scale

## Conventions

### Code Style
- **Column matching**: Always use `find_column(df, 'Name1', 'name2', ...)` — case-insensitive. Never hardcode column names directly.
- **Tapping job detection**: Use `from utils.helpers import is_tapping_job` — shared utility, don't duplicate.
- **Weather coordinates**: Always use `config.SITE_COORDINATES` — never hardcode lat/lon.
- **Exception handling**: Use `except Exception:` not bare `except:`.
- **Numeric coercion**: `pd.to_numeric(col, errors='coerce').fillna(0)`
- **Date parsing**: `pd.to_datetime(col, errors='coerce')`
- **TSheets Updated detection**: Uses `np.isclose(atol=0.01)` for float comparison
- **New shared utilities** go in `utils/helpers.py` and get exported via `utils/__init__.py`
- **New page modules** must be added to both `page_modules/__init__.py` imports and `dashboard.py` routing
- **Sensor column name matching**: When using `find_column()` for lat/lon in vacuum data, use the same variants as `sensor_map.py`: `find_column(df, 'Latitude', 'latitude', 'lat')` and `find_column(df, 'Longitude', 'longitude', 'lon', 'long')`
- **Hiding columns without breaking save logic**: Use `column_order=[...]` on `st.data_editor` / `st.dataframe` to hide a column from view while keeping it in the underlying DataFrame — do NOT remove the column from the data when downstream code (e.g. save logic) needs it

### Manager Approval Workflow
Raw TSheets data → Manager Data Review page → corrections → `approved_personnel` tab → `merge_approved_data()` joins raw + approved with change detection

### Version Bumps
Update `st.caption(f"v9.XX | ...")` in `dashboard.py` `render_sidebar()` function.

### Git
- Single `main` branch, push directly
- Remote: `https://github.com/jeremylfarrell/Forest-Farmers.git`
- Commit message style: `v9.XX: Short description of changes`

### Deployment
- Push to `main` → Streamlit Cloud auto-redeploys (1-2 min)
- Data cached 1 hour; separate "🔄 Vacuum" and "🔄 Personnel" refresh buttons in sidebar
- "⬇️ Sync from TSheets" button triggers GitHub Actions workflow via API

### Secrets (never commit these)
- `[passwords] password` — dashboard login
- `[sheets] NY_VACUUM_SHEET_URL`, `VT_VACUUM_SHEET_URL`, `PERSONNEL_SHEET_URL`
- `[github] GITHUB_TOKEN` — for TSheets sync trigger
- `[gcp_service_account]` — Google service account credentials

## Common Pitfalls

- `mainline.` column has a trailing period in the actual data — use `find_column()` to match it
- `Repairs needed` is a free-text field, not numeric — use string matching
- `st.data_editor` keys must be unique across the page or Streamlit throws DuplicateWidgetID
- Pivot tables with `margins=True` + `sort_index()` crashes on mixed date/string index
- Folium maps: use `returned_objects=[]` in `st_folium()` to prevent rerun on every click
- Page render() param order varies — some take `(vacuum_df, personnel_df)`, others `(personnel_df, vacuum_df)`. Check the function signature.
- `st.cache_data` ttl is 3600 seconds (1 hour) — `config.CACHE_TIMEOUT` matches this
- Sensor name regex for map filtering uses `^[A-Z]{1,4}\d` (1–4 uppercase letters then a digit) — do NOT use `{2,4}`, which silently excludes single-letter prefixes like Matthews sensors (`M01`, `M02`)

## Deferred Work (Not Yet Done)
- Splitting large files: `sensor_map.py` (~1,280 lines), `vacuum.py` (~995 lines), `data_loader.py` (~970 lines)
- Adding type hints across the codebase
- Adding unit tests

## Completed Refactoring (for reference)
- ✅ `calculate_sap_flow_likelihood()` — extracted to `utils/helpers.py`
- ✅ `add_freeze_bands_to_figure()` — extracted to `utils/freeze_thaw.py`
- ✅ `get_temperature_data()` / `get_hourly_temperature()` — extracted to `utils/weather_api.py`
- ✅ `match_mainline_to_sensor()` — extracted to `utils/helpers.py`
