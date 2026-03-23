"""
Mainlines Needing Attention — Standalone Page

Shows mainlines within *active* conductor systems (≥1 tap in 2026)
that either:
  • Have NO 2026 data at all (tapped in 2025 but zero in 2026)
  • Are SIGNIFICANTLY LESS than 2025 (<95%)

If a conductor system hasn't started tapping at all, its mainlines
are excluded — no point flagging lines we haven't gotten to yet.
"""

import streamlit as st
import pandas as pd
import os
import config
from utils import find_column, extract_conductor_system


# Year columns in the historical data
YEAR_COLS = [2021, 2022, 2023, 2024, 2025]


# ── Status helpers ─────────────────────────────────────────────────────

def _classify_status(t2025, t2026):
    """5-tier status (same as tap_history)."""
    if t2025 > 0 and t2026 == 0:
        return "No 2026 data"
    if t2025 == 0 and t2026 > 0:
        return "New tapping"
    if t2025 == 0 and t2026 == 0:
        return ""
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
    """CSS for status cell."""
    color_map = {
        'No 2026 data': 'background-color: #1a1a1a; color: white',
        'Significantly less': 'background-color: #dc3545; color: white',
        'On track': 'background-color: #ffc107; color: black',
        'On target': 'background-color: #28a745; color: white',
        'Significantly more': 'background-color: #9b59b6; color: white',
        'New tapping': 'background-color: #17a2b8; color: white',
    }
    return color_map.get(val, '')


# ── Data loaders (shared with tap_history) ─────────────────────────────

@st.cache_data(ttl=3600)
def _load_historical_taps():
    """Load VT historical tap data from the committed Excel file."""
    possible_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'vt_taps_historical.xlsx'),
        'data/vt_taps_historical.xlsx',
    ]
    for path in possible_paths:
        if os.path.exists(path):
            df = pd.read_excel(path)
            df = df.dropna(subset=['mainline'])
            df['mainline'] = df['mainline'].str.replace(r'^GBW', 'GDW', regex=True)
            df['Conductor System'] = df['mainline'].apply(extract_conductor_system)
            for yr in YEAR_COLS:
                if yr in df.columns:
                    df[yr] = pd.to_numeric(df[yr], errors='coerce').fillna(0)
            return df
    return pd.DataFrame()


def _get_2026_taps(personnel_df):
    """Extract 2026 taps-put-in from live personnel data, grouped by mainline."""
    if personnel_df is None or personnel_df.empty:
        return {}

    mainline_col = find_column(personnel_df, 'mainline.', 'mainline', 'Mainline', 'location')
    taps_col = find_column(personnel_df, 'Taps Put In', 'taps_in', 'taps put in')
    date_col = find_column(personnel_df, 'Date', 'date', 'timestamp')

    if not all([mainline_col, taps_col]):
        return {}

    p = personnel_df.copy()
    if date_col:
        p[date_col] = pd.to_datetime(p[date_col], errors='coerce')
        p = p[p[date_col] >= pd.Timestamp('2025-12-01')]

    p['_taps'] = pd.to_numeric(p[taps_col], errors='coerce').fillna(0)
    p['_ml'] = p[mainline_col].astype(str).str.strip()

    grouped = p.groupby('_ml')['_taps'].sum()
    return grouped.to_dict()


def _get_2026_taps_deleted(personnel_df):
    """Extract 2026 deleted taps from live personnel data, grouped by mainline."""
    if personnel_df is None or personnel_df.empty:
        return {}

    mainline_col = find_column(personnel_df, 'mainline.', 'mainline', 'Mainline', 'location')
    del_col = find_column(personnel_df, 'Taps Removed', 'taps removed', 'taps_removed')
    date_col = find_column(personnel_df, 'Date', 'date', 'timestamp')

    if not all([mainline_col, del_col]):
        return {}

    p = personnel_df.copy()
    if date_col:
        p[date_col] = pd.to_datetime(p[date_col], errors='coerce')
        p = p[p[date_col] >= pd.Timestamp('2025-12-01')]

    p['_del'] = pd.to_numeric(p[del_col], errors='coerce').fillna(0)
    p['_ml'] = p[mainline_col].astype(str).str.strip()

    grouped = p.groupby('_ml')['_del'].sum()
    return grouped.to_dict()


# ── Main render ────────────────────────────────────────────────────────

def render(personnel_df=None, vacuum_df=None):
    """Render Mainlines Needing Attention page."""

    st.title("⚠️ Mainlines Needing Attention")
    st.markdown(
        "*Mainlines within **active** conductor systems (where tapping has started) "
        "that have **No 2026 data** or are **Significantly less** (<95%) compared to 2025.*"
    )

    hist_df = _load_historical_taps()
    if hist_df.empty:
        st.warning("Could not load historical tap data.")
        return

    # Merge 2026 live data
    taps_2026 = _get_2026_taps(personnel_df)
    deleted_2026 = _get_2026_taps_deleted(personnel_df)

    if not taps_2026:
        st.info("No 2026 tapping data available yet.")
        return

    hist_df['2026'] = hist_df['mainline'].map(
        lambda ml: taps_2026.get(ml, 0)
    ).fillna(0)
    hist_df['2026 Deleted'] = hist_df['mainline'].map(
        lambda ml: deleted_2026.get(ml, 0)
    ).fillna(0)

    # Identify active conductor systems (any 2026 taps at all)
    cs_2026_totals = hist_df.groupby('Conductor System')['2026'].sum()
    active_conductor_systems = set(cs_2026_totals[cs_2026_totals > 0].index)

    if not active_conductor_systems:
        st.info("No conductor systems have started tapping in 2026 yet.")
        return

    # Build attention list
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

        # Skip conductor systems that haven't started tapping
        if cs not in active_conductor_systems:
            continue

        status = _classify_status(t2025, net_2026)

        # Only show mainlines that NEED ATTENTION:
        # "No 2026 data" = not started within an active conductor
        # "Significantly less" = started but well below 2025 baseline
        if status not in ('No 2026 data', 'Significantly less'):
            continue

        pct = (net_2026 / t2025 * 100) if t2025 > 0 else 0

        attention.append({
            'Mainline': mainline,
            'Conductor System': cs,
            '2025 Taps': int(t2025),
            '2026 Taps': int(t2026),
            'Net 2026': int(net_2026),
            '% of 2025': f"{pct:.0f}%",
            'Remaining': int(max(t2025 - net_2026, 0)),
            'Status': status,
        })

    if not attention:
        st.success("🎉 All mainlines in active conductor systems are on track or better!")
        return

    att_df = pd.DataFrame(attention)

    # Sort: "No 2026 data" first, then "Significantly less", then by remaining desc
    status_order = {'No 2026 data': 0, 'Significantly less': 1}
    att_df['_sort'] = att_df['Status'].map(status_order).fillna(5)
    att_df = att_df.sort_values(['_sort', 'Remaining'], ascending=[True, False]).drop(columns='_sort')

    # ── Conductor system filter ──────────────────────────────────
    active_in_attention = sorted(att_df['Conductor System'].unique())
    filter_col1, filter_col2 = st.columns([1, 2])
    with filter_col1:
        cs_filter = st.selectbox(
            "Filter by Conductor System",
            ["All"] + active_in_attention,
            key="attn_cs_filter"
        )
    if cs_filter != "All":
        att_df = att_df[att_df['Conductor System'] == cs_filter].copy()

    # ── Let managers hide resolved mainlines ─────────────────────
    _hide_key = "attn_page_hidden"
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

    # ── Summary metrics ──────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        no_data_ct = len(att_df[att_df['Status'] == 'No 2026 data'])
        st.metric("🔴 No 2026 Data", no_data_ct)
    with col2:
        sig_less_ct = len(att_df[att_df['Status'] == 'Significantly less'])
        st.metric("🟡 Significantly Less", sig_less_ct)
    with col3:
        total_remaining = att_df['Remaining'].sum()
        st.metric("Total Taps Remaining", f"{total_remaining:,}")

    st.divider()

    # ── Conductor system breakdown ───────────────────────────────
    cs_summary = att_df.groupby('Conductor System').agg(
        Lines=('Mainline', 'count'),
        Remaining=('Remaining', 'sum'),
    ).sort_values('Remaining', ascending=False).reset_index()
    cs_summary.columns = ['Conductor System', 'Lines Needing Attention', 'Taps Remaining']

    st.markdown("**By Conductor System:**")
    st.dataframe(cs_summary, use_container_width=True, hide_index=True,
                 height=min(38 + len(cs_summary) * 36, 300))

    st.divider()

    # ── Full attention table ─────────────────────────────────────
    st.markdown("**All Mainlines Needing Attention:**")
    styled_att = att_df.style.map(_color_status, subset=['Status'])
    st.dataframe(styled_att, use_container_width=True, hide_index=True,
                 height=min(38 + len(att_df) * 36, 600))

    # ── Info note ────────────────────────────────────────────────
    with st.expander("💡 How this works"):
        st.markdown("""
        **Active conductor systems** = any system where ≥1 mainline has 2026 taps.

        **No 2026 data** = mainline had taps in 2025 but zero recorded in 2026.
        This usually means we haven't gotten to it yet, or a data entry issue
        (wrong mainline name in TSheets).

        **Significantly less** = mainline has 2026 taps but < 95% of 2025 baseline.
        Could indicate incomplete tapping or data not recorded properly.

        Conductor systems with *zero* 2026 activity are excluded — we haven't
        started those yet, so they don't need attention.
        """)
