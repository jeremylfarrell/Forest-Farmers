"""
Raw Data Explorer Page Module
Displays and exports raw data from vacuum and personnel sheets
"""

import streamlit as st
from datetime import datetime


def render(vacuum_df, personnel_df):
    """Render raw data explorer page"""

    st.title("📊 Raw Data Explorer")

    data_type = st.radio("Select Data", ["Vacuum Data", "Personnel Data"])

    if data_type == "Vacuum Data":
        st.subheader("Vacuum Sensor Data")

        if not vacuum_df.empty:
            st.write(f"Total records: **{len(vacuum_df):,}**")
            st.dataframe(vacuum_df.head(100), use_container_width=True)

            csv = vacuum_df.to_csv(index=False)
            st.download_button(
                "📥 Download Full Dataset (CSV)",
                csv,
                f"vacuum_data_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv"
            )
        else:
            st.info("No vacuum data available")

    else:
        st.subheader("Personnel Timesheet Data")

        if not personnel_df.empty:
            st.write(f"Total records: **{len(personnel_df):,}**")
            st.dataframe(personnel_df.head(100), use_container_width=True)

            csv = personnel_df.to_csv(index=False)
            st.download_button(
                "📥 Download Full Dataset (CSV)",
                csv,
                f"personnel_data_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv"
            )
        else:
            st.info("No personnel data available")
