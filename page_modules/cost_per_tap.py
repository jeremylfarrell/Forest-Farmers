"""
Cost Per Tap Page Module
Shows full cost picture per mainline and per employee:
tapping cost, fixing cost, leak-checking cost, and releaser differential quality.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import config
from utils import find_column, is_tapping_job, extract_conductor_system, get_releaser_column, get_temperature_column, match_mainline_to_sensor


def render(personnel_df, vacuum_df=None):
    """Render the Cost Per Tap analysis page."""

    st.title("Cost Per Tap")
    st.markdown("*Full cost picture: tapping cost + downstream repair and leak-checking costs per mainline and employee.*")

    if personnel_df is None or personnel_df.empty:
        st.info("No personnel data available.")
        return

    overhead = config.LABOR_OVERHEAD_MULTIPLIER

    # --- Find columns ---
    mainline_col = find_column(personnel_df, 'mainline.', 'mainline', 'Mainline', 'location')
    job_col = find_column(personnel_df, 'Job', 'job', 'Job Code', 'jobcode')
    emp_col = find_column(personnel_df, 'Employee Name', 'employee', 'name')
    hours_col = find_column(personnel_df, 'Hours', 'hours')
    rate_col = find_column(personnel_df, 'Rate', 'rate', 'Hourly Rate')
    taps_col = find_column(personnel_df, 'Taps Put In', 'taps put in', 'taps_put_in')

    if not all([mainline_col, job_col, emp_col, hours_col]):
        st.warning("Required columns not found in personnel data.")
        return

    # --- Prepare data ---
    df = personnel_df.copy()
    df['_mainline'] = df[mainline_col].astype(str).str.strip()
    df['_job'] = df[job_col].astype(str).str.strip()
    df['_job_lower'] = df['_job'].str.lower()
    df['_employee'] = df[emp_col].astype(str).str.strip()
    df['_hours'] = pd.to_numeric(df[hours_col], errors='coerce').fillna(0)
    df['_rate'] = pd.to_numeric(df[rate_col], errors='coerce').fillna(0) if rate_col else 0
    df['_taps'] = pd.to_numeric(df[taps_col], errors='coerce').fillna(0) if taps_col else 0
    df['_cost'] = df['_hours'] * df['_rate'] * overhead

    # Filter out blank mainlines
    df = df[df['_mainline'].ne('') & df['_mainline'].ne('nan')]

    # Classify job types
    df['_is_tapping'] = df['_job'].apply(is_tapping_job)

    fixing_keywords = ['fixing identified tubing', 'already identified tubing issue']
    df['_is_fixing'] = df['_job_lower'].apply(lambda j: any(kw in j for kw in fixing_keywords))

    leak_keywords = ['inseason tubing repair', 'maple tubing inseason', 'leak check']
    df['_is_leak_check'] = df['_job_lower'].apply(lambda j: any(kw in j for kw in leak_keywords))

    # --- Build releaser differential lookup by sensor ---
    rel_diff_by_sensor = _get_releaser_diff_above_freezing(vacuum_df)

    # --- Aggregate by mainline ---
    mainline_stats = _aggregate_by_mainline(df, rel_diff_by_sensor, vacuum_df)

    # --- Aggregate by employee ---
    employee_stats = _aggregate_by_employee(df)

    # --- Aggregate by employee + mainline ---
    combo_stats = _aggregate_by_employee_mainline(df, rel_diff_by_sensor, vacuum_df)

    # --- View selector ---
    view = st.radio(
        "View",
        ["By Mainline", "By Employee", "By Employee + Mainline"],
        horizontal=True,
        key="cost_per_tap_view"
    )

    st.divider()

    if view == "By Mainline":
        _render_mainline_view(mainline_stats)
    elif view == "By Employee":
        _render_employee_view(employee_stats)
    else:
        _render_combo_view(combo_stats)


def _get_releaser_diff_above_freezing(vacuum_df):
    """
    Calculate average releaser differential per sensor for readings when
    temperature is above freezing. Uses the temperature column from the
    vacuum Google Sheet directly.

    Returns dict: {sensor_name: avg_rel_diff} (only above-freezing readings).
    """
    if vacuum_df is None or vacuum_df.empty:
        return {}

    sensor_col = find_column(vacuum_df, 'Name', 'name', 'Sensor Name', 'sensor')
    rel_col = get_releaser_column(vacuum_df)
    temp_col = get_temperature_column(vacuum_df)

    if not sensor_col or not rel_col:
        return {}

    vdf = vacuum_df.copy()
    vdf[rel_col] = pd.to_numeric(vdf[rel_col], errors='coerce')
    vdf = vdf.dropna(subset=[rel_col])

    if vdf.empty:
        return {}

    # Filter to above-freezing readings using the temperature column
    if temp_col:
        vdf[temp_col] = pd.to_numeric(vdf[temp_col], errors='coerce')
        above_freezing = vdf[vdf[temp_col] > 32]
        if not above_freezing.empty:
            vdf = above_freezing

    # Calculate average absolute releaser diff per sensor
    result = {}
    for sensor, group in vdf.groupby(sensor_col):
        sensor_name = str(sensor).strip()
        avg_diff = group[rel_col].abs().mean()
        if pd.notna(avg_diff):
            result[sensor_name] = round(avg_diff, 2)

    return result


def _aggregate_by_mainline(df, rel_diff_by_sensor, vacuum_df):
    """Aggregate costs by mainline."""
    rows = []
    sensor_names = list(rel_diff_by_sensor.keys()) if rel_diff_by_sensor else []

    for mainline, group in df.groupby('_mainline'):
        tapping = group[group['_is_tapping']]
        fixing = group[group['_is_fixing']]
        leak = group[group['_is_leak_check']]

        total_taps = tapping['_taps'].sum()
        tapping_cost = tapping['_cost'].sum()
        tapping_hours = tapping['_hours'].sum()
        fixing_cost = fixing['_cost'].sum()
        fixing_hours = fixing['_hours'].sum()
        leak_cost = leak['_cost'].sum()
        leak_hours = leak['_hours'].sum()

        cost_per_tap = tapping_cost / total_taps if total_taps > 0 else 0
        total_cost = tapping_cost + fixing_cost + leak_cost
        all_in_cost_per_tap = total_cost / total_taps if total_taps > 0 else 0

        # Get releaser differential — match mainline to sensor
        avg_rel_diff = None
        if sensor_names:
            matched_sensor = match_mainline_to_sensor(mainline, sensor_names)
            if matched_sensor and matched_sensor in rel_diff_by_sensor:
                avg_rel_diff = rel_diff_by_sensor[matched_sensor]

        tappers = sorted(tapping['_employee'].unique().tolist())

        conductor = extract_conductor_system(mainline)

        fixing_cost_per_tap = fixing_cost / total_taps if total_taps > 0 else 0
        leak_cost_per_tap = leak_cost / total_taps if total_taps > 0 else 0

        rows.append({
            'Mainline': mainline,
            'Conductor': conductor,
            'Tapped By': ', '.join(tappers) if tappers else '',
            'Taps': int(total_taps),
            'Tapping Hours': round(tapping_hours, 1),
            'Tapping Cost': round(tapping_cost, 2),
            'Cost/Tap (Tapping)': round(cost_per_tap, 2),
            'Fixing Hours': round(fixing_hours, 1),
            'Fixing Cost': round(fixing_cost, 2),
            'Fixing Cost/Tap': round(fixing_cost_per_tap, 2),
            'Leak Check Hours': round(leak_hours, 1),
            'Leak Check Cost': round(leak_cost, 2),
            'Leak Check Cost/Tap': round(leak_cost_per_tap, 2),
            'Total Cost': round(total_cost, 2),
            'All-In Cost/Tap': round(all_in_cost_per_tap, 2),
            'Avg Rel Diff (>32F)': avg_rel_diff,
        })

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values('Taps', ascending=False)
    return result


def _aggregate_by_employee(df):
    """Aggregate costs by employee."""
    rows = []

    for employee, group in df.groupby('_employee'):
        tapping = group[group['_is_tapping']]
        fixing = group[group['_is_fixing']]
        leak = group[group['_is_leak_check']]

        total_taps = tapping['_taps'].sum()
        tapping_cost = tapping['_cost'].sum()
        tapping_hours = tapping['_hours'].sum()
        fixing_cost = fixing['_cost'].sum()
        fixing_hours = fixing['_hours'].sum()
        leak_cost = leak['_cost'].sum()
        leak_hours = leak['_hours'].sum()

        cost_per_tap = tapping_cost / total_taps if total_taps > 0 else 0
        fixing_cost_per_tap = fixing_cost / total_taps if total_taps > 0 else 0
        leak_cost_per_tap = leak_cost / total_taps if total_taps > 0 else 0
        total_cost = tapping_cost + fixing_cost + leak_cost
        all_in_cost_per_tap = total_cost / total_taps if total_taps > 0 else 0

        mainlines_tapped = sorted(tapping['_mainline'].unique().tolist())

        rows.append({
            'Employee': employee,
            'Mainlines Tapped': len(mainlines_tapped),
            'Taps': int(total_taps),
            'Tapping Hours': round(tapping_hours, 1),
            'Tapping Cost': round(tapping_cost, 2),
            'Cost/Tap (Tapping)': round(cost_per_tap, 2),
            'Fixing Hours': round(fixing_hours, 1),
            'Fixing Cost': round(fixing_cost, 2),
            'Fixing Cost/Tap': round(fixing_cost_per_tap, 2),
            'Leak Check Hours': round(leak_hours, 1),
            'Leak Check Cost': round(leak_cost, 2),
            'Leak Check Cost/Tap': round(leak_cost_per_tap, 2),
            'All-In Cost/Tap': round(all_in_cost_per_tap, 2),
        })

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values('Taps', ascending=False)
    return result


def _aggregate_by_employee_mainline(df, rel_diff_by_sensor, vacuum_df):
    """Aggregate costs by employee + mainline combination."""
    rows = []
    sensor_names = list(rel_diff_by_sensor.keys()) if rel_diff_by_sensor else []

    for (employee, mainline), group in df.groupby(['_employee', '_mainline']):
        tapping = group[group['_is_tapping']]
        fixing = group[group['_is_fixing']]
        leak = group[group['_is_leak_check']]

        total_taps = tapping['_taps'].sum()
        tapping_cost = tapping['_cost'].sum()
        tapping_hours = tapping['_hours'].sum()
        fixing_cost = fixing['_cost'].sum()
        fixing_hours = fixing['_hours'].sum()
        leak_cost = leak['_cost'].sum()
        leak_hours = leak['_hours'].sum()

        # Skip rows with no activity
        if tapping_hours == 0 and fixing_hours == 0 and leak_hours == 0:
            continue

        cost_per_tap = tapping_cost / total_taps if total_taps > 0 else 0
        total_cost = tapping_cost + fixing_cost + leak_cost
        all_in_cost_per_tap = total_cost / total_taps if total_taps > 0 else 0

        avg_rel_diff = None
        if sensor_names:
            matched_sensor = match_mainline_to_sensor(mainline, sensor_names)
            if matched_sensor and matched_sensor in rel_diff_by_sensor:
                avg_rel_diff = rel_diff_by_sensor[matched_sensor]

        fixing_cost_per_tap = fixing_cost / total_taps if total_taps > 0 else 0
        leak_cost_per_tap = leak_cost / total_taps if total_taps > 0 else 0

        rows.append({
            'Employee': employee,
            'Mainline': mainline,
            'Taps': int(total_taps),
            'Tapping Hours': round(tapping_hours, 1),
            'Tapping Cost': round(tapping_cost, 2),
            'Cost/Tap (Tapping)': round(cost_per_tap, 2),
            'Fixing Hours': round(fixing_hours, 1),
            'Fixing Cost': round(fixing_cost, 2),
            'Fixing Cost/Tap': round(fixing_cost_per_tap, 2),
            'Leak Check Hours': round(leak_hours, 1),
            'Leak Check Cost': round(leak_cost, 2),
            'Leak Check Cost/Tap': round(leak_cost_per_tap, 2),
            'Total Cost': round(total_cost, 2),
            'All-In Cost/Tap': round(all_in_cost_per_tap, 2),
            'Avg Rel Diff (>32F)': avg_rel_diff,
        })

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(['Employee', 'Taps'], ascending=[True, False])
    return result


def _render_mainline_view(stats):
    """Render the by-mainline view with summary metrics, table, and charts."""
    if stats.empty:
        st.info("No mainline data available.")
        return

    st.subheader("Cost by Mainline")
    st.caption(f"Costs include {config.LABOR_OVERHEAD_MULTIPLIER}x overhead multiplier (workers comp, payroll)")

    # Filter
    conductors = ['All'] + sorted(stats['Conductor'].unique().tolist())
    selected_conductor = st.selectbox("Filter by Conductor System", conductors, key="cpt_ml_conductor")
    if selected_conductor != 'All':
        display = stats[stats['Conductor'] == selected_conductor].copy()
    else:
        display = stats.copy()

    if display.empty:
        st.info("No data for selected filter.")
        return

    # Summary metrics
    total_taps = display['Taps'].sum()
    total_tapping_cost = display['Tapping Cost'].sum()
    total_fixing_cost = display['Fixing Cost'].sum()
    total_leak_cost = display['Leak Check Cost'].sum()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Taps", f"{total_taps:,}")
    with col2:
        avg_cpt = total_tapping_cost / total_taps if total_taps > 0 else 0
        st.metric("Avg Cost/Tap", f"${avg_cpt:.2f}")
    with col3:
        st.metric("Tapping Cost", f"${total_tapping_cost:,.0f}")
    with col4:
        st.metric("Fixing Cost", f"${total_fixing_cost:,.0f}")
    with col5:
        st.metric("Leak Check Cost", f"${total_leak_cost:,.0f}")

    st.divider()

    # Format for display
    fmt = display.copy()
    money_cols = ['Tapping Cost', 'Cost/Tap (Tapping)', 'Fixing Cost', 'Fixing Cost/Tap',
                  'Leak Check Cost', 'Leak Check Cost/Tap', 'Total Cost', 'All-In Cost/Tap']
    for c in money_cols:
        if c in fmt.columns:
            fmt[c] = fmt[c].apply(lambda x: f"${x:,.2f}" if x > 0 else "")

    if 'Avg Rel Diff (>32F)' in fmt.columns:
        fmt['Avg Rel Diff (>32F)'] = fmt['Avg Rel Diff (>32F)'].apply(
            lambda x: f"{x:.1f}\"" if pd.notna(x) else ""
        )

    # Visible columns: mainline, tapped by, taps, then 4 cost/tap columns + rel diff
    visible_cols = ['Mainline', 'Tapped By', 'Taps', 'Cost/Tap (Tapping)',
                    'Fixing Cost/Tap', 'Leak Check Cost/Tap',
                    'All-In Cost/Tap', 'Avg Rel Diff (>32F)']
    visible_cols = [c for c in visible_cols if c in fmt.columns]

    col_config = {
        'Mainline': st.column_config.TextColumn('Mainline'),
        'Tapped By': st.column_config.TextColumn('Tapped\nBy'),
        'Taps': st.column_config.NumberColumn('Taps', width='small'),
        'Cost/Tap (Tapping)': st.column_config.TextColumn('Tapping\nCost/Tap', width='small'),
        'Fixing Cost/Tap': st.column_config.TextColumn('Fixing\nCost/Tap', width='small'),
        'Leak Check Cost/Tap': st.column_config.TextColumn('Leak Check\nCost/Tap', width='small'),
        'All-In Cost/Tap': st.column_config.TextColumn('All-In\nCost/Tap', width='small'),
        'Avg Rel Diff (>32F)': st.column_config.TextColumn('Avg Rel Diff\n(>32°F)', width='small'),
    }

    st.dataframe(fmt, column_config=col_config, column_order=visible_cols,
                 use_container_width=True, hide_index=True,
                 height=min(400 + len(fmt) * 10, 800))

    # Charts
    st.divider()
    chart_data = display[display['Taps'] > 0].copy()
    if not chart_data.empty:
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("Cost/Tap by Mainline (Top 20)")
            top20 = chart_data.nlargest(20, 'Cost/Tap (Tapping)').sort_values('Cost/Tap (Tapping)')
            fig = px.bar(top20, x='Cost/Tap (Tapping)', y='Mainline', orientation='h',
                         color='Cost/Tap (Tapping)',
                         color_continuous_scale=['#4CAF50', '#FFC107', '#ff6b6b'])
            fig.update_layout(height=max(400, len(top20) * 28 + 100),
                              showlegend=False, coloraxis_showscale=False,
                              xaxis_title='Cost/Tap ($)')
            st.plotly_chart(fig, use_container_width=True)

        with chart_col2:
            st.subheader("Fixing + Leak Check Cost (Top 20)")
            chart_data['Repair Total'] = chart_data['Fixing Cost'] + chart_data['Leak Check Cost']
            top20_repair = chart_data[chart_data['Repair Total'] > 0].nlargest(20, 'Repair Total').sort_values('Repair Total')
            if not top20_repair.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(y=top20_repair['Mainline'], x=top20_repair['Fixing Cost'],
                                     name='Fixing', orientation='h', marker_color='#FF7043'))
                fig.add_trace(go.Bar(y=top20_repair['Mainline'], x=top20_repair['Leak Check Cost'],
                                     name='Leak Check', orientation='h', marker_color='#42A5F5'))
                fig.update_layout(barmode='stack',
                                  height=max(400, len(top20_repair) * 28 + 100),
                                  xaxis_title='Cost ($)',
                                  legend=dict(orientation='h', yanchor='bottom', y=1.02))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No fixing or leak checking costs recorded.")


def _render_employee_view(stats):
    """Render the by-employee view."""
    if stats.empty:
        st.info("No employee data available.")
        return

    st.subheader("Cost by Employee")
    st.caption(f"Costs include {config.LABOR_OVERHEAD_MULTIPLIER}x overhead multiplier")

    # Summary
    total_taps = stats['Taps'].sum()
    total_tapping_cost = stats['Tapping Cost'].sum()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Taps", f"{total_taps:,}")
    with col2:
        avg_cpt = total_tapping_cost / total_taps if total_taps > 0 else 0
        st.metric("Avg Cost/Tap", f"${avg_cpt:.2f}")
    with col3:
        st.metric("Total Tapping Cost", f"${total_tapping_cost:,.0f}")

    st.divider()

    # Table — only show employees who tapped
    tappers = stats[stats['Taps'] > 0].copy()

    if tappers.empty:
        st.info("No tapping data found.")
        return

    fmt = tappers.copy()
    money_cols = ['Tapping Cost', 'Cost/Tap (Tapping)', 'Fixing Cost', 'Fixing Cost/Tap',
                  'Leak Check Cost', 'Leak Check Cost/Tap', 'All-In Cost/Tap']
    for c in money_cols:
        if c in fmt.columns:
            fmt[c] = fmt[c].apply(lambda x: f"${x:,.2f}" if x > 0 else "")

    visible_cols = ['Employee', 'Mainlines Tapped', 'Taps', 'Cost/Tap (Tapping)',
                    'Fixing Cost/Tap', 'Leak Check Cost/Tap', 'All-In Cost/Tap']
    visible_cols = [c for c in visible_cols if c in fmt.columns]

    emp_col_config = {
        'Employee': st.column_config.TextColumn('Employee'),
        'Mainlines Tapped': st.column_config.NumberColumn('Mainlines\nTapped', width='small'),
        'Taps': st.column_config.NumberColumn('Taps', width='small'),
        'Cost/Tap (Tapping)': st.column_config.TextColumn('Tapping\nCost/Tap', width='small'),
        'Fixing Cost/Tap': st.column_config.TextColumn('Fixing\nCost/Tap', width='small'),
        'Leak Check Cost/Tap': st.column_config.TextColumn('Leak Check\nCost/Tap', width='small'),
        'All-In Cost/Tap': st.column_config.TextColumn('All-In\nCost/Tap', width='small'),
    }

    st.dataframe(fmt, column_config=emp_col_config, column_order=visible_cols,
                 use_container_width=True, hide_index=True,
                 height=min(400 + len(fmt) * 10, 600))

    # Chart
    st.divider()
    st.subheader("Cost/Tap by Employee")
    chart_data = tappers.sort_values('Cost/Tap (Tapping)')
    fig = px.bar(chart_data, x='Cost/Tap (Tapping)', y='Employee', orientation='h',
                 color='Cost/Tap (Tapping)',
                 color_continuous_scale=['#4CAF50', '#FFC107', '#ff6b6b'])
    fig.update_layout(height=max(400, len(chart_data) * 35 + 100),
                      showlegend=False, coloraxis_showscale=False,
                      xaxis_title='Cost/Tap ($)')
    st.plotly_chart(fig, use_container_width=True)


def _render_combo_view(stats):
    """Render the by-employee+mainline combination view."""
    if stats.empty:
        st.info("No data available.")
        return

    st.subheader("Cost by Employee + Mainline")
    st.caption(f"Costs include {config.LABOR_OVERHEAD_MULTIPLIER}x overhead multiplier")

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        employees = ['All'] + sorted(stats['Employee'].unique().tolist())
        selected_emp = st.selectbox("Employee", employees, key="cpt_combo_emp")
    with col2:
        mainlines = ['All'] + sorted(stats['Mainline'].unique().tolist())
        selected_ml = st.selectbox("Mainline", mainlines, key="cpt_combo_ml")

    display = stats.copy()
    if selected_emp != 'All':
        display = display[display['Employee'] == selected_emp]
    if selected_ml != 'All':
        display = display[display['Mainline'] == selected_ml]

    if display.empty:
        st.info("No data for selected filters.")
        return

    st.divider()

    # Format for display
    fmt = display.copy()
    money_cols = ['Tapping Cost', 'Cost/Tap (Tapping)', 'Fixing Cost', 'Leak Check Cost',
                  'Total Cost', 'All-In Cost/Tap']
    for c in money_cols:
        if c in fmt.columns:
            fmt[c] = fmt[c].apply(lambda x: f"${x:,.2f}" if x > 0 else "")

    if 'Avg Rel Diff (>32F)' in fmt.columns:
        fmt['Avg Rel Diff (>32F)'] = fmt['Avg Rel Diff (>32F)'].apply(
            lambda x: f"{x:.1f}\"" if pd.notna(x) else ""
        )

    visible_cols = ['Employee', 'Mainline', 'Taps', 'Cost/Tap (Tapping)',
                    'Fixing Cost/Tap', 'Leak Check Cost/Tap',
                    'All-In Cost/Tap', 'Avg Rel Diff (>32F)']
    visible_cols = [c for c in visible_cols if c in fmt.columns]

    combo_col_config = {
        'Employee': st.column_config.TextColumn('Employee'),
        'Mainline': st.column_config.TextColumn('Mainline'),
        'Taps': st.column_config.NumberColumn('Taps', width='small'),
        'Cost/Tap (Tapping)': st.column_config.TextColumn('Tapping\nCost/Tap', width='small'),
        'Fixing Cost/Tap': st.column_config.TextColumn('Fixing\nCost/Tap', width='small'),
        'Leak Check Cost/Tap': st.column_config.TextColumn('Leak Check\nCost/Tap', width='small'),
        'All-In Cost/Tap': st.column_config.TextColumn('All-In\nCost/Tap', width='small'),
        'Avg Rel Diff (>32F)': st.column_config.TextColumn('Avg Rel Diff\n(>32°F)', width='small'),
    }

    st.dataframe(fmt, column_config=combo_col_config, column_order=visible_cols,
                 use_container_width=True, hide_index=True,
                 height=min(400 + len(fmt) * 10, 800))
