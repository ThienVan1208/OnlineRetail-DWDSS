import os
import sys
import time
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.db_config import create_mysql_engine

start_time = time.time()

# ---------------------------------------------------------
# DATABASE CONFIGURATION
# ---------------------------------------------------------
engine = create_mysql_engine(connect_timeout=30, pool_pre_ping=True)

# Test database connection
try:
    with engine.connect() as conn:
        print("[SUCCESS] Connected to MySQL database.")
except Exception as e:
    print("[ERROR] Cannot connect to MySQL database.")
    print(e)
    raise

# ---------------------------------------------------------
# EXTRACT
# ---------------------------------------------------------
print("==================================================")
print("[1/5] EXTRACT: Reading raw CSV dataset...")

csv_path = (
    os.path.join("data", "data.csv")
    if os.path.exists(os.path.join("data", "data.csv"))
    else "data.csv"
)

df = pd.read_csv(csv_path, encoding="ISO-8859-1")

total_raw_rows = len(df)

print(f"  -> Successfully loaded {total_raw_rows:,} " f"raw records from '{csv_path}'.")

# ---------------------------------------------------------
# TRANSFORM
# ---------------------------------------------------------
print("\n[2/5] TRANSFORM: Cleaning and auditing data quality...")

# Drop missing CustomerID
null_customers = df["CustomerID"].isna().sum()

df = df.dropna(subset=["CustomerID"])
df["CustomerID"] = df["CustomerID"].astype(int)

print(
    f" Dropped missing CustomerID: {null_customers:,} records "
    f"({(null_customers / total_raw_rows) * 100:.2f}%)"
)

# Drop invalid transactions
invalid_qty = (df["Quantity"] <= 0).sum()
invalid_price = (df["UnitPrice"] <= 0).sum()

invalid_records = ((df["Quantity"] <= 0) | (df["UnitPrice"] <= 0)).sum()

df = df[(df["Quantity"] > 0) & (df["UnitPrice"] > 0)]

print(
    f" Dropped invalid transactions: {invalid_records:,} records "
    f"(Non-positive Qty: {invalid_qty:,}, "
    f"Non-positive Price: {invalid_price:,})"
)

# Drop duplicate rows
duplicates = df.duplicated().sum()

df = df.drop_duplicates()

print(f"  Dropped duplicates: {duplicates:,} records")

# Summary of retained data
clean_rows = len(df)

retained_rate = (clean_rows / total_raw_rows) * 100

print(
    f"  --> Quality Audit Summary: Retained "
    f"{clean_rows:,} / {total_raw_rows:,} rows "
    f"({retained_rate:.2f}%). "
    f"Filtered out {total_raw_rows - clean_rows:,} rows."
)

# Standardize text, timestamps, and compute derived measures
df["StockCode"] = df["StockCode"].astype(str).str.strip()

df["Description"] = df["Description"].astype(str).str.strip()

df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])

df["total_amount"] = (df["Quantity"] * df["UnitPrice"]).round(2)

df["date_key"] = df["InvoiceDate"].dt.strftime("%Y%m%d").astype(int)

# ---------------------------------------------------------
# LOAD DIMENSION TABLES
# ---------------------------------------------------------
print("\n[3/5] LOAD: Populating Dimension tables...")

# Date Dimension
dates = df["InvoiceDate"].dt.date.drop_duplicates()

dim_date = pd.DataFrame(
    {
        "date_key": dates.apply(lambda d: int(d.strftime("%Y%m%d"))),
        "full_date": dates,
        "day": dates.apply(lambda d: d.day),
        "month": dates.apply(lambda d: d.month),
        "quarter": dates.apply(lambda d: (d.month - 1) // 3 + 1),
        "year": dates.apply(lambda d: d.year),
        "day_of_week": dates.apply(lambda d: d.strftime("%A")),
        "is_weekend": dates.apply(lambda d: d.weekday() >= 5),
    }
)

dim_date.to_sql("dim_date", engine, if_exists="append", index=False)

print(f"  -> dim_date: Inserted {len(dim_date):,} unique dates.")

# Customer Dimension
dim_customer = (
    df[["CustomerID", "Country"]]
    .drop_duplicates(subset=["CustomerID"])
    .rename(columns={"CustomerID": "customer_id", "Country": "country"})
)

dim_customer.to_sql("dim_customer", engine, if_exists="append", index=False)

print(f"  -> dim_customer: Inserted " f"{len(dim_customer):,} unique customers.")

# Product Dimension
dim_product = (
    df.sort_values("InvoiceDate")
    .groupby("StockCode")
    .last()
    .reset_index()[["StockCode", "Description", "UnitPrice"]]
    .rename(
        columns={
            "StockCode": "stock_code",
            "Description": "description",
            "UnitPrice": "unit_price",
        }
    )
)

dim_product["description"] = dim_product["description"].fillna("Unknown")

dim_product.to_sql("dim_product", engine, if_exists="append", index=False)

print(f"  -> dim_product: Inserted " f"{len(dim_product):,} unique products.")

# ---------------------------------------------------------
# KEY MAPPING
# ---------------------------------------------------------
print("\n[4/5] TRANSFORM: Mapping surrogate keys " "from Dimension tables...")

with engine.connect() as conn:
    map_cust = pd.read_sql("SELECT customer_key, customer_id FROM dim_customer", conn)

    map_prod = pd.read_sql("SELECT product_key, stock_code FROM dim_product", conn)

df = df.merge(map_cust, left_on="CustomerID", right_on="customer_id", how="inner")

df = df.merge(map_prod, left_on="StockCode", right_on="stock_code", how="inner")

fact_sales = df[
    [
        "InvoiceNo",
        "date_key",
        "customer_key",
        "product_key",
        "Quantity",
        "UnitPrice",
        "total_amount",
    ]
].rename(
    columns={
        "InvoiceNo": "invoice_no",
        "Quantity": "quantity",
        "UnitPrice": "unit_price",
    }
)

print("  -> Surrogate key mapping completed successfully.")

# ---------------------------------------------------------
# LOAD FACT TABLE
# ---------------------------------------------------------
print(f"\n[5/5] LOAD: Ingesting " f"{len(fact_sales):,} records into fact_sales ...")

fact_sales.to_sql(
    "fact_sales", engine, if_exists="append", index=False, chunksize=10000
)

print("  -> fact_sales ingestion completed.")

# ---------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------
elapsed = time.time() - start_time

print("==================================================")
print(f"[SUCCESS] ETL Pipeline finished successfully " f"in {elapsed:.2f} seconds.")
print("==================================================")

engine.dispose()
