"""
Tap History Page Module
Historical tap count analysis by conductor system and mainline.
Loads static Excel data (VT 2021-2025) and compares against live 2026 tapping data.

Status Color Codes (manager-defined):
    Black  = Not started (0 taps in 2026, had taps in 2025)
    Red    = Significantly less (< 95% of 2025)
    Yellow = On track (within 5%: 95-99% or 101-105%)
    Green  = On target (within 1%: 99-101%)
    Purple = Significantly more (> 105% of 2025)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import config
from utils import find_column, extract_conductor_system


# Year columns in the historical data
YEAR_COLS = [2021, 2022, 2023, 2024, 2025]


# ── Status helpers ─────────────────────────────────────────────────────

def _classify_status(t2025, t2026):
    """
    Classify a mainline's 2026 vs 2025 status using the manager's 5-tier system.
    Returns (label, css_style) tuple.
    """
    if t2025 > 0 and t2026 == 0:
        return "No 2026 data"
    if t2025 == 0 and t2026 > 0:
        return "New tapping"
    if t2025 == 0 and t2026 == 0:
        return ""
    # Both > 0
    pct = t2026 / t2025 * 100
    if pct < 95:
        return "Significantly less"
    elif pct < 99:
        return "On track"
    elif pct <= 101:
        return "On target"
    elif pct <= 105:
        return "On track"
    else:
        return "Significantly more"


def _color_status(val):
    """Return CSS styling for a status cell (used with pandas Styler.map)."""
    color_map = {
        'No 2026 data': 'background-color: #1a1a1a; color: white',
        'Significantly less': 'background-color: #dc3545; color: white',
        'On track': 'background-color: #ffc107; color: black',
        'On target': 'background-color: #28a745; color: white',
        'Significantly more': 'background-color: #9b59b6; color: white',
        'New tapping': 'background-color: #17a2b8; color: white',
    }
    return color_map.get(val, '')


# ── Data loaders ───────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_historical_taps():
    """Load VT historical tap data from the committed Excel file."""
    possible_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'vt_taps_historical.xlsx'),
        'data/vt_taps_historical.xlsx',
    ]
    for path in possible_paths:
        if os.path.exists(path):
            df = pd.read_excel(path)
            df = df.dropna(subset=['mainline'])
            # Fix GBW typo (2025 data entry error) — should be GDW
            df['mainline'] = df['mainline'].str.replace(r'^GBW', 'GDW', regex=True)
            df['Conductor System'] = df['mainline'].apply(extract_conductor_system)
            for yr in YEAR_COLS:
                if yr in df.columns:
                    df[yr] = pd.to_numeric(df[yr], errors='coerce')
            return df
    return pd.DataFrame()


def get_2026_taps(personnel_df):
    """
    Extract current season taps per mainline from live personnel data.
    Includes December 2025 onward (season start) through current date.
    Returns a Series indexed by mainline name with total taps put in.
    """
    if personnel_df is None or personnel_df.empty:
        return pd.Series(dtype=float)

    mainline_col = find_column(personnel_df, 'mainline.', 'mainline', 'Mainline', 'location')
    taps_col = find_column(personnel_df, 'Taps Put In', 'taps_in', 'taps put in')

    if not mainline_col or not taps_col:
        return pd.Series(dtype=float)

    df = personnel_df.copy()
    df['_taps'] = pd.to_numeric(df[taps_col], errors='coerce').fillna(0)
    df['_ml'] = df[mainline_col].astype(str).str.strip()

    # Include December 2025 onward (tapping season starts in December)
    date_col = find_column(df, 'Date', 'date', 'timestamp')
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df[df[date_col] >= pd.Timestamp(config.SEASON_START)]

    # Filter to rows with actual mainline entries and taps
    df = df[df['_ml'].str.len() > 0]
    df = df[df['_ml'] != 'nan']

    taps_by_ml = df.groupby('_ml')['_taps'].sum()
    return taps_by_ml


def get_2026_taps_deleted(personnel_df):
    """
    Extract current season taps DELETED per mainline from live personnel data.
    Includes December 2025 onward (season start) through current date.
    Returns a Series indexed by mainline name with total taps removed.
    """
    if personnel_df is None or personnel_df.empty:
        return pd.Series(dtype=float)

    mainline_col = find_column(personnel_df, 'mainline.', 'mainline', 'Mainline', 'location')
    taps_del_col = find_column(personnel_df, 'Taps Removed', 'taps_removed', 'taps out')

    if not mainline_col or not taps_del_col:
        return pd.Series(dtype=float)

    df = personnel_df.copy()
    df['_taps_del'] = pd.to_numeric(df[taps_del_col], errors='coerce').fillna(0)
    df['_ml'] = df[mainline_col].astype(str).str.strip()

    # Include December 2025 onward (tapping season starts in December)
    date_col = find_column(df, 'Date', 'date', 'timestamp')
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df[df[date_col] >= pd.Timestamp(config.SEASON_START)]

    # Filter to rows with actual mainline entries
    df = df[df['_ml'].str.len() > 0]
    df = df[df['_ml'] != 'nan']

    taps_del_by_ml = df.groupby('_ml')['_taps_del'].sum()
    return taps_del_by_ml


def get_2026_taps_capped(personnel_df):
    """
    Extract current season taps CAPPED per mainline from live personnel data.
    Includes December 2025 onward (season start) through current date.
    Returns a Series indexed by mainline name with total taps capped.
    """
    if personnel_df is None or personnel_df.empty:
        return pd.Series(dtype=float)

    mainline_col = find_column(personnel_df, 'mainline.', 'mainline', 'Mainline', 'location')
    taps_cap_col = find_column(personnel_df, 'taps capped', 'Taps Capped', 'taps_capped')

    if not mainline_col or not taps_cap_col:
        return pd.Series(dtype=float)

    df = personnel_df.copy()
    df['_taps_cap'] = pd.to_numeric(df[taps_cap_col], errors='coerce').fillna(0)
    df['_ml'] = df[mainline_col].astype(str).str.strip()

    date_col = find_column(df, 'Date', 'date', 'timestamp')
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df[df[date_col] >= pd.Timestamp(config.SEASON_START)]

    df = df[df['_ml'].str.len() > 0]
    df = df[df['_ml'] != 'nan']

    return df.groupby('_ml')['_taps_cap'].sum()


def get_2026_tappers(personnel_df):
    """
    Extract unique employee names per mainline from live personnel data.
    Includes December 2025 onward (season start).
    Returns a Series indexed by mainline name with comma-separated employee names.
    """
    if personnel_df is None or personnel_df.empty:
        return pd.Series(dtype=str)

    mainline_col = find_column(personnel_df, 'mainline.', 'mainline', 'Mainline', 'location')
    taps_col = find_column(personnel_df, 'Taps Put In', 'taps_in', 'taps put in')
    emp_col = find_column(personnel_df, 'Employee Name', 'Employee', 'EE First', 'Name')

    if not mainline_col or not taps_col or not emp_col:
        return pd.Series(dtype=str)

    df = personnel_df.copy()
    df['_taps'] = pd.to_numeric(df[taps_col], errors='coerce').fillna(0)
    df['_ml'] = df[mainline_col].astype(str).str.strip()
    df['_emp'] = df[emp_col].astype(str).str.strip()

    # Include December 2025 onward (tapping season starts in December)
    date_col = find_column(df, 'Date', 'date', 'timestamp')
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df[df[date_col] >= pd.Timestamp(config.SEASON_START)]

    # Filter to rows with actual taps > 0
    df = df[df['_ml'].str.len() > 0]
    df = df[df['_ml'] != 'nan']
    df = df[df['_taps'] > 0]

    tappers_by_ml = df.groupby('_ml')['_emp'].apply(
        lambda names: ', '.join(sorted(names.unique()))
    )
    return tappers_by_ml


# ── Save helpers ───────────────────────────────────────────────────────

def _save_mainline_corrections(changed_rows, unknown_df, personnel_df,
                                mainline_col, emp_col, date_col, job_col):
    """Write corrected mainline names back to approved_personnel via data_loader."""
    from data_loader import save_approved_personnel
    from datetime import datetime as dt

    try:
        sheet_url = st.secrets['sheets']['PERSONNEL_SHEET_URL']
        creds = dict(st.secrets['gcp_service_account'])
    except (KeyError, FileNotFoundError):
        st.error("Missing Google Sheets credentials in secrets.")
        return

    # Build approved rows with corrected mainline
    corrections = []
    for idx, row in changed_rows.iterrows():
        new_mainline = row['Mainline']
        emp = row.get('Employee', '')
        date_str = row.get('Date', '')

        # Find the original personnel row to get all columns
        match_mask = pd.Series([True] * len(personnel_df))
        if emp_col and emp:
            match_mask &= personnel_df[emp_col].astype(str).str.strip() == emp.strip()
        if date_col and date_str:
            p_dates = pd.to_datetime(personnel_df[date_col], errors='coerce').dt.strftime('%Y-%m-%d')
            match_mask &= p_dates == date_str

        matched = personnel_df[match_mask]
        if matched.empty:
            continue

        for _, orig_row in matched.iterrows():
            correction = orig_row.to_dict()
            correction[mainline_col] = new_mainline
            correction['Approved Date'] = dt.now().strftime('%Y-%m-%d %H:%M')
            correction['Approved By'] = 'Dashboard (Mainline Fix)'
            corrections.append(correction)

    if corrections:
        approved_df = pd.DataFrame(corrections)
        success, msg = save_approved_personnel(sheet_url, creds, approved_df)
        if success:
            st.success(f"✅ Saved {len(corrections)} mainline correction(s). Refresh Personnel to see changes.")
            # Clear caches so next load picks up corrections
            from data_loader import load_approved_personnel
            load_approved_personnel.clear()
        else:
            st.error(f"Save failed: {msg}")
    else:
        st.warning("No matching personnel rows found for corrections.")


# ── Main render ────────────────────────────────────────────────────────

def render(personnel_df=None, vacuum_df=None):
    """Render tap history analysis page."""

    st.title("📈 Tap History — VT")
    st.markdown("*Compare 2026 live tapping against historical baselines by conductor system*")

    hist_df = load_historical_taps()
    if hist_df.empty:
        st.error("Could not load historical tap data. Ensure `data/vt_taps_historical.xlsx` exists.")
        return

    variance_pct = getattr(config, 'VARIANCE_THRESHOLD', 20)

    # Get live 2026 data from personnel sheet
    taps_2026 = get_2026_taps(personnel_df)
    taps_2026_del = get_2026_taps_deleted(personnel_df)
    taps_2026_cap = get_2026_taps_capped(personnel_df)
    tappers_2026 = get_2026_tappers(personnel_df)
    has_2026 = len(taps_2026) > 0

    # Merge 2026 taps into historical dataframe
    if has_2026:
        hist_df['2026'] = hist_df['mainline'].map(taps_2026).fillna(0)
        hist_df['2026 Deleted'] = hist_df['mainline'].map(taps_2026_del).fillna(0)
        hist_df['2026 Capped'] = hist_df['mainline'].map(taps_2026_cap).fillna(0)
    else:
        hist_df['2026'] = 0
        hist_df['2026 Deleted'] = 0
        hist_df['2026 Capped'] = 0

    all_years = YEAR_COLS + ['2026'] if has_2026 else YEAR_COLS
    agg_years = all_years + (['2026 Deleted', '2026 Capped'] if has_2026 else [])

    # ==================================================================
    # SECTION 1: 2026 vs 2025 Season Comparison (THE MAIN EVENT)
    # ==================================================================
    st.subheader("🔥 2026 Season vs 2025 Baseline")
    if has_2026:
        st.markdown("*Live tapping data from this season compared to last year's final counts*")
    else:
        st.warning("No 2026 tapping data found in personnel records yet. Showing historical data only.")

    # Conductor system level comparison
    cs_agg = hist_df.groupby('Conductor System')[agg_years].sum().reset_index()
    cs_agg[2025] = cs_agg[2025].fillna(0)

    if has_2026:
        cs_agg['2026'] = cs_agg['2026'].fillna(0)
        cs_agg['2026 Deleted'] = cs_agg['2026 Deleted'].fillna(0)
        cs_agg['2026 Capped'] = cs_agg['2026 Capped'].fillna(0)
        # Net taps = put in minus deleted
        cs_agg['Net 2026'] = cs_agg['2026'] - cs_agg['2026 Deleted']
        # Diff = 2025 - 2026 (positive = behind last year, negative = ahead)
        cs_agg['Diff (26 vs 25)'] = cs_agg[2025] - cs_agg['2026']
        cs_agg['% of 2025'] = ((cs_agg['Net 2026'] / cs_agg[2025]) * 100).round(1)
        cs_agg['% of 2025'] = cs_agg['% of 2025'].replace([float('inf'), float('-inf')], 0).fillna(0)
        # Remaining = 2025 - net 2026 (treats deleted taps as permanent losses)
        cs_agg['Remaining'] = (cs_agg[2025] - cs_agg['Net 2026']).clip(lower=0)
        cs_agg = cs_agg.sort_values('% of 2025', ascending=True)  # Worst first

        # Top-level metrics
        total_2025 = cs_agg[2025].sum()
        total_2026 = cs_agg['2026'].sum()
        total_2026_del = cs_agg['2026 Deleted'].sum()
        total_2026_cap = cs_agg['2026 Capped'].sum()
        total_net = cs_agg['Net 2026'].sum()

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            st.metric("2025 Baseline (VT)", f"{int(total_2025):,}")
        with col2:
            st.metric("2026 Tapped", f"{int(total_2026):,}")
        with col3:
            st.metric("2026 Deleted", f"{int(total_2026_del):,}")
        with col4:
            st.metric("2026 Capped", f"{int(total_2026_cap):,}")
        with col5:
            pct_overall = (total_net / total_2025 * 100) if total_2025 > 0 else 0
            st.metric("% Complete (Net)", f"{pct_overall:.1f}%")
        with col6:
            remaining = max(total_2025 - total_net, 0)
            st.metric("Remaining to Match", f"{int(remaining):,}")

        # Sap drop progress visual
        _pct_clamped = min(pct_overall, 100)
        _fill_color = '#D4A017' if _pct_clamped < 100 else '#28a745'
        _drop_html = f'''
        <div style="display:flex; align-items:center; justify-content:center; margin:10px 0;">
          <svg width="80" height="110" viewBox="0 0 80 110">
            <defs>
              <clipPath id="dropClip">
                <path d="M40 5 C40 5 10 50 10 72 C10 92 23 105 40 105 C57 105 70 92 70 72 C70 50 40 5 40 5Z"/>
              </clipPath>
            </defs>
            <path d="M40 5 C40 5 10 50 10 72 C10 92 23 105 40 105 C57 105 70 92 70 72 C70 50 40 5 40 5Z"
                  fill="#e8e8e8" stroke="#8B4513" stroke-width="2"/>
            <rect x="0" y="{105 - _pct_clamped}" width="80" height="{_pct_clamped}"
                  fill="{_fill_color}" clip-path="url(#dropClip)" opacity="0.85"/>
            <text x="40" y="75" text-anchor="middle" font-size="18" font-weight="bold"
                  fill="#333">{pct_overall:.0f}%</text>
          </svg>
          <span style="margin-left:12px; font-size:16px; color:#555;">
            <b>{int(total_net):,}</b> of <b>{int(total_2025):,}</b> taps
          </span>
        </div>
        '''
        st.markdown(_drop_html, unsafe_allow_html=True)

        st.divider()

        # Horizontal bar chart FIRST — easy visual overview (per manager request)
        chart_data = cs_agg[['Conductor System', '% of 2025']].copy()
        chart_data = chart_data.sort_values('% of 2025', ascending=True)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=chart_data['% of 2025'],
            y=chart_data['Conductor System'],
            orientation='h',
            marker=dict(
                color=chart_data['% of 2025'],
                colorscale=[[0, '#dc3545'], [0.5, '#ffc107'], [1.0, '#28a745']],
                cmin=0, cmax=100,
            ),
            text=chart_data['% of 2025'].apply(lambda x: f"{x:.0f}%"),
            textposition='outside',
        ))
        fig.add_vline(x=100, line_dash="dash", line_color="gray", annotation_text="2025 level")
        fig.update_layout(
            title='2026 Progress vs 2025 Baseline by Conductor System',
            xaxis_title='% of 2025 Taps',
            height=max(400, len(chart_data) * 28),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Conductor system comparison table — detailed numbers
        st.markdown("**By Conductor System** — sorted alphabetically")
        cs_agg_table = cs_agg.sort_values('Conductor System')
        display_cs = cs_agg_table[['Conductor System', 2025, '2026', '2026 Deleted', '2026 Capped',
                             'Net 2026', 'Diff (26 vs 25)', '% of 2025', 'Remaining']].copy()
        display_cs = display_cs.rename(columns={
            2025: '2025',
            '2026 Deleted': 'Del',
            '2026 Capped': 'Cap',
            'Diff (26 vs 25)': 'Diff',
            '% of 2025': '%',
        })
        for int_col in ['2025', '2026', 'Del', 'Cap', 'Net 2026', 'Diff', 'Remaining']:
            display_cs[int_col] = display_cs[int_col].astype(int)
        display_cs['%'] = display_cs['%'].apply(lambda x: f"{x:.1f}%")

        _cs_col_cfg = {
            'Conductor System': st.column_config.TextColumn(width='medium'),
            '2025':      st.column_config.NumberColumn(width='small'),
            '2026':      st.column_config.NumberColumn(width='small'),
            'Del':       st.column_config.NumberColumn(width='small'),
            'Cap':       st.column_config.NumberColumn(width='small'),
            'Net 2026':  st.column_config.NumberColumn(width='small'),
            'Diff':      st.column_config.NumberColumn(width='small'),
            '%':         st.column_config.TextColumn(width='small'),
            'Remaining': st.column_config.NumberColumn(width='small'),
        }
        st.dataframe(display_cs, column_config=_cs_col_cfg,
                     use_container_width=True, hide_index=True,
                     height=min(38 + len(display_cs) * 36, 500))

    else:
        # No 2026 data — show historical overview
        cs_agg['Change (24-25)'] = cs_agg[2025] - cs_agg[2024]
        cs_agg['% Change'] = ((cs_agg['Change (24-25)'] / cs_agg[2024]) * 100).round(1)
        cs_agg['% Change'] = cs_agg['% Change'].replace([float('inf'), float('-inf')], 0).fillna(0)
        cs_agg = cs_agg.sort_values(2025, ascending=False)

        display_cs = cs_agg[['Conductor System'] + YEAR_COLS + ['Change (24-25)', '% Change']].copy()
        for yr in YEAR_COLS:
            display_cs[yr] = display_cs[yr].fillna(0).astype(int)
        display_cs['Change (24-25)'] = display_cs['Change (24-25)'].fillna(0).astype(int)
        display_cs['% Change'] = display_cs['% Change'].apply(lambda x: f"{x:+.1f}%")

        st.dataframe(display_cs, use_container_width=True, hide_index=True,
                     height=min(38 + len(display_cs) * 36, 500))

    st.divider()

    # ==================================================================
    # SECTION 2: Conductor System Detail
    # ==================================================================
    st.subheader("🔍 Conductor System Detail")

    selected_cs = st.selectbox(
        "Select Conductor System",
        sorted(hist_df['Conductor System'].unique()),
        key='tap_history_cs'
    )

    if selected_cs:
        cs_data = hist_df[hist_df['Conductor System'] == selected_cs].copy()

        # Line chart: total taps per year for this system (including 2026)
        chart_years = all_years
        yearly_totals = cs_data[chart_years].sum()
        fig_line = go.Figure()

        # Historical years in green
        fig_line.add_trace(go.Scatter(
            x=[str(y) for y in YEAR_COLS],
            y=[yearly_totals[y] for y in YEAR_COLS],
            mode='lines+markers+text',
            text=[f"{int(v):,}" for v in [yearly_totals[y] for y in YEAR_COLS]],
            textposition='top center',
            marker=dict(size=10, color='#28a745'),
            line=dict(width=3, color='#28a745'),
            name='Historical',
        ))

        # 2026 in orange (in progress)
        if has_2026:
            fig_line.add_trace(go.Scatter(
                x=['2026'],
                y=[yearly_totals['2026']],
                mode='markers+text',
                text=[f"{int(yearly_totals['2026']):,}"],
                textposition='top center',
                marker=dict(size=14, color='#ff7f0e', symbol='star'),
                name='2026 (in progress)',
            ))

        fig_line.update_layout(
            title=f'{selected_cs} — Taps Over Time',
            xaxis_title='Year',
            yaxis_title='Total Taps',
            height=350,
        )
        st.plotly_chart(fig_line, use_container_width=True)

        # Mainline detail table
        display_cols = ['mainline'] + YEAR_COLS
        if has_2026:
            display_cols.extend(['2026', '2026 Deleted', '2026 Capped'])

        ml_display = cs_data[display_cols].copy()

        if has_2026:
            ml_display['2026 Deleted'] = ml_display['2026 Deleted'].fillna(0)
            ml_display['2026 Capped'] = ml_display['2026 Capped'].fillna(0)
            ml_display['Net 2026'] = ml_display['2026'].fillna(0) - ml_display['2026 Deleted']
            ml_display['Count Diff'] = (
                ml_display['2026'].fillna(0)
                - ml_display[2025].fillna(0)
            ).astype(int)
            ml_display['Actual Diff'] = (
                ml_display['Net 2026']
                - ml_display[2025].fillna(0)
            ).astype(int)
            ml_display['% of 2025'] = ((ml_display['Net 2026'] / ml_display[2025].fillna(0)) * 100).round(1)
            ml_display['% of 2025'] = ml_display['% of 2025'].replace([float('inf'), float('-inf')], 0).fillna(0)
        else:
            ml_display['Change (24-25)'] = (ml_display[2025].fillna(0) - ml_display[2024].fillna(0)).astype(int)

        # Assign status using the new 5-tier system
        def _flag_mainline(row):
            t2025 = row[2025] if pd.notna(row[2025]) else 0
            if has_2026:
                t2026 = row.get('Net 2026', 0) if pd.notna(row.get('Net 2026', 0)) else 0
                return _classify_status(t2025, t2026)
            else:
                t2024 = row[2024] if pd.notna(row[2024]) else 0
                has_prior = any(pd.notna(row[yr]) and row[yr] > 0 for yr in [2021, 2022, 2023])
                if t2024 == 0 and t2025 > 0 and not has_prior:
                    return "New line"
                if t2024 > 0 and t2025 == 0:
                    return "Missing data"
                if t2024 > 0:
                    pct = abs(t2025 - t2024) / t2024 * 100
                    if pct >= variance_pct:
                        return "Large decrease" if t2025 < t2024 else "Large increase"
                return ""

        ml_display['Status'] = ml_display.apply(_flag_mainline, axis=1)

        # Add tappers column
        if has_2026:
            ml_display['Tappers (2026)'] = cs_data['mainline'].map(tappers_2026).fillna('')

        for yr in YEAR_COLS:
            ml_display[yr] = ml_display[yr].fillna(0).astype(int)
        if has_2026:
            ml_display['2026'] = ml_display['2026'].fillna(0).astype(int)
            ml_display['2026 Deleted'] = ml_display['2026 Deleted'].astype(int)
            ml_display['2026 Capped'] = ml_display['2026 Capped'].astype(int)
            ml_display['Net 2026'] = ml_display['Net 2026'].astype(int)
            ml_display['% of 2025'] = ml_display['% of 2025'].apply(lambda x: f"{x:.0f}%")

        ml_display = ml_display.rename(columns={'mainline': 'Mainline'})
        ml_display = ml_display.sort_values('Mainline')

        # Reorder columns for clarity
        if has_2026:
            col_order = ['Mainline'] + [yr for yr in YEAR_COLS] + [
                '2026', '2026 Deleted', '2026 Capped', 'Net 2026',
                'Count Diff', 'Actual Diff',
                '% of 2025', 'Tappers (2026)', 'Status'
            ]
            ml_display = ml_display[[c for c in col_order if c in ml_display.columns]]

        # Apply color-coded styling to Status column
        _ml_height = min(38 + len(ml_display) * 36, 500)
        if has_2026 and 'Status' in ml_display.columns:
            styled_ml = ml_display.style.map(_color_status, subset=['Status'])
            st.dataframe(styled_ml, use_container_width=True, hide_index=True, height=_ml_height)
        else:
            st.dataframe(ml_display, use_container_width=True, hide_index=True, height=_ml_height)

    st.divider()

    # ==================================================================
    # SECTION 3: Mainlines Needing Attention
    # ==================================================================
    if has_2026:
        st.subheader("⚠️ Mainlines Needing Attention")
        st.markdown(
            "*Mainlines that had taps in 2025 but have 0 or very few in 2026 so far — "
            "excludes conductor systems with zero 2026 taps (not yet started)*"
        )

        # Compute total 2026 taps per conductor system to identify active systems
        cs_2026_totals = hist_df.groupby('Conductor System')['2026'].sum()
        active_conductor_systems = set(cs_2026_totals[cs_2026_totals > 0].index)

        attention = []
        for _, row in hist_df.iterrows():
            mainline = row['mainline']
            cs = row['Conductor System']
            t2025 = row[2025] if pd.notna(row[2025]) else 0
            t2026 = row.get('2026', 0) if pd.notna(row.get('2026', 0)) else 0
            t2026_del = row.get('2026 Deleted', 0) if pd.notna(row.get('2026 Deleted', 0)) else 0
            t2026_cap = row.get('2026 Capped', 0) if pd.notna(row.get('2026 Capped', 0)) else 0
            net_2026 = t2026 - t2026_del

            # Skip mainlines with no 2025 baseline
            if t2025 <= 0:
                continue

            # Skip mainlines from conductor systems with zero total 2026 taps
            # (entire system hasn't started tapping yet — not useful to list)
            if cs not in active_conductor_systems:
                continue

            pct = (net_2026 / t2025 * 100) if t2025 > 0 else 0
            status = _classify_status(t2025, net_2026)

            attention.append({
                'Mainline': mainline,
                'Conductor System': cs,
                '2025 Taps': int(t2025),
                '2026 Taps': int(t2026),
                '2026 Deleted': int(t2026_del),
                '2026 Capped': int(t2026_cap),
                'Net 2026': int(net_2026),
                '% of 2025': f"{pct:.0f}%",
                'Remaining': int(max(t2025 - net_2026, 0)),
                'Status': status,
            })

        if attention:
            att_df = pd.DataFrame(attention)

            # Sort by status priority (worst first), then by Remaining descending
            status_order = {
                'No 2026 data': 0,
                'Significantly less': 1,
                'On track': 2,
                'On target': 3,
                'Significantly more': 4,
            }
            att_df['_sort'] = att_df['Status'].map(status_order).fillna(5)
            att_df = att_df.sort_values(['_sort', 'Remaining'], ascending=[True, False]).drop(columns='_sort')

            # Let managers hide mainlines they know are done but lack TSheets data
            _hide_key = "tap_attention_hidden"
            _all_ml = att_df['Mainline'].tolist()
            _hidden = st.multiselect(
                "✅ Mark as resolved (hide from list):",
                options=_all_ml,
                default=[m for m in st.session_state.get(_hide_key, []) if m in _all_ml],
                key=_hide_key,
                help="Select mainlines that are complete but not yet in TSheets. "
                     "Deselect to restore. Resets on page refresh.",
            )
            if _hidden:
                att_df = att_df[~att_df['Mainline'].isin(_hidden)].copy()
                st.caption(f"ℹ️ {len(_hidden)} mainline(s) hidden — deselect above to restore.")

            # Summary metrics by status
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                not_started = len(att_df[att_df['Status'] == 'No 2026 data'])
                st.metric("No 2026 Data", not_started)
            with col2:
                sig_less = len(att_df[att_df['Status'] == 'Significantly less'])
                st.metric("Sig. Less", sig_less)
            with col3:
                on_track = len(att_df[att_df['Status'] == 'On track'])
                st.metric("On Track", on_track)
            with col4:
                on_target = len(att_df[att_df['Status'] == 'On target'])
                st.metric("On Target", on_target)
            with col5:
                sig_more = len(att_df[att_df['Status'] == 'Significantly more'])
                st.metric("Sig. More", sig_more)

            # Also show total taps remaining
            total_remaining = att_df['Remaining'].sum()
            st.caption(f"**Total Taps Remaining:** {total_remaining:,}")

            # Apply color-coded styling to Status column
            styled_att = att_df.style.map(_color_status, subset=['Status'])
            st.dataframe(styled_att, use_container_width=True, hide_index=True,
                         height=min(38 + len(att_df) * 36, 500))
        else:
            st.success("All mainlines with 2025 data are progressing in 2026!")
    else:
        st.subheader(f"⚠️ Variance Flags (>{variance_pct}% change)")
        st.markdown(f"*Mainlines where 2025 taps differ from 2024 by more than {variance_pct}%*")

        flagged = []
        for _, row in hist_df.iterrows():
            mainline = row['mainline']
            cs = row['Conductor System']
            t2024 = row[2024] if pd.notna(row[2024]) else 0
            t2025 = row[2025] if pd.notna(row[2025]) else 0
            has_prior = any(pd.notna(row[yr]) and row[yr] > 0 for yr in [2021, 2022, 2023])

            flag = None
            pct_change = 0

            if t2024 == 0 and t2025 > 0 and not has_prior:
                flag = "New line (no prior data)"
                pct_change = 100
            elif t2024 > 0 and t2025 == 0:
                flag = "Missing data (had prior)"
                pct_change = -100
            elif t2024 > 0:
                pct_change = ((t2025 - t2024) / t2024) * 100
                if pct_change >= variance_pct:
                    flag = "Large increase"
                elif pct_change <= -variance_pct:
                    flag = "Large decrease"

            if flag:
                flagged.append({
                    'Mainline': mainline,
                    'Conductor System': cs,
                    '2024 Taps': int(t2024),
                    '2025 Taps': int(t2025),
                    '% Change': f"{pct_change:+.1f}%",
                    'Flag': flag,
                })

        if flagged:
            flagged_df = pd.DataFrame(flagged)
            flag_order = {"Missing data (had prior)": 0, "Large decrease": 1, "Large increase": 2, "New line (no prior data)": 3}
            flagged_df['_sort'] = flagged_df['Flag'].map(flag_order)
            flagged_df = flagged_df.sort_values(['_sort', 'Conductor System', 'Mainline']).drop(columns='_sort')

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Flagged", len(flagged_df))
            with col2:
                decreases = len(flagged_df[flagged_df['Flag'].str.contains('decrease|Missing', case=False)])
                st.metric("Decreases / Missing", decreases)
            with col3:
                increases = len(flagged_df[flagged_df['Flag'].str.contains('increase|New', case=False)])
                st.metric("Increases / New", increases)

            st.dataframe(flagged_df, use_container_width=True, hide_index=True,
                         height=min(38 + len(flagged_df) * 36, 500))
        else:
            st.success(f"No mainlines with >{variance_pct}% variance between 2024 and 2025")

    st.divider()

    # ==================================================================
    # SECTION 4: Untracked Taps
    # Taps that appear in TSheets (counted in Tapping Operations totals)
    # but cannot be matched to a mainline in the historical Excel file.
    # Two root causes: (a) blank mainline in TSheets, (b) mainline name
    # doesn't exist in vt_taps_historical.xlsx.
    # ==================================================================
    if has_2026 and personnel_df is not None and not personnel_df.empty:
        st.subheader("🔎 Untracked Taps")
        st.markdown(
            "*TSheets entries with Taps Put In > 0 that are **not** reflected in the "
            "Tap History totals above — either the mainline was left blank or the name "
            "doesn't match the historical file.*"
        )

        mainline_col_u = find_column(personnel_df, 'mainline.', 'mainline', 'Mainline', 'location')
        taps_col_u     = find_column(personnel_df, 'Taps Put In', 'taps_in', 'taps put in')
        date_col_u     = find_column(personnel_df, 'Date', 'date', 'timestamp')
        emp_col_u      = find_column(personnel_df, 'Employee Name', 'employee', 'EE First')
        job_col_u      = find_column(personnel_df, 'Job', 'job', 'Job Code')
        notes_col_u    = find_column(personnel_df, 'Notes', 'notes')

        if mainline_col_u and taps_col_u:
            # Build case-insensitive set of known mainlines
            known_mainlines = set(
                hist_df['mainline'].dropna().astype(str).str.strip().str.lower()
            )
            known_mainlines.discard('')
            known_mainlines.discard('nan')

            untrk = personnel_df.copy()

            # Season filter — same as get_2026_taps
            if date_col_u:
                untrk[date_col_u] = pd.to_datetime(untrk[date_col_u], errors='coerce')
                untrk = untrk[untrk[date_col_u] >= pd.Timestamp('2025-12-01')]

            # Only rows where taps were actually entered
            untrk['_taps'] = pd.to_numeric(untrk[taps_col_u], errors='coerce').fillna(0)
            untrk = untrk[untrk['_taps'] > 0]

            # Normalise mainline for comparison
            untrk['_ml'] = untrk[mainline_col_u].astype(str).str.strip()
            untrk['_ml_low'] = untrk['_ml'].str.lower()

            _blank_vals = {'', 'nan', 'none', 'na', 'n/a'}
            blank_mask   = untrk['_ml_low'].isin(_blank_vals)
            unknown_mask = (~blank_mask) & (~untrk['_ml_low'].isin(known_mainlines))

            blank_df   = untrk[blank_mask].copy()
            unknown_df = untrk[unknown_mask].copy()

            total_untracked_taps = int(blank_df['_taps'].sum() + unknown_df['_taps'].sum())
            total_untracked_rows = len(blank_df) + len(unknown_df)

            # Build a helper to produce a clean display table
            _disp_col_map = {}
            for _c, _lbl in [
                (emp_col_u,      'Employee'),
                (date_col_u,     'Date'),
                (taps_col_u,     'Taps Put In'),
                (mainline_col_u, 'Mainline'),
                (job_col_u,      'Job'),
                (notes_col_u,    'Notes'),
            ]:
                if _c and _c in untrk.columns:
                    _disp_col_map[_c] = _lbl

            def _make_untrk_display(df):
                d = df[[c for c in _disp_col_map]].rename(columns=_disp_col_map).copy()
                if 'Date' in d.columns:
                    d['Date'] = pd.to_datetime(d['Date'], errors='coerce').dt.strftime('%Y-%m-%d')
                if 'Taps Put In' in d.columns:
                    d['Taps Put In'] = d['Taps Put In'].astype(int)
                sort_by = [c for c in ['Date', 'Employee', 'Mainline'] if c in d.columns]
                if sort_by:
                    d = d.sort_values(sort_by)
                return d.reset_index(drop=True)

            if total_untracked_taps > 0:
                st.warning(
                    f"⚠️ **{total_untracked_taps:,} taps** across "
                    f"**{total_untracked_rows} TSheets entr"
                    f"{'y' if total_untracked_rows == 1 else 'ies'}** "
                    f"are counted in Tapping Operations but missing from Tap History. "
                    f"Fix the mainline field in TSheets (or the Manager Review editor) "
                    f"to close the gap."
                )

                tab_blank, tab_unknown = st.tabs([
                    f"🚫 No Mainline Entered  —  "
                    f"{len(blank_df)} {'entry' if len(blank_df) == 1 else 'entries'}, "
                    f"{int(blank_df['_taps'].sum()):,} taps",

                    f"❓ Unrecognised Mainline  —  "
                    f"{len(unknown_df)} {'entry' if len(unknown_df) == 1 else 'entries'}, "
                    f"{int(unknown_df['_taps'].sum()):,} taps",
                ])

                with tab_blank:
                    if blank_df.empty:
                        st.success("No entries with a blank mainline field.")
                    else:
                        st.markdown(
                            "*Worker logged taps in TSheets but left the mainline field empty. "
                            "Ask them to correct it, or fix it in Manager Data Review.*"
                        )
                        st.dataframe(
                            _make_untrk_display(blank_df),
                            use_container_width=True, hide_index=True,
                            height=min(38 + len(blank_df) * 36, 500),
                        )

                with tab_unknown:
                    if unknown_df.empty:
                        st.success("No entries with unrecognised mainline names.")
                    else:
                        st.markdown(
                            "*Mainline name is filled in but doesn't match any row in "
                            "`vt_taps_historical.xlsx`. Common causes: spelling difference, "
                            "extra space, or a brand-new mainline not yet in the Excel file. "
                            "**Edit the Mainline column to fix, then click Save.***"
                        )
                        disp_unk = _make_untrk_display(unknown_df)
                        # Show unique unrecognised names as a quick reference
                        if 'Mainline' in disp_unk.columns:
                            bad_names = (
                                disp_unk.groupby('Mainline')['Taps Put In']
                                .sum().sort_values(ascending=False)
                                .reset_index()
                            )
                            bad_names.columns = ['Mainline (as entered)', 'Total Taps']
                            st.markdown("**Unique unrecognised mainline names:**")
                            st.dataframe(
                                bad_names, use_container_width=True, hide_index=True,
                                height=min(38 + len(bad_names) * 36, 250),
                            )
                        st.markdown("**All entries** *(edit Mainline to correct)*:")
                        # Keep original mainline for change detection
                        disp_unk['_Original Mainline'] = disp_unk['Mainline'].copy()
                        edited_unk = st.data_editor(
                            disp_unk,
                            use_container_width=True, hide_index=True,
                            height=min(38 + len(disp_unk) * 36, 500),
                            key="untracked_editor",
                            column_config={
                                'Mainline': st.column_config.TextColumn('Mainline', help='Edit to correct the mainline name'),
                                'Employee': st.column_config.TextColumn('Employee', disabled=True),
                                'Date': st.column_config.TextColumn('Date', disabled=True),
                                'Taps Put In': st.column_config.NumberColumn('Taps Put In', disabled=True),
                                'Job': st.column_config.TextColumn('Job', disabled=True),
                                'Notes': st.column_config.TextColumn('Notes', disabled=True),
                                '_Original Mainline': None,  # Hidden
                            },
                            column_order=['Employee', 'Date', 'Taps Put In', 'Mainline', 'Job', 'Notes'],
                        )

                        # Save button — write corrected mainlines to approved_personnel
                        changed_rows = edited_unk[
                            edited_unk['Mainline'] != edited_unk['_Original Mainline']
                        ]
                        if not changed_rows.empty:
                            st.info(f"📝 {len(changed_rows)} mainline correction(s) pending.")
                            if st.button("💾 Save Mainline Corrections", key="save_untracked_fixes"):
                                _save_mainline_corrections(
                                    changed_rows, unknown_df, personnel_df,
                                    mainline_col_u, emp_col_u, date_col_u, job_col_u
                                )
            else:
                st.success(
                    "✅ All tapped entries are matched to a known mainline — "
                    "Tap History and Tapping Operations totals are in sync."
                )

    st.divider()

    # ==================================================================
    # SECTION 4b: Duplicate Entry Detection
    # Flags TSheets rows that share the same Employee + Date + Mainline
    # but were entered multiple times (e.g. Howard Palmer / GDW20.3 issue).
    # ==================================================================
    if has_2026 and personnel_df is not None and not personnel_df.empty:
        with st.expander("🔁 Duplicate Entry Detection"):
            st.markdown(
                "*Rows where the same employee logged taps on the same date for the same mainline more than once. "
                "These may be accidental double-entries — confirm with the employee before deleting in TSheets.*"
            )

            mainline_col_d = find_column(personnel_df, 'mainline.', 'mainline', 'Mainline', 'location')
            taps_col_d = find_column(personnel_df, 'Taps Put In', 'taps_in', 'taps put in')
            date_col_d = find_column(personnel_df, 'Date', 'date', 'timestamp')
            emp_col_d = find_column(personnel_df, 'Employee Name', 'employee', 'EE First')
            job_col_d = find_column(personnel_df, 'Job', 'job', 'Job Code')

            clock_in_col_d = find_column(personnel_df, 'Clock In', 'clock_in', 'clock in')

            if all([mainline_col_d, taps_col_d, date_col_d, emp_col_d]):
                dup_df = personnel_df.copy()
                dup_df[date_col_d] = pd.to_datetime(dup_df[date_col_d], errors='coerce')
                dup_df = dup_df[dup_df[date_col_d] >= pd.Timestamp('2025-12-01')]
                dup_df['_taps'] = pd.to_numeric(dup_df[taps_col_d], errors='coerce').fillna(0)
                dup_df = dup_df[dup_df['_taps'] > 0]
                dup_df['_ml'] = dup_df[mainline_col_d].astype(str).str.strip()
                dup_df['_emp'] = dup_df[emp_col_d].astype(str).str.strip()
                dup_df['_date'] = dup_df[date_col_d].dt.date

                # Count occurrences per Employee + Date + Mainline
                key_cols = ['_emp', '_date', '_ml']
                counts = dup_df.groupby(key_cols).size().reset_index(name='_count')
                dup_keys = counts[counts['_count'] > 1]

                if dup_keys.empty:
                    st.success("✅ No duplicate entries detected for this season.")
                else:
                    # Merge back to get full rows
                    dup_rows = dup_df.merge(dup_keys[key_cols], on=key_cols, how='inner')

                    # Build display columns — include Clock In for timestamp disambiguation
                    _dup_col_map = {}
                    for _c, _lbl in [
                        (emp_col_d,      'Employee'),
                        (date_col_d,     'Date'),
                        (clock_in_col_d, 'Clock In'),
                        (mainline_col_d, 'Mainline'),
                        (taps_col_d,     'Taps Put In'),
                        (job_col_d,      'Job'),
                    ]:
                        if _c and _c in dup_rows.columns:
                            _dup_col_map[_c] = _lbl

                    disp_dup = dup_rows[[c for c in _dup_col_map]].rename(columns=_dup_col_map)
                    if 'Date' in disp_dup.columns:
                        disp_dup['Date'] = pd.to_datetime(disp_dup['Date'], errors='coerce').dt.strftime('%Y-%m-%d')
                    if 'Clock In' in disp_dup.columns:
                        disp_dup['Clock In'] = pd.to_datetime(disp_dup['Clock In'], errors='coerce').dt.strftime('%H:%M')
                    if 'Taps Put In' in disp_dup.columns:
                        disp_dup['Taps Put In'] = pd.to_numeric(disp_dup['Taps Put In'], errors='coerce').fillna(0).astype(int)
                    disp_dup = disp_dup.sort_values([c for c in ['Employee', 'Date', 'Mainline'] if c in disp_dup.columns])
                    disp_dup = disp_dup.reset_index(drop=True)

                    # Add editable columns for manager actions
                    disp_dup['Is Duplicate'] = False
                    disp_dup['_Original Mainline'] = disp_dup['Mainline'].copy()

                    st.warning(
                        f"⚠️ Found **{len(dup_keys)} unique Employee/Date/Mainline combinations** with duplicate entries "
                        f"({len(dup_rows)} total rows). Use **Clock In** time to tell real duplicates from split shifts."
                    )
                    st.markdown(
                        "*✅ Check **Is Duplicate** to mark true duplicates. "
                        "Edit **Mainline** to fix wrong entries. Then click **Save**.*"
                    )

                    col_order = ['Is Duplicate', 'Employee', 'Date', 'Clock In', 'Mainline', 'Taps Put In', 'Job']
                    col_order = [c for c in col_order if c in disp_dup.columns]

                    edited_dup = st.data_editor(
                        disp_dup,
                        use_container_width=True, hide_index=True,
                        height=min(38 + len(disp_dup) * 36, 500),
                        key="dup_editor",
                        column_config={
                            'Is Duplicate': st.column_config.CheckboxColumn('Is Duplicate', help='Check if this is a true duplicate to remove'),
                            'Mainline': st.column_config.TextColumn('Mainline', help='Edit to correct the mainline name'),
                            'Employee': st.column_config.TextColumn('Employee', disabled=True),
                            'Date': st.column_config.TextColumn('Date', disabled=True),
                            'Clock In': st.column_config.TextColumn('Clock In', disabled=True),
                            'Taps Put In': st.column_config.NumberColumn('Taps Put In', disabled=True),
                            'Job': st.column_config.TextColumn('Job', disabled=True),
                            '_Original Mainline': None,  # Hidden
                        },
                        column_order=col_order,
                    )

                    # Detect changes
                    marked_dups = edited_dup[edited_dup['Is Duplicate'] == True]
                    fixed_ml = edited_dup[edited_dup['Mainline'] != edited_dup['_Original Mainline']]
                    has_changes = not marked_dups.empty or not fixed_ml.empty

                    if has_changes:
                        parts = []
                        if not marked_dups.empty:
                            parts.append(f"{len(marked_dups)} marked as duplicate")
                        if not fixed_ml.empty:
                            parts.append(f"{len(fixed_ml)} mainline correction(s)")
                        st.info(f"📝 {', '.join(parts)} pending.")

                        if st.button("💾 Save Duplicate Corrections", key="save_dup_fixes"):
                            # Save mainline corrections via approved_personnel
                            if not fixed_ml.empty:
                                _save_mainline_corrections(
                                    fixed_ml, dup_rows, personnel_df,
                                    mainline_col_d, emp_col_d, date_col_d, job_col_d
                                )
                            if not marked_dups.empty:
                                # For true duplicates, save with Taps Put In = 0 to zero them out
                                zeroed = marked_dups.copy()
                                zeroed['Taps Put In'] = 0
                                _save_mainline_corrections(
                                    zeroed, dup_rows, personnel_df,
                                    mainline_col_d, emp_col_d, date_col_d, job_col_d
                                )
            else:
                st.info("Could not find required columns for duplicate detection.")

    st.divider()

    # ==================================================================
    # SECTION 5: Notes
    # ==================================================================
    with st.expander("💡 Understanding This Data"):
        st.markdown("""
        **Data Sources:**
        - **2021-2025:** VT historical tap counts from Excel file (committed to repo)
        - **2026:** Live tapping data from personnel Google Sheet (same data as Tapping Operations page)

        **Conductor Systems:** The 1-4 letter prefix of a mainline name (e.g., DHE05 → DHE).

        **2026 vs 2025 Comparison:**
        - Shows how the current season's tapping compares to last year's final counts
        - **% of 2025** = (2026 taps / 2025 taps) × 100

        **Status Color Codes:**
        - **Black — Not started:** Mainline had taps in 2025 but none in 2026 yet
        - **Red — Significantly less:** Less than 95% of 2025 taps
        - **Yellow — On track:** Within 5% of 2025 taps (95–99% or 101–105%)
        - **Green — On target:** Within 1% of 2025 taps (99–101%)
        - **Purple — Significantly more:** More than 105% of 2025 taps

        **Attention List Filtering:**
        - Conductor systems with zero total 2026 taps are excluded (haven't started tapping yet)
        - Individual mainlines within partially-tapped systems that have zero 2026 taps are shown as "Not started"
        - Example: If DHE has taps in 2026 overall, but DHE08 specifically has zero, DHE08 will appear as "Not started"

        **Data Notes:**
        - If a mainline never had data before 2024/2025, it's a **new line** that was installed
        - If a mainline had taps in 2021-2023 but shows 0 in 2024/2025, it's likely **employee error** (forgot to enter tap count)
        - Mainline names must match between the historical Excel and the live personnel sheet for 2026 comparison to work
        """)
