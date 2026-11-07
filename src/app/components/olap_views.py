"""OLAP view components for the Online Retail analytical dashboard.
Implements Tab 1 (Overview) and Tab 2 (OLAP explorer) matching Member 3's design style.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from sqlalchemy import text

from src.app.components.db_connector import run_sql_query
from src.app.olap_queries import (
    KPI_QUERY,
    MONTHLY_REVENUE_QUERY,
    COUNTRY_REVENUE_QUERY,
    TOP_PRODUCTS_QUERY,
    WEEKDAY_QUERY,
    RANK_COUNTRIES_QUERY,
    SALES_FILTER,
)


def safe_float(value):
    """Safely convert database numeric return types to Python float."""
    if pd.isna(value):
        return 0.0
    return float(value)


def render_overview_tab(params: dict, top_n: int = 10):
    """Tab 1: Executive KPI overview, monthly trends, geo breakdown, top products and weekday performance."""
    kpi_df = run_sql_query(KPI_QUERY, params)

    if kpi_df.empty or safe_float(kpi_df.iloc[0]["orders"]) == 0:
        st.warning("No transaction data found for the selected filter range.")
        return

    kpi = kpi_df.iloc[0]
    revenue = safe_float(kpi["revenue"])
    items_sold = safe_float(kpi["items_sold"])
    orders = safe_float(kpi["orders"])
    customers = safe_float(kpi["customers"])
    avg_order_value = safe_float(kpi["avg_order_value"])

    # 1. Five executive KPI metrics matching Member 3's native layout
    cols = st.columns(5)
    cols[0].metric("Revenue", f"£{revenue:,.2f}")
    cols[1].metric("Items sold", f"{items_sold:,.0f}")
    cols[2].metric("Orders", f"{orders:,.0f}")
    cols[3].metric("Customers", f"{customers:,.0f}")
    cols[4].metric("Average order value", f"£{avg_order_value:,.2f}")

    st.divider()

    # 2. Monthly trend and Country distribution
    left, right = st.columns(2)

    with left:
        st.subheader("Revenue by month")
        monthly = run_sql_query(MONTHLY_REVENUE_QUERY, params)
        if not monthly.empty:
            fig_month = make_subplots(specs=[[{"secondary_y": True}]])
            fig_month.add_trace(
                go.Bar(
                    x=monthly["year_month"],
                    y=monthly["revenue"],
                    name="Revenue (£)",
                    marker_color="#3B82F6",
                ),
                secondary_y=False,
            )
            fig_month.add_trace(
                go.Scatter(
                    x=monthly["year_month"],
                    y=monthly["mom_growth_pct"],
                    name="MoM Growth (%)",
                    mode="lines+markers",
                    line=dict(color="#EF4444", width=2.2),
                ),
                secondary_y=True,
            )
            fig_month.update_layout(
                height=380,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=10, r=10, t=25, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            fig_month.update_xaxes(showgrid=False)
            fig_month.update_yaxes(title_text="Revenue (£)", secondary_y=False, showgrid=True, gridcolor="rgba(128,128,128,0.15)")
            fig_month.update_yaxes(title_text="MoM (%)", secondary_y=True, showgrid=False)
            st.plotly_chart(fig_month, use_container_width=True)
        else:
            st.info("No records for the selected filters.")

    with right:
        st.subheader("Revenue by country")
        countries = run_sql_query(COUNTRY_REVENUE_QUERY, params)
        if not countries.empty:
            top_countries = countries.head(15)
            fig_country = px.bar(
                top_countries,
                x="country",
                y="revenue",
                text_auto=".2s",
                labels={"country": "Country", "revenue": "Revenue (£)"},
                color_discrete_sequence=["#60A5FA"],
            )
            fig_country.update_layout(
                height=380,
                margin=dict(l=10, r=10, t=25, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            fig_country.update_xaxes(showgrid=False)
            fig_country.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.15)")
            st.plotly_chart(fig_country, use_container_width=True)
        else:
            st.info("No records for the selected filters.")

    # 3. Top products and Weekday distribution
    left, right = st.columns(2)

    with left:
        st.subheader(f"Top {top_n} products by revenue")
        products = run_sql_query(
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
        weekdays = run_sql_query(WEEKDAY_QUERY, params)
        if not weekdays.empty:
            st.bar_chart(weekdays.set_index("day_of_week")["revenue"])
        else:
            st.info("No records for the selected filters.")

    # 4. Country revenue ranking (DENSE_RANK)
    st.subheader("Country revenue ranking (DENSE_RANK)")
    ranking = run_sql_query(RANK_COUNTRIES_QUERY, params)
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


def render_olap_tab(params: dict):
    """Tab 2: Advanced OLAP explorations (WITH ROLLUP, Slice & Dice Crosstab, and Pareto 80/20)."""
    subtab1, subtab2, subtab3 = st.tabs(
        [
            "Roll-up & Drill-down",
            "Slice & Dice / Pivot matrix",
            "Pareto 80/20 analysis",
        ]
    )

    # ------------------------------------------------------------------
    # SUBTAB 1: HIERARCHICAL ROLL-UP (WITH ROLLUP)
    # ------------------------------------------------------------------
    with subtab1:
        st.caption("Time hierarchy aggregation: Year -> Quarter -> Month using MySQL GROUP BY WITH ROLLUP")
        drill_level = st.radio(
            "Aggregation level:",
            options=["By year", "By quarter", "By month"],
            index=1,
            horizontal=True,
        )

        rollup_sql = text("""
        SELECT
            IF(GROUPING(d.`year`), 'ALL YEARS (Grand Total)', CAST(d.`year` AS CHAR)) AS sales_year,
            IF(GROUPING(d.quarter),
               IF(GROUPING(d.`year`), '---', 'Year Subtotal'),
               CONCAT('Q', d.quarter)) AS sales_quarter,
            IF(GROUPING(d.`month`),
               IF(GROUPING(d.quarter), '---', 'Quarter Subtotal'),
               LPAD(d.`month`, 2, '0')) AS sales_month,
            COUNT(DISTINCT f.invoice_no) AS total_orders,
            SUM(f.quantity) AS total_units_sold,
            ROUND(SUM(f.total_amount), 2) AS total_revenue,
            ROUND(SUM(f.total_amount) / NULLIF(COUNT(DISTINCT f.invoice_no), 0), 2) AS avg_order_value
        FROM fact_sales f
        JOIN dim_date d ON f.date_key = d.date_key
        JOIN dim_customer c ON f.customer_key = c.customer_key
        """ + SALES_FILTER + """
        GROUP BY d.`year`, d.quarter, d.`month` WITH ROLLUP;
        """)

        rollup_df = run_sql_query(rollup_sql, params)

        if not rollup_df.empty:
            if drill_level == "By year":
                chart_df = rollup_df[
                    (rollup_df["sales_quarter"] == "Year Subtotal")
                    & (rollup_df["sales_year"] != "ALL YEARS (Grand Total)")
                ].copy()
                x_col = "sales_year"
            elif drill_level == "By quarter":
                chart_df = rollup_df[
                    (rollup_df["sales_month"] == "Quarter Subtotal")
                    & (~rollup_df["sales_quarter"].isin(["---", "Year Subtotal"]))
                ].copy()
                chart_df["period"] = chart_df["sales_year"] + " - " + chart_df["sales_quarter"]
                x_col = "period"
            else:
                chart_df = rollup_df[
                    ~rollup_df["sales_month"].isin(["---", "Quarter Subtotal"])
                ].copy()
                chart_df["period"] = chart_df["sales_year"] + "-" + chart_df["sales_month"]
                x_col = "period"

            fig_rollup = px.bar(
                chart_df,
                x=x_col,
                y="total_revenue",
                color="total_orders",
                text_auto=".3s",
                labels={
                    x_col: "Time period",
                    "total_revenue": "Total revenue (£)",
                    "total_orders": "Orders",
                },
                color_continuous_scale="Blues",
            )
            fig_rollup.update_layout(
                height=380,
                margin=dict(l=10, r=10, t=25, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_rollup, use_container_width=True)

            st.dataframe(rollup_df, use_container_width=True, hide_index=True)

        with st.expander("View SQL query (WITH ROLLUP)"):
            st.code(str(rollup_sql), language="sql")

    # ------------------------------------------------------------------
    # SUBTAB 2: SLICE & DICE / PIVOT MATRIX
    # ------------------------------------------------------------------
    with subtab2:
        c1, c2, c3 = st.columns(3)
        with c1:
            row_choice = st.selectbox(
                "Row dimension:",
                options=["Country (Top 12)", "Day of week", "Quarter"],
                index=0,
            )
        with c2:
            col_choice = st.selectbox(
                "Column dimension:",
                options=["Year - Quarter", "Month", "Weekend vs Weekday"],
                index=0,
            )
        with c3:
            meas_choice = st.selectbox(
                "Measure:",
                options=["Total revenue (£)", "Total units sold", "Total orders"],
                index=0,
            )

        row_map = {
            "Country (Top 12)": "c.country",
            "Day of week": "d.day_of_week",
            "Quarter": "CONCAT('Q', d.quarter)",
        }
        col_map = {
            "Year - Quarter": "CONCAT(d.`year`, '-Q', d.quarter)",
            "Month": "LPAD(d.`month`, 2, '0')",
            "Weekend vs Weekday": "IF(d.is_weekend, 'Weekend', 'Weekday')",
        }
        meas_map = {
            "Total revenue (£)": "ROUND(SUM(f.total_amount), 2)",
            "Total units sold": "SUM(f.quantity)",
            "Total orders": "COUNT(DISTINCT f.invoice_no)",
        }

        r_expr = row_map[row_choice]
        c_expr = col_map[col_choice]
        m_expr = meas_map[meas_choice]

        pivot_sql = text(f"""
        SELECT
            {r_expr} AS row_dim,
            {c_expr} AS col_dim,
            {m_expr} AS metric_val
        FROM fact_sales f
        JOIN dim_date d ON f.date_key = d.date_key
        JOIN dim_customer c ON f.customer_key = c.customer_key
        {SALES_FILTER}
        GROUP BY row_dim, col_dim;
        """)

        pivot_raw = run_sql_query(pivot_sql, params)

        if not pivot_raw.empty:
            if row_choice == "Country (Top 12)":
                top_12_rows = (
                    pivot_raw.groupby("row_dim")["metric_val"]
                    .sum()
                    .nlargest(12)
                    .index.tolist()
                )
                pivot_raw = pivot_raw[pivot_raw["row_dim"].isin(top_12_rows)]

            table_matrix = pivot_raw.pivot_table(
                index="row_dim",
                columns="col_dim",
                values="metric_val",
                aggfunc="sum",
                fill_value=0,
            )

            fig_pivot = px.imshow(
                table_matrix,
                text_auto=".2s",
                aspect="auto",
                color_continuous_scale="Blues",
            )
            fig_pivot.update_layout(
                height=420,
                margin=dict(l=10, r=10, t=20, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_pivot, use_container_width=True)
            st.dataframe(table_matrix, use_container_width=True)

        with st.expander("View SQL query (Slice & Dice)"):
            st.code(str(pivot_sql), language="sql")

    # ------------------------------------------------------------------
    # SUBTAB 3: PARETO 80/20 ANALYSIS
    # ------------------------------------------------------------------
    with subtab3:
        st.subheader("Pareto 80/20 customer revenue distribution")

        pareto_sql = text("""
        WITH cust_rev AS (
            SELECT
                c.customer_id,
                c.country,
                COUNT(DISTINCT f.invoice_no) AS total_orders,
                ROUND(SUM(f.total_amount), 2) AS customer_revenue
            FROM fact_sales f
            JOIN dim_customer c ON f.customer_key = c.customer_key
            JOIN dim_date d ON f.date_key = d.date_key
        """ + SALES_FILTER + """
            GROUP BY c.customer_id, c.country
        ),
        ordered_cust AS (
            SELECT
                customer_id,
                country,
                total_orders,
                customer_revenue,
                ROW_NUMBER() OVER (ORDER BY customer_revenue DESC) AS cust_rank,
                COUNT(*) OVER () AS total_cust,
                SUM(customer_revenue) OVER (ORDER BY customer_revenue DESC) AS cum_revenue,
                SUM(customer_revenue) OVER () AS grand_revenue
            FROM cust_rev
        )
        SELECT
            cust_rank,
            customer_id,
            country,
            total_orders,
            customer_revenue,
            ROUND(cust_rank * 100.0 / total_cust, 2) AS cum_customer_pct,
            ROUND(cum_revenue * 100.0 / grand_revenue, 2) AS cum_revenue_pct
        FROM ordered_cust
        ORDER BY cust_rank;
        """)

        pareto_df = run_sql_query(pareto_sql, params)

        if not pareto_df.empty:
            top_80 = pareto_df[pareto_df["cum_revenue_pct"] <= 80.0]
            pct_for_80 = float(top_80["cum_customer_pct"].max()) if not top_80.empty else 0.0
            cnt_for_80 = len(top_80)

            st.info(
                f"Pareto insight (Intelligence phase): Exactly {pct_for_80:.1f}% of top customers "
                f"({cnt_for_80:,} of {len(pareto_df):,} customers) generate 80% of total revenue. "
                f"This empirical skewness confirms the necessity of targeted RFM customer segmentation in Tab 3."
            )

            step = max(1, len(pareto_df) // 200)
            sampled = pareto_df.iloc[::step].copy()

            fig_pareto = make_subplots(specs=[[{"secondary_y": True}]])
            fig_pareto.add_trace(
                go.Bar(
                    x=sampled["cum_customer_pct"],
                    y=sampled["customer_revenue"],
                    name="Customer Revenue (£)",
                    marker_color="#60A5FA",
                ),
                secondary_y=False,
            )
            fig_pareto.add_trace(
                go.Scatter(
                    x=sampled["cum_customer_pct"],
                    y=sampled["cum_revenue_pct"],
                    name="Cumulative Revenue (%)",
                    mode="lines",
                    line=dict(color="#EF4444", width=2.8),
                ),
                secondary_y=True,
            )
            fig_pareto.add_hline(
                y=80.0,
                line_dash="dash",
                line_color="#10B981",
                annotation_text="80% Revenue Cutoff",
                secondary_y=True,
            )
            fig_pareto.update_layout(
                height=400,
                margin=dict(l=10, r=10, t=20, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            fig_pareto.update_xaxes(title_text="% Cumulative Customers (Ranked VIP -> Retail)")
            fig_pareto.update_yaxes(title_text="Customer Revenue (£)", secondary_y=False, showgrid=True, gridcolor="rgba(128,128,128,0.15)")
            fig_pareto.update_yaxes(title_text="Cumulative Revenue (%)", range=[0, 105], secondary_y=True, showgrid=False)
            st.plotly_chart(fig_pareto, use_container_width=True)

            st.dataframe(pareto_df.head(20), use_container_width=True, hide_index=True)

        with st.expander("View SQL query (Window Functions)"):
            st.code(str(pareto_sql), language="sql")
