"""Export high-resolution charts for LaTeX DSS report.
- kmeans_evaluation.png (Elbow & Silhouette)
- whatif_simulation.png (Financial impact bar chart & Sensitivity heatmap)
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

from src.dss.promotion_simulator import generate_sensitivity_matrix


def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    report_img_dir = os.path.join(base_dir, "docs", "images")
    os.makedirs(report_img_dir, exist_ok=True)
    plt.rcParams.update({"font.sans-serif": "Arial", "font.size": 9.5})

    # 1. K-MEANS ELBOW & SILHOUETTE CHART
    k_vals = [2, 3, 4, 5, 6]
    wcss_vals = [6476.54, 4858.19, 3925.34, 3269.01, 2840.47]
    sil_vals = [0.4308, 0.3350, 0.3329, 0.3167, 0.3153]

    fig, ax1 = plt.subplots(figsize=(7.5, 4.0), dpi=300)
    color_wcss = "#1E40AF"
    ax1.set_xlabel("Number of clusters (K)", fontweight="bold", labelpad=8)
    ax1.set_ylabel("Inertia / WCSS (Within-cluster variance)", color=color_wcss, fontweight="bold")
    line1 = ax1.plot(k_vals, wcss_vals, color=color_wcss, marker="o", linewidth=2.4, markersize=7, label="WCSS (Elbow)")
    ax1.tick_params(axis="y", labelcolor=color_wcss)
    ax1.grid(True, linestyle="--", alpha=0.5)

    ax2 = ax1.twinx()
    color_sil = "#15803D"
    ax2.set_ylabel("Silhouette Score", color=color_sil, fontweight="bold")
    line2 = ax2.plot(k_vals, sil_vals, color=color_sil, marker="s", linewidth=2.4, linestyle="--", markersize=7, label="Silhouette Score")
    ax2.tick_params(axis="y", labelcolor=color_sil)

    ax1.axvline(x=4, color="#DC2626", linestyle=":", linewidth=1.8, alpha=0.8)
    ax1.annotate(
        "Optimal balance point (K=4)\nWCSS=3,925 | Silhouette=0.3329",
        xy=(4, 3925.34),
        xytext=(4.15, 4750),
        arrowprops=dict(facecolor="#DC2626", shrink=0.08, width=1.5, headwidth=6),
        fontweight="bold",
        fontsize=8.5,
        color="#991B1B",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#FEF2F2", edgecolor="#F87171"),
    )

    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="upper right", framealpha=0.9)
    plt.title("K-Means clustering diagnostics via Elbow and Silhouette metrics", fontweight="bold", fontsize=11, pad=10)
    fig.tight_layout()
    eval_path = os.path.join(report_img_dir, "kmeans_evaluation.png")
    plt.savefig(eval_path, dpi=300)
    plt.close()
    print("Saved:", eval_path)

    # 2. WHAT-IF PROMOTION IMPACT AND SENSITIVITY MATRIX
    fig, (ax_bar, ax_heat) = plt.subplots(1, 2, figsize=(14.0, 5.0), dpi=300)

    # Panel A: Bar chart
    segments = ["Champions\n(VIP)", "Loyal\nCustomers", "Potential\nPromising", "At Risk\nHibernating", "All Segments\n(Total)"]
    baseline_profit = np.array([2326.26, 836.90, 180.74, 210.99, 3554.88])
    simulated_profit = np.array([1994.19, 754.21, 168.93, 203.78, 3121.12])
    delta_profit = simulated_profit - baseline_profit

    x = np.arange(len(segments))
    width = 0.35
    ax_bar.bar(x - width/2, baseline_profit, width, label="Baseline profit (Pre-campaign)", color="#64748B", alpha=0.9)
    ax_bar.bar(x + width/2, simulated_profit, width, label="Simulated profit (10% discount)", color="#2563EB", alpha=0.9)

    for i in range(len(segments)):
        val = delta_profit[i]
        ax_bar.annotate(
            f"{val:+.1f}k\n({val/baseline_profit[i]*100:.1f}%)",
            xy=(x[i] + width/2, simulated_profit[i]),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7.8,
            fontweight="bold",
            color="#DC2626",
        )

    ax_bar.set_ylabel("Profit (thousand GBP)", fontweight="bold")
    ax_bar.set_title("(a) Profit variance under 10% mass promotion scenario", fontweight="bold", fontsize=11, pad=10)
    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels(segments)
    ax_bar.set_ylim(0, 4100)
    ax_bar.legend(loc="upper right", framealpha=0.9)
    ax_bar.grid(True, axis="y", linestyle="--", alpha=0.5)

    # Panel B: Sensitivity Matrix Heatmap
    sens_df = generate_sensitivity_matrix(
        baseline_revenue=8887208.89,
        customer_count=4338,
        response_rate_pct=65.0,
        cogs_pct=60.0,
        fixed_marketing_cost=500.0,
        cost_per_customer=0.50,
    )
    sens_mat = sens_df.values / 1000.0

    v_min = float(np.min(sens_mat))
    v_max = float(max(abs(v_min) / 4.0, 100.0))
    norm = TwoSlopeNorm(vmin=v_min, vcenter=0.0, vmax=v_max)
    im = ax_heat.imshow(sens_mat, cmap="RdYlGn", norm=norm, aspect="auto")

    x_labels = [c.replace("Discount ", "") for c in sens_df.columns]
    y_labels = [r.replace("Elasticity = ", "ε = ") for r in sens_df.index]
    ax_heat.set_xticks(np.arange(len(x_labels)))
    ax_heat.set_yticks(np.arange(len(y_labels)))
    ax_heat.set_xticklabels(x_labels, fontsize=8.5)
    ax_heat.set_yticklabels(y_labels, fontsize=8.5)
    ax_heat.set_xlabel("Proposed discount (%)", fontweight="bold", labelpad=6)
    ax_heat.set_ylabel("Price elasticity of demand (ε)", fontweight="bold")
    ax_heat.set_title("(b) 2D Net profit lift sensitivity matrix (thousand GBP)", fontweight="bold", fontsize=11, pad=10)

    for i in range(len(y_labels)):
        for j in range(len(x_labels)):
            val = sens_mat[i, j]
            text_color = "white" if val < -1000 or val > 500 else "black"
            ax_heat.text(j, i, f"{val:+.0f}k", ha="center", va="center", color=text_color, fontsize=7.2, fontweight="bold")

    cbar = fig.colorbar(im, ax=ax_heat, shrink=0.85, pad=0.03)
    cbar.set_label("Net profit lift ΔΠ (thousand GBP)", fontsize=8.5)

    fig.tight_layout()
    whatif_path = os.path.join(report_img_dir, "whatif_simulation.png")
    plt.savefig(whatif_path, dpi=300)
    plt.close()
    print("Saved:", whatif_path)


if __name__ == "__main__":
    main()
