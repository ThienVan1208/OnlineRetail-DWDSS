"""Database connection and query caching utilities for the Online Retail dashboard."""

import os
from urllib.parse import quote_plus
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


@st.cache_resource(show_spinner=False)
def get_db_engine():
    """Create and cache the SQLAlchemy Engine pool across Streamlit sessions."""
    user = os.getenv("DB_USER", "root")
    password = quote_plus(os.getenv("DB_PASS", "") or "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    db_name = os.getenv("DB_NAME", "retail_dw")

    connection_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"
    return create_engine(
        connection_url,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args={"connect_timeout": 5},
    )


@st.cache_data(ttl=600, show_spinner=False)
def _execute_cached_sql(query_sql: str, params: dict | None = None) -> pd.DataFrame:
    """Internal cached executor using hashable SQL string."""
    engine = get_db_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(query_sql), conn, params=params or {})


def run_sql_query(query, params: dict | None = None) -> pd.DataFrame:
    """Execute a SQL SELECT query with parameter binding and cache results for 10 minutes.
    Accepts either string queries or SQLAlchemy TextClause instances safely.
    """
    query_str = str(query.text) if hasattr(query, "text") else str(query)
    return _execute_cached_sql(query_str, params)


@st.cache_data(ttl=600, show_spinner=False)
def get_warehouse_health_and_filters() -> dict:
    """Check connectivity to data warehouse tables and retrieve filter boundaries."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            fact_cnt = conn.execute(text("SELECT COUNT(*) FROM fact_sales")).scalar()
            cust_cnt = conn.execute(text("SELECT COUNT(*) FROM dim_customer")).scalar()
            prod_cnt = conn.execute(text("SELECT COUNT(*) FROM dim_product")).scalar()
            date_cnt = conn.execute(text("SELECT COUNT(*) FROM dim_date")).scalar()

            date_range = conn.execute(
                text("SELECT MIN(full_date), MAX(full_date) FROM dim_date")
            ).fetchone()

            countries_df = pd.read_sql(
                text("SELECT DISTINCT country FROM dim_customer ORDER BY country"),
                conn,
            )

        min_d = pd.to_datetime(date_range[0]).date() if date_range and date_range[0] else None
        max_d = pd.to_datetime(date_range[1]).date() if date_range and date_range[1] else None

        return {
            "connected": True,
            "error": None,
            "fact_sales_count": int(fact_cnt or 0),
            "dim_customer_count": int(cust_cnt or 0),
            "dim_product_count": int(prod_cnt or 0),
            "dim_date_count": int(date_cnt or 0),
            "min_date": min_d,
            "max_date": max_d,
            "countries": countries_df["country"].dropna().tolist() if not countries_df.empty else [],
        }
    except Exception as exc:
        return {
            "connected": False,
            "error": str(exc),
            "fact_sales_count": 0,
            "dim_customer_count": 0,
            "dim_product_count": 0,
            "dim_date_count": 0,
            "min_date": None,
            "max_date": None,
            "countries": [],
        }


def build_filter_clauses(
    start_date=None,
    end_date=None,
    country: str | None = None,
    date_alias: str = "d",
    cust_alias: str = "c",
) -> tuple[str, dict]:
    """Generate parameterized SQL WHERE clause and bindings from global filters."""
    clauses = ["1=1"]
    params = {}

    if start_date:
        clauses.append(f"{date_alias}.full_date >= :start_date")
        params["start_date"] = start_date

    if end_date:
        clauses.append(f"{date_alias}.full_date <= :end_date")
        params["end_date"] = end_date

    if country and country != "All countries":
        clauses.append(f"{cust_alias}.country = :country")
        params["country"] = country

    return " AND ".join(clauses), params
