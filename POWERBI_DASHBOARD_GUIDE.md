# Power BI Dashboard — Build Guide

Connect Power BI to the `retail.dbo.orders` table produced by `etl_pipeline.py` and
build a 3-page dashboard. Includes connection steps, DAX measures, and a
page-by-page layout.

---

## 1. Connect Power BI to SQL Server (live data)

Your ETL already loaded a clean `retail.dbo.orders` table, so Power BI reads it directly — no in-Power-BI cleaning needed. Power BI's SQL Server connector is built in (no extra driver install).

1. In Power BI Desktop: **Home → Get Data → SQL Server database**.
2. Server: `localhost` · Database: `retail`.
3. Choose **Import** (recommended for a portfolio dashboard).
4. Data Connectivity → leave default; expand and select the `dbo.orders` table.
5. When prompted for credentials, pick **Windows** (uses your logged-in account — the same Windows Authentication the ETL uses). No password to enter.

> **CSV alternative:** if you'd rather not depend on SQL Server, use **Get Data → Text/CSV**
> on the raw `orders.csv` and reproduce the cleaning in Power Query. See the appendix.

### Model housekeeping
- Confirm `order_date` is typed as **Date**.
- Add a **month name** column for a clean trend axis: *Modeling → New Column*
  ```dax
  Month = FORMAT(orders[order_date], "MMM")
  Month Number = MONTH(orders[order_date])
  Order Year = YEAR(orders[order_date])
  ```
  Then select the `Month` column → *Sort by Column* → `Month Number` (so months show Jan→Dec).

---

## 2. DAX Measures

Create these (Modeling → New Measure). Group them under a `_Measures` table if you like.

### KPIs
```dax
Total Sales     = SUM(orders[sale_price])
Total Profit    = SUM(orders[profit])
Total Orders    = DISTINCTCOUNT(orders[order_id])
Total Quantity  = SUM(orders[quantity])
Profit Margin % = DIVIDE([Total Profit], [Total Sales])
Avg Order Value = DIVIDE([Total Sales], [Total Orders])
```

### Year-over-year
```dax
Sales 2022  = CALCULATE([Total Sales], orders[Order Year] = 2022)
Sales 2023  = CALCULATE([Total Sales], orders[Order Year] = 2023)
YoY Growth % = DIVIDE([Sales 2023] - [Sales 2022], [Sales 2022])
```

### Top 5 products per region (needs a calculated table)
Visual-level Top N can't rank *within* each region, so replicate
`ROW_NUMBER() OVER (PARTITION BY region ...)`:
```dax
Top5ProductsPerRegion =
VAR Summary =
    ADDCOLUMNS(
        SUMMARIZE(orders, orders[region], orders[product_id]),
        "Sales", CALCULATE([Total Sales])
    )
RETURN
    FILTER(
        ADDCOLUMNS(
            Summary,
            "rn",
            VAR r = [region] VAR s = [Sales]
            RETURN COUNTROWS(FILTER(Summary, [region] = r && [Sales] > s)) + 1
        ),
        [rn] <= 5
    )
```

### Best month per category (calculated table)
```dax
BestMonthPerCategory =
VAR Summary =
    ADDCOLUMNS(
        SUMMARIZE(orders, orders[category], orders[Order Year], orders[Month]),
        "MonthSales", CALCULATE([Total Sales])
    )
RETURN
    FILTER(
        ADDCOLUMNS(
            Summary,
            "rn",
            VAR c = [category] VAR s = [MonthSales]
            RETURN COUNTROWS(FILTER(Summary, [category] = c && [MonthSales] > s)) + 1
        ),
        [rn] = 1
    )
```

### Sub-category growth 2022 → 2023 (calculated table)
```dax
SubCategoryGrowth =
VAR Base =
    ADDCOLUMNS(
        SUMMARIZE(orders, orders[sub_category]),
        "Sales2022", CALCULATE([Total Sales], orders[Order Year] = 2022),
        "Sales2023", CALCULATE([Total Sales], orders[Order Year] = 2023)
    )
RETURN
    ADDCOLUMNS(Base, "Growth", [Sales2023] - [Sales2022])
```

> **Top 10 products** and the **2022-vs-2023 month matrix** need no DAX:
> - Top 10: a bar chart of `product_id` by `[Total Sales]` with a **Top N = 10** visual filter.
> - Month matrix: a **Matrix** with Rows = `Month`, Columns = `Order Year`, Values = `[Total Sales]`.

---

## 3. Page-by-Page Layout

### Page 1 — Executive Overview
- **Slicers (top):** `Order Year`, `region`, `category`
- **KPI cards:** Total Sales · Total Profit · Profit Margin % · Total Orders · YoY Growth %
- **Line chart:** `Month` (axis) × `[Total Sales]`, legend = `Order Year` → the 2022-vs-2023 trend
- **Bar:** `[Total Sales]` by `category`
- **Map / bar:** `[Total Sales]` by `state`
- **Donut:** `[Total Sales]` by `segment`

### Page 2 — Product & Category Deep Dive
- **Bar (Top N = 10):** top products by `[Total Sales]`
- **Table:** `Top5ProductsPerRegion` (region, product_id, Sales, rn)
- **Table:** `BestMonthPerCategory` (category, Month, MonthSales)
- **Table:** `SubCategoryGrowth` sorted by `Growth` desc, data-bar conditional formatting
- **Bar:** `[Total Profit]` by `sub_category`

### Page 3 — Operations & Margins
- **Bar/table:** `[Total Sales]` & `[Total Profit]` by `ship_mode`
- **Scatter:** X = `discount`, Y = `profit`, legend = `category` (spot discounts that erode profit)
- **Matrix:** rows = `segment`, columns = `ship_mode`, values = `[Total Sales]`

---

## Appendix — CSV cleaning in Power Query (only if not using SQL Server)

Get Data → Blank Query → Advanced Editor, then point at your `orders.csv`:

```m
let
    Source = Csv.Document(File.Contents("C:\Users\singh\Desktop\orders.csv"),
        [Delimiter=",", Columns=16, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    NA1 = Table.ReplaceValue(Promoted, "Not Available", null, Replacer.ReplaceValue, {"Ship Mode"}),
    NA2 = Table.ReplaceValue(NA1, "unknown", null, Replacer.ReplaceValue, {"Ship Mode"}),
    Renamed = Table.RenameColumns(NA2, {
        {"Order Id","order_id"},{"Order Date","order_date"},{"Ship Mode","ship_mode"},
        {"Segment","segment"},{"Country","country"},{"City","city"},{"State","state"},
        {"Postal Code","postal_code"},{"Region","region"},{"Category","category"},
        {"Sub Category","sub_category"},{"Product Id","product_id"},{"cost price","cost_price"},
        {"List Price","list_price"},{"Quantity","quantity"},{"Discount Percent","discount_percent"}}),
    Typed = Table.TransformColumnTypes(Renamed, {
        {"order_id",Int64.Type},{"order_date",type date},{"postal_code",Int64.Type},
        {"cost_price",Int64.Type},{"list_price",Int64.Type},{"quantity",Int64.Type},
        {"discount_percent",Int64.Type}}),
    Discount   = Table.AddColumn(Typed, "discount", each [list_price]*[discount_percent]*0.01, type number),
    SalePrice  = Table.AddColumn(Discount, "sale_price", each [list_price]-[discount], type number),
    Profit     = Table.AddColumn(SalePrice, "profit", each [sale_price]-[cost_price], type number)
in
    Profit
```
