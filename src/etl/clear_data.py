import os
import sys
from sqlalchemy import text

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.db_config import create_mysql_engine

engine = create_mysql_engine(connect_timeout=15)

def truncate_tables():    
    # Order of tables to clear
    tables = ["fact_sales", "dim_customer", "dim_product", "dim_date"]
    
    with engine.begin() as conn:
        # Disable foreign key checks to allow truncating parent tables
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        
        for table in tables:
            conn.execute(text(f"TRUNCATE TABLE {table};"))
            print(f"  Clear: {table}")
            
        # Re-enable foreign key checks
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        
    print("All tables have been cleared.")

if __name__ == "__main__":
    confirm = input("Are you sure you want to delete ALL data in 'retail_dw'? (y/n): ")
    if confirm.lower() == "y":
        truncate_tables()
    else:
        print("Operation cancelled.")