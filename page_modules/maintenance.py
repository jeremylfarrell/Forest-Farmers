"""
Maintenance Tracking & Leak Detection Page Module - MULTI-SITE POLISHED
Automatically detect vacuum leaks for proactive maintenance
Now with site-aware recommendations
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import config
from utils import find_column, get_vacuum_column


def detect_leaks(vacuum_df, hours_for_sudden=6, sudden_drop_threshold=5.0,
                 days_for_gradual=7, gradual_drop_threshold=3.0):
    """
    Detect potential leaks in vacuum system with site information

    Args:
        vacuum_df: Vacuum sensor data
        hours_for_sudden: Time window for sudden drop detection (default 6h)
        sudden_drop_threshold: Vacuum drop that indicates sudden leak (default 5")
        days_for_gradual: Time window for gradual degradation (default 7 days)
        gradual_drop_threshold: Vacuum drop that indicates gradual leak (default 3")

    Returns:
        DataFrame with detected leaks including site information
    """
    if vacuum_df.empty:
        return pd.DataFrame()

    sensor_col = find_column(vacuum_df, 'Name', 'name', 'mainline', 'Sensor Name', 'sensor', 'location')
    vacuum_col = get_vacuum_column(vacuum_df)
    timestamp_col = find_column(
        vacuum_df,
        'Last communication', 'Last Communication', 'Timestamp', 'timestamp'
    )

    if not all([sensor_col, vacuum_col, timestamp_col]):
        return pd.DataFrame()

    # Prepare data
    df = vacuum_df[[sensor_col, vacuum_col, timestamp_col]].copy()
    
    # Add site if available
    if 'Site' in vacuum_df.columns:
        df['Site'] = vacuum_df['Site']
    
    df.columns = ['Sensor', 'Vacuum', 'Timestamp'] + (['Site'] if 'Site' in vacuum_df.columns else [])
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
    df['Vacuum'] = pd.to_numeric(df['Vacuum'], errors='coerce')
    df = df.dropna()
    df = df.sort_values(['Sensor', 'Timestamp'])

    leaks = []
    has_site = 'Site' in df.columns

    for sensor in df['Sensor'].unique():
        sensor_data = df[df['Sensor'] == sensor].copy()

        if len(sensor_data) < 2:
            continue

        # Get site for this sensor if available
        sensor_site = sensor_data['Site'].iloc[0] if has_site else None

        # Get latest reading
        latest = sensor_data.iloc[-1]
        current_vacuum = latest['Vacuum']
        current_time = latest['Timestamp']

        # Check for SUDDEN drop (last 6 hours)
        recent_cutoff = current_time - timedelta(hours=hours_for_sudden)
        recent_data = sensor_data[sensor_data['Timestamp'] >= recent_cutoff]

        if len(recent_data) >= 2:
            max_recent = recent_data['Vacuum'].max()
            drop = max_recent - current_vacuum

            if drop >= sudden_drop_threshold:
                leak_info = {
                    'Sensor': sensor,
                    'Type': 'Sudden Leak',
                    'Current_Vacuum': current_vacuum,
                    'Previous_Vacuum': max_recent,
                    'Drop': drop,
                    'Time_Period': f'{hours_for_sudden}h',
                    'Severity': 'Critical' if drop > 8 else 'High',
                    'Detected_At': current_time,
                    'Priority': 1
                }
                if has_site:
                    leak_info['Site'] = sensor_site
                leaks.append(leak_info)

        # Check for GRADUAL degradation (last 7 days)
        gradual_cutoff = current_time - timedelta(days=days_for_gradual)
        historical_data = sensor_data[sensor_data['Timestamp'] >= gradual_cutoff]

        if len(historical_data) >= 10:  # Need enough data points
            # Get average from first 25% of period
            early_period = historical_data.head(len(historical_data) // 4)
            early_avg = early_period['Vacuum'].mean()

            drop = early_avg - current_vacuum

            if drop >= gradual_drop_threshold:
                # Make sure this isn't already flagged as sudden
                if not any(l['Sensor'] == sensor and l['Type'] == 'Sudden Leak' for l in leaks):
                    leak_info = {
                        'Sensor': sensor,
                        'Type': 'Gradual Degradation',
                        'Current_Vacuum': current_vacuum,
                        'Previous_Vacuum': early_avg,
                        'Drop': drop,
                        'Time_Period': f'{days_for_gradual}d',
                        'Severity': 'Medium' if drop < 5 else 'High',
                        'Detected_At': current_time,
                        'Priority': 2
                    }
                    if has_site:
                        leak_info['Site'] = sensor_site
                    leaks.append(leak_info)

    if leaks:
        return pd.DataFrame(leaks).sort_values(['Priority', 'Drop'], ascending=[True, False])
    else:
        return pd.DataFrame()


def render(vacuum_df, personnel_df):
    """Render leak detection page with site awareness"""

    st.title("🔧 Maintenance & Leak Detection")
    st.markdown("*Automatically detect vacuum issues for proactive maintenance*")

    if vacuum_df.empty:
        st.warning("No vacuum data available for leak detection")
        return

    # Check site context
    has_site = 'Site' in vacuum_df.columns
    viewing_site = None
    
    if has_site and len(vacuum_df['Site'].unique()) == 1:
        viewing_site = vacuum_df['Site'].iloc[0]
        site_emoji = "🟦" if viewing_site == "NY" else "🟩" if viewing_site == "VT" else "⚫"
        st.info(f"{site_emoji} **Analyzing {viewing_site} site** - Leak detection optimized for this location")
    elif has_site:
        site_counts = vacuum_df['Site'].value_counts()
        st.info(f"📊 **Analyzing all sites** - Will group issues by location for efficient dispatch")

    # Detection settings
    with st.expander("⚙️ Detection Settings", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Sudden Leak Detection**")
            sudden_hours = st.slider(
                "Time window (hours)",
                min_value=1,
                max_value=24,
                value=6,
                help="Look for drops within this many hours"
            )
            sudden_threshold = st.slider(
                "Drop threshold (inches)",
                min_value=2.0,
                max_value=10.0,
                value=5.0,
                step=0.5,
                help="Flag if vacuum drops by this much"
            )

        with col2:
            st.markdown("**Gradual Degradation Detection**")
            gradual_days = st.slider(
                "Time window (days)",
                min_value=3,
                max_value=14,
                value=7,
                help="Look for degradation over this many days"
            )
            gradual_threshold = st.slider(
                "Drop threshold (inches)",
                min_value=1.0,
                max_value=8.0,
                value=3.0,
                step=0.5,
                help="Flag if vacuum drops by this much"
            )

    # Run leak detection
    with st.spinner("Analyzing vacuum data for leaks..."):
        leaks_df = detect_leaks(
            vacuum_df,
            hours_for_sudden=sudden_hours,
            sudden_drop_threshold=sudden_threshold,
            days_for_gradual=gradual_days,
            gradual_drop_threshold=gradual_threshold
        )

    st.divider()

    # Display results
    if leaks_df.empty:
        st.success("🎉 No leaks detected! All systems operating normally.")
        if viewing_site:
            st.info(f"The {viewing_site} site shows no significant vacuum drops in the configured time windows.")
        else:
            st.info("No sensors at either site show significant vacuum drops in the configured time windows.")
    else:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Issues", len(leaks_df))

        with col2:
            critical = len(leaks_df[leaks_df['Severity'] == 'Critical'])
            st.metric("🔴 Critical", critical)

        with col3:
            high = len(leaks_df[leaks_df['Severity'] == 'High'])
            st.metric("🟠 High", high)

        with col4:
            medium = len(leaks_df[leaks_df['Severity'] == 'Medium'])
            st.metric("🟡 Medium", medium)

        # Site breakdown if viewing all sites
        if has_site and 'Site' in leaks_df.columns and not viewing_site:
            st.markdown("**Issues by Site:**")
            
            site_issues = leaks_df['Site'].value_counts().reset_index()
            site_issues.columns = ['Site', 'Count']
            
            cols = st.columns(len(site_issues))
            for idx, row in site_issues.iterrows():
                with cols[idx]:
                    emoji = "🟦" if row['Site'] == "NY" else "🟩" if row['Site'] == "VT" else "⚫"
                    st.metric(f"{emoji} {row['Site']}", f"{row['Count']} issues")

        st.divider()

        # Detected leaks table grouped by site if applicable
        if has_site and 'Site' in leaks_df.columns and not viewing_site:
            st.subheader(f"⚠️ Detected Issues by Site ({len(leaks_df)} total)")
            
            # Group by site for easier dispatch
            for site in sorted(leaks_df['Site'].unique()):
                site_leaks = leaks_df[leaks_df['Site'] == site]
                site_emoji = "🟦" if site == "NY" else "🟩" if site == "VT" else "⚫"
                
                with st.expander(f"{site_emoji} **{site} Site** - {len(site_leaks)} issue(s)", expanded=True):
                    display = site_leaks.copy()
                    display['Current'] = display['Current_Vacuum'].apply(lambda x: f"{x:.1f}\"")
                    display['Previous'] = display['Previous_Vacuum'].apply(lambda x: f"{x:.1f}\"")
                    display['Drop'] = display['Drop'].apply(lambda x: f"↓{x:.1f}\"")
                    display['Detected'] = display['Detected_At'].dt.strftime('%Y-%m-%d %H:%M')

                    # Add severity emoji
                    severity_emoji = {
                        'Critical': '🔴',
                        'High': '🟠',
                        'Medium': '🟡'
                    }
                    display['Status'] = display['Severity'].apply(lambda x: f"{severity_emoji.get(x, '')} {x}")

                    # Select columns for display
                    display_cols = ['Status', 'Sensor', 'Type', 'Current', 'Previous', 'Drop', 'Time_Period', 'Detected']
                    col_names = ['⚫', 'Location', 'Issue Type', 'Current', 'Was', 'Change', 'Period', 'Detected']

                    display_table = display[display_cols].copy()
                    display_table.columns = col_names

                    st.dataframe(display_table, use_container_width=True, hide_index=True)
        else:
            # Single site or no site info - flat list
            st.subheader(f"⚠️ Detected Issues ({len(leaks_df)} locations)")

            display = leaks_df.copy()
            display['Current'] = display['Current_Vacuum'].apply(lambda x: f"{x:.1f}\"")
            display['Previous'] = display['Previous_Vacuum'].apply(lambda x: f"{x:.1f}\"")
            display['Drop'] = display['Drop'].apply(lambda x: f"↓{x:.1f}\"")
            display['Detected'] = display['Detected_At'].dt.strftime('%Y-%m-%d %H:%M')

            # Add severity emoji
            severity_emoji = {
                'Critical': '🔴',
                'High': '🟠',
                'Medium': '🟡'
            }
            display['Status'] = display['Severity'].apply(lambda x: f"{severity_emoji.get(x, '')} {x}")

            # Select columns for display
            display_cols = ['Status', 'Sensor', 'Type', 'Current', 'Previous', 'Drop', 'Time_Period', 'Detected']
            col_names = ['⚫', 'Location', 'Issue Type', 'Current', 'Was', 'Change', 'Period', 'Detected']

            display_table = display[display_cols].copy()
            display_table.columns = col_names

            st.dataframe(display_table, use_container_width=True, hide_index=True, height=400)

        # Action recommendations
        st.divider()
        st.subheader("✅ Recommended Actions")

        # Group recommendations by site if viewing all
        if has_site and 'Site' in leaks_df.columns and not viewing_site:
            for site in sorted(leaks_df['Site'].unique()):
                site_leaks = leaks_df[leaks_df['Site'] == site]
                site_emoji = "🟦" if site == "NY" else "🟩" if site == "VT" else "⚫"
                
                st.markdown(f"### {site_emoji} {site} Site Priorities")
                
                for idx, leak in site_leaks.head(3).iterrows():
                    with st.expander(f"🔧 {leak['Sensor']} - {leak['Type']}", expanded=(idx == site_leaks.index[0])):
                        col1, col2 = st.columns([2, 1])

                        with col1:
                            st.markdown(f"**Issue:** {leak['Type']}")
                            st.markdown(f"**Severity:** {leak['Severity']}")
                            st.markdown(f"**Vacuum Drop:** {leak['Drop']:.1f}\" over {leak['Time_Period']}")
                            st.markdown(f"**Current Reading:** {leak['Current_Vacuum']:.1f}\"")

                        with col2:
                            st.markdown("**Priority:**")
                            st.markdown(f"{'🔴' * leak['Priority']} Level {leak['Priority']}")
                            st.markdown(f"**Site:** {site_emoji} {site}")

                        st.markdown("---")

                        if leak['Type'] == 'Sudden Leak':
                            st.markdown(f"""
                            **Likely Causes:**
                            - ✗ Broken or disconnected line
                            - ✗ Releaser malfunction
                            - ✗ Major crack in tubing
                            - ✗ Pump failure

                            **Recommended Action ({site} Crew):**
                            1. Inspect this mainline immediately
                            2. Check releaser for proper operation
                            3. Walk the line looking for visible damage
                            4. Check pump pressure gauge
                            5. Test for leaks with smoke or listen for hissing
                            """)
                        else:
                            st.markdown(f"""
                            **Likely Causes:**
                            - ✗ Small leak developing
                            - ✗ Multiple small taps leaking
                            - ✗ Gradual releaser degradation
                            - ✗ Accumulating sap in lines

                            **Recommended Action ({site} Crew):**
                            1. Schedule inspection within 24-48 hours
                            2. Check tap connections for leaks
                            3. Inspect releaser seals
                            4. Check for sap buildup in lines
                            5. Consider preventive maintenance
                            """)
        else:
            # Single site view - standard recommendations
            for idx, leak in leaks_df.head(5).iterrows():
                with st.expander(f"🔧 {leak['Sensor']} - {leak['Type']}", expanded=(idx == 0)):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.markdown(f"**Issue:** {leak['Type']}")
                        st.markdown(f"**Severity:** {leak['Severity']}")
                        st.markdown(f"**Vacuum Drop:** {leak['Drop']:.1f}\" over {leak['Time_Period']}")
                        st.markdown(f"**Current Reading:** {leak['Current_Vacuum']:.1f}\"")

                    with col2:
                        st.markdown("**Priority:**")
                        st.markdown(f"{'🔴' * leak['Priority']} Level {leak['Priority']}")

                    st.markdown("---")

                    if leak['Type'] == 'Sudden Leak':
                        st.markdown("""
                        **Likely Causes:**
                        - ✗ Broken or disconnected line
                        - ✗ Releaser malfunction
                        - ✗ Major crack in tubing
                        - ✗ Pump failure

                        **Recommended Action:**
                        1. Inspect this mainline immediately
                        2. Check releaser for proper operation
                        3. Walk the line looking for visible damage
                        4. Check pump pressure gauge
                        5. Test for leaks with smoke or listen for hissing
                        """)
                    else:
                        st.markdown("""
                        **Likely Causes:**
                        - ✗ Small leak developing
                        - ✗ Multiple small taps leaking
                        - ✗ Gradual releaser degradation
                        - ✗ Accumulating sap in lines

                        **Recommended Action:**
                        1. Schedule inspection within 24-48 hours
                        2. Check tap connections for leaks
                        3. Inspect releaser seals
                        4. Check for sap buildup in lines
                        5. Consider preventive maintenance
                        """)

    st.divider()

    # Tips
    with st.expander("💡 Understanding Leak Detection"):
        st.markdown("""
        **How It Works:**
        
        This page automatically analyzes vacuum patterns to identify potential leaks:
        
        - **Sudden Leaks**: Sharp drops over hours (default: 5" in 6 hours)
        - **Gradual Degradation**: Slow decline over days (default: 3" in 7 days)
        
        **Multi-Site Features:**
        
        When viewing all sites:
        - Issues grouped by site for efficient dispatch
        - Crew recommendations site-specific
        - Compare leak patterns between locations
        - Identify if one site has more issues
        
        When viewing single site:
        - Focused leak detection for that location
        - Clean, targeted recommendations
        - Site-specific context in alerts
        
        **Severity Levels:**
        
        - **Critical** (🔴): Drop >8" - Immediate action required
        - **High** (🟠): Drop 5-8" - Address today
        - **Medium** (🟡): Drop 3-5" - Schedule soon
        
        **False Positives:**
        
        Some vacuum drops are normal:
        - Initial system startup
        - Seasonal temperature changes
        - Intentional shutdowns
        - Maintenance work
        
        **Best Practices:**
        
        - Check this page daily before dispatch
        - Address critical issues immediately
        - Track patterns to predict failures
        - Share solutions if one site solves a recurring issue
        - Compare leak frequencies between sites
        - Consider site-specific environmental factors
        
        **Using Detection Settings:**
        
        Adjust thresholds based on your system:
        - **Tighter settings**: Catch more issues, some false positives
        - **Looser settings**: Only major problems, may miss small leaks
        - **Recommended**: Start with defaults, tune based on experience
        """)
