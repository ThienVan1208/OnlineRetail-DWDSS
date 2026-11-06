"""Streamlit OLAP dashboard for the Online Retail data warehouse."""

import os
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from olap_queries import (
    KPI_QUERY,
    MONTHLY_REVENUE_QUERY,
    COUNTRY_REVENUE_QUERY,
    TOP_PRODUCTS_QUERY,
    WEEKDAY_QUERY,
    RANK_COUNTRIES_QUERY,
)

load_dotenv()

st.set_page_config(
    page_title="Online Retail | OLAP Dashboard",
    page_icon="🛍️",
    layout="wide",
)

st.title("🛍️ Online Retail — OLAP Dashboard")
st.caption("Interactive analytical dashboard on the retail_dw star schema.")


@st.cache_resource
def get_engine():
    user = os.getenv("DB_USER", "root")
    password = quote_plus(os.getenv("DB_PASS", ""))
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    db = os.getenv("DB_NAME", "retail_dw")

    return create_engine(
        f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}",
        pool_pre_ping=True,
    )


engine = get_engine()


def read_df(query, params=None):
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params=params or {})


def safe_float(value):
    """Convert database numeric values safely to float."""
    if pd.isna(value):
        return 0.0
    return float(value)


try:
    # Get date range from warehouse
    filter_df = read_df(text("""
            SELECT MIN(full_date) AS min_date,
                   MAX(full_date) AS max_date
            FROM dim_date
        """))

    if filter_df.empty or pd.isna(filter_df.loc[0, "min_date"]):
        st.warning(
            "The data warehouse tables exist, but no date data has been loaded yet. "
            "Please run the ETL pipeline first."
        )
        st.stop()

    min_date = pd.to_datetime(filter_df.loc[0, "min_date"]).date()
    max_date = pd.to_datetime(filter_df.loc[0, "max_date"]).date()

    countries_df = read_df(text("""
            SELECT DISTINCT country
            FROM dim_customer
            ORDER BY country
        """))

    country_options = ["All countries"] + (
        countries_df["country"].dropna().tolist() if not countries_df.empty else []
    )

    # Sidebar filters
    with st.sidebar:
        st.header("Filters")

        date_range = st.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

        country_selected = st.selectbox(
            "Country",
            country_options,
        )

        top_n = st.slider(
            "Top products",
            min_value=5,
            max_value=30,
            value=10,
        )

    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range

    if start_date > end_date:
        st.error("Start date must not be later than end date.")
        st.stop()

    params = {
        "start_date": start_date,
        "end_date": end_date,
        "country": (None if country_selected == "All countries" else country_selected),
    }

    # KPI metrics
    kpi_df = read_df(KPI_QUERY, params)

    if kpi_df.empty:
        st.warning("No KPI data found for the selected filters.")
        st.stop()

    kpi = kpi_df.iloc[0]

    revenue = safe_float(kpi["revenue"])
    items_sold = safe_float(kpi["items_sold"])
    orders = safe_float(kpi["orders"])
    customers = safe_float(kpi["customers"])
    avg_order_value = safe_float(kpi["avg_order_value"])

    cols = st.columns(5)

    labels = [
        ("Revenue", f"£{revenue:,.2f}"),
        ("Items sold", f"{items_sold:,.0f}"),
        ("Orders", f"{orders:,.0f}"),
        ("Customers", f"{customers:,.0f}"),
        ("Average order value", f"£{avg_order_value:,.2f}"),
    ]

    for col, (label, value) in zip(cols, labels):
        col.metric(label, value)

    st.divider()

    # Revenue by month and country
    left, right = st.columns(2)

    with left:
        st.subheader("Revenue by month")

        monthly = read_df(MONTHLY_REVENUE_QUERY, params)

        if not monthly.empty:
            st.line_chart(monthly.set_index("year_month")["revenue"])
        else:
            st.info("No records for the selected filters.")

    with right:
        st.subheader("Revenue by country")

        countries = read_df(
            COUNTRY_REVENUE_QUERY,
            params,
        ).head(15)

        if not countries.empty:
            st.bar_chart(countries.set_index("country")["revenue"])
        else:
            st.info("No records for the selected filters.")

    # Top products and weekday analysis
    left, right = st.columns(2)

    with left:
        st.subheader(f"Top {top_n} products by revenue")

        products = read_df(
            TOP_PRODUCTS_QUERY,
            {**params, "top_n": top_n},
        )

        if not products.empty:
            st.dataframe(
                products,
                use_container_width=True,
                hide_index=True,
            )

            st.bar_chart(products.set_index("product")["revenue"])
        else:
            st.info("No product records for the selected filters.")

    with right:
        st.subheader("Revenue by weekday")

        weekdays = read_df(
            WEEKDAY_QUERY,
            params,
        )

        if not weekdays.empty:
            st.bar_chart(weekdays.set_index("day_of_week")["revenue"])
        else:
            st.info("No records for the selected filters.")

    # Country revenue ranking
    st.subheader("Country revenue ranking (DENSE_RANK)")

    ranking = read_df(
        RANK_COUNTRIES_QUERY,
        params,
    )

    if not ranking.empty:
        st.dataframe(
            ranking,
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Download country ranking CSV",
            ranking.to_csv(index=False).encode("utf-8-sig"),
            file_name="country_revenue_ranking.csv",
            mime="text/csv",
        )
    else:
        st.info("No country ranking data available.")

except SQLAlchemyError as exc:
    st.error("Cannot load dashboard data from MySQL.")

    st.warning(
        "Check that MySQL is running, DB credentials in .env are correct, "
        "the retail_dw schema has been created, and ETL has loaded the tables."
    )

    st.code(str(exc))

except (KeyError, TypeError, ValueError) as exc:
    st.error("An error occurred while processing dashboard data.")
    st.code(str(exc))
