# Online Retail DW-DSS
dataset: https://www.kaggle.com/datasets/carrie1/ecommerce-data

## Structure

```text
data/                 Sample input data and the input-column contract
docs/                 Project report and presentation files
src/sql/              Warehouse schema and OLAP query examples
src/etl/              Data loading and cleaning pipeline
src/dss/              RFM and what-if analysis modules
src/app/              Streamlit dashboard and UI components
```

Report: https://www.overleaf.com/project/6ad590f280348f75895d4188/share#fbebbe90b01bde0b365214946895453b8922b774bf1bb4d5

HOW TO RUN:
Import data:
```bash
py src/etl/etl.py
```