"""
Customer RFM segmentation and K-Means clustering.
"""

import os
from urllib.parse import quote_plus
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

# Customer segment labels by cluster rank (1 is best)
SEGMENT_LABELS_MAP = {
    2: [
        "1. High-Value Customers",
        "2. Low-Value / At Risk",
    ],
    3: [
        "1. Champions (VIP)",
        "2. Loyal & Potential",
        "3. At Risk / Hibernating",
    ],
    4: [
        "1. Champions (VIP)",
        "2. Loyal Customers",
        "3. Potential / Promising",
        "4. At Risk / Hibernating",
    ],
    5: [
        "1. Champions (VIP)",
        "2. Loyal Customers",
        "3. Potential Loyalists",
        "4. Needs Attention",
        "5. At Risk / Lost",
    ],
    6: [
        "1. Champions (VIP)",
        "2. Loyal Customers",
        "3. Potential Loyalists",
        "4. Promising New",
        "5. Needs Attention",
        "6. Hibernating / Lost",
    ],
}

SEGMENT_STRATEGY_MAP = {
    "1. Champions (VIP)": (
        "Reward with exclusive VIP privileges, early access to new collections, "
        "and personalized service. Avoid deep discounts to safeguard gross margins."
    ),
    "2. Loyal Customers": (
        "Maximize customer lifetime value via cross-selling and up-selling bundles "
        "(8%-12% basket discounts) and structured loyalty rewards."
    ),
    "3. Potential / Promising": (
        "Stimulate purchase frequency with time-sensitive coupons (10%-15% discount) "
        "and tailored product recommendations to convert into loyalists."
    ),
    "4. At Risk / Hibernating": (
        "Execute targeted win-back campaigns offering aggressive reactivation discounts (15%-20%), "
        "closely monitoring break-even volume hurdles."
    ),
}


def get_standalone_engine():
    """Create SQLAlchemy engine from .env variables."""
    load_dotenv()
    user = os.getenv("DB_USER", "root")
    password = quote_plus(os.getenv("DB_PASS", ""))
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    db_name = os.getenv("DB_NAME", "retail_dw")
    connection_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"
    return create_engine(connection_url, pool_pre_ping=True)


def extract_rfm_from_db(
    engine,
    years: list[int] | None = None,
    countries: list[str] | None = None,
) -> pd.DataFrame:
    """Extract customer RFM metrics from fact_sales and dimension tables."""
    where_clauses = ["1=1"]
    params = {}

    if years:
        year_placeholders = ", ".join([f":y_{i}" for i in range(len(years))])
        where_clauses.append(f"d.year IN ({year_placeholders})")
        for i, y in enumerate(years):
            params[f"y_{i}"] = int(y)

    if countries:
        country_placeholders = ", ".join([f":c_{i}" for i in range(len(countries))])
        where_clauses.append(f"c.country IN ({country_placeholders})")
        for i, c_name in enumerate(countries):
            params[f"c_{i}"] = str(c_name)

    where_sql = " AND ".join(where_clauses)

    query = f"""
    WITH filtered_sales AS (
        SELECT
            f.customer_key,
            c.customer_id,
            c.country,
            f.invoice_no,
            f.quantity,
            f.total_amount,
            d.full_date
        FROM fact_sales f
        INNER JOIN dim_customer c ON f.customer_key = c.customer_key
        INNER JOIN dim_date d ON f.date_key = d.date_key
        WHERE {where_sql}
    ),
    ref_date_cte AS (
        SELECT DATE_ADD(MAX(full_date), INTERVAL 1 DAY) AS ref_date
        FROM filtered_sales
    )
    SELECT
        fs.customer_key,
        fs.customer_id,
        fs.country,
        MAX(fs.full_date) AS last_purchase_date,
        DATEDIFF((SELECT ref_date FROM ref_date_cte), MAX(fs.full_date)) AS recency,
        COUNT(DISTINCT fs.invoice_no) AS frequency,
        ROUND(SUM(fs.total_amount), 2) AS monetary,
        ROUND(SUM(fs.total_amount) / COUNT(DISTINCT fs.invoice_no), 2) AS avg_order_value,
        SUM(fs.quantity) AS total_items
    FROM filtered_sales fs
    GROUP BY fs.customer_key, fs.customer_id, fs.country
    HAVING frequency > 0 AND monetary > 0
    ORDER BY monetary DESC;
    """

    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params=params)

    for col in ["recency", "frequency", "total_items"]:
        if col in df.columns:
            df[col] = df[col].astype(int)
    for col in ["monetary", "avg_order_value"]:
        if col in df.columns:
            df[col] = df[col].astype(float)

    return df


def preprocess_rfm(rfm_df: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame, StandardScaler]:
    """Log-transform (log1p) and scale RFM features."""
    features = ["recency", "frequency", "monetary"]
    for col in features:
        if col not in rfm_df.columns:
            raise KeyError(f"Required RFM feature '{col}' missing from input DataFrame.")

    log_df = pd.DataFrame(index=rfm_df.index)
    for col in features:
        log_df[col] = np.log1p(rfm_df[col].clip(lower=0))

    scaler = StandardScaler()
    scaled_matrix = scaler.fit_transform(log_df[features])
    return scaled_matrix, log_df, scaler


def evaluate_optimal_k(
    scaled_matrix: np.ndarray,
    k_min: int = 2,
    k_max: int = 8,
    random_state: int = 42,
) -> pd.DataFrame:
    """Calculate inertia (Elbow) and silhouette scores for different K values."""
    records = []
    sample_size = min(len(scaled_matrix), 4000)

    for k in range(k_min, k_max + 1):
        if k >= len(scaled_matrix):
            break
        kmeans = KMeans(n_clusters=k, init="k-means++", n_init=10, random_state=random_state)
        labels = kmeans.fit_predict(scaled_matrix)
        sil_score = silhouette_score(
            scaled_matrix,
            labels,
            sample_size=sample_size,
            random_state=random_state,
        )
        records.append(
            {
                "k": int(k),
                "inertia": round(float(kmeans.inertia_), 2),
                "silhouette_score": round(float(sil_score), 4),
            }
        )

    return pd.DataFrame(records)


def run_kmeans_clustering(
    rfm_df: pd.DataFrame,
    n_clusters: int = 4,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Run K-Means on RFM data and sort clusters by rank (score = -z_R + z_F + z_M)."""
    if rfm_df.empty or len(rfm_df) < n_clusters:
        raise ValueError(
            f"Insufficient customer sample size ({len(rfm_df)}) to partition into {n_clusters} clusters."
        )

    scaled_matrix, log_df, _ = preprocess_rfm(rfm_df)

    kmeans = KMeans(
        n_clusters=n_clusters,
        init="k-means++",
        n_init=10,
        random_state=random_state,
    )
    raw_labels = kmeans.fit_predict(scaled_matrix)

    sil_score = silhouette_score(
        scaled_matrix,
        raw_labels,
        sample_size=min(len(scaled_matrix), 4000),
        random_state=random_state,
    )

    # Rank centroids: lower recency is better, higher freq & monetary is better
    centroids = kmeans.cluster_centers_  # shape: (n_clusters, 3)
    composite_scores = -centroids[:, 0] + centroids[:, 1] + centroids[:, 2]
    sorted_cluster_indices = np.argsort(composite_scores)[::-1]

    labels_list = SEGMENT_LABELS_MAP.get(
        n_clusters,
        [f"Segment {i + 1}" for i in range(n_clusters)],
    )

    cluster_to_rank = {}
    cluster_to_name = {}
    for rank_idx, orig_cluster_id in enumerate(sorted_cluster_indices):
        cluster_to_rank[int(orig_cluster_id)] = int(rank_idx + 1)
        cluster_to_name[int(orig_cluster_id)] = labels_list[rank_idx]

    clustered_df = rfm_df.copy()
    clustered_df["cluster_id"] = raw_labels
    clustered_df["segment_rank"] = clustered_df["cluster_id"].map(cluster_to_rank)
    clustered_df["segment_name"] = clustered_df["cluster_id"].map(cluster_to_name)

    # Save z-scores and log values for charts
    clustered_df["z_recency"] = scaled_matrix[:, 0]
    clustered_df["z_frequency"] = scaled_matrix[:, 1]
    clustered_df["z_monetary"] = scaled_matrix[:, 2]
    clustered_df["log_recency"] = log_df["recency"]
    clustered_df["log_frequency"] = log_df["frequency"]
    clustered_df["log_monetary"] = log_df["monetary"]

    total_customers = len(clustered_df)
    total_revenue = clustered_df["monetary"].sum()

    summary_df = (
        clustered_df.groupby(["segment_rank", "segment_name"], as_index=False)
        .agg(
            customer_count=("customer_id", "count"),
            avg_recency=("recency", "mean"),
            avg_frequency=("frequency", "mean"),
            avg_monetary=("monetary", "mean"),
            total_revenue=("monetary", "sum"),
            avg_order_value=("avg_order_value", "mean"),
            z_recency=("z_recency", "mean"),
            z_frequency=("z_frequency", "mean"),
            z_monetary=("z_monetary", "mean"),
        )
        .sort_values("segment_rank")
        .reset_index(drop=True)
    )

    summary_df["customer_share_pct"] = (summary_df["customer_count"] / total_customers * 100).round(2)
    summary_df["revenue_share_pct"] = (summary_df["total_revenue"] / total_revenue * 100).round(2)
    summary_df["avg_recency"] = summary_df["avg_recency"].round(1)
    summary_df["avg_frequency"] = summary_df["avg_frequency"].round(2)
    summary_df["avg_monetary"] = summary_df["avg_monetary"].round(2)
    summary_df["total_revenue"] = summary_df["total_revenue"].round(2)
    summary_df["avg_order_value"] = summary_df["avg_order_value"].round(2)
    summary_df["recommended_strategy"] = summary_df["segment_name"].map(
        lambda name: SEGMENT_STRATEGY_MAP.get(
            name,
            "Personalize promotional engagement based on segment frequency and basket size.",
        )
    )

    metrics = {
        "n_clusters": int(n_clusters),
        "total_customers": int(total_customers),
        "total_revenue": round(float(total_revenue), 2),
        "inertia": round(float(kmeans.inertia_), 2),
        "silhouette_score": round(float(sil_score), 4),
    }

    return clustered_df, summary_df, metrics


def generate_mock_rfm_data(n_samples: int = 1500) -> pd.DataFrame:
    """Generate dummy RFM data for testing when database is not connected."""
    np.random.seed(42)
    customer_ids = [10000 + i for i in range(n_samples)]
    countries = np.random.choice(
        ["United Kingdom", "Germany", "France", "EIRE", "Spain"],
        size=n_samples,
        p=[0.82, 0.06, 0.05, 0.04, 0.03],
    )
    recency = np.random.exponential(scale=60, size=n_samples).astype(int) + 1
    frequency = np.random.geometric(p=0.3, size=n_samples)
    monetary = (frequency * np.random.exponential(scale=350, size=n_samples) + 20).round(2)
    avg_order_value = (monetary / frequency).round(2)
    total_items = (frequency * np.random.randint(5, 50, size=n_samples)).astype(int)

    return pd.DataFrame(
        {
            "customer_key": range(1, n_samples + 1),
            "customer_id": customer_ids,
            "country": countries,
            "last_purchase_date": pd.Timestamp("2011-12-09") - pd.to_timedelta(recency, unit="D"),
            "recency": recency,
            "frequency": frequency,
            "monetary": monetary,
            "avg_order_value": avg_order_value,
            "total_items": total_items,
        }
    )


if __name__ == "__main__":
    print("--- Testing RFM Clustering ---")

    try:
        engine = get_standalone_engine()
        print("Connecting to database...")
        rfm_data = extract_rfm_from_db(engine)
        if rfm_data.empty:
            raise ValueError("No customer records found in database.")
        print(f"Loaded {len(rfm_data):,} customers from DB.")
    except Exception as exc:
        print(f"Cannot connect to DB ({exc}). Generating mock data...")
        rfm_data = generate_mock_rfm_data(n_samples=1500)

    print("\nEvaluating K values:")
    scaled_mat, _, _ = preprocess_rfm(rfm_data)
    eval_df = evaluate_optimal_k(scaled_mat, k_min=2, k_max=6)
    print(eval_df.to_string(index=False))

    print("\nFitting K-Means (k=4)...")
    clustered_customers, segment_summary, model_metrics = run_kmeans_clustering(rfm_data, n_clusters=4)
    print(
        f"Silhouette Score: {model_metrics['silhouette_score']} | "
        f"Inertia: {model_metrics['inertia']:,}"
    )

    print("\nSegment Summary:")
    display_cols = [
        "segment_name",
        "customer_count",
        "customer_share_pct",
        "avg_recency",
        "avg_frequency",
        "avg_monetary",
        "total_revenue",
        "revenue_share_pct",
    ]
    print(segment_summary[display_cols].to_string(index=False))

    print("\nStrategies:")
    for _, row in segment_summary.iterrows():
        print(f"- {row['segment_name']}:\n  {row['recommended_strategy']}")
    print("\nDone.")
