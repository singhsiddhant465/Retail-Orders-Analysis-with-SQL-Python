"""
Retail Orders — ETL Pipeline (Microsoft SQL Server)
===================================================
Extract  : read the raw Kaggle orders.csv
Transform: clean placeholders, standardise column names, engineer
           discount / sale_price / profit, fix data types
Load     : write a clean `orders` table into a local SQL Server database

Connects to SQL Server with Windows Authentication by default (no password).
To use SQL Authentication instead, set MSSQL_AUTH=sql and provide
MSSQL_USER / MSSQL_PASSWORD via environment variables or a .env file.

Author: Siddhant Singh
"""

import os
import urllib.parse

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.types import Integer, String, Date, Numeric

# Optional: load a local .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# --------------------------------------------------------------------------- #
# Configuration (override any of these via environment variables)
# --------------------------------------------------------------------------- #
RAW_CSV     = os.environ.get("ORDERS_CSV", r"C:\Users\singh\Desktop\orders.csv")
DB_SERVER   = os.environ.get("MSSQL_SERVER", "localhost")        # default instance
DB_NAME     = os.environ.get("MSSQL_DB",     "retail")
DB_DRIVER   = os.environ.get("MSSQL_DRIVER", "ODBC Driver 17 for SQL Server")
DB_AUTH     = os.environ.get("MSSQL_AUTH",   "windows")          # "windows" or "sql"
DB_USER     = os.environ.get("MSSQL_USER")                       # only for sql auth
DB_PASSWORD = os.environ.get("MSSQL_PASSWORD")                   # only for sql auth
TABLE_NAME  = "orders"

# Placeholder strings that really mean "missing"
NA_PLACEHOLDERS = ["Not Available", "unknown"]

# Explicit SQL types so the table schema is clean and predictable
SQL_DTYPES = {
    "order_id":         Integer(),
    "order_date":       Date(),
    "ship_mode":        String(50),
    "segment":          String(50),
    "country":          String(100),
    "city":             String(100),
    "state":            String(100),
    "postal_code":      String(20),
    "region":           String(50),
    "category":         String(50),
    "sub_category":     String(50),
    "product_id":       String(100),
    "quantity":         Integer(),
    "cost_price":       Numeric(10, 2),
    "list_price":       Numeric(10, 2),
    "discount_percent": Integer(),
    "discount":         Numeric(10, 2),
    "sale_price":       Numeric(10, 2),
    "profit":           Numeric(10, 2),
}


# --------------------------------------------------------------------------- #
# Connection helpers
# --------------------------------------------------------------------------- #
def _odbc_conn_str(database: str) -> str:
    """Build an ODBC connection string for the given database."""
    parts = [
        f"DRIVER={{{DB_DRIVER}}}",
        f"SERVER={DB_SERVER}",
        f"DATABASE={database}",
        "Encrypt=no",  # fine for a local dev instance
    ]
    if DB_AUTH.lower() == "sql":
        if not (DB_USER and DB_PASSWORD):
            raise SystemExit("MSSQL_AUTH=sql requires MSSQL_USER and MSSQL_PASSWORD.")
        parts += [f"UID={DB_USER}", f"PWD={DB_PASSWORD}"]
    else:
        parts.append("Trusted_Connection=yes")  # Windows Authentication
    return ";".join(parts)


def get_engine(database: str, autocommit: bool = False):
    """Create a SQLAlchemy engine for SQL Server via pyodbc."""
    url = "mssql+pyodbc:///?odbc_connect=" + urllib.parse.quote_plus(_odbc_conn_str(database))
    engine = create_engine(url, fast_executemany=True)
    if autocommit:
        engine = engine.execution_options(isolation_level="AUTOCOMMIT")
    return engine


# --------------------------------------------------------------------------- #
# ETL steps
# --------------------------------------------------------------------------- #
def extract(csv_path: str) -> pd.DataFrame:
    """Read the raw CSV, treating placeholder strings as NaN."""
    print(f"[extract] reading {csv_path}")
    df = pd.read_csv(csv_path, na_values=NA_PLACEHOLDERS)
    print(f"[extract] {len(df):,} rows x {df.shape[1]} columns")
    return df


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Clean, standardise, and engineer features."""
    # snake_case column names: "Order Id" -> "order_id"
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    # proper date type
    df["order_date"] = pd.to_datetime(df["order_date"], format="%Y-%m-%d")

    # feature engineering
    df["discount"]   = df["list_price"] * df["discount_percent"] * 0.01
    df["sale_price"] = df["list_price"] - df["discount"]
    df["profit"]     = df["sale_price"] - df["cost_price"]

    # round money columns to 2 dp
    for col in ["discount", "sale_price", "profit"]:
        df[col] = df[col].round(2)

    # store order_date as a pure date (no time component)
    df["order_date"] = df["order_date"].dt.date

    # keep columns in a sensible order
    ordered = [
        "order_id", "order_date", "ship_mode", "segment", "country", "city",
        "state", "postal_code", "region", "category", "sub_category",
        "product_id", "quantity", "cost_price", "list_price", "discount_percent",
        "discount", "sale_price", "profit",
    ]
    df = df[ordered]

    # object columns with NaN -> None so they insert as SQL NULL
    df = df.astype(object).where(pd.notnull(df), None)

    print(f"[transform] {sum(v is None for v in df['ship_mode'])} rows have a missing ship_mode")
    print(f"[transform] final columns: {list(df.columns)}")
    return df


def load(df: pd.DataFrame) -> None:
    """Create the database if needed and (re)write the orders table.

    if_exists='replace' means re-running the pipeline is idempotent —
    it never appends duplicate rows.
    """
    # 1) create the database if it doesn't exist (run against master, autocommit)
    with get_engine("master", autocommit=True).connect() as conn:
        conn.execute(text(
            f"IF DB_ID('{DB_NAME}') IS NULL CREATE DATABASE [{DB_NAME}]"
        ))
    print(f"[load] database '{DB_NAME}' ready")

    # 2) write the table
    engine = get_engine(DB_NAME)
    df.to_sql(TABLE_NAME, engine, if_exists="replace", index=False, dtype=SQL_DTYPES)
    print(f"[load] wrote {len(df):,} rows to {DB_NAME}.dbo.{TABLE_NAME}")

    # 3) quick sanity check
    with engine.connect() as conn:
        n = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE_NAME}")).scalar()
    print(f"[load] verification — {n:,} rows now in {DB_NAME}.dbo.{TABLE_NAME}")


def main() -> None:
    df = extract(RAW_CSV)
    df = transform(df)
    load(df)
    print("[done] ETL complete.")


if __name__ == "__main__":
    main()
