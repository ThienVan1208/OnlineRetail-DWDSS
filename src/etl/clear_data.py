import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

connection_string = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(connection_string)

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