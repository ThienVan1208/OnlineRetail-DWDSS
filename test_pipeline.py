"""
End-to-end integration test: RFM Segmentation to What-If Promotion DSS.
Extracts customer transactions from MySQL Data Warehouse, performs K-Means
clustering, and feeds segment metrics directly into the promotion simulation engine.
"""

from src.dss.rfm_clustering import (
    get_standalone_engine,
    extract_rfm_from_db,
    run_kmeans_clustering,
)
from src.dss.promotion_simulator import (
    compare_all_segments_what_if,
)


def main():
    print("=" * 80)
    print("STEP 1: EXTRACT RFM METRICS AND FIT K-MEANS CLUSTERING")
    print("=" * 80)

    engine = get_standalone_engine()
    print("Connecting to MySQL data warehouse (retail_dw)...")
    rfm_df = extract_rfm_from_db(engine)
    print(f"Loaded {len(rfm_df):,} active customers from database.")

    print("\nFitting K-Means model (k=4) with automated centroid ranking...")
    clustered_df, segment_summary, metrics = run_kmeans_clustering(rfm_df, n_clusters=4)

    print(
        f"Model Diagnostics -> Silhouette Score: {metrics['silhouette_score']} | "
        f"Inertia (WCSS): {metrics['inertia']:,}"
    )

    print("\n--- Segment Profile Summary (RFM Clustering Output) ---")
    summary_cols = [
        "segment_name",
        "customer_count",
        "customer_share_pct",
        "avg_recency",
        "avg_frequency",
        "avg_monetary",
        "total_revenue",
        "revenue_share_pct",
    ]
    print(segment_summary[summary_cols].to_string(index=False))

    print("\n" + "=" * 80)
    print("STEP 2: RUN WHAT-IF PROMOTION SIMULATION ON ACTUAL SEGMENTS")
    print("=" * 80)
    print(
        "Scenario parameters: 10% discount, 60% COGS, "
        "fixed marketing cost = GBP 500, cost per customer = GBP 0.50\n"
    )

    what_if_comparison = compare_all_segments_what_if(
        segment_summary_df=segment_summary,
        discount_pct=10.0,
        cogs_pct=60.0,
        fixed_marketing_cost=500.0,
        cost_per_customer=0.50,
    )

    display_cols = [
        "segment_name",
        "customer_count",
        "baseline_revenue",
        "simulated_revenue",
        "expected_volume_lift_pct",
        "breakeven_volume_lift_pct",
        "net_profit_lift",
        "roi_pct",
        "decision_badge",
    ]
    print("--- What-If Simulation Results by Customer Segment ---")
    print(what_if_comparison[display_cols].to_string(index=False))

    print("\n" + "=" * 80)
    print("STEP 3: DETAILED ECONOMIC EVALUATION OF TOP-RANKED SEGMENT")
    print("=" * 80)
    top_seg = what_if_comparison.iloc[0]
    print(f"Segment Analyzed               : {top_seg['segment_name']}")
    print(f"- Customer Base                : {top_seg['customer_count']:,} customers")
    print(f"- Baseline Revenue             : GBP {top_seg['baseline_revenue']:,.2f}")
    print(f"- Expected Simulated Revenue   : GBP {top_seg['simulated_revenue']:,.2f}")
    print(f"- Expected Volume Expansion    : +{top_seg['expected_volume_lift_pct']:.2f}%")
    print(f"- Break-Even Volume Hurdle     : +{top_seg['breakeven_volume_lift_pct']:.2f}%")
    print(f"- Net Profit Lift (Variance)   : GBP {top_seg['net_profit_lift']:+,.2f}")
    print(f"- Campaign ROI                 : {top_seg['roi_pct']:+.1f}%")
    print(f"- Managerial Recommendation    : {top_seg['decision_badge']}")

    print("=" * 80)
    print("End-to-end integration test completed successfully.")
    print("=" * 80)


if __name__ == "__main__":
    main()
