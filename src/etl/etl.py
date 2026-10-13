import os
import time
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

start_time = time.time()
load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

connection_string = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(connection_string)

# ---------------------------------------------------------
# EXTRACT
# ---------------------------------------------------------
print("==================================================")
print("[1/5] EXTRACT: Reading raw CSV dataset...")
csv_path = os.path.join("data", "data.csv") if os.path.exists(os.path.join("data", "data.csv")) else "data.csv"
df = pd.read_csv(csv_path, encoding="ISO-8859-1")
total_raw_rows = len(df)
print(f"  -> Successfully loaded {total_raw_rows:,} raw records from '{csv_path}'.")

# ---------------------------------------------------------
# TRANSFORM
# ---------------------------------------------------------
print("\n[2/5] TRANSFORM: Cleaning and auditing data quality...")

# Drop missing CustomerID
null_customers = df["CustomerID"].isna().sum()
df = df.dropna(subset=["CustomerID"])
df["CustomerID"] = df["CustomerID"].astype(int)
print(f" Dropped missing CustomerID: {null_customers:,} records ({(null_customers / total_raw_rows) * 100:.2f}%)")

# Drop invalid transactions 
invalid_qty = (df["Quantity"] <= 0).sum()
invalid_price = (df["UnitPrice"] <= 0).sum()
invalid_records = ((df["Quantity"] <= 0) | (df["UnitPrice"] <= 0)).sum()
df = df[(df["Quantity"] > 0) & (df["UnitPrice"] > 0)]
print(f" Dropped invalid transactions: {invalid_records:,} records (Non-positive Qty: {invalid_qty:,}, Non-positive Price: {invalid_price:,})")

# Drop duplicate rows
duplicates = df.duplicated().sum()
df = df.drop_duplicates()
print(f"  Dropped duplicates: {duplicates:,} records")

# Summary of retained data
clean_rows = len(df)
retained_rate = (clean_rows / total_raw_rows) * 100
print(f"  --> Quality Audit Summary: Retained {clean_rows:,} / {total_raw_rows:,} rows ({retained_rate:.2f}%). Filtered out {total_raw_rows - clean_rows:,} rows.")

# Standardize text, timestamps, and compute derived measures
df["StockCode"] = df["StockCode"].astype(str).str.strip()
df["Description"] = df["Description"].astype(str).str.strip()
df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
df["total_amount"] = (df["Quantity"] * df["UnitPrice"]).round(2)
df["date_key"] = df["InvoiceDate"].dt.strftime("%Y%m%d").astype(int)

# ---------------------------------------------------------
# LOAD 
# ---------------------------------------------------------
print("\n[3/5] LOAD: Populating Dimension tables...")

# Date Dimension
dates = df["InvoiceDate"].dt.date.drop_duplicates()
dim_date = pd.DataFrame({
    "date_key": dates.apply(lambda d: int(d.strftime("%Y%m%d"))),
    "full_date": dates,
    "day": dates.apply(lambda d: d.day),
    "month": dates.apply(lambda d: d.month),
    "quarter": dates.apply(lambda d: (d.month - 1) // 3 + 1),
    "year": dates.apply(lambda d: d.year),
    "day_of_week": dates.apply(lambda d: d.strftime("%A")),
    "is_weekend": dates.apply(lambda d: d.weekday() >= 5)
})
dim_date.to_sql("dim_date", engine, if_exists="append", index=False)
print(f"  -> dim_date: Inserted {len(dim_date):,} unique dates.")

# Customer Dimension
dim_customer = df[["CustomerID", "Country"]].drop_duplicates(subset=["CustomerID"]).rename(
    columns={"CustomerID": "customer_id", "Country": "country"}
)
dim_customer.to_sql("dim_customer", engine, if_exists="append", index=False)
print(f"  -> dim_customer: Inserted {len(dim_customer):,} unique customers.")

# Product Dimension 
dim_product = df.sort_values("InvoiceDate").groupby("StockCode").last().reset_index()[
    ["StockCode", "Description", "UnitPrice"]
].rename(
    columns={"StockCode": "stock_code", "Description": "description", "UnitPrice": "unit_price"}
)
dim_product["description"] = dim_product["description"].fillna("Unknown")
dim_product.to_sql("dim_product", engine, if_exists="append", index=False)
print(f"  -> dim_product: Inserted {len(dim_product):,} unique products.")

# ---------------------------------------------------------
# KEY MAPPING
# ---------------------------------------------------------
print("\n[4/5] TRANSFORM: Mapping surrogate keys from Dimension tables...")

with engine.connect() as conn:
    map_cust = pd.read_sql("SELECT customer_key, customer_id FROM dim_customer", conn)
    map_prod = pd.read_sql("SELECT product_key, stock_code FROM dim_product", conn)

df = df.merge(map_cust, left_on="CustomerID", right_on="customer_id", how="inner")
df = df.merge(map_prod, left_on="StockCode", right_on="stock_code", how="inner")

fact_sales = df[[
    "InvoiceNo", "date_key", "customer_key", "product_key", 
    "Quantity", "UnitPrice", "total_amount"
]].rename(columns={
    "InvoiceNo": "invoice_no",
    "Quantity": "quantity",
    "UnitPrice": "unit_price"
})
print("  -> Surrogate key mapping completed successfully.")

# ---------------------------------------------------------
# LOAD FACT TABLE
# ---------------------------------------------------------
print(f"\n[5/5] LOAD: Ingesting {len(fact_sales):,} records into fact_sales ...")
fact_sales.to_sql("fact_sales", engine, if_exists="append", index=False, chunksize=10000)
print("  -> fact_sales ingestion completed.")

elapsed = time.time() - start_time
print("==================================================")
print(f"[SUCCESS] ETL Pipeline finished successfully in {elapsed:.2f} seconds.")
print("==================================================")