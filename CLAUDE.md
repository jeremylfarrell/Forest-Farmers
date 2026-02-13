# Forest Farmers Dashboard — CLAUDE.md

## What This Is

Streamlit dashboard for a maple syrup operation. Monitors vacuum systems, tracks employee productivity, and manages tapping operations across two sites: **New York (NY)** and **Vermont (VT)**. Deployed on Streamlit Cloud, auto-deploys from `main` branch.

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
| `config.py` | All thresholds, colors, targets (edit here, not in page modules) |
| `data_loader.py` | Google Sheets loading with `@st.cache_data(ttl=3600)` |
| `utils.py` | `find_column()`, `extract_conductor_system()`, formatters |
| `metrics.py` | Vacuum improvement and employee effectiveness calculations |
| `styling.py` | Custom CSS (maple/brown theme) |

### Page Modules (`page_modules/`)

| Module | Dashboard Name | What It Does |
|--------|---------------|-------------|
| `tapping.py` | Tapping Operations | Season progress, daily taps by employee pivot, employee productivity |
| `employees.py` | Employee Performance | Overtime watch (52h), hours by state, individual detail |
| `repairs_analysis.py` | Repairs Analysis | Interactive repairs tracker with `st.data_editor`, conductor system grouping |
| `employee_effectiveness.py` | Leak Checking | Vacuum before/after for repair work, mainline history |
| `sensor_map.py` | Interactive Map | Folium map with tap-count-scaled dots, repairs attention map |
| `vacuum.py` | Vacuum Performance | Sensor performance trends |
| `maintenance.py` | Maintenance & Leaks | Proactive leak detection alerts |
| `data_quality.py` | Alerts | Anomaly detection (largest module) |
| `sap_forecast.py` | Sap Flow Forecast | Weather-based sap prediction |
| `raw_data.py` | Raw Data | Direct data inspection |

## Domain Knowledge

### Sites
- **NY** = New York operation (larger, ~102k tap target)
- **VT** = Vermont operation (~49k tap target)
- Site is determined from the `Site` column in personnel data, or parsed from Job Code text

### Conductor Systems
The 2-4 letter prefix before the number in a mainline name. E.g., `RHAS13` → conductor system `RHAS`, `MPC5` → `MPC`. Used to group mainlines that share the same releaser/infrastructure.

### Sensor Naming
- Valid sensors: 2-4 uppercase letters followed by a number (e.g., `RHAS13`, `AB5`)
- Lowercase 'b' prefix = birch sensor (filter out from map)
- Anything not matching `^[A-Z]{2,4}\d` = relay or inactive (filter out)

### Job Codes (from TSheets)
Job codes contain site identifiers like "- NY - 240114" or "- VT 241111". The meaningful part is typically in parentheses or after "Maple Tapping -".

**Tapping job codes** (used for productivity metrics):
- "new spout install"
- "dropline install & tap" (NY only)
- "spout already on" (NY only)
- "maple tapping" (general prefix)

**Repair job codes** (used for leak checking):
- "inseason tubing repair"
- "already identified tubing issue"
- "fixing identified tubing"
- "tubing repair", "leak repair"

**Excluded from repair analysis:**
- "storm repair" — weather damage, not leak work
- "road improvement" — infrastructure, not tubing

### Personnel Data Columns
From Google Sheets via TSheets backup:
- `Employee Name`, `Date`, `Hours`, `Rate`
- `mainline.` (note the period — that's the actual column name)
- `Job` or `Job Code`
- `Taps Put In`, `Taps Removed`, `taps capped`
- `Repairs needed` (free-text field, not numeric)
- `Notes`
- `Site` (NY/VT/UNK)

### Vacuum Data Columns
- `Name` — sensor name (matches mainline naming)
- `Vacuum` or `Vacuum Reading` — inches of mercury
- `Last Communication` or `Timestamp`
- `Latitude`, `Longitude`
- `Site` (NY/VT)

### Key Thresholds
- Vacuum: Excellent ≥ 20", Fair ≥ 15", Poor < 15", Critical < 12"
- Overtime: 52 hours/week, warning at 45h
- Tap targets: NY = 102,000, VT = 49,000
- Min hours for employee ranking: 5.0h
- Week definition: Monday 12:01am to Sunday midnight

## Conventions

### Code Style
- All page modules export a single `render()` function
- Use `find_column(df, 'Name1', 'name2', ...)` for flexible column matching
- Use `extract_conductor_system(mainline)` to get the system prefix
- Numeric columns need `pd.to_numeric(col, errors='coerce').fillna(0)`
- Dates need `pd.to_datetime(col, errors='coerce')`
- Pivot tables with `margins=True` create mixed-type indexes — handle the "Total" row separately when sorting

### Deployment
- Push to `main` → Streamlit Cloud auto-redeploys (1-2 min)
- Test by refreshing the live URL after push
- If deploy seems stuck, reboot the app from Streamlit Cloud dashboard
- Data is cached 1 hour; "Refresh Data" button in sidebar clears cache

### Secrets (never commit these)
- `[passwords] password` — dashboard login
- `[sheets] NY_VACUUM_SHEET_URL`, `VT_VACUUM_SHEET_URL`, `PERSONNEL_SHEET_URL`
- `[github] GITHUB_TOKEN` — for TSheets sync trigger
- Google service account credentials in `[gcp_service_account]`

## Common Pitfalls

- `mainline.` column has a trailing period in the actual data — use `find_column()` to match it
- `Repairs needed` is a free-text field, not numeric — use string matching, not numeric comparison
- `st.data_editor` keys must be unique across the page or Streamlit throws DuplicateWidgetID
- Pivot tables with `margins=True` + `sort_index()` crashes on mixed date/string index
- Folium maps: use `returned_objects=[]` in `st_folium()` to prevent rerun on every click
- `st.tabs()` — first tab is always selected; reorder the list to change default

## Open Questions for Manager

1. **Cost for repair / cost per tap:** How to calculate? Is it `hours * rate`? Cost/tap = repair cost / taps on that mainline?
2. **Vacuum differential timing:** Want reading at job start vs 1hr after clock-out. Does vacuum data have frequent enough readings? Is "start" the TSheets clock-in time?
3. **Releaser differential:** Is this the vacuum change at the releaser over time, or the difference between releaser and mainline readings?
4. **Successful repair threshold:** What vacuum increase = "successful"? Currently any positive change shows green.
