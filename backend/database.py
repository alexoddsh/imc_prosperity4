import os
import io
import json
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def fast_pg_insert(df: pd.DataFrame, table_name: str):
    if df.empty:
        return
        
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)
    
    raw_conn = engine.raw_connection()
    try:
        with raw_conn.cursor() as cursor:
            columns = ",".join([f'"{c}"' for c in df.columns])
            copy_sql = f"COPY {table_name} ({columns}) FROM STDIN WITH CSV"
            cursor.copy_expert(sql=copy_sql, file=buffer)
        raw_conn.commit()
    finally:
        raw_conn.close()

def update_backtest_status(task_id, status, pnl=0.0, product_pnls=None, products_sharpes=None):
    if product_pnls is None:
        product_pnls = {}
    if products_sharpes is None:
        products_sharpes = {}
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE backtest_runs SET status = :s, total_pnl = :p, products_pnl = :pnls, products_sharpes = :sharpes WHERE id = :id"),
            {"s": status, "p": pnl, "pnls": json.dumps(product_pnls), "sharpes": json.dumps(products_sharpes), "id": task_id}
        )