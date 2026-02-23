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
        return "Not started"
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
        'Not started': 'background-color: #1a1a1a; color: white',
        'Significantly less': 'background-color: #dc3545; color: white',
        'On track': 'background-color: #ffc107; color: black',
        'On target': 'background-color: #28a745; color: white',
        'Significantly more': 'background-color: #9b59b6; color: white',
        'New tapping': 'background-color: #17a2b8; color: white',
    }
    return color_map.get(val, '')


# ── Data loaders ───────────────────────────────────────────────────────

@st.cache_data
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
        season_start = pd.Timestamp('2025-12-01')
        df = df[df[date_col] >= season_start]

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
        season_start = pd.Timestamp('2025-12-01')
        df = df[df[date_col] >= season_start]

    # Filter to rows with actual mainline entries
    df = df[df['_ml'].str.len() > 0]
    df = df[df['_ml'] != 'nan']

    taps_del_by_ml = df.groupby('_ml')['_taps_del'].sum()
    return taps_del_by_ml


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
        season_start = pd.Timestamp('2025-12-01')
        df = df[df[date_col] >= season_start]

    # Filter to rows with actual taps > 0
    df = df[df['_ml'].str.len() > 0]
    df = df[df['_ml'] != 'nan']
    df = df[df['_taps'] > 0]

    tappers_by_ml = df.groupby('_ml')['_emp'].apply(
        lambda names: ', '.join(sorted(names.unique()))
    )
    return tappers_by_ml


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
    tappers_2026 = get_2026_tappers(personnel_df)
    has_2026 = len(taps_2026) > 0

    # Merge 2026 taps into historical dataframe
    if has_2026:
        hist_df['2026'] = hist_df['mainline'].map(taps_2026).fillna(0)
        hist_df['2026 Deleted'] = hist_df['mainline'].map(taps_2026_del).fillna(0)
    else:
        hist_df['2026'] = 0
        hist_df['2026 Deleted'] = 0

    all_years = YEAR_COLS + ['2026'] if has_2026 else YEAR_COLS
    agg_years = all_years + (['2026 Deleted'] if has_2026 else [])

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
        # Net taps = put in minus deleted
        cs_agg['Net 2026'] = cs_agg['2026'] - cs_agg['2026 Deleted']
        cs_agg['Diff (26 vs 25)'] = cs_agg['Net 2026'] - cs_agg[2025]
        cs_agg['% of 2025'] = ((cs_agg['Net 2026'] / cs_agg[2025]) * 100).round(1)
        cs_agg['% of 2025'] = cs_agg['% of 2025'].replace([float('inf'), float('-inf')], 0).fillna(0)
        # Remaining accounts for deletions: need (2025 target - net taps) more
        cs_agg['Remaining'] = (cs_agg[2025] - cs_agg['Net 2026']).clip(lower=0)
        cs_agg = cs_agg.sort_values('% of 2025', ascending=True)  # Worst first

        # Top-level metrics
        total_2025 = cs_agg[2025].sum()
        total_2026 = cs_agg['2026'].sum()
        total_2026_del = cs_agg['2026 Deleted'].sum()
        total_net = cs_agg['Net 2026'].sum()

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("2025 Baseline (VT)", f"{int(total_2025):,}")
        with col2:
            st.metric("2026 Tapped", f"{int(total_2026):,}")
        with col3:
            st.metric("2026 Deleted", f"{int(total_2026_del):,}")
        with col4:
            pct_overall = (total_net / total_2025 * 100) if total_2025 > 0 else 0
            st.metric("% Complete (Net)", f"{pct_overall:.1f}%")
        with col5:
            remaining = max(total_2025 - total_net, 0)
            st.metric("Remaining to Match", f"{int(remaining):,}")

        # Progress bar
        st.progress(min(pct_overall / 100, 1.0))

        st.divider()

        # Conductor system comparison table
        st.markdown("**By Conductor System** — sorted by % complete (lowest first = needs attention)")
        display_cs = cs_agg[['Conductor System', 2025, '2026', '2026 Deleted', 'Net 2026',
                             'Diff (26 vs 25)', '% of 2025', 'Remaining']].copy()
        display_cs = display_cs.rename(columns={2025: '2025'})
        for int_col in ['2025', '2026', '2026 Deleted', 'Net 2026', 'Diff (26 vs 25)', 'Remaining']:
            display_cs[int_col] = display_cs[int_col].astype(int)
        display_cs['% of 2025'] = display_cs['% of 2025'].apply(lambda x: f"{x:.1f}%")

        st.dataframe(display_cs, use_container_width=True, hide_index=True, height=500)

        # Horizontal bar chart: % of 2025 by conductor system (uses Net 2026)
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

        st.dataframe(display_cs, use_container_width=True, hide_index=True, height=500)

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
            display_cols.extend(['2026', '2026 Deleted'])

        ml_display = cs_data[display_cols].copy()

        if has_2026:
            ml_display['2026 Deleted'] = ml_display['2026 Deleted'].fillna(0)
            ml_display['Net 2026'] = ml_display['2026'].fillna(0) - ml_display['2026 Deleted']
            ml_display['Diff (26 vs 25)'] = (ml_display['Net 2026'] - ml_display[2025].fillna(0)).astype(int)
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

        ml_display['Status'] = cs_data.apply(_flag_mainline, axis=1)

        # Add tappers column
        if has_2026:
            ml_display['Tappers (2026)'] = cs_data['mainline'].map(tappers_2026).fillna('')

        for yr in YEAR_COLS:
            ml_display[yr] = ml_display[yr].fillna(0).astype(int)
        if has_2026:
            ml_display['2026'] = ml_display['2026'].fillna(0).astype(int)
            ml_display['2026 Deleted'] = ml_display['2026 Deleted'].astype(int)
            ml_display['Net 2026'] = ml_display['Net 2026'].astype(int)
            ml_display['% of 2025'] = ml_display['% of 2025'].apply(lambda x: f"{x:.0f}%")

        ml_display = ml_display.rename(columns={'mainline': 'Mainline'})
        ml_display = ml_display.sort_values('Mainline')

        # Reorder columns for clarity
        if has_2026:
            col_order = ['Mainline'] + [yr for yr in YEAR_COLS] + [
                '2026', '2026 Deleted', 'Net 2026', 'Diff (26 vs 25)',
                '% of 2025', 'Tappers (2026)', 'Status'
            ]
            ml_display = ml_display[[c for c in col_order if c in ml_display.columns]]

        # Apply color-coded styling to Status column
        if has_2026 and 'Status' in ml_display.columns:
            styled_ml = ml_display.style.map(_color_status, subset=['Status'])
            st.dataframe(styled_ml, use_container_width=True, hide_index=True, height=400)
        else:
            st.dataframe(ml_display, use_container_width=True, hide_index=True, height=400)

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
                'Net 2026': int(net_2026),
                '% of 2025': f"{pct:.0f}%",
                'Remaining': int(max(t2025 - net_2026, 0)),
                'Status': status,
            })

        if attention:
            att_df = pd.DataFrame(attention)

            # Sort by status priority (worst first), then by Remaining descending
            status_order = {
                'Not started': 0,
                'Significantly less': 1,
                'On track': 2,
                'On target': 3,
                'Significantly more': 4,
            }
            att_df['_sort'] = att_df['Status'].map(status_order).fillna(5)
            att_df = att_df.sort_values(['_sort', 'Remaining'], ascending=[True, False]).drop(columns='_sort')

            # Summary metrics by status
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                not_started = len(att_df[att_df['Status'] == 'Not started'])
                st.metric("Not Started", not_started)
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
            st.dataframe(styled_att, use_container_width=True, hide_index=True, height=500)
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

            st.dataframe(flagged_df, use_container_width=True, hide_index=True, height=500)
        else:
            st.success(f"No mainlines with >{variance_pct}% variance between 2024 and 2025")

    st.divider()

    # ==================================================================
    # SECTION 4: Full Historical View (now includes 2026 + % of 2026)
    # ==================================================================
    if has_2026:
        with st.expander("📊 Full Historical Data (2021-2026)"):
            agg_cols = YEAR_COLS + ['2026']
            full_cs = hist_df.groupby('Conductor System')[agg_cols].sum().reset_index()
            full_cs['Change (25-26)'] = full_cs['2026'] - full_cs[2025]
            full_cs = full_cs.sort_values('Conductor System')

            for yr in YEAR_COLS:
                full_cs[yr] = full_cs[yr].fillna(0).astype(int)
            full_cs['2026'] = full_cs['2026'].fillna(0).astype(int)
            full_cs['Change (25-26)'] = full_cs['Change (25-26)'].fillna(0).astype(int)

            # Build display with "% of 2026" interleaved after each historical year
            display_data = full_cs[['Conductor System']].copy()
            for yr in YEAR_COLS:
                display_data[str(yr)] = full_cs[yr]
                pct_col = f'% 2026'
                pct_vals = ((full_cs[yr] / full_cs['2026']) * 100).round(0)
                pct_vals = pct_vals.replace([float('inf'), float('-inf')], 0).fillna(0)
                display_data[f'{yr} % of 2026'] = pct_vals.astype(int).astype(str) + '%'
            display_data['2026'] = full_cs['2026']
            display_data['Change (25-26)'] = full_cs['Change (25-26)']

            st.dataframe(display_data, use_container_width=True, hide_index=True)
    else:
        with st.expander("📊 Full Historical Data (2021-2025)"):
            full_cs = hist_df.groupby('Conductor System')[YEAR_COLS].sum().reset_index()
            full_cs['Change (24-25)'] = full_cs[2025] - full_cs[2024]
            full_cs = full_cs.sort_values(2025, ascending=False)
            for yr in YEAR_COLS:
                full_cs[yr] = full_cs[yr].fillna(0).astype(int)
            full_cs['Change (24-25)'] = full_cs['Change (24-25)'].fillna(0).astype(int)
            st.dataframe(full_cs, use_container_width=True, hide_index=True)

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
