"""Online Retail Data Warehouse & Decision Support System (CO4031) - Streamlit Dashboard.
Modular 4-Tab analytical architecture preserving Member 3's native Streamlit design style.
"""

import os
import sys
import pandas as pd
import streamlit as st

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.app.components.db_connector import get_warehouse_health_and_filters
from src.app.components.olap_views import render_overview_tab, render_olap_tab
from src.app.components.dss_views import render_segmentation_tab, render_what_if_tab


def main():
    st.set_page_config(
        page_title="Online Retail | DW & DSS Dashboard",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("Online Retail")

    health = get_warehouse_health_and_filters()

    # ------------------------------------------------------------------
    # SIDEBAR: GLOBAL FILTERS (MEMBER 3'S NATIVE DESIGN)
    # ------------------------------------------------------------------
    with st.sidebar:
        st.header("Filters")

        if not health["connected"]:
            st.error("Cannot connect to MySQL Data Warehouse.")
            st.code(health["error"])
            st.info("Please verify database credentials in .env and ensure retail_dw is initialized.")
            st.stop()

        if health["fact_sales_count"] == 0:
            st.warning("Data warehouse tables exist but fact_sales is empty.")
            st.info("Please run python src/etl/etl.py to load data first.")
            st.stop()

        min_date = health["min_date"]
        max_date = health["max_date"]

        date_range = st.date_input(
            "Date range",
            value=(min_date, max_date) if min_date and max_date else None,
            min_value=min_date,
            max_value=max_date,
        )

        country_options = ["All countries"] + health["countries"]
        country_selected = st.selectbox(
            "Country",
            options=country_options,
            index=0,
        )

        top_n = st.slider(
            "Top products",
            min_value=5,
            max_value=30,
            value=10,
        )

    # Parse date range safely
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range

    if start_date and end_date and start_date > end_date:
        st.error("Start date must not be later than end date.")
        st.stop()

    country_val = None if country_selected == "All countries" else country_selected

    params = {
        "start_date": start_date,
        "end_date": end_date,
        "country": country_val,
    }

    # Derive year range for RFM
    if start_date and end_date:
        years_tuple = tuple(range(start_date.year, end_date.year + 1))
    else:
        years_tuple = (2010, 2011)

    # ------------------------------------------------------------------
    # MAIN APPLICATION: 4 STRATEGIC TABS
    # ------------------------------------------------------------------
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Overview",
            "OLAP explorer",
            "Customer segmentation",
            "What-If simulation",
        ]
    )

    with tab1:
        render_overview_tab(params, top_n=top_n)

    with tab2:
        render_olap_tab(params)

    with tab3:
        render_segmentation_tab(years_tuple, country_val)

    with tab4:
        render_what_if_tab(years_tuple, country_val)


if __name__ == "__main__":
    main()
