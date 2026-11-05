"""
Customer segmentation and scenario simulation modules.
"""

from src.dss.rfm_clustering import (
    extract_rfm_from_db,
    preprocess_rfm,
    evaluate_optimal_k,
    run_kmeans_clustering,
    get_standalone_engine,
)
from src.dss.promotion_simulator import (
    simulate_promotion_scenario,
    generate_sensitivity_matrix,
    compare_all_segments_what_if,
    get_segment_prior,
    DEFAULT_SEGMENT_PRIORS,
)

__all__ = [
    "extract_rfm_from_db",
    "preprocess_rfm",
    "evaluate_optimal_k",
    "run_kmeans_clustering",
    "get_standalone_engine",
    "simulate_promotion_scenario",
    "generate_sensitivity_matrix",
    "compare_all_segments_what_if",
    "get_segment_prior",
    "DEFAULT_SEGMENT_PRIORS",
]
