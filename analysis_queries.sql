-- ============================================================================
-- Retail Orders — Analytical SQL (Microsoft SQL Server / T-SQL)
-- Runs against the retail.dbo.orders table produced by etl_pipeline.py
-- Techniques: CTEs, window functions, conditional aggregation, date parts
-- Author: Siddhant Singh
-- ============================================================================

USE retail;
GO


-- ----------------------------------------------------------------------------
-- 1. Top 10 highest revenue-generating products
-- ----------------------------------------------------------------------------
SELECT TOP 10
    product_id,
    ROUND(SUM(sale_price), 2) AS total_sales
FROM orders
GROUP BY product_id
ORDER BY total_sales DESC;
GO


-- ----------------------------------------------------------------------------
-- 2. Top 5 best-selling products in each region
--    ROW_NUMBER() restarts the ranking for every region.
-- ----------------------------------------------------------------------------
WITH region_sales AS (
    SELECT
        region,
        product_id,
        ROUND(SUM(sale_price), 2) AS total_sales
    FROM orders
    GROUP BY region, product_id
),
ranked AS (
    SELECT
        region,
        product_id,
        total_sales,
        ROW_NUMBER() OVER (PARTITION BY region ORDER BY total_sales DESC) AS rn
    FROM region_sales
)
SELECT region, product_id, total_sales, rn
FROM ranked
WHERE rn <= 5
ORDER BY region, rn;
GO


-- ----------------------------------------------------------------------------
-- 3. Month-over-month sales: 2022 vs 2023 (Jan 2022 vs Jan 2023, ...)
--    Conditional aggregation pivots the two years into side-by-side columns.
-- ----------------------------------------------------------------------------
WITH monthly AS (
    SELECT
        YEAR(order_date)  AS order_year,
        MONTH(order_date) AS order_month,
        SUM(sale_price)   AS sales
    FROM orders
    GROUP BY YEAR(order_date), MONTH(order_date)
)
SELECT
    order_month,
    ROUND(SUM(CASE WHEN order_year = 2022 THEN sales ELSE 0 END), 2) AS sales_2022,
    ROUND(SUM(CASE WHEN order_year = 2023 THEN sales ELSE 0 END), 2) AS sales_2023
FROM monthly
GROUP BY order_month
ORDER BY order_month;
GO


-- ----------------------------------------------------------------------------
-- 4. For each category, which month had the highest sales?
-- ----------------------------------------------------------------------------
WITH category_month AS (
    SELECT
        category,
        FORMAT(order_date, 'yyyy-MM') AS order_year_month,
        SUM(sale_price)               AS sales
    FROM orders
    GROUP BY category, FORMAT(order_date, 'yyyy-MM')
),
ranked AS (
    SELECT
        category,
        order_year_month,
        sales,
        ROW_NUMBER() OVER (PARTITION BY category ORDER BY sales DESC) AS rn
    FROM category_month
)
SELECT category, order_year_month, ROUND(sales, 2) AS sales
FROM ranked
WHERE rn = 1;
GO


-- ----------------------------------------------------------------------------
-- 5. Which sub-category grew the most (by sales) from 2022 to 2023?
-- ----------------------------------------------------------------------------
WITH yearly AS (
    SELECT
        sub_category,
        YEAR(order_date) AS order_year,
        SUM(sale_price)  AS sales
    FROM orders
    GROUP BY sub_category, YEAR(order_date)
),
pivoted AS (
    SELECT
        sub_category,
        SUM(CASE WHEN order_year = 2022 THEN sales ELSE 0 END) AS sales_2022,
        SUM(CASE WHEN order_year = 2023 THEN sales ELSE 0 END) AS sales_2023
    FROM yearly
    GROUP BY sub_category
)
SELECT
    sub_category,
    ROUND(sales_2022, 2)              AS sales_2022,
    ROUND(sales_2023, 2)              AS sales_2023,
    ROUND(sales_2023 - sales_2022, 2) AS sales_growth
FROM pivoted
ORDER BY sales_growth DESC;
GO


-- ============================================================================
-- Extra analysis (beyond the original scope)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 6. Profit margin by category and sub-category
-- ----------------------------------------------------------------------------
SELECT
    category,
    sub_category,
    ROUND(SUM(sale_price), 2)                     AS total_sales,
    ROUND(SUM(profit), 2)                         AS total_profit,
    ROUND(100.0 * SUM(profit) / SUM(sale_price), 2) AS profit_margin_pct
FROM orders
GROUP BY category, sub_category
ORDER BY profit_margin_pct DESC;
GO


-- ----------------------------------------------------------------------------
-- 7. Do bigger discounts actually hurt profit?
--    Average profit grouped by discount band.
-- ----------------------------------------------------------------------------
SELECT
    CASE
        WHEN discount_percent = 0             THEN '0%'
        WHEN discount_percent BETWEEN 1 AND 2 THEN '1-2%'
        WHEN discount_percent BETWEEN 3 AND 4 THEN '3-4%'
        ELSE '5%+'
    END                       AS discount_band,
    COUNT(*)                  AS order_lines,
    ROUND(AVG(profit), 2)     AS avg_profit,
    ROUND(SUM(profit), 2)     AS total_profit
FROM orders
GROUP BY
    CASE
        WHEN discount_percent = 0             THEN '0%'
        WHEN discount_percent BETWEEN 1 AND 2 THEN '1-2%'
        WHEN discount_percent BETWEEN 3 AND 4 THEN '3-4%'
        ELSE '5%+'
    END
ORDER BY discount_band;
GO


-- ----------------------------------------------------------------------------
-- 8. Top 10 states by total sales, with their profit
-- ----------------------------------------------------------------------------
SELECT TOP 10
    state,
    ROUND(SUM(sale_price), 2) AS total_sales,
    ROUND(SUM(profit), 2)     AS total_profit,
    COUNT(DISTINCT order_id)  AS orders
FROM orders
GROUP BY state
ORDER BY total_sales DESC;
GO


-- ----------------------------------------------------------------------------
-- 9. Sales & profit split by customer segment and ship mode
-- ----------------------------------------------------------------------------
SELECT
    segment,
    ship_mode,
    ROUND(SUM(sale_price), 2) AS total_sales,
    ROUND(SUM(profit), 2)     AS total_profit
FROM orders
GROUP BY segment, ship_mode
ORDER BY segment, total_sales DESC;
GO
