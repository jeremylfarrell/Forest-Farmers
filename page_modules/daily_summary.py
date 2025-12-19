"""
Daily Operations Summary Page Module - MULTI-SITE ENHANCED
Quick morning briefing with actionable recommendations and site breakdowns
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
import config
from utils import find_column, get_vacuum_column


def get_today_weather_brief(latitude=43.4267, longitude=-73.7123):
    """Get today's weather forecast briefly"""
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": ["temperature_2m_max", "temperature_2m_min"],
            "temperature_unit": "fahrenheit",
            "timezone": "America/New_York",
            "forecast_days": 1
        }
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()['daily']
        return {
            'high': data['temperature_2m_max'][0],
            'low': data['temperature_2m_min'][0]
        }
    except:
        return None


def calculate_sap_likelihood_today(high, low):
    """Calculate today's sap flow likelihood"""
    if high is None or low is None:
        return None

    likelihood = 0

    # Freeze/thaw cycle
    if low < 32 and high > 32:
        likelihood += 40

    # Temperature swing
    swing = high - low
    if 15 <= swing <= 25:
        likelihood += 30

    # Optimal temps
    min_score = max(0, 20 - abs(low - 25) * 2)
    max_score = max(0, 20 - abs(high - 45) * 2)
    likelihood += (min_score + max_score) / 2

    return min(100, likelihood)


def get_critical_sensors(vacuum_df, threshold=config.VACUUM_FAIR):
    """Get sensors below threshold with site information"""
    if vacuum_df.empty:
        return pd.DataFrame()

    sensor_col = find_column(vacuum_df, 'Name', 'name', 'mainline', 'Sensor Name', 'sensor', 'location')
    vacuum_col = get_vacuum_column(vacuum_df)
    timestamp_col = find_column(
        vacuum_df,
        'Last communication', 'Last Communication', 'Timestamp', 'timestamp'
    )

    if not all([sensor_col, vacuum_col]):
        return pd.DataFrame()

    # Get latest reading per sensor
    if timestamp_col:
        temp_df = vacuum_df.copy()
        temp_df[timestamp_col] = pd.to_datetime(temp_df[timestamp_col], errors='coerce')
        latest = temp_df.sort_values(timestamp_col, ascending=False).groupby(sensor_col).first().reset_index()
    else:
        latest = vacuum_df.groupby(sensor_col).first().reset_index()

    # Filter to problem sensors
    problems = latest[pd.to_numeric(latest[vacuum_col], errors='coerce') < threshold].copy()
    problems['Vacuum'] = pd.to_numeric(problems[vacuum_col], errors='coerce')
    problems['Sensor'] = problems[sensor_col]
    
    # Add site if available
    if 'Site' in problems.columns:
        result = problems[['Sensor', 'Vacuum', 'Site']].sort_values('Vacuum')
    else:
        result = problems[['Sensor', 'Vacuum']].sort_values('Vacuum')
    
    return result


def generate_action_plan(vacuum_df, personnel_df, weather):
    """Generate realistic daily action plan with site information"""
    actions = []

    # Get critical sensors
    critical = get_critical_sensors(vacuum_df)
    
    # Check if we have site information
    has_site = 'Site' in critical.columns if not critical.empty else False

    # Weather-based actions
    if weather:
        likelihood = calculate_sap_likelihood_today(weather['high'], weather['low'])

        if likelihood and likelihood >= 70:
            actions.append({
                'priority': 1,
                'category': '🌡️ Weather',
                'action': 'Excellent sap flow expected today',
                'detail': f"Conditions optimal: Low {weather['low']:.0f}°F, High {weather['high']:.0f}°F",
                'time_estimate': 'All day',
                'recommendation': '✓ Ensure maximum collection capacity\n✓ Check all releasers before peak\n✓ Have extra staff ready'
            })
        elif likelihood and likelihood < 30:
            actions.append({
                'priority': 3,
                'category': '🌡️ Weather',
                'action': 'Poor sap flow expected today',
                'detail': f"Conditions marginal: Low {weather['low']:.0f}°F, High {weather['high']:.0f}°F",
                'time_estimate': 'Plan maintenance',
                'recommendation': '✓ Focus on repairs and maintenance\n✓ Good day to fix problem sensors\n✓ Prepare for better days ahead'
            })

    # Critical sensor actions with site breakdown
    if not critical.empty and len(critical) <= 5:
        if has_site:
            # Group by site for better dispatch
            site_breakdown = critical.groupby('Site')['Sensor'].apply(list).to_dict()
            detail_parts = []
            for site, sensors in site_breakdown.items():
                site_emoji = "🟦" if site == "NY" else "🟩" if site == "VT" else "⚫"
                detail_parts.append(f"{site_emoji} {site}: {', '.join(sensors[:2])}")
            detail = "Urgent attention needed:\n" + "\n".join(detail_parts)
        else:
            sensor_list = ', '.join(critical['Sensor'].head(5).tolist())
            detail = f"Urgent attention needed: {sensor_list}"
            
        actions.append({
            'priority': 1,
            'category': '🔴 Critical',
            'action': f'Fix {len(critical)} critical sensor(s)',
            'detail': detail,
            'time_estimate': f'{len(critical) * 2}h',
            'recommendation': f'✓ Inspect these {len(critical)} locations first\n✓ Check for leaks and damaged lines\n✓ Test releasers'
        })
    elif not critical.empty:
        if has_site:
            # Show site breakdown for large problem counts
            site_counts = critical['Site'].value_counts()
            breakdown = ", ".join([f"🟦 NY: {site_counts.get('NY', 0)}" if s == 'NY' 
                                 else f"🟩 VT: {site_counts.get('VT', 0)}" if s == 'VT'
                                 else f"⚫ UNK: {site_counts.get('UNK', 0)}"
                                 for s in site_counts.index])
            detail = f'Too many for one day ({breakdown}) - prioritize worst'
        else:
            detail = 'Too many for one day - prioritize worst'
            
        actions.append({
            'priority': 1,
            'category': '🔴 Critical',
            'action': f'System has {len(critical)} problem sensors',
            'detail': detail,
            'time_estimate': 'Full day',
            'recommendation': f'✓ Start with worst 5 sensors\n✓ Categorize by geographic area\n✓ Schedule remaining for tomorrow'
        })

    # Check for sensors not reporting
    sensor_col = find_column(vacuum_df, 'Name', 'name', 'mainline', 'Sensor Name', 'sensor', 'location')
    timestamp_col = find_column(
        vacuum_df,
        'Last communication', 'Last Communication', 'Timestamp', 'timestamp'
    )

    if sensor_col and timestamp_col and not vacuum_df.empty:
        temp_df = vacuum_df.copy()
        temp_df[timestamp_col] = pd.to_datetime(temp_df[timestamp_col], errors='coerce')
        latest_times = temp_df.groupby(sensor_col)[timestamp_col].max()
        cutoff = datetime.now() - timedelta(days=2)
        stale = latest_times[latest_times < cutoff]

        if len(stale) > 0:
            actions.append({
                'priority': 2,
                'category': '⚠️ Warning',
                'action': f'{len(stale)} sensor(s) not reporting',
                'detail': 'No data received in 48+ hours',
                'time_estimate': f'{len(stale) * 0.5}h',
                'recommendation': '✓ Check sensor power/connectivity\n✓ Verify network connection\n✓ May need sensor replacement'
            })

    # Personnel-based actions with site awareness
    if not personnel_df.empty:
        date_col = find_column(personnel_df, 'Date', 'date', 'timestamp')
        if date_col:
            yesterday = datetime.now().date() - timedelta(days=1)
            yesterday_work = personnel_df[pd.to_datetime(personnel_df[date_col]).dt.date == yesterday]

            if not yesterday_work.empty:
                emp_col = find_column(yesterday_work, 'Employee Name', 'employee', 'name')
                if emp_col:
                    emp_count = yesterday_work[emp_col].nunique()
                    
                    # Add site breakdown if available
                    detail = 'Review their work effectiveness'
                    if 'Site' in yesterday_work.columns:
                        site_counts = yesterday_work['Site'].value_counts()
                        site_info = []
                        for site in ['NY', 'VT', 'UNK']:
                            if site in site_counts.index:
                                emoji = "🟦" if site == "NY" else "🟩" if site == "VT" else "⚫"
                                site_info.append(f"{emoji} {site}: {site_counts[site]} sessions")
                        if site_info:
                            detail = f"Work distribution:\n" + "\n".join(site_info)
                    
                    actions.append({
                        'priority': 3,
                        'category': '📊 Info',
                        'action': f'{emp_count} employee(s) worked yesterday',
                        'detail': detail,
                        'time_estimate': '15min',
                        'recommendation': '✓ Check Employee Effectiveness page\n✓ Verify vacuum improvements\n✓ Provide feedback'
                    })

    # General daily tasks
    actions.append({
        'priority': 3,
        'category': '📋 Daily',
        'action': 'Morning system check',
        'detail': 'Standard daily procedures',
        'time_estimate': '30min',
        'recommendation': '✓ Check all pump pressure gauges\n✓ Verify vacuum levels\n✓ Check for alerts\n✓ Review weather forecast'
    })

    # Sort by priority
    actions.sort(key=lambda x: x['priority'])

    return actions


def render(vacuum_df, personnel_df):
    """Render daily operations summary page with site awareness"""

    st.title("📱 Daily Operations Summary")
    current_time = datetime.now()
    st.markdown(f"*{current_time.strftime('%A, %B %d, %Y - %I:%M %p')}*")

    # Check if we have multi-site data
    has_vacuum_site = 'Site' in vacuum_df.columns if not vacuum_df.empty else False
    has_personnel_site = 'Site' in personnel_df.columns if not personnel_df.empty else False
    
    # Quick stats banner with site breakdown
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if not vacuum_df.empty:
            sensor_col = find_column(vacuum_df, 'Name', 'name', 'mainline', 'Sensor Name', 'sensor', 'location')
            if sensor_col:
                total_sensors = vacuum_df[sensor_col].nunique()
                
                # Add site breakdown if available
                if has_vacuum_site:
                    ny_count = vacuum_df[vacuum_df['Site'] == 'NY'][sensor_col].nunique()
                    vt_count = vacuum_df[vacuum_df['Site'] == 'VT'][sensor_col].nunique()
                    st.metric("Total Sensors", total_sensors)
                    st.caption(f"🟦 NY: {ny_count} | 🟩 VT: {vt_count}")
                else:
                    st.metric("Total Sensors", total_sensors)
            else:
                st.metric("Total Sensors", "N/A")
        else:
            st.metric("Total Sensors", "N/A")

    with col2:
        if not vacuum_df.empty:
            vacuum_col = get_vacuum_column(vacuum_df)
            if vacuum_col:
                avg_vac = pd.to_numeric(vacuum_df[vacuum_col], errors='coerce').mean()
                status = config.get_vacuum_emoji(avg_vac)
                
                # Show site breakdown if available
                if has_vacuum_site:
                    ny_avg = pd.to_numeric(vacuum_df[vacuum_df['Site'] == 'NY'][vacuum_col], errors='coerce').mean()
                    vt_avg = pd.to_numeric(vacuum_df[vacuum_df['Site'] == 'VT'][vacuum_col], errors='coerce').mean()
                    st.metric("Avg Vacuum", f"{avg_vac:.1f}\"", delta=status)
                    if not pd.isna(ny_avg) and not pd.isna(vt_avg):
                        st.caption(f"🟦 NY: {ny_avg:.1f}\" | 🟩 VT: {vt_avg:.1f}\"")
                else:
                    st.metric("Avg Vacuum", f"{avg_vac:.1f}\"", delta=status)
            else:
                st.metric("Avg Vacuum", "N/A")
        else:
            st.metric("Avg Vacuum", "N/A")

    with col3:
        critical = get_critical_sensors(vacuum_df)
        problem_count = len(critical)
        st.metric("Problem Sensors", problem_count,
                  delta="🔴" if problem_count > 20 else ("🟡" if problem_count > 10 else "🟢"))
        
        # Show site breakdown of problems if available
        if not critical.empty and 'Site' in critical.columns:
            site_counts = critical['Site'].value_counts()
            breakdown = " | ".join([f"🟦 {site_counts.get('NY', 0)}" if s == 'NY' 
                                   else f"🟩 {site_counts.get('VT', 0)}" 
                                   for s in ['NY', 'VT'] if s in site_counts.index])
            if breakdown:
                st.caption(breakdown)

    with col4:
        # Get weather
        weather = get_today_weather_brief()
        if weather:
            likelihood = calculate_sap_likelihood_today(weather['high'], weather['low'])
            if likelihood:
                if likelihood >= 70:
                    flow_status = "🟢 Excellent"
                elif likelihood >= 50:
                    flow_status = "🟡 Good"
                elif likelihood >= 30:
                    flow_status = "🟠 Fair"
                else:
                    flow_status = "🔴 Poor"
                st.metric("Sap Flow Today", f"{likelihood:.0f}%", delta=flow_status)
            else:
                st.metric("Sap Flow Today", "N/A")
        else:
            st.metric("Sap Flow Today", "Loading...")

    st.markdown("---")

    # Today's weather brief
    st.subheader("🌤️ Today's Conditions")

    if weather:
        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            st.markdown(f"**High:** {weather['high']:.0f}°F")

        with col2:
            st.markdown(f"**Low:** {weather['low']:.0f}°F")

        with col3:
            likelihood = calculate_sap_likelihood_today(weather['high'], weather['low'])
            if likelihood:
                if likelihood >= 70:
                    st.success(f"🟢 **Excellent sap flow expected** ({likelihood:.0f}% likelihood)")
                elif likelihood >= 50:
                    st.info(f"🟡 **Good sap flow likely** ({likelihood:.0f}% likelihood)")
                elif likelihood >= 30:
                    st.warning(f"🟠 **Fair sap flow possible** ({likelihood:.0f}% likelihood)")
                else:
                    st.error(f"🔴 **Poor sap flow expected** ({likelihood:.0f}% likelihood)")
    else:
        st.info("Weather data temporarily unavailable")

    st.markdown("---")

    # Critical alerts with site information
    st.subheader("🚨 Critical Alerts")

    critical = get_critical_sensors(vacuum_df)

    if critical.empty:
        st.success("✅ No critical alerts - all systems healthy!")
    else:
        # Group by site if available
        if 'Site' in critical.columns:
            st.error(f"⚠️ {len(critical)} sensor(s) need immediate attention")
            
            # Show breakdown by site
            for site in ['NY', 'VT', 'UNK']:
                site_problems = critical[critical['Site'] == site]
                if not site_problems.empty:
                    site_emoji = "🟦" if site == "NY" else "🟩" if site == "VT" else "⚫"
                    with st.expander(f"{site_emoji} **{site} Site** - {len(site_problems)} problem sensors", expanded=(site == 'NY')):
                        for idx, row in site_problems.head(10).iterrows():
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.markdown(f"**{row['Sensor']}**")
                            with col2:
                                st.markdown(f"🔴 {row['Vacuum']:.1f}\"")
        else:
            # No site info, show flat list
            if len(critical) <= 10:
                st.error(f"⚠️ {len(critical)} sensor(s) need immediate attention")
                for idx, row in critical.head(10).iterrows():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{row['Sensor']}**")
                    with col2:
                        st.markdown(f"🔴 {row['Vacuum']:.1f}\"")
            else:
                st.error(f"⚠️ **{len(critical)} sensors below threshold** - System-wide issue likely!")
                st.markdown("**Worst 5 locations:**")
                for idx, row in critical.head(5).iterrows():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"• {row['Sensor']}")
                    with col2:
                        st.markdown(f"🔴 {row['Vacuum']:.1f}\"")
                st.info(f"💡 {len(critical) - 5} more sensors need attention - see Vacuum Performance page")

    st.markdown("---")

    # Today's Action Plan
    st.subheader("✅ Today's Action Plan")
    st.markdown("*Prioritized tasks based on current conditions*")

    actions = generate_action_plan(vacuum_df, personnel_df, weather)

    # Estimate total time
    total_time = 0
    for action in actions:
        time_str = action['time_estimate']
        if 'h' in time_str:
            hours = float(time_str.replace('h', '').replace('Full day', '8').replace('All day', '8'))
            total_time += hours
        elif 'min' in time_str:
            mins = float(time_str.replace('min', ''))
            total_time += mins / 60

    st.info(
        f"📅 Estimated time needed: **{total_time:.1f} hours** | 👥 Recommended crew size: **{max(1, int(total_time / 8) + 1)} person(s)**")

    # Display actions
    for i, action in enumerate(actions, 1):
        priority_color = {
            1: "🔴",
            2: "🟡",
            3: "🟢"
        }

        with st.expander(
                f"{priority_color[action['priority']]} **{i}. {action['action']}** ({action['time_estimate']})",
                expanded=(action['priority'] == 1)):

            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"**Category:** {action['category']}")
                st.markdown(f"**Details:** {action['detail']}")
                st.markdown("**Recommended Steps:**")
                st.markdown(action['recommendation'])

            with col2:
                st.markdown(f"**Priority:** {action['priority']}")
                st.markdown(f"**Time:** {action['time_estimate']}")

                if action['priority'] == 1:
                    st.error("⚠️ High Priority")
                elif action['priority'] == 2:
                    st.warning("⚡ Medium Priority")
                else:
                    st.success("📋 Routine")

    st.markdown("---")

    # Quick links
    st.subheader("🔗 Quick Access")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        **Data & Analysis**
        - 🔧 Vacuum Performance - System status
        - 🌍 Interactive Map - Visual layout
        - 🗺️ Problem Clusters - Geographic issues
        """)

    with col2:
        st.markdown("""
        **Operations**
        - 🌳 Tapping Operations - Productivity
        - 🔧 Maintenance Tracking - Log work
        - ⭐ Employee Effectiveness - Performance
        """)

    with col3:
        st.markdown("""
        **Planning**
        - 🌡️ Sap Flow Forecast - 10-day outlook
        - 📊 Raw Data - Detailed analysis
        - 👥 Employee Performance - Rankings
        """)

    st.markdown("---")

    # Yesterday's summary with site breakdown
    if not personnel_df.empty:
        st.subheader("📊 Yesterday's Summary")

        date_col = find_column(personnel_df, 'Date', 'date', 'timestamp')
        if date_col:
            yesterday = datetime.now().date() - timedelta(days=1)
            yesterday_data = personnel_df[pd.to_datetime(personnel_df[date_col]).dt.date == yesterday]

            if not yesterday_data.empty:
                col1, col2, col3 = st.columns(3)

                with col1:
                    emp_col = find_column(yesterday_data, 'Employee Name', 'employee', 'name')
                    if emp_col:
                        emp_count = yesterday_data[emp_col].nunique()
                        st.metric("Employees", emp_count)

                with col2:
                    hours_col = find_column(yesterday_data, 'Hours', 'hours', 'time')
                    if hours_col:
                        total_hours = yesterday_data[hours_col].sum()
                        st.metric("Total Hours", f"{total_hours:.1f}h")

                with col3:
                    mainline_col = find_column(yesterday_data, 'mainline', 'Mainline', 'location')
                    if mainline_col:
                        locations = yesterday_data[mainline_col].nunique()
                        st.metric("Locations Worked", locations)
                
                # Show site breakdown if available
                if has_personnel_site:
                    st.markdown("**Work Distribution by Site:**")
                    site_counts = yesterday_data['Site'].value_counts()
                    
                    cols = st.columns(len(site_counts))
                    for idx, (site, count) in enumerate(site_counts.items()):
                        with cols[idx]:
                            emoji = "🟦" if site == "NY" else "🟩" if site == "VT" else "⚫"
                            st.metric(f"{emoji} {site}", f"{count} sessions")
            else:
                st.info("No work recorded for yesterday")

    st.markdown("---")

    # Footer with tips
    with st.expander("💡 How to Use This Page"):
        st.markdown("""
        This page gives you a quick morning briefing to start your day efficiently.

        **Best Practice:**
        1. **Check this page first thing** each morning
        2. **Review critical alerts** - address red items immediately
        3. **Check weather/sap flow** - plan capacity accordingly
        4. **Follow the action plan** - tasks are prioritized for you
        5. **Update throughout the day** - refresh to see latest data

        **Multi-Site Features:**
        - Quick stats show breakdown by site (NY/VT)
        - Critical alerts grouped by site for better dispatch
        - Action plan includes site-specific recommendations
        - Yesterday's summary shows work distribution

        **Time-Saving Tips:**
        - Bookmark this page as your dashboard homepage
        - Check on mobile before leaving for the sugar bush
        - Share action plan with your crew
        - Use quick links to jump to detailed pages

        **Understanding Priorities:**
        - 🔴 **Priority 1 (High)**: Do these first - critical issues
        - 🟡 **Priority 2 (Medium)**: Do today if time permits
        - 🟢 **Priority 3 (Routine)**: Normal daily tasks

        The action plan is automatically generated based on:
        - Current sensor status (across all sites)
        - Weather conditions
        - Historical patterns
        - Best practices for maple operations
        """)
