"""
UI Components Module
Reusable Streamlit UI components for consistent dashboard look and feel
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import config


def display_metric_cards(metrics_dict):
    """
    Display a row of metric cards
    
    Args:
        metrics_dict: Dictionary where keys are metric names and values are dicts with:
            - 'label': Display label
            - 'value': Metric value
            - 'delta': Optional delta value
            - 'help': Optional help text
    """
    cols = st.columns(len(metrics_dict))
    
    for idx, (key, metric_info) in enumerate(metrics_dict.items()):
        with cols[idx]:
            st.metric(
                label=metric_info.get('label', key),
                value=metric_info.get('value', 'N/A'),
                delta=metric_info.get('delta'),
                help=metric_info.get('help')
            )


def display_vacuum_gauge(vacuum_value, title="Current Vacuum"):
    """
    Display a gauge chart for vacuum level
    
    Args:
        vacuum_value: Vacuum reading in inches
        title: Chart title
    """
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=vacuum_value,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title},
        delta={'reference': config.VACUUM_EXCELLENT},
        gauge={
            'axis': {'range': [None, 30]},
            'bar': {'color': config.get_vacuum_color(vacuum_value)},
            'steps': [
                {'range': [0, config.VACUUM_FAIR], 'color': "lightgray"},
                {'range': [config.VACUUM_FAIR, config.VACUUM_EXCELLENT], 'color': "gray"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': config.VACUUM_FAIR
            }
        }
    ))
    
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)


def display_trend_chart(df, x_col, y_col, title, color=None):
    """
    Display a line chart for trends
    
    Args:
        df: DataFrame with data
        x_col: Column name for x-axis
        y_col: Column name for y-axis
        title: Chart title
        color: Optional color for line
    """
    fig = px.line(df, x=x_col, y=y_col, title=title)
    
    if color:
        fig.update_traces(line_color=color)
    
    # Add threshold lines if vacuum data
    if 'vacuum' in y_col.lower():
        fig.add_hline(
            y=config.VACUUM_EXCELLENT,
            line_dash="dash",
            line_color="green",
            annotation_text="Excellent"
        )
        fig.add_hline(
            y=config.VACUUM_FAIR,
            line_dash="dash",
            line_color="orange",
            annotation_text="Fair"
        )
    
    st.plotly_chart(fig, use_container_width=True)


def display_bar_chart(df, x_col, y_col, title, color=None, orientation='v'):
    """
    Display a bar chart
    
    Args:
        df: DataFrame with data
        x_col: Column name for x-axis
        y_col: Column name for y-axis
        title: Chart title
        color: Optional color column
        orientation: 'v' for vertical, 'h' for horizontal
    """
    fig = px.bar(
        df,
        x=x_col if orientation == 'v' else y_col,
        y=y_col if orientation == 'v' else x_col,
        title=title,
        color=color,
        orientation=orientation
    )
    
    st.plotly_chart(fig, use_container_width=True)


def display_dataframe_with_filters(df, title=None, filters=None):
    """
    Display a DataFrame with optional column filters
    
    Args:
        df: DataFrame to display
        title: Optional title
        filters: Optional dict of {column: list_of_values} to filter by
    """
    if title:
        st.subheader(title)
    
    if df.empty:
        st.info("No data to display")
        return
    
    # Apply filters if provided
    filtered_df = df.copy()
    if filters:
        for col, values in filters.items():
            if col in filtered_df.columns and values:
                filtered_df = filtered_df[filtered_df[col].isin(values)]
    
    # Display
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    
    # Download button
    csv = filtered_df.to_csv(index=False)
    st.download_button(
        "📥 Download CSV",
        csv,
        f"data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
        "text/csv"
    )


def display_status_table(df, status_col='Status', sort_col=None):
    """
    Display a table with status indicators
    
    Args:
        df: DataFrame to display
        status_col: Column containing status values
        sort_col: Optional column to sort by
    """
    if df.empty:
        st.info("No data to display")
        return
    
    display_df = df.copy()
    
    if sort_col and sort_col in display_df.columns:
        display_df = display_df.sort_values(sort_col)
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            status_col: st.column_config.TextColumn(
                status_col,
                help="Current status"
            )
        }
    )


def display_ranked_list(df, rank_col, title, n=10):
    """
    Display a ranked list (e.g., top performers)
    
    Args:
        df: DataFrame with rankings
        rank_col: Column to rank by
        title: Section title
        n: Number of items to show
    """
    st.subheader(title)
    
    if df.empty:
        st.info("No data available")
        return
    
    # Show top N
    top_df = df.head(n)
    
    # Add rank column
    top_df = top_df.copy()
    top_df.insert(0, 'Rank', range(1, len(top_df) + 1))
    
    st.dataframe(top_df, use_container_width=True, hide_index=True)


def display_alert_banner(message, alert_type='info'):
    """
    Display a prominent alert banner
    
    Args:
        message: Alert message
        alert_type: 'info', 'warning', 'error', or 'success'
    """
    if alert_type == 'info':
        st.info(message)
    elif alert_type == 'warning':
        st.warning(message)
    elif alert_type == 'error':
        st.error(message)
    elif alert_type == 'success':
        st.success(message)


def display_comparison_chart(df, categories, values, title):
    """
    Display a comparison chart (e.g., comparing employees or mainlines)
    
    Args:
        df: DataFrame with data
        categories: Column name for categories (x-axis)
        values: Column name for values (y-axis)
        title: Chart title
    """
    fig = px.bar(df, x=categories, y=values, title=title)
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)


def create_two_column_layout(left_content_func, right_content_func):
    """
    Create a two-column layout and execute content functions
    
    Args:
        left_content_func: Function to call for left column content
        right_content_func: Function to call for right column content
    """
    col1, col2 = st.columns(2)
    
    with col1:
        left_content_func()
    
    with col2:
        right_content_func()


def display_summary_statistics(df, columns_to_summarize):
    """
    Display summary statistics for specified columns
    
    Args:
        df: DataFrame
        columns_to_summarize: List of column names to summarize
    """
    st.subheader("Summary Statistics")
    
    if df.empty:
        st.info("No data available")
        return
    
    summary_data = []
    
    for col in columns_to_summarize:
        if col in df.columns:
            summary_data.append({
                'Metric': col,
                'Mean': df[col].mean(),
                'Median': df[col].median(),
                'Min': df[col].min(),
                'Max': df[col].max(),
                'Std Dev': df[col].std()
            })
    
    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)


def display_heatmap(df, x_col, y_col, value_col, title):
    """
    Display a heatmap visualization
    
    Args:
        df: DataFrame with data
        x_col: Column for x-axis
        y_col: Column for y-axis
        value_col: Column for cell values
        title: Chart title
    """
    pivot_df = df.pivot(index=y_col, columns=x_col, values=value_col)
    
    fig = px.imshow(
        pivot_df,
        title=title,
        aspect="auto",
        color_continuous_scale='RdYlGn'
    )
    
    st.plotly_chart(fig, use_container_width=True)
