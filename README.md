# Online Retail Data Warehouse & DSS

Project components: MySQL star schema, ETL pipeline, OLAP dashboard (Streamlit),
RFM customer segmentation with K-Means, and promotion what-if simulation.

## Prerequisites
- Python 3.10+
- MySQL 8.0+
- The Online Retail CSV dataset stored as `data/data.csv` (dataset is not included in this archive).

## Setup (PowerShell)
```powershell
cd D:\Downloads\OnlineRetail-DWDSS
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```
Fill in your MySQL password locally in `.env`. Never commit `.env`.

## Database and ETL
1. Start MySQL Server.
2. In MySQL Workbench, run `src/sql/create_tables.sql`.
3. Put the source CSV at `data/data.csv`.
4. Run ETL:
```powershell
python -m src.etl.etl
```
The ETL appends rows. For a clean re-run, use the clear-data utility only after
confirming that the existing data can be deleted:
```powershell
python -m src.etl.clear_data
```

## OLAP Dashboard
```powershell
streamlit run src/app/main.py
```
Dashboard includes KPI cards, monthly revenue, country revenue, top products,
weekday revenue and a country revenue ranking using `DENSE_RANK()`.

## DSS modules
- `src/dss/rfm_clustering.py`: RFM extraction, log transform, standardization,
  K-Means and cluster summaries.
- `src/dss/promotion_simulator.py`: promotion profitability simulation and
  sensitivity analysis.

## Important
This archive was assembled from the source ZIP supplied for review. The original
CSV, project-specific automated tests, and course rubric were not present.
Run the pipeline locally with the course dataset and verify results against the
team's rubric before submission.
