"""
Freezing Report Page Module
Per-conductor system freeze analysis with zero-vacuum priority ranking,
24-hour vacuum charts, tap counts, and PDF export for field crews.
"""

import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime, timedelta

import config
from utils import (
    find_column, get_vacuum_column, extract_conductor_system
)
from utils.helpers import get_releaser_column
from utils.freeze_thaw import get_current_freeze_thaw_status, render_freeze_thaw_banner


def render(vacuum_df, personnel_df):
    """Render the Freezing Report page."""

    st.title("🧊 Freezing Report")

    # Freeze/thaw context banner
    freeze_status = get_current_freeze_thaw_status()
    render_freeze_thaw_banner(freeze_status)

    st.markdown(
        "*Per-conductor system analysis of frozen and critical lines. "
        "Download a PDF per conductor system for field crews.*"
    )

    if vacuum_df.empty:
        st.warning("No vacuum data available.")
        return

    # ── Detect columns ───────────────────────────────────────────────
    sensor_col = find_column(vacuum_df, 'Name', 'name', 'Sensor Name', 'sensor')
    vacuum_col = get_vacuum_column(vacuum_df)
    releaser_col = get_releaser_column(vacuum_df)
    timestamp_col = find_column(
        vacuum_df, 'Last communication', 'Last Communication',
        'Timestamp', 'timestamp'
    )

    if not all([sensor_col, vacuum_col, timestamp_col]):
        st.error("Missing required columns (sensor name, vacuum, timestamp).")
        return

    # ── Prepare data ─────────────────────────────────────────────────
    vdf = vacuum_df.copy()
    vdf[timestamp_col] = pd.to_datetime(vdf[timestamp_col], errors='coerce')
    vdf = vdf.dropna(subset=[timestamp_col])
    vdf[vacuum_col] = pd.to_numeric(vdf[vacuum_col], errors='coerce')
    if releaser_col:
        vdf[releaser_col] = pd.to_numeric(vdf[releaser_col], errors='coerce')

    # Filter to valid maple sensors (2+ uppercase letters + number)
    valid_pattern = r'^[A-Z]{2,6}\d'
    vdf = vdf[vdf[sensor_col].str.match(valid_pattern, na=False)]

    # Exclude non-maple sensors (birch, relays, typos)
    vdf = vdf[~vdf[sensor_col].apply(config.is_excluded_sensor)]

    if vdf.empty:
        st.warning("No valid sensor data found.")
        return

    # Add conductor system
    vdf['Conductor'] = vdf[sensor_col].apply(extract_conductor_system)

    # Get latest reading per sensor
    latest = vdf.sort_values(timestamp_col, ascending=False).groupby(sensor_col).first().reset_index()

    # ── Identify frozen / critical lines ────────────────────────────
    # A sensor "went to zero" if its latest vacuum reading = 0
    # and its releaser differential > 0 (meaning pump is on but line frozen)
    def _classify_freeze(row):
        vac = row[vacuum_col]
        rel = row[releaser_col] if releaser_col else 0
        if pd.isna(vac):
            return 'No Data'
        if vac <= 0.01:
            if releaser_col and pd.notna(rel) and rel <= 0.01:
                return 'OFF'
            return 'FROZEN'
        if releaser_col and pd.notna(rel):
            _, label = config.get_releaser_diff_color(vac, rel)
            return label
        return 'OK'

    latest['Freeze_Status'] = latest.apply(_classify_freeze, axis=1)
    latest['Conductor'] = latest[sensor_col].apply(extract_conductor_system)

    # Find when each sensor first went to zero (freeze order ranking)
    # Look at all data — find the earliest timestamp where vacuum = 0
    zero_times = vdf[vdf[vacuum_col] <= 0.01].groupby(sensor_col)[timestamp_col].min().reset_index()
    zero_times.columns = ['Sensor', 'First_Zero_Time']
    latest = latest.merge(zero_times, left_on=sensor_col, right_on='Sensor', how='left')

    # Add freeze rank: sensors that went to zero first get rank 1
    frozen_sensors = latest[latest['Freeze_Status'] == 'FROZEN'].copy()
    if not frozen_sensors.empty:
        frozen_sensors = frozen_sensors.sort_values('First_Zero_Time', ascending=True)
        frozen_sensors['Freeze_Rank'] = range(1, len(frozen_sensors) + 1)
        latest = latest.merge(
            frozen_sensors[[sensor_col, 'Freeze_Rank']],
            on=sensor_col, how='left'
        )
    else:
        latest['Freeze_Rank'] = None

    # ── Get tap counts from personnel data ──────────────────────────
    taps_per_sensor = {}
    if not personnel_df.empty:
        mainline_col = None
        for c in personnel_df.columns:
            if 'mainline' in c.lower():
                mainline_col = c
                break
        taps_col = None
        for c in personnel_df.columns:
            if 'taps put in' in c.lower():
                taps_col = c
                break
        if mainline_col and taps_col:
            tap_agg = personnel_df.groupby(mainline_col)[taps_col].sum()
            for mainline, total in tap_agg.items():
                if pd.notna(mainline) and total > 0:
                    taps_per_sensor[str(mainline).strip().upper()] = int(total)

    latest['Taps'] = latest[sensor_col].apply(
        lambda s: taps_per_sensor.get(str(s).strip().upper(), 0)
    )

    # Add Sugarbush
    latest['Sugarbush'] = latest['Conductor'].apply(config.get_sugarbush)

    # ── Summary metrics ─────────────────────────────────────────────
    frozen_count = len(latest[latest['Freeze_Status'] == 'FROZEN'])
    critical_count = len(latest[latest['Freeze_Status'] == 'Critical'])
    off_count = len(latest[latest['Freeze_Status'] == 'OFF'])
    total_sensors = len(latest)

    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        st.metric("🔴 FROZEN", frozen_count)
    with mc2:
        st.metric("🩷 Critical", critical_count)
    with mc3:
        st.metric("⚫ Pump Off", off_count)
    with mc4:
        st.metric("Total Sensors", total_sensors)

    st.divider()

    # ── Per-conductor system reports ────────────────────────────────
    conductors = sorted(latest['Conductor'].unique())

    if not conductors:
        st.info("No conductor systems found.")
        return

    # Build selector with sugarbush grouping
    conductor_options = ["Overview (All)"]
    for bush_name, bush_conds in config.SUGARBUSH_MAP.items():
        matching = [c for c in conductors if c in bush_conds]
        if matching:
            for c in sorted(matching):
                conductor_options.append(f"{bush_name} — {c}")
    # Add any conductors not in sugarbush map
    mapped = set()
    for bush_conds in config.SUGARBUSH_MAP.values():
        mapped.update(bush_conds)
    for c in conductors:
        if c not in mapped:
            conductor_options.append(f"Other — {c}")

    selected = st.selectbox(
        "Conductor System",
        conductor_options,
        key="freeze_report_conductor_select"
    )

    if selected == "Overview (All)":
        _render_overview(latest, conductors, sensor_col, vacuum_col, releaser_col, timestamp_col, vdf)
    else:
        # Parse "Sugarbush — Conductor" format
        conductor_name = selected.split(" — ")[-1].strip()
        _render_conductor_report(
            conductor_name, latest, sensor_col, vacuum_col, releaser_col,
            timestamp_col, vdf, personnel_df
        )


def _render_overview(latest, conductors, sensor_col, vacuum_col, releaser_col, timestamp_col, vdf):
    """Render the overview of all conductor systems."""

    st.subheader("Conductor System Overview")

    # Build summary per conductor
    rows = []
    for cond in conductors:
        cdf = latest[latest['Conductor'] == cond]
        frozen = len(cdf[cdf['Freeze_Status'] == 'FROZEN'])
        critical = len(cdf[cdf['Freeze_Status'] == 'Critical'])
        total = len(cdf)
        total_taps = cdf['Taps'].sum()
        sugarbush = config.get_sugarbush(cond)
        rows.append({
            'Sugarbush': sugarbush,
            'Conductor': cond,
            'Total Lines': total,
            'Frozen': frozen,
            'Critical (>10")': critical,
            'Priority Lines': frozen + critical,
            'Total Taps': total_taps,
        })

    overview_df = pd.DataFrame(rows)
    overview_df = overview_df.sort_values(['Sugarbush', 'Priority Lines'], ascending=[True, False])

    # Highlight rows with frozen/critical
    def _highlight_row(row):
        if row['Frozen'] > 0:
            return ['background-color: #ffcccc'] * len(row)
        elif row['Critical (>10")'] > 0:
            return ['background-color: #fff3cd'] * len(row)
        return [''] * len(row)

    st.dataframe(
        overview_df.style.apply(_highlight_row, axis=1),
        use_container_width=True, hide_index=True
    )


def _render_conductor_report(conductor, latest, sensor_col, vacuum_col,
                              releaser_col, timestamp_col, vdf, personnel_df):
    """Render detailed report for a single conductor system."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    cdf = latest[latest['Conductor'] == conductor].copy()

    if cdf.empty:
        st.info(f"No sensors found for conductor {conductor}")
        return

    st.subheader(f"Conductor System: {conductor}")

    # Sort: FROZEN first (by freeze rank), then by releaser diff descending
    status_order = {'FROZEN': 0, 'Critical': 1, 'Elevated': 2, 'Moderate': 3,
                    'Acceptable': 4, 'Good': 5, 'Excellent': 6, 'OFF': 7, 'No Data': 8}
    cdf['_sort'] = cdf['Freeze_Status'].map(status_order).fillna(9)
    cdf = cdf.sort_values(['_sort', 'Freeze_Rank'], ascending=[True, True])

    # Priority table — only lines where vacuum is near-zero (FROZEN) or
    # the releaser differential is critically high (>10").
    # Exclude sensors that have healthy vacuum but happen to have a moderate diff.
    priority_lines = cdf[cdf['Freeze_Status'].isin(['FROZEN', 'Critical'])].copy()

    if not priority_lines.empty:
        st.markdown("### Priority Lines")

        display = priority_lines[[sensor_col, 'Freeze_Status', 'Freeze_Rank', 'Taps']].copy()
        if releaser_col:
            display['Rel_Diff'] = priority_lines[releaser_col].apply(
                lambda x: f'{x:.1f}"' if pd.notna(x) else 'N/A'
            )
        display['Vacuum'] = priority_lines[vacuum_col].apply(
            lambda x: f'{x:.1f}"' if pd.notna(x) else 'N/A'
        )
        display['First_Zero'] = priority_lines['First_Zero_Time'].apply(
            lambda x: x.strftime('%m/%d %H:%M') if pd.notna(x) else ''
        )

        col_map = {sensor_col: 'Line', 'Freeze_Status': 'Status',
                    'Freeze_Rank': 'Freeze Order', 'Taps': 'Taps'}
        display = display.rename(columns=col_map)

        st.dataframe(display, use_container_width=True, hide_index=True)
    else:
        st.success(f"No priority lines in {conductor} — all sensors healthy.")

    # ── 24-hour vacuum charts for pink/red lines ────────────────────
    chart_sensors = cdf[cdf['Freeze_Status'].isin(['FROZEN', 'Critical'])]
    if not chart_sensors.empty:
        st.markdown("### Vacuum History — Priority Lines")

        now = vdf[timestamp_col].max()
        cutoff_24h = now - pd.Timedelta(hours=24)
        cutoff_7d = now - pd.Timedelta(days=7)

        for _, srow in chart_sensors.iterrows():
            sensor_name = srow[sensor_col]
            freeze_label = srow['Freeze_Status']

            sdata = vdf[vdf[find_column(vdf, 'Name', 'name', 'Sensor Name', 'sensor')] == sensor_name].copy()
            sdata = sdata.sort_values(timestamp_col)

            if sdata.empty:
                continue

            data_24h = sdata[sdata[timestamp_col] >= cutoff_24h]
            data_7d = sdata[sdata[timestamp_col] >= cutoff_7d]

            icon = '🔴' if freeze_label == 'FROZEN' else '🩷' if freeze_label == 'Critical' else '🟡'
            st.markdown(f"**{icon} {sensor_name}** — {freeze_label} | {srow['Taps']} taps")

            tab1, tab2 = st.tabs(["Last 24 Hours", "Last 7 Days"])

            for tab, data, label in [(tab1, data_24h, "24H"), (tab2, data_7d, "7D")]:
                with tab:
                    if data.empty:
                        st.caption(f"No data for {label}")
                        continue

                    fig = make_subplots(specs=[[{"secondary_y": True}]])

                    # Color dots by releaser differential
                    if releaser_col and releaser_col in data.columns:
                        dot_colors = data.apply(
                            lambda r: config.get_releaser_diff_color(
                                r[vacuum_col], r[releaser_col]
                            )[0], axis=1
                        )
                    else:
                        dot_colors = '#1f77b4'

                    fig.add_trace(
                        go.Scatter(
                            x=data[timestamp_col], y=data[vacuum_col],
                            mode='lines+markers',
                            name='Vacuum',
                            line=dict(color='#1f77b4', width=2),
                            marker=dict(color=dot_colors, size=8,
                                        line=dict(width=1, color='white')),
                        ),
                        secondary_y=False,
                    )

                    if releaser_col and releaser_col in data.columns:
                        fig.add_trace(
                            go.Scatter(
                                x=data[timestamp_col], y=data[releaser_col],
                                mode='lines+markers',
                                name='Releaser Diff',
                                line=dict(color='#C43E00', width=2),
                                marker=dict(color='#C43E00', size=6,
                                            symbol='circle'),
                            ),
                            secondary_y=True,
                        )

                    # Add temperature overlay
                    try:
                        import requests as _req
                        _temp_url = "https://api.open-meteo.com/v1/forecast"
                        _days = 2 if label == "24H" else 8
                        _params = {
                            "latitude": 43.4267, "longitude": -73.7123,
                            "hourly": "temperature_2m",
                            "temperature_unit": "fahrenheit",
                            "timezone": "America/New_York",
                            "past_days": _days, "forecast_days": 0
                        }
                        _resp = _req.get(_temp_url, params=_params, timeout=3)
                        if _resp.ok:
                            _td = _resp.json()['hourly']
                            _temp_series = pd.DataFrame({
                                'time': pd.to_datetime(_td['time']),
                                'temp': _td['temperature_2m']
                            })
                            _temp_series = _temp_series[
                                (_temp_series['time'] >= data[timestamp_col].min()) &
                                (_temp_series['time'] <= data[timestamp_col].max())
                            ]
                            if not _temp_series.empty:
                                fig.add_trace(
                                    go.Scatter(
                                        x=_temp_series['time'],
                                        y=_temp_series['temp'],
                                        mode='lines',
                                        name='Temp (F)',
                                        line=dict(color='#999999', width=1,
                                                  dash='dot'),
                                        yaxis='y3',
                                        hovertemplate='%{y:.0f}°F<extra></extra>',
                                    )
                                )
                                # Add freezing line
                                fig.add_hline(
                                    y=32, line_dash="dash",
                                    line_color="lightblue", line_width=1,
                                    annotation_text="32°F",
                                    annotation_position="bottom right",
                                    row=1, col=1, secondary_y=False,
                                )
                    except Exception:
                        pass

                    fig.update_layout(
                        height=300, margin=dict(t=30, b=30, l=50, r=50),
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="bottom",
                                    y=1.02, xanchor="right", x=1),
                        font=dict(size=12),
                    )
                    fig.update_yaxes(title_text="Vacuum (in)",
                                     secondary_y=False)
                    fig.update_yaxes(title_text="Rel Diff (in)",
                                     secondary_y=True)

                    st.plotly_chart(fig, use_container_width=True)

    # ── All lines table ─────────────────────────────────────────────
    with st.expander(f"All {len(cdf)} lines in {conductor}"):
        all_display = cdf[[sensor_col, 'Freeze_Status', vacuum_col, 'Taps']].copy()
        if releaser_col:
            all_display['Rel_Diff'] = cdf[releaser_col].apply(
                lambda x: f'{x:.1f}"' if pd.notna(x) else 'N/A'
            )
        all_display[vacuum_col] = all_display[vacuum_col].apply(
            lambda x: f'{x:.1f}"' if pd.notna(x) else 'N/A'
        )
        all_display = all_display.rename(columns={sensor_col: 'Line', 'Freeze_Status': 'Status',
                                                    vacuum_col: 'Vacuum'})
        st.dataframe(all_display, use_container_width=True, hide_index=True)

    # ── PDF Export ──────────────────────────────────────────────────
    st.divider()
    _render_pdf_export(conductor, cdf, sensor_col, vacuum_col, releaser_col,
                       timestamp_col, vdf)


# ============================================================================
# PDF EXPORT
# ============================================================================

def _render_pdf_export(conductor, cdf, sensor_col, vacuum_col, releaser_col,
                       timestamp_col, vdf):
    """Generate a PDF report for a single conductor system."""

    st.markdown("### 📄 PDF Export")
    st.caption(f"Download a PDF report for **{conductor}** to share with field crew.")

    if st.button(f"Generate PDF for {conductor}", key=f"pdf_{conductor}"):
        with st.spinner("Generating PDF..."):
            pdf_bytes = _build_pdf(
                conductor, cdf, sensor_col, vacuum_col, releaser_col,
                timestamp_col, vdf
            )

        if pdf_bytes:
            filename = f"freeze_report_{conductor}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            st.download_button(
                label=f"Download {filename}",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf",
                key=f"download_{conductor}"
            )
        else:
            st.error("Failed to generate PDF. Check that fpdf2 is installed.")


def _safe_text(text):
    """Sanitise text for fpdf2's built-in fonts (latin-1 only).
    Replaces smart quotes, em-dashes, and other Unicode with ASCII equivalents."""
    if not isinstance(text, str):
        text = str(text)
    replacements = {
        '\u201c': '"', '\u201d': '"',   # smart double quotes
        '\u2018': "'", '\u2019': "'",   # smart single quotes
        '\u2014': '--', '\u2013': '-',  # em/en dash
        '\u2026': '...',                # ellipsis
        '\u00b0': 'deg',               # degree sign
        '\u2033': '"', '\u2032': "'",   # prime / double prime
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Final safety: encode to latin-1, replacing anything remaining
    return text.encode('latin-1', 'replace').decode('latin-1')


def _build_pdf(conductor, cdf, sensor_col, vacuum_col, releaser_col,
               timestamp_col, vdf):
    """Build a PDF report for a conductor system using fpdf2."""
    try:
        from fpdf import FPDF
    except ImportError:
        st.error("PDF generation requires the `fpdf2` library. Add `fpdf2` to requirements.txt.")
        return None

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font('Helvetica', 'B', 18)
    pdf.cell(0, 12, _safe_text(f'Freezing Report: {conductor}'), new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, _safe_text(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}'),
             new_x='LMARGIN', new_y='NEXT', align='C')
    sugarbush = config.get_sugarbush(conductor)
    if sugarbush != 'Other':
        pdf.cell(0, 6, _safe_text(f'Sugarbush: {sugarbush}'),
                 new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(6)

    # Summary
    frozen = cdf[cdf['Freeze_Status'] == 'FROZEN']
    critical = cdf[cdf['Freeze_Status'] == 'Critical']
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, _safe_text(f'Summary: {len(frozen)} FROZEN | {len(critical)} Critical | {len(cdf)} Total Lines'),
             new_x='LMARGIN', new_y='NEXT')
    pdf.ln(4)

    # Priority lines table
    priority = cdf[cdf['Freeze_Status'].isin(['FROZEN', 'Critical'])].copy()
    if not priority.empty:
        # Sort by freeze rank
        priority = priority.sort_values('Freeze_Rank', ascending=True, na_position='last')

        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(0, 8, _safe_text('Priority Lines (Fix First)'), new_x='LMARGIN', new_y='NEXT')
        pdf.ln(2)

        # Table header
        pdf.set_font('Helvetica', 'B', 9)
        col_widths = [12, 30, 25, 25, 20, 20, 35]
        headers = ['#', 'Line', 'Status', 'Vacuum', 'Rel Diff', 'Taps', 'Went to Zero']
        for w, h in zip(col_widths, headers):
            pdf.cell(w, 7, _safe_text(h), border=1)
        pdf.ln()

        # Table rows
        pdf.set_font('Helvetica', '', 8)
        for _, row in priority.iterrows():
            rank_str = str(int(row['Freeze_Rank'])) if pd.notna(row.get('Freeze_Rank')) else '-'
            vac_str = f'{row[vacuum_col]:.1f} in' if pd.notna(row[vacuum_col]) else 'N/A'
            rel_str = f'{row[releaser_col]:.1f} in' if releaser_col and pd.notna(row.get(releaser_col)) else 'N/A'
            taps_str = str(int(row['Taps'])) if row['Taps'] > 0 else '-'
            zero_str = ''
            if pd.notna(row.get('First_Zero_Time')):
                zero_str = row['First_Zero_Time'].strftime('%m/%d %H:%M')

            vals = [rank_str, str(row[sensor_col]), row['Freeze_Status'],
                    vac_str, rel_str, taps_str, zero_str]
            for w, v in zip(col_widths, vals):
                pdf.cell(w, 6, _safe_text(v), border=1)
            pdf.ln()

        pdf.ln(4)
    else:
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 8, _safe_text('No priority lines -- all sensors healthy.'),
                 new_x='LMARGIN', new_y='NEXT')

    # 24-hour vacuum history charts as images
    # Generate small matplotlib charts for each priority sensor
    chart_sensors = cdf[cdf['Freeze_Status'].isin(['FROZEN', 'Critical'])]
    if not chart_sensors.empty:
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            now = vdf[timestamp_col].max()
            cutoff_24h = now - pd.Timedelta(hours=24)
            cutoff_7d = now - pd.Timedelta(days=7)

            s_col = find_column(vdf, 'Name', 'name', 'Sensor Name', 'sensor')

            for _, srow in chart_sensors.iterrows():
                sensor_name = srow[sensor_col]

                sdata = vdf[vdf[s_col] == sensor_name].copy()
                sdata = sdata.sort_values(timestamp_col)
                data_24h = sdata[sdata[timestamp_col] >= cutoff_24h]
                data_7d = sdata[sdata[timestamp_col] >= cutoff_7d]

                if data_24h.empty and data_7d.empty:
                    continue

                fig, axes = plt.subplots(1, 2, figsize=(7, 2.2))

                for ax, data, label in [(axes[0], data_24h, '24H'), (axes[1], data_7d, '7D')]:
                    if data.empty:
                        ax.text(0.5, 0.5, f'No {label} data', ha='center', va='center',
                                transform=ax.transAxes, fontsize=8)
                        ax.set_title(f'{sensor_name} — {label}', fontsize=8)
                        continue

                    ax.plot(data[timestamp_col], data[vacuum_col],
                            color='#1f77b4', linewidth=1.2, marker='o', markersize=3)
                    if releaser_col and releaser_col in data.columns:
                        ax2 = ax.twinx()
                        ax2.plot(data[timestamp_col], data[releaser_col],
                                 color='#C43E00', linewidth=1.2, marker='o',
                                 markersize=2)
                        ax2.set_ylabel('Rel Diff', fontsize=6)
                        ax2.tick_params(labelsize=5)

                    ax.set_title(f'{sensor_name} — {label}', fontsize=8)
                    ax.set_ylabel('Vacuum', fontsize=6)
                    ax.tick_params(labelsize=5)
                    ax.tick_params(axis='x', rotation=30)

                plt.tight_layout()

                # Save to buffer and add to PDF
                buf = io.BytesIO()
                fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
                plt.close(fig)
                buf.seek(0)

                # Check if we need a new page
                if pdf.get_y() > 230:
                    pdf.add_page()

                pdf.image(buf, x=10, w=190)
                pdf.ln(3)

        except ImportError:
            pdf.set_font('Helvetica', 'I', 8)
            pdf.cell(0, 6, _safe_text('(Charts require matplotlib -- install to include charts in PDF)'),
                     new_x='LMARGIN', new_y='NEXT')

    # All lines summary
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 8, _safe_text(f'All Lines in {conductor} ({len(cdf)} total)'),
             new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)

    pdf.set_font('Helvetica', 'B', 9)
    col_widths_all = [30, 25, 25, 20, 20]
    headers_all = ['Line', 'Status', 'Vacuum', 'Rel Diff', 'Taps']
    for w, h in zip(col_widths_all, headers_all):
        pdf.cell(w, 7, _safe_text(h), border=1)
    pdf.ln()

    pdf.set_font('Helvetica', '', 8)
    for _, row in cdf.sort_values(sensor_col).iterrows():
        vac_str = f'{row[vacuum_col]:.1f} in' if pd.notna(row[vacuum_col]) else 'N/A'
        rel_str = f'{row[releaser_col]:.1f} in' if releaser_col and pd.notna(row.get(releaser_col)) else 'N/A'
        taps_str = str(int(row['Taps'])) if row['Taps'] > 0 else '-'
        vals = [str(row[sensor_col]), row['Freeze_Status'], vac_str, rel_str, taps_str]
        for w, v in zip(col_widths_all, vals):
            pdf.cell(w, 6, _safe_text(v), border=1)
        pdf.ln()

    # Return PDF bytes
    return pdf.output()
