"""
Custom Styling Module
Adds enhanced visual styling to the dashboard
"""

import streamlit as st


def apply_custom_css():
    """Apply custom CSS styling to the dashboard"""

    st.markdown("""
    <style>
    /* ========================================
       MAPLE THEME CUSTOM STYLING
       ======================================== */

    /* Main container styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Header styling */
    h1 {
        color: #8B4513;
        font-weight: 700;
        padding-bottom: 0.5rem;
        border-bottom: 3px solid #D2691E;
        margin-bottom: 1.5rem;
    }

    h2 {
        color: #A0522D;
        font-weight: 600;
        margin-top: 1.5rem;
    }

    h3 {
        color: #CD853F;
        font-weight: 600;
    }

    /* Metric card styling */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #8B4513;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        font-weight: 600;
        color: #654321;
    }

    [data-testid="stMetricDelta"] {
        font-size: 0.9rem;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #F5DEB3 0%, #F0E5D0 100%);
    }

    [data-testid="stSidebar"] h1 {
        color: #654321;
        border-bottom: 2px solid #8B4513;
    }

    /* Radio button styling */
    [data-testid="stSidebar"] .stRadio > label {
        font-weight: 600;
        color: #654321;
    }

    /* Make radio buttons more prominent */
    [data-testid="stSidebar"] [role="radiogroup"] label {
        padding: 0.5rem;
        border-radius: 0.5rem;
        transition: background-color 0.3s;
    }

    [data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background-color: rgba(210, 105, 30, 0.1);
    }

    /* Button styling */
    .stButton > button {
        background: linear-gradient(90deg, #D2691E 0%, #C7522A 100%);
        color: white;
        border: none;
        border-radius: 0.5rem;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s;
    }

    .stButton > button:hover {
        background: linear-gradient(90deg, #C7522A 0%, #B8441D 100%);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        transform: translateY(-2px);
    }

    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: rgba(245, 222, 179, 0.5);
        border-radius: 0.5rem;
        font-weight: 600;
        color: #654321;
    }

    .streamlit-expanderHeader:hover {
        background-color: rgba(245, 222, 179, 0.8);
    }

    /* Dataframe styling */
    .dataframe {
        border-radius: 0.5rem;
        overflow: hidden;
    }

    /* Info/Success/Warning/Error boxes */
    .stAlert {
        border-radius: 0.5rem;
        border-left: 4px solid;
    }

    /* Success boxes - green */
    [data-baseweb="notification"][kind="success"] {
        background-color: rgba(40, 167, 69, 0.1);
        border-left-color: #28a745;
    }

    /* Info boxes - blue */
    [data-baseweb="notification"][kind="info"] {
        background-color: rgba(210, 105, 30, 0.1);
        border-left-color: #D2691E;
    }

    /* Warning boxes - yellow */
    [data-baseweb="notification"][kind="warning"] {
        background-color: rgba(255, 193, 7, 0.1);
        border-left-color: #ffc107;
    }

    /* Error boxes - red */
    [data-baseweb="notification"][kind="error"] {
        background-color: rgba(220, 53, 69, 0.1);
        border-left-color: #dc3545;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(245, 222, 179, 0.3);
        padding: 0.5rem;
        border-radius: 0.5rem;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 0.5rem;
        padding: 0.5rem 1rem;
        font-weight: 600;
        color: #654321;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(90deg, #D2691E 0%, #C7522A 100%);
        color: white;
    }

    /* Divider styling */
    hr {
        margin: 1.5rem 0;
        border: none;
        border-top: 2px solid rgba(210, 105, 30, 0.3);
    }

    /* Input field styling */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > select {
        border-radius: 0.5rem;
        border: 2px solid rgba(210, 105, 30, 0.3);
    }

    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stSelectbox > div > div > select:focus {
        border-color: #D2691E;
        box-shadow: 0 0 0 0.2rem rgba(210, 105, 30, 0.25);
    }

    /* Slider styling */
    .stSlider > div > div > div > div {
        background-color: #D2691E;
    }

    /* Checkbox styling */
    .stCheckbox > label {
        font-weight: 500;
        color: #654321;
    }

    /* Caption text */
    .caption {
        color: #8B7355;
        font-size: 0.85rem;
    }

    /* Code blocks */
    code {
        background-color: rgba(139, 69, 19, 0.1);
        padding: 0.2rem 0.4rem;
        border-radius: 0.25rem;
        color: #8B4513;
    }

    /* Plotly charts - ensure they look good with theme */
    .js-plotly-plot .plotly {
        border-radius: 0.5rem;
    }

    /* Add subtle maple leaf watermark to main content */
    .main::before {
        content: "🍁";
        position: fixed;
        bottom: 20px;
        right: 20px;
        font-size: 3rem;
        opacity: 0.1;
        pointer-events: none;
        z-index: 0;
    }

    /* Improve spacing */
    .element-container {
        margin-bottom: 0.5rem;
    }

    /* Make forms look better */
    [data-testid="stForm"] {
        background-color: rgba(245, 222, 179, 0.2);
        border-radius: 0.5rem;
        padding: 1rem;
        border: 1px solid rgba(210, 105, 30, 0.2);
    }

    /* Improve table appearance */
    .dataframe thead tr th {
        background-color: #D2691E !important;
        color: white !important;
        font-weight: 600 !important;
    }

    .dataframe tbody tr:nth-child(even) {
        background-color: rgba(245, 222, 179, 0.2);
    }

    .dataframe tbody tr:hover {
        background-color: rgba(210, 105, 30, 0.1);
    }

    /* ========================================
       RESPONSIVE DESIGN
       ======================================== */

    @media (max-width: 768px) {
        .main .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }

        h1 {
            font-size: 1.75rem;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.5rem;
        }
    }

    /* ========================================
       DARK THEME OVERRIDES (when using dark base)
       ======================================== */

    @media (prefers-color-scheme: dark) {
        /* These styles apply when dark theme is active */
        .dataframe thead tr th {
            background-color: #FF6B35 !important;
        }

        .stButton > button {
            background: linear-gradient(90deg, #FF6B35 0%, #FF8C42 100%);
        }

        .main::before {
            opacity: 0.05;
        }
    }

    /* ========================================
       ANIMATION ENHANCEMENTS
       ======================================== */

    /* Fade in animation for main content */
    .main > div {
        animation: fadeIn 0.5s ease-in;
    }

    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* Pulse animation for critical alerts */
    .stAlert[data-baseweb="notification"][kind="error"] {
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0%, 100% {
            box-shadow: 0 0 0 0 rgba(220, 53, 69, 0.4);
        }
        50% {
            box-shadow: 0 0 0 10px rgba(220, 53, 69, 0);
        }
    }

    /* Make dataframe scrollbars bigger and always visible */
    [data-testid="stDataFrame"] ::-webkit-scrollbar {
        width: 14px !important;
        height: 14px !important;
    }

    [data-testid="stDataFrame"] ::-webkit-scrollbar-track {
        background: #f0f0f0 !important;
        border-radius: 7px !important;
    }

    [data-testid="stDataFrame"] ::-webkit-scrollbar-thumb {
        background-color: #8B4513 !important;
        border-radius: 7px !important;
        border: 2px solid #f0f0f0 !important;
    }

    [data-testid="stDataFrame"] ::-webkit-scrollbar-thumb:hover {
        background-color: #654321 !important;
    }

    </style>
    """, unsafe_allow_html=True)


def add_maple_header():
    """Add a decorative maple-themed header"""
    st.markdown("""
    <div style="text-align: center; padding: 1rem; background: linear-gradient(90deg, #F5DEB3 0%, #FFE4B5 50%, #F5DEB3 100%); border-radius: 0.5rem; margin-bottom: 1rem;">
        <span style="font-size: 2rem;">🍁</span>
        <span style="font-size: 1.5rem; font-weight: 700; color: #8B4513; margin: 0 1rem;">Forest Farmers Dashboard</span>
        <span style="font-size: 2rem;">🍁</span>
    </div>
    """, unsafe_allow_html=True)


def add_page_footer():
    """Add a subtle footer to pages"""
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0 1rem 0; color: #8B7355; font-size: 0.85rem; border-top: 1px solid rgba(210, 105, 30, 0.2);">
        🍁 Forest Farmers Maple Operations Dashboard | Made with Streamlit
    </div>
    """, unsafe_allow_html=True)


def metric_card(label, value, delta=None, emoji=""):
    """Create a custom styled metric card"""
    delta_html = ""
    if delta:
        delta_color = "#28a745" if "+" in str(delta) or delta > 0 else "#dc3545"
        delta_html = f'<div style="color: {delta_color}; font-size: 0.9rem; font-weight: 600;">{delta}</div>'

    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, rgba(245, 222, 179, 0.3) 0%, rgba(255, 228, 181, 0.3) 100%);
        border-left: 4px solid #D2691E;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    ">
        <div style="font-size: 0.85rem; color: #654321; font-weight: 600; margin-bottom: 0.5rem;">
            {emoji} {label}
        </div>
        <div style="font-size: 2rem; color: #8B4513; font-weight: 700;">
            {value}
        </div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)