"""
Tap History Page Module
Historical tap count analysis by conductor system and mainline.
Loads static Excel data (VT 2021-2025) and compares against live 2026 tapping data.
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
    Extract 2026 taps per mainline from live personnel data.
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

    # Filter to rows with actual mainline entries and taps
    df = df[df['_ml'].str.len() > 0]
    df = df[df['_ml'] != 'nan']

    taps_by_ml = df.groupby('_ml')['_taps'].sum()
    return taps_by_ml


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
    has_2026 = len(taps_2026) > 0

    # Merge 2026 taps into historical dataframe
    if has_2026:
        hist_df['2026'] = hist_df['mainline'].map(taps_2026).fillna(0)
    else:
        hist_df['2026'] = 0

    all_years = YEAR_COLS + ['2026'] if has_2026 else YEAR_COLS

    # ==================================================================
    # SECTION 1: 2026 vs 2025 Season Comparison (THE MAIN EVENT)
    # ==================================================================
    st.subheader("🔥 2026 Season vs 2025 Baseline")
    if has_2026:
        st.markdown("*Live tapping data from this season compared to last year's final counts*")
    else:
        st.warning("No 2026 tapping data found in personnel records yet. Showing historical data only.")

    # Conductor system level comparison
    cs_agg = hist_df.groupby('Conductor System')[all_years].sum().reset_index()
    cs_agg[2025] = cs_agg[2025].fillna(0)

    if has_2026:
        cs_agg['2026'] = cs_agg['2026'].fillna(0)
        cs_agg['Diff (26 vs 25)'] = cs_agg['2026'] - cs_agg[2025]
        cs_agg['% of 2025'] = ((cs_agg['2026'] / cs_agg[2025]) * 100).round(1)
        cs_agg['% of 2025'] = cs_agg['% of 2025'].replace([float('inf'), float('-inf')], 0).fillna(0)
        cs_agg['Remaining'] = (cs_agg[2025] - cs_agg['2026']).clip(lower=0)
        cs_agg = cs_agg.sort_values('% of 2025', ascending=True)  # Worst first

        # Top-level metrics
        col1, col2, col3, col4 = st.columns(4)
        total_2025 = cs_agg[2025].sum()
        total_2026 = cs_agg['2026'].sum()
        with col1:
            st.metric("2025 Baseline (VT)", f"{int(total_2025):,}")
        with col2:
            st.metric("2026 Tapped So Far", f"{int(total_2026):,}")
        with col3:
            pct_overall = (total_2026 / total_2025 * 100) if total_2025 > 0 else 0
            st.metric("% Complete vs 2025", f"{pct_overall:.1f}%")
        with col4:
            remaining = max(total_2025 - total_2026, 0)
            st.metric("Remaining to Match 2025", f"{int(remaining):,}")

        # Progress bar
        st.progress(min(pct_overall / 100, 1.0))

        st.divider()

        # Conductor system comparison table
        st.markdown("**By Conductor System** — sorted by % complete (lowest first = needs attention)")
        display_cs = cs_agg[['Conductor System', 2025, '2026', 'Diff (26 vs 25)', '% of 2025', 'Remaining']].copy()
        display_cs = display_cs.rename(columns={2025: '2025'})
        display_cs['2025'] = display_cs['2025'].astype(int)
        display_cs['2026'] = display_cs['2026'].astype(int)
        display_cs['Diff (26 vs 25)'] = display_cs['Diff (26 vs 25)'].astype(int)
        display_cs['Remaining'] = display_cs['Remaining'].astype(int)
        display_cs['% of 2025'] = display_cs['% of 2025'].apply(lambda x: f"{x:.1f}%")

        st.dataframe(display_cs, use_container_width=True, hide_index=True, height=500)

        # Horizontal bar chart: % of 2025 by conductor system
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
            display_cols.append('2026')

        ml_display = cs_data[display_cols].copy()

        if has_2026:
            ml_display['Diff (26 vs 25)'] = (ml_display['2026'].fillna(0) - ml_display[2025].fillna(0)).astype(int)
            ml_display['% of 2025'] = ((ml_display['2026'].fillna(0) / ml_display[2025].fillna(0)) * 100).round(1)
            ml_display['% of 2025'] = ml_display['% of 2025'].replace([float('inf'), float('-inf')], 0).fillna(0)
        else:
            ml_display['Change (24-25)'] = (ml_display[2025].fillna(0) - ml_display[2024].fillna(0)).astype(int)

        # Flag variances
        def _flag_mainline(row):
            t2025 = row[2025] if pd.notna(row[2025]) else 0
            if has_2026:
                t2026 = row.get('2026', 0) if pd.notna(row.get('2026', 0)) else 0
                if t2025 > 0 and t2026 == 0:
                    return "⚠️ Not started"
                if t2025 > 0 and t2026 > 0:
                    pct = t2026 / t2025 * 100
                    if pct < 50:
                        return "🔴 Behind"
                    elif pct < 90:
                        return "🟡 In progress"
                    elif pct < 110:
                        return "🟢 On track"
                    else:
                        return "🔵 Over 2025"
                if t2025 == 0 and t2026 > 0:
                    return "🆕 New tapping"
                return ""
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

        for yr in YEAR_COLS:
            ml_display[yr] = ml_display[yr].fillna(0).astype(int)
        if has_2026:
            ml_display['2026'] = ml_display['2026'].fillna(0).astype(int)
            ml_display['% of 2025'] = ml_display['% of 2025'].apply(lambda x: f"{x:.0f}%")

        ml_display = ml_display.rename(columns={'mainline': 'Mainline'})
        ml_display = ml_display.sort_values('Mainline')

        st.dataframe(ml_display, use_container_width=True, hide_index=True, height=400)

    st.divider()

    # ==================================================================
    # SECTION 3: Variance Flags / Attention List
    # ==================================================================
    if has_2026:
        st.subheader("⚠️ Mainlines Needing Attention")
        st.markdown("*Mainlines that had taps in 2025 but have 0 or very few in 2026 so far*")

        attention = []
        for _, row in hist_df.iterrows():
            mainline = row['mainline']
            cs = row['Conductor System']
            t2025 = row[2025] if pd.notna(row[2025]) else 0
            t2026 = row.get('2026', 0) if pd.notna(row.get('2026', 0)) else 0

            if t2025 <= 0:
                continue

            pct = (t2026 / t2025 * 100) if t2025 > 0 else 0

            flag = None
            if t2026 == 0:
                flag = "Not started"
            elif pct < 50:
                flag = "Significantly behind"

            if flag:
                attention.append({
                    'Mainline': mainline,
                    'Conductor System': cs,
                    '2025 Taps': int(t2025),
                    '2026 Taps': int(t2026),
                    '% of 2025': f"{pct:.0f}%",
                    'Remaining': int(max(t2025 - t2026, 0)),
                    'Status': flag,
                })

        if attention:
            att_df = pd.DataFrame(attention)
            att_df = att_df.sort_values(['Status', 'Remaining'], ascending=[True, False])

            col1, col2, col3 = st.columns(3)
            with col1:
                not_started = len(att_df[att_df['Status'] == 'Not started'])
                st.metric("Not Started", not_started)
            with col2:
                behind = len(att_df[att_df['Status'] == 'Significantly behind'])
                st.metric("Significantly Behind", behind)
            with col3:
                total_remaining = att_df['Remaining'].sum()
                st.metric("Total Taps Remaining", f"{total_remaining:,}")

            st.dataframe(att_df, use_container_width=True, hide_index=True, height=500)
        else:
            st.success("All mainlines with 2025 data are at 50%+ in 2026!")
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
    # SECTION 4: Full Historical View
    # ==================================================================
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
        st.markdown(f"""
        **Data Sources:**
        - **2021-2025:** VT historical tap counts from Excel file (committed to repo)
        - **2026:** Live tapping data from personnel Google Sheet (same data as Tapping Operations page)

        **Conductor Systems:** The 1-4 letter prefix of a mainline name (e.g., DHE05 → DHE).

        **2026 vs 2025 Comparison:**
        - Shows how the current season's tapping compares to last year's final counts
        - **% of 2025** = (2026 taps / 2025 taps) × 100
        - Red/yellow/green coloring shows which systems need the most attention
        - "Not started" = mainline had taps in 2025 but none recorded in 2026 yet
        - "Significantly behind" = less than 50% of 2025's total

        **Data Notes:**
        - If a mainline never had data before 2024/2025, it's a **new line** that was installed
        - If a mainline had taps in 2021-2023 but shows 0 in 2024/2025, it's likely **employee error** (forgot to enter tap count)
        - Variance threshold is **{variance_pct}%** (configurable in config.py)
        - Mainline names must match between the historical Excel and the live personnel sheet for 2026 comparison to work
        """)
