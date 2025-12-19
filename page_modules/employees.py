"""
Employee Performance Page Module - MULTI-SITE ENHANCED
Displays employee activity and productivity metrics with site awareness
"""

import streamlit as st
import pandas as pd
import config
from utils import find_column


def render(personnel_df):
    """Render employee performance page with site tracking"""

    st.title("👥 Employee Performance")

    if personnel_df.empty:
        st.warning("No personnel data available")
        return

    # Check if we have site information
    has_site = 'Site' in personnel_df.columns

    # Find column names (case-insensitive)
    emp_name_col = find_column(personnel_df, 'Employee Name', 'employee', 'name')
    mainline_col = find_column(personnel_df, 'mainline', 'Mainline', 'location', 'sensor')
    hours_col = find_column(personnel_df, 'Hours', 'hours', 'time')
    date_col = find_column(personnel_df, 'Date', 'date', 'timestamp')

    if not emp_name_col:
        st.warning("Employee Name column not found")
        st.info("Available columns: " + ", ".join(personnel_df.columns))
        return

    # Build aggregation dict dynamically
    agg_dict = {}

    if hours_col:
        agg_dict[hours_col] = 'sum'

    if mainline_col:
        agg_dict[mainline_col] = 'nunique'

    if date_col:
        agg_dict[date_col] = 'count'
    elif emp_name_col:
        agg_dict[emp_name_col] = 'count'

    if not agg_dict:
        st.warning("Required columns for analysis not found")
        return

    # Calculate employee summary
    emp_summary = personnel_df.groupby(emp_name_col).agg(agg_dict).reset_index()

    # Rename columns based on what we found
    col_mapping = {emp_name_col: 'Employee'}
    if hours_col:
        col_mapping[hours_col] = 'Total_Hours'
    if mainline_col:
        col_mapping[mainline_col] = 'Locations'
    if date_col:
        col_mapping[date_col] = 'Entries'
    elif emp_name_col in emp_summary.columns and emp_name_col != 'Employee':
        for col in emp_summary.columns:
            if col not in col_mapping:
                col_mapping[col] = 'Entries'

    emp_summary = emp_summary.rename(columns=col_mapping)

    # Add site information if available
    if has_site:
        # Calculate primary site (where they work most) and site distribution
        emp_sites = personnel_df.groupby(emp_name_col)['Site'].agg([
            ('Primary_Site', lambda x: x.value_counts().index[0] if len(x) > 0 else 'UNK'),
            ('Sites_Worked', lambda x: ', '.join(sorted(x.unique()))),
            ('NY_Sessions', lambda x: (x == 'NY').sum()),
            ('VT_Sessions', lambda x: (x == 'VT').sum()),
            ('UNK_Sessions', lambda x: (x == 'UNK').sum())
        ]).reset_index()
        
        emp_sites.columns = ['Employee', 'Primary_Site', 'Sites_Worked', 'NY_Sessions', 'VT_Sessions', 'UNK_Sessions']
        
        # Merge with summary
        emp_summary = emp_summary.merge(emp_sites, on='Employee', how='left')

    # Filter by minimum hours if available
    if 'Total_Hours' in emp_summary.columns:
        emp_summary = emp_summary[emp_summary['Total_Hours'] >= config.MIN_HOURS_FOR_RANKING]
        emp_summary = emp_summary.sort_values('Total_Hours', ascending=False)

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Employees", len(emp_summary))

    with col2:
        if 'Total_Hours' in emp_summary.columns:
            st.metric("Total Hours", f"{emp_summary['Total_Hours'].sum():.1f}h")
        else:
            st.metric("Total Hours", "N/A")

    with col3:
        if 'Locations' in emp_summary.columns:
            st.metric("Locations Worked", int(emp_summary['Locations'].sum()))
        else:
            st.metric("Locations Worked", "N/A")

    with col4:
        if 'Total_Hours' in emp_summary.columns:
            st.metric("Avg Hours/Employee", f"{emp_summary['Total_Hours'].mean():.1f}h")
        else:
            st.metric("Avg Hours/Employee", "N/A")

    # Site distribution overview if available
    if has_site:
        st.divider()
        st.subheader("🏢 Employee Distribution by Site")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            ny_primary = len(emp_summary[emp_summary['Primary_Site'] == 'NY'])
            st.metric("🟦 NY Primary", ny_primary)
            st.caption(f"{ny_primary/len(emp_summary)*100:.0f}% of employees")
        
        with col2:
            vt_primary = len(emp_summary[emp_summary['Primary_Site'] == 'VT'])
            st.metric("🟩 VT Primary", vt_primary)
            st.caption(f"{vt_primary/len(emp_summary)*100:.0f}% of employees")
        
        with col3:
            multi_site = len(emp_summary[emp_summary['Sites_Worked'].str.contains(',')])
            st.metric("🔄 Multi-Site", multi_site)
            st.caption(f"{multi_site/len(emp_summary)*100:.0f}% work both")
        
        with col4:
            unk_primary = len(emp_summary[emp_summary['Primary_Site'] == 'UNK'])
            st.metric("⚫ Unknown", unk_primary)
            st.caption(f"{unk_primary/len(emp_summary)*100:.0f}% unclassified")

    st.divider()

    # Top performers
    st.subheader("🏆 Employee Rankings")

    display = emp_summary.copy()

    # Format display columns
    display_cols = ['Employee']
    col_names = ['Employee']

    # Add primary site if available
    if has_site and 'Primary_Site' in display.columns:
        # Add emoji to primary site
        display['Primary_Site_Display'] = display['Primary_Site'].apply(
            lambda x: f"🟦 {x}" if x == 'NY' else f"🟩 {x}" if x == 'VT' else f"⚫ {x}"
        )
        display_cols.append('Primary_Site_Display')
        col_names.append('Primary Site')

    if 'Total_Hours' in display.columns:
        display['Total_Hours'] = display['Total_Hours'].apply(lambda x: f"{x:.1f}h")
        display_cols.append('Total_Hours')
        col_names.append('Hours')

    if 'Locations' in display.columns:
        display_cols.append('Locations')
        col_names.append('Locations')

    if 'Entries' in display.columns:
        display_cols.append('Entries')
        col_names.append('Days Worked')
    
    # Add sites worked if available and different from primary
    if has_site and 'Sites_Worked' in display.columns:
        display_cols.append('Sites_Worked')
        col_names.append('Sites')

    display = display[display_cols]
    display.columns = col_names

    st.dataframe(display, use_container_width=True, hide_index=True, height=400)

    st.divider()

    # Individual detail
    st.subheader("📊 Individual Detail")

    selected = st.selectbox("Select Employee", emp_summary['Employee'].tolist())

    if selected:
        emp_data = personnel_df[personnel_df[emp_name_col] == selected].copy()

        if date_col and date_col in emp_data.columns:
            emp_data = emp_data.sort_values(date_col, ascending=False)

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if hours_col:
                st.metric("Total Hours", f"{emp_data[hours_col].sum():.1f}h")
            else:
                st.metric("Total Hours", "N/A")

        with col2:
            st.metric("Days Worked", len(emp_data))

        with col3:
            if hours_col:
                st.metric("Avg Hours/Day", f"{emp_data[hours_col].mean():.1f}h")
            else:
                st.metric("Avg Hours/Day", "N/A")
        
        with col4:
            if has_site:
                primary = emp_data['Site'].value_counts().index[0] if len(emp_data) > 0 else 'UNK'
                emoji = "🟦" if primary == "NY" else "🟩" if primary == "VT" else "⚫"
                st.metric("Primary Site", f"{emoji} {primary}")

        # Site breakdown chart if available and multi-site
        if has_site and len(emp_data['Site'].unique()) > 1:
            st.subheader("Work Distribution by Site")
            
            import plotly.graph_objects as go
            
            site_hours = emp_data.groupby('Site')[hours_col].sum().reset_index() if hours_col else \
                        emp_data['Site'].value_counts().reset_index()
            
            if hours_col:
                site_hours.columns = ['Site', 'Hours']
            else:
                site_hours.columns = ['Site', 'Sessions']
            
            # Color code
            colors = []
            for site in site_hours['Site']:
                if site == 'NY':
                    colors.append('#2196F3')
                elif site == 'VT':
                    colors.append('#4CAF50')
                else:
                    colors.append('#9E9E9E')
            
            fig = go.Figure()
            
            y_col = 'Hours' if hours_col else 'Sessions'
            y_label = 'Hours Worked' if hours_col else 'Work Sessions'
            
            fig.add_trace(go.Bar(
                x=site_hours['Site'],
                y=site_hours[y_col],
                marker_color=colors,
                text=site_hours[y_col].apply(lambda x: f"{x:.1f}h" if hours_col else f"{int(x)}"),
                textposition='outside'
            ))
            
            fig.update_layout(
                yaxis_title=y_label,
                xaxis_title="Site",
                height=300,
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Session counts by site
            st.markdown("**Session Breakdown:**")
            cols = st.columns(len(site_hours))
            for idx, row in site_hours.iterrows():
                with cols[idx]:
                    emoji = "🟦" if row['Site'] == "NY" else "🟩" if row['Site'] == "VT" else "⚫"
                    if hours_col:
                        st.metric(f"{emoji} {row['Site']}", f"{row['Hours']:.1f}h")
                    else:
                        st.metric(f"{emoji} {row['Site']}", f"{int(row['Sessions'])} sessions")

        st.subheader("Recent Activity")

        # Build display columns
        display_cols = []
        if date_col:
            display_cols.append(date_col)
        
        # Add site if available
        if has_site:
            # Create site display column with emoji
            emp_data['Site_Display'] = emp_data['Site'].apply(
                lambda x: f"🟦 {x}" if x == 'NY' else f"🟩 {x}" if x == 'VT' else f"⚫ {x}"
            )
            display_cols.append('Site_Display')
        
        if mainline_col:
            display_cols.append(mainline_col)
        if hours_col:
            display_cols.append(hours_col)

        # Add any other interesting columns
        job_col = find_column(emp_data, 'Job', 'job', 'task', 'work')
        if job_col:
            display_cols.append(job_col)

        if display_cols:
            recent = emp_data[display_cols].head(20)
            
            # Rename Site_Display back to Site for cleaner display
            if 'Site_Display' in recent.columns:
                recent = recent.rename(columns={'Site_Display': 'Site'})
            
            st.dataframe(recent, use_container_width=True, hide_index=True)
        else:
            st.info("No detail columns available")

    st.divider()

    # Tips with multi-site context
    with st.expander("💡 Understanding Employee Performance"):
        st.markdown("""
        **Metrics Explained:**
        
        - **Total Hours**: All hours worked by employee
        - **Locations**: Number of unique mainlines/locations worked
        - **Days Worked**: Number of separate work sessions
        - **Primary Site**: The site where employee works most often
        - **Sites Worked**: All sites this employee has worked at
        
        **Multi-Site Features:**
        
        - **Primary Site**: Identify where each employee primarily works
        - **Multi-Site Workers**: See who works at both NY and VT
        - **Site Distribution**: Understand resource allocation
        - **Work Patterns**: Track if employees specialize or rotate
        
        **Using This Page:**
        
        - **Planning**: Assign employees based on their primary site
        - **Cross-Training**: Identify opportunities to share expertise
        - **Scheduling**: Balance crew availability across sites
        - **Recognition**: Acknowledge both specialist and versatile workers
        
        **Multi-Site Workers:**
        
        Employees who work both sites are valuable because they:
        - Can share best practices between locations
        - Provide scheduling flexibility
        - Understand site-specific challenges
        - Help maintain consistency across operations
        
        **Site Specialization:**
        
        Some employees may primarily work one site due to:
        - Proximity to their home
        - Expertise with that terrain
        - Equipment familiarity
        - Team preferences
        
        This is normal and can be an advantage - specialists develop
        deep knowledge of their site's specific challenges and solutions.
        """)
