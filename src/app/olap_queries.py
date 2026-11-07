"""Reusable OLAP queries for the Online Retail star schema."""

from sqlalchemy import text

SALES_FILTER = """
    WHERE (:start_date IS NULL OR d.full_date >= :start_date)
      AND (:end_date IS NULL OR d.full_date <= :end_date)
      AND (:country IS NULL OR c.country = :country)
"""

KPI_QUERY = text("""
SELECT
    ROUND(SUM(f.total_amount), 2) AS revenue,
    SUM(f.quantity) AS items_sold,
    COUNT(DISTINCT f.invoice_no) AS orders,
    COUNT(DISTINCT f.customer_key) AS customers,
    ROUND(SUM(f.total_amount) / NULLIF(COUNT(DISTINCT f.invoice_no), 0), 2) AS avg_order_value
FROM fact_sales f
JOIN dim_customer c ON c.customer_key = f.customer_key
JOIN dim_date d ON d.date_key = f.date_key
""" + SALES_FILTER)

MONTHLY_REVENUE_QUERY = text("""
WITH monthly_cte AS (
    SELECT
        d.`year`,
        d.`month`,
        CONCAT(d.`year`, '-', LPAD(d.`month`, 2, '0')) AS `year_month`,
        ROUND(SUM(f.total_amount), 2) AS revenue,
        COUNT(DISTINCT f.invoice_no) AS orders
    FROM fact_sales f
    JOIN dim_customer c ON c.customer_key = f.customer_key
    JOIN dim_date d ON d.date_key = f.date_key
""" + SALES_FILTER + """
    GROUP BY d.`year`, d.`month`
)
SELECT
    `year`,
    `month`,
    `year_month`,
    revenue,
    orders,
    ROUND(
        (revenue - LAG(revenue, 1) OVER (ORDER BY `year`, `month`))
        / NULLIF(LAG(revenue, 1) OVER (ORDER BY `year`, `month`), 0) * 100,
        2
    ) AS mom_growth_pct,
    ROUND(SUM(revenue) OVER (PARTITION BY `year` ORDER BY `month`), 2) AS ytd_cumulative_revenue
FROM monthly_cte
ORDER BY `year`, `month`
""")

COUNTRY_REVENUE_QUERY = text("""
SELECT
    c.country,
    ROUND(SUM(f.total_amount), 2) AS revenue,
    COUNT(DISTINCT f.invoice_no) AS orders,
    COUNT(DISTINCT f.customer_key) AS customers,
    ROUND(SUM(f.total_amount) * 100.0 / NULLIF(SUM(SUM(f.total_amount)) OVER (), 0), 2) AS revenue_share_pct
FROM fact_sales f
JOIN dim_customer c ON c.customer_key = f.customer_key
JOIN dim_date d ON d.date_key = f.date_key
""" + SALES_FILTER + """
GROUP BY c.country
ORDER BY revenue DESC
""")

TOP_PRODUCTS_QUERY = text("""
SELECT
    p.stock_code,
    COALESCE(p.description, 'Unknown') AS product,
    agg.quantity_sold,
    agg.revenue
FROM (
    SELECT
        f.product_key,
        SUM(f.quantity) AS quantity_sold,
        ROUND(SUM(f.total_amount), 2) AS revenue
    FROM fact_sales f
    JOIN dim_customer c ON c.customer_key = f.customer_key
    JOIN dim_date d ON d.date_key = f.date_key
""" + SALES_FILTER + """
    GROUP BY f.product_key
    ORDER BY revenue DESC
    LIMIT :top_n
) agg
JOIN dim_product p ON p.product_key = agg.product_key
ORDER BY agg.revenue DESC
""")

WEEKDAY_QUERY = text("""
SELECT
    d.day_of_week,
    d.is_weekend,
    ROUND(SUM(f.total_amount), 2) AS revenue,
    COUNT(DISTINCT f.invoice_no) AS orders,
    SUM(f.quantity) AS units_sold
FROM fact_sales f
JOIN dim_customer c ON c.customer_key = f.customer_key
JOIN dim_date d ON d.date_key = f.date_key
""" + SALES_FILTER + """
GROUP BY d.day_of_week, d.is_weekend
ORDER BY FIELD(d.day_of_week, 'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')
""")

RANK_COUNTRIES_QUERY = text("""
SELECT
    country,
    revenue,
    orders,
    customers,
    DENSE_RANK() OVER (ORDER BY revenue DESC) AS revenue_rank
FROM (
    SELECT
        c.country,
        ROUND(SUM(f.total_amount), 2) AS revenue,
        COUNT(DISTINCT f.invoice_no) AS orders,
        COUNT(DISTINCT f.customer_key) AS customers
    FROM fact_sales f
    JOIN dim_customer c ON c.customer_key = f.customer_key
    JOIN dim_date d ON d.date_key = f.date_key
""" + SALES_FILTER + """
    GROUP BY c.country
) ranked
ORDER BY revenue_rank
""")
