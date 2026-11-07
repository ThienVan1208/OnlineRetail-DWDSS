

USE retail_dw;

SELECT 
    IF(GROUPING(d.year), 'ALL YEARS (Grand Total)', CAST(d.year AS CHAR)) AS sales_year,
    IF(GROUPING(d.quarter), 
       IF(GROUPING(d.year), '---', 'All Quarters (Year Total)'), 
       CONCAT('Q', d.quarter)) AS sales_quarter,
    IF(GROUPING(d.month), 
       IF(GROUPING(d.quarter), '---', 'All Months (Quarter Total)'), 
       LPAD(d.month, 2, '0')) AS sales_month,
    COUNT(DISTINCT f.invoice_no) AS total_orders,
    COUNT(DISTINCT f.customer_key) AS unique_customers,
    SUM(f.quantity) AS total_units_sold,
    ROUND(SUM(f.total_amount), 2) AS total_revenue,
    ROUND(SUM(f.total_amount) / COUNT(DISTINCT f.invoice_no), 2) AS avg_order_value
FROM fact_sales f
INNER JOIN dim_date d ON f.date_key = d.date_key
GROUP BY d.year, d.quarter, d.month WITH ROLLUP;


WITH monthly_sales AS (
    SELECT 
        d.year,
        d.month,
        CONCAT(d.year, '-', LPAD(d.month, 2, '0')) AS year_month_label,
        COUNT(DISTINCT f.invoice_no) AS total_orders,
        SUM(f.quantity) AS total_units,
        ROUND(SUM(f.total_amount), 2) AS monthly_revenue
    FROM fact_sales f
    INNER JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY d.year, d.month
)
SELECT 
    year_month_label,
    total_orders,
    total_units,
    monthly_revenue,
    LAG(monthly_revenue, 1) OVER (ORDER BY year, month) AS prev_month_revenue,
    ROUND(
        (monthly_revenue - LAG(monthly_revenue, 1) OVER (ORDER BY year, month))
        / NULLIF(LAG(monthly_revenue, 1) OVER (ORDER BY year, month), 0) * 100,
        2
    ) AS mom_growth_pct,
    ROUND(
        SUM(monthly_revenue) OVER (PARTITION BY year ORDER BY month),
        2
    ) AS ytd_cumulative_revenue
FROM monthly_sales
ORDER BY year, month;


WITH quarterly_product_sales AS (
    SELECT 
        d.year,
        d.quarter,
        p.stock_code,
        p.description,
        SUM(f.quantity) AS units_sold,
        ROUND(SUM(f.total_amount), 2) AS product_revenue,
        DENSE_RANK() OVER (
            PARTITION BY d.year, d.quarter 
            ORDER BY SUM(f.total_amount) DESC
        ) AS revenue_rank_in_quarter
    FROM fact_sales f
    INNER JOIN dim_date d ON f.date_key = d.date_key
    INNER JOIN dim_product p ON f.product_key = p.product_key
    WHERE d.year = 2011
    GROUP BY d.year, d.quarter, p.stock_code, p.description
)
SELECT 
    year,
    CONCAT('Q', quarter) AS quarter_label,
    revenue_rank_in_quarter,
    stock_code,
    description,
    units_sold,
    product_revenue
FROM quarterly_product_sales
WHERE revenue_rank_in_quarter <= 5
ORDER BY year, quarter, revenue_rank_in_quarter;


SELECT 
    c.country,
    COUNT(DISTINCT c.customer_key) AS total_customers,
    COUNT(DISTINCT f.invoice_no) AS total_orders,
    SUM(f.quantity) AS total_units_sold,
    ROUND(SUM(f.total_amount), 2) AS total_revenue,
    ROUND(SUM(f.total_amount) / COUNT(DISTINCT f.invoice_no), 2) AS avg_order_value,
    ROUND(
        SUM(f.total_amount) * 100.0 / SUM(SUM(f.total_amount)) OVER (),
        2
    ) AS revenue_share_pct
FROM fact_sales f
INNER JOIN dim_customer c ON f.customer_key = c.customer_key
GROUP BY c.country
ORDER BY total_revenue DESC;


SELECT 
    d.day_of_week,
    d.is_weekend,
    COUNT(DISTINCT d.full_date) AS active_days_count,
    COUNT(DISTINCT f.invoice_no) AS total_orders,
    SUM(f.quantity) AS total_units_sold,
    ROUND(SUM(f.total_amount), 2) AS total_revenue,
    ROUND(SUM(f.total_amount) / COUNT(DISTINCT d.full_date), 2) AS avg_daily_revenue
FROM fact_sales f
INNER JOIN dim_date d ON f.date_key = d.date_key
GROUP BY d.day_of_week, d.is_weekend
ORDER BY FIELD(
    d.day_of_week,
    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'
);


WITH customer_revenue_cte AS (
    SELECT 
        c.customer_id,
        c.country,
        COUNT(DISTINCT f.invoice_no) AS total_orders,
        ROUND(SUM(f.total_amount), 2) AS customer_revenue
    FROM fact_sales f
    INNER JOIN dim_customer c ON f.customer_key = c.customer_key
    GROUP BY c.customer_id, c.country
),
pareto_calc AS (
    SELECT 
        customer_id,
        country,
        total_orders,
        customer_revenue,
        ROW_NUMBER() OVER (ORDER BY customer_revenue DESC) AS customer_rank,
        COUNT(*) OVER () AS total_customers_count,
        SUM(customer_revenue) OVER (ORDER BY customer_revenue DESC) AS cumulative_revenue,
        SUM(customer_revenue) OVER () AS grand_total_revenue
    FROM customer_revenue_cte
)
SELECT 
    customer_rank,
    customer_id,
    country,
    total_orders,
    customer_revenue,
    ROUND(customer_rank * 100.0 / total_customers_count, 2) AS cumulative_customer_pct,
    ROUND(cumulative_revenue * 100.0 / grand_total_revenue, 2) AS cumulative_revenue_pct,
    CASE 
        WHEN (cumulative_revenue * 100.0 / grand_total_revenue) <= 80.0 THEN 'Top 80% Revenue Contributors (VIP Core)'
        ELSE 'Remaining 20% Revenue Tail'
    END AS pareto_class
FROM pareto_calc
ORDER BY customer_rank
LIMIT 100;
