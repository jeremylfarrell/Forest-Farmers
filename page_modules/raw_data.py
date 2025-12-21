"""
Raw Data Page Module - MULTI-SITE ENHANCED
Display raw vacuum and personnel data with site prominence
UPDATED: Tabbed interface for easier access to both datasets
"""

import streamlit as st
import pandas as pd
from utils import find_column


def render(vacuum_df, personnel_df):
    """Render raw data page with tabbed interface for vacuum and personnel data"""

    st.title("📊 Raw Data")
    st.markdown("*View and export raw data from Google Sheets*")

    # Check if we have site information
    has_vacuum_site = 'Site' in vacuum_df.columns if not vacuum_df.empty else False
    has_personnel_site = 'Site' in personnel_df.columns if not personnel_df.empty else False

    # Create tabs for vacuum and personnel data
    tab1, tab2 = st.tabs(["🔧 Vacuum Data", "👥 Personnel Data"])

    # ============================================================================
    # VACUUM DATA TAB
    # ============================================================================

    with tab1:
        st.subheader("🔧 Vacuum Sensor Data")

        if vacuum_df.empty:
            st.warning("No vacuum data available")
        else:
            # Show summary with site breakdown
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Records", f"{len(vacuum_df):,}")

            with col2:
                sensor_col = find_column(vacuum_df, 'Name', 'name', 'Sensor Name', 'sensor', 'mainline', 'location')
                if sensor_col:
                    st.metric("Unique Sensors", vacuum_df[sensor_col].nunique())

            with col3:
                if 'Date' in vacuum_df.columns:
                    date_range = vacuum_df['Date'].agg(['min', 'max'])
                    st.metric("Date Range", f"{pd.to_datetime(date_range['min']).strftime('%Y-%m-%d')} to {pd.to_datetime(date_range['max']).strftime('%Y-%m-%d')}")
            
            with col4:
                if has_vacuum_site:
                    site_counts = vacuum_df['Site'].value_counts()
                    ny_count = site_counts.get('NY', 0)
                    vt_count = site_counts.get('VT', 0)
                    st.metric("Site Distribution", f"🟦 {ny_count:,} | 🟩 {vt_count:,}")

            # Site breakdown if available
            if has_vacuum_site:
                with st.expander("📍 Records by Site", expanded=False):
                    site_summary = vacuum_df['Site'].value_counts().reset_index()
                    site_summary.columns = ['Site', 'Records']
                    
                    # Add emoji
                    site_summary['Site_Display'] = site_summary['Site'].apply(
                        lambda x: f"🟦 {x}" if x == 'NY' else f"🟩 {x}" if x == 'VT' else f"⚫ {x}"
                    )
                    
                    # Show as metrics
                    cols = st.columns(len(site_summary))
                    for idx, row in site_summary.iterrows():
                        with cols[idx]:
                            st.metric(row['Site_Display'], f"{row['Records']:,} records")

            st.markdown("---")

            # Display options
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown("**Display Options:**")

            with col2:
                num_rows = st.number_input("Rows to show", min_value=10, max_value=1000, value=100, step=10, key="vacuum_rows")

            # Prepare display dataframe
            display_df = vacuum_df.copy()

            # Move Site column to front if it exists
            if has_vacuum_site:
                cols = display_df.columns.tolist()
                cols.remove('Site')
                cols.insert(0, 'Site')
                display_df = display_df[cols]
                
                # Add emoji to Site column for display
                display_df['Site'] = display_df['Site'].apply(
                    lambda x: f"🟦 {x}" if x == 'NY' else f"🟩 {x}" if x == 'VT' else f"⚫ {x}"
                )

            # Show data
            st.dataframe(display_df.head(num_rows), use_container_width=True, height=500)

            # Column info
            with st.expander("📋 Column Information"):
                st.write(f"**Total Columns:** {len(vacuum_df.columns)}")
                st.write("**Column Names:**")
                
                # Group columns by category
                site_cols = ['Site'] if has_vacuum_site else []
                sensor_cols = [col for col in vacuum_df.columns if any(term in col.lower() for term in ['name', 'sensor', 'mainline', 'location'])]
                vacuum_cols = [col for col in vacuum_df.columns if 'vacuum' in col.lower() or 'reading' in col.lower()]
                time_cols = [col for col in vacuum_df.columns if any(term in col.lower() for term in ['time', 'date', 'timestamp', 'communication'])]
                other_cols = [col for col in vacuum_df.columns if col not in site_cols + sensor_cols + vacuum_cols + time_cols]
                
                if site_cols:
                    st.markdown("**🏢 Site Information:**")
                    st.write(", ".join(f"`{col}`" for col in site_cols))
                
                if sensor_cols:
                    st.markdown("**📍 Sensor Identification:**")
                    st.write(", ".join(f"`{col}`" for col in sensor_cols))
                
                if vacuum_cols:
                    st.markdown("**🔧 Vacuum Readings:**")
                    st.write(", ".join(f"`{col}`" for col in vacuum_cols))
                
                if time_cols:
                    st.markdown("**⏰ Timestamps:**")
                    st.write(", ".join(f"`{col}`" for col in time_cols))
                
                if other_cols:
                    st.markdown("**📊 Other:**")
                    st.write(", ".join(f"`{col}`" for col in other_cols))

            # Download
            csv = vacuum_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Vacuum Data as CSV",
                data=csv,
                file_name=f"vacuum_data_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )

    # ============================================================================
    # PERSONNEL DATA TAB
    # ============================================================================

    with tab2:
        st.subheader("👥 Personnel Timesheet Data")

        if personnel_df.empty:
            st.warning("No personnel data available")
        else:
            # Show summary with site breakdown
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Records", f"{len(personnel_df):,}")

            with col2:
                emp_col = find_column(personnel_df, 'Employee Name', 'employee', 'name')
                if emp_col:
                    st.metric("Unique Employees", personnel_df[emp_col].nunique())

            with col3:
                if 'Date' in personnel_df.columns:
                    date_range = personnel_df['Date'].agg(['min', 'max'])
                    st.metric("Date Range", f"{pd.to_datetime(date_range['min']).strftime('%Y-%m-%d')} to {pd.to_datetime(date_range['max']).strftime('%Y-%m-%d')}")
            
            with col4:
                if has_personnel_site:
                    site_counts = personnel_df['Site'].value_counts()
                    ny_count = site_counts.get('NY', 0)
                    vt_count = site_counts.get('VT', 0)
                    unk_count = site_counts.get('UNK', 0)
                    st.metric("Site Distribution", f"🟦 {ny_count} | 🟩 {vt_count} | ⚫ {unk_count}")

            # Site breakdown if available
            if has_personnel_site:
                with st.expander("📍 Work Sessions by Site", expanded=False):
                    site_summary = personnel_df['Site'].value_counts().reset_index()
                    site_summary.columns = ['Site', 'Sessions']
                    
                    # Add percentage
                    site_summary['Percentage'] = (site_summary['Sessions'] / site_summary['Sessions'].sum() * 100).round(1)
                    
                    # Add emoji
                    site_summary['Site_Display'] = site_summary['Site'].apply(
                        lambda x: f"🟦 {x}" if x == 'NY' else f"🟩 {x}" if x == 'VT' else f"⚫ {x}"
                    )
                    
                    # Show as metrics
                    cols = st.columns(len(site_summary))
                    for idx, row in site_summary.iterrows():
                        with cols[idx]:
                            st.metric(
                                row['Site_Display'], 
                                f"{row['Sessions']:,} sessions",
                                delta=f"{row['Percentage']:.1f}%"
                            )
                    
                    # Show UNK examples if they exist
                    unk_count = site_summary[site_summary['Site'] == 'UNK']['Sessions'].sum() if 'UNK' in site_summary['Site'].values else 0
                    if unk_count > 0:
                        st.warning(f"⚠️ {unk_count} work sessions classified as 'UNK' (unknown site)")
                        st.markdown("**Examples of UNK Job descriptions:**")
                        
                        unk_jobs = personnel_df[personnel_df['Site'] == 'UNK']
                        if 'Job' in unk_jobs.columns:
                            examples = unk_jobs['Job'].dropna().unique()[:5]
                            for job in examples:
                                st.text(f"• {job}")
                            
                            st.info("""
                            💡 **Tip:** Update Job descriptions to include "NY" or "VT" for better site classification.
                            
                            Examples:
                            - ✅ "Tapping - VT Woods"
                            - ✅ "Maintenance - NY Mainline 3"
                            - ❌ "Office Work" → Will be UNK
                            """)

            st.markdown("---")

            # Display options
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown("**Display Options:**")

            with col2:
                num_rows_personnel = st.number_input("Rows to show", min_value=10, max_value=1000, value=100, step=10, key="personnel_rows")

            # Prepare display dataframe
            display_df = personnel_df.copy()

            # Move Site column to front if it exists
            if has_personnel_site:
                cols = display_df.columns.tolist()
                cols.remove('Site')
                cols.insert(0, 'Site')
                display_df = display_df[cols]
                
                # Add emoji to Site column for display
                display_df['Site'] = display_df['Site'].apply(
                    lambda x: f"🟦 {x}" if x == 'NY' else f"🟩 {x}" if x == 'VT' else f"⚫ {x}"
                )

            # Show data
            st.dataframe(display_df.head(num_rows_personnel), use_container_width=True, height=500)

            # Column info
            with st.expander("📋 Column Information"):
                st.write(f"**Total Columns:** {len(personnel_df.columns)}")
                st.write("**Column Names:**")
                
                # Group columns by category
                site_cols = ['Site'] if has_personnel_site else []
                emp_cols = [col for col in personnel_df.columns if any(term in col.lower() for term in ['employee', 'name', 'ee first', 'ee last'])]
                time_cols = [col for col in personnel_df.columns if any(term in col.lower() for term in ['date', 'hours', 'time'])]
                work_cols = [col for col in personnel_df.columns if any(term in col.lower() for term in ['job', 'mainline', 'location', 'taps', 'repairs'])]
                cost_cols = [col for col in personnel_df.columns if any(term in col.lower() for term in ['rate', 'cost', 'pay'])]
                other_cols = [col for col in personnel_df.columns if col not in site_cols + emp_cols + time_cols + work_cols + cost_cols]
                
                if site_cols:
                    st.markdown("**🏢 Site Information:**")
                    st.write(", ".join(f"`{col}`" for col in site_cols))
                    st.caption("Site is parsed from Job description (NY, VT, or UNK)")
                
                if emp_cols:
                    st.markdown("**👤 Employee Information:**")
                    st.write(", ".join(f"`{col}`" for col in emp_cols))
                
                if time_cols:
                    st.markdown("**⏰ Time Tracking:**")
                    st.write(", ".join(f"`{col}`" for col in time_cols))
                
                if work_cols:
                    st.markdown("**🔧 Work Details:**")
                    st.write(", ".join(f"`{col}`" for col in work_cols))
                
                if cost_cols:
                    st.markdown("**💰 Cost Information:**")
                    st.write(", ".join(f"`{col}`" for col in cost_cols))
                
                if other_cols:
                    st.markdown("**📊 Other:**")
                    st.write(", ".join(f"`{col}`" for col in other_cols))

            # Download
            csv = personnel_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Personnel Data as CSV",
                data=csv,
                file_name=f"personnel_data_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )

    # Tips at bottom (outside tabs)
    st.divider()

    with st.expander("💡 Using Raw Data"):
        st.markdown("""
        **What's New:**
        
        - **Tabbed Interface**: Easily switch between Vacuum Data and Personnel Data
        - **Vacuum Data Now Visible**: Full vacuum sensor readings in first tab
        - **Side-by-Side Access**: No more scrolling to find the data you need
        
        **Purpose of This Page:**
        
        - **Troubleshooting**: Verify data is loading correctly
        - **Analysis**: Export for external analysis (Excel, Python, R)
        - **Column Discovery**: See all available data fields
        - **Data Quality**: Check for missing or incorrect values
        
        **Multi-Site Features:**
        
        - **Site Column**: Prominently displayed at the front
        - **Site Distribution**: See breakdown of records by site
        - **UNK Detection**: Identify work sessions needing site classification
        - **Color Coding**: 🟦 NY, 🟩 VT, ⚫ UNK
        
        **Understanding Site Classification:**
        
        **Vacuum Data:**
        - Site assigned based on which Google Sheet data came from
        - NY sheet → Site = "NY"
        - VT sheet → Site = "VT"
        
        **Personnel Data:**
        - Site parsed from Job description column
        - "NY" in job → Site = "NY"
        - "VT" in job → Site = "VT"
        - Neither → Site = "UNK"
        
        **Export Tips:**
        
        - CSV files open in Excel, Google Sheets, or any spreadsheet software
        - Use for pivot tables, advanced analysis, or custom reports
        - Filename includes today's date for easy tracking
        - Site column is included in export
        - Download buttons available in each tab
        """)
