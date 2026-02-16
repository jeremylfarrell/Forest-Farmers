"""
Tap History Page Module
Historical tap count analysis by conductor system and mainline.
Loads static Excel data (VT 2021-2025) and shows trends, variance flags.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import config
from utils import extract_conductor_system


# Year columns in the data
YEAR_COLS = [2021, 2022, 2023, 2024, 2025]


@st.cache_data
def load_historical_taps():
    """Load VT historical tap data from the committed Excel file."""
    # Try multiple paths (local dev vs Streamlit Cloud)
    possible_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'vt_taps_historical.xlsx'),
        'data/vt_taps_historical.xlsx',
    ]
    for path in possible_paths:
        if os.path.exists(path):
            df = pd.read_excel(path)
            df = df.dropna(subset=['mainline'])
            # Extract conductor system
            df['Conductor System'] = df['mainline'].apply(extract_conductor_system)
            # Ensure year columns are numeric
            for yr in YEAR_COLS:
                if yr in df.columns:
                    df[yr] = pd.to_numeric(df[yr], errors='coerce')
            return df
    return pd.DataFrame()


def render(personnel_df=None, vacuum_df=None):
    """Render tap history analysis page."""

    st.title("📈 Tap History — VT")
    st.markdown("*Historical tap counts by conductor system and mainline (2021-2025)*")

    df = load_historical_taps()
    if df.empty:
        st.error("Could not load historical tap data. Ensure `data/vt_taps_historical.xlsx` exists.")
        return

    variance_pct = getattr(config, 'VARIANCE_THRESHOLD', 20)

    # ==================================================================
    # SECTION 1: Conductor System Overview
    # ==================================================================
    st.subheader("Conductor System Overview")

    # Aggregate by conductor system
    cs_agg = df.groupby('Conductor System')[YEAR_COLS].sum().reset_index()

    # Calculate change columns
    cs_agg['Change (24-25)'] = cs_agg[2025] - cs_agg[2024]
    cs_agg['% Change'] = ((cs_agg['Change (24-25)'] / cs_agg[2024]) * 100).round(1)
    cs_agg['% Change'] = cs_agg['% Change'].replace([float('inf'), float('-inf')], 0).fillna(0)

    cs_agg = cs_agg.sort_values(2025, ascending=False)

    # Display table
    display_cs = cs_agg.copy()
    for yr in YEAR_COLS:
        display_cs[yr] = display_cs[yr].fillna(0).astype(int)
    display_cs['Change (24-25)'] = display_cs['Change (24-25)'].fillna(0).astype(int)
    display_cs['% Change'] = display_cs['% Change'].apply(lambda x: f"{x:+.1f}%")

    st.dataframe(display_cs, use_container_width=True, hide_index=True, height=500)

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Conductor Systems", len(cs_agg))
    with col2:
        st.metric("Total Mainlines", len(df))
    with col3:
        total_2025 = cs_agg[2025].sum()
        st.metric("Total Taps (2025)", f"{int(total_2025):,}")
    with col4:
        total_2024 = cs_agg[2024].sum()
        overall_change = total_2025 - total_2024
        st.metric("Net Change (24-25)", f"{int(overall_change):+,}")

    # Bar chart of 2025 taps by conductor system
    fig_bar = px.bar(
        cs_agg.sort_values(2025, ascending=True),
        x=2025, y='Conductor System',
        orientation='h',
        title='Total Taps by Conductor System (2025)',
        labels={2025: 'Taps', 'Conductor System': ''},
        color=2025,
        color_continuous_scale='Greens',
    )
    fig_bar.update_layout(height=max(400, len(cs_agg) * 25), showlegend=False)
    st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()

    # ==================================================================
    # SECTION 2: Conductor System Detail
    # ==================================================================
    st.subheader("Conductor System Detail")

    selected_cs = st.selectbox(
        "Select Conductor System",
        sorted(df['Conductor System'].unique()),
        key='tap_history_cs'
    )

    if selected_cs:
        cs_data = df[df['Conductor System'] == selected_cs].copy()

        # Line chart: total taps per year for this system
        yearly_totals = cs_data[YEAR_COLS].sum()
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=[str(y) for y in YEAR_COLS],
            y=yearly_totals.values,
            mode='lines+markers+text',
            text=[f"{int(v):,}" for v in yearly_totals.values],
            textposition='top center',
            marker=dict(size=10),
            line=dict(width=3, color='#28a745'),
        ))
        fig_line.update_layout(
            title=f'{selected_cs} — Total Taps Over Time',
            xaxis_title='Year',
            yaxis_title='Total Taps',
            height=350,
        )
        st.plotly_chart(fig_line, use_container_width=True)

        # Mainline detail table
        ml_display = cs_data[['mainline'] + YEAR_COLS].copy()
        ml_display['Change (24-25)'] = (ml_display[2025].fillna(0) - ml_display[2024].fillna(0)).astype(int)

        # Flag variances
        def _flag_mainline(row):
            t2024 = row[2024] if pd.notna(row[2024]) else 0
            t2025 = row[2025] if pd.notna(row[2025]) else 0
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

        ml_display['Flag'] = cs_data.apply(_flag_mainline, axis=1)

        for yr in YEAR_COLS:
            ml_display[yr] = ml_display[yr].fillna(0).astype(int)

        ml_display = ml_display.rename(columns={'mainline': 'Mainline'})
        ml_display = ml_display.sort_values('Mainline')

        st.dataframe(ml_display, use_container_width=True, hide_index=True, height=400)

    st.divider()

    # ==================================================================
    # SECTION 3: Variance Flags for Recount
    # ==================================================================
    st.subheader(f"Variance Flags (>{variance_pct}% change)")
    st.markdown(f"*Mainlines where 2025 taps differ from 2024 by more than {variance_pct}% — candidates for recount in 2026*")

    flagged = []
    for _, row in df.iterrows():
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
        # Sort: missing data first, then large decreases, then increases, then new
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
    # SECTION 4: Notes
    # ==================================================================
    with st.expander("Understanding This Data"):
        st.markdown(f"""
        **Data Source:** VT historical tap counts (2021-2025) from Excel file.

        **Conductor Systems:** The 1-4 letter prefix of a mainline name (e.g., DHE05 -> DHE).

        **Interpreting Changes:**
        - If a mainline never had data before 2024/2025, it's a **new line** that was installed.
        - If a mainline had taps in 2021-2023 but shows 0 in 2024/2025, it's likely **employee error** (forgot to enter tap count), not an actual removal.
        - The variance threshold is set to **{variance_pct}%** — mainlines exceeding this are flagged for potential recount.

        **Using Variance Flags:**
        - **Large decrease:** May need recount — could be data entry error or actual line removal.
        - **Large increase:** Usually legit (line expansion), but verify if numbers seem too high.
        - **Missing data:** Mainline had taps before but shows 0 — almost certainly employee error.
        - **New line:** First time this mainline appears — verify it's a real new installation.

        **Tips:**
        - Use the Conductor System Detail view to see all mainlines in a system.
        - Compare 2025 vs 2024 to catch data entry issues early.
        - Flag list can be exported and used as a recount checklist for 2026 season.
        """)
