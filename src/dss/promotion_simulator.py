"""
Retail promotion scenario simulation engine and break-even decision support module.
Evaluates elasticity-driven volume lift, incremental revenue, COGS, marketing costs,
and net profit variance across customer segments.
"""

import numpy as np
import pandas as pd

# Default econometric priors by customer segment
DEFAULT_SEGMENT_PRIORS = {
    "1. Champions (VIP)": {
        "discount_pct": 8.0,
        "price_elasticity": 1.1,
        "response_rate_pct": 85.0,
        "description": (
            "High loyalty and low price sensitivity (Elasticity ~ 1.1), "
            "paired with a very high campaign engagement rate."
        ),
    },
    "2. Loyal Customers": {
        "discount_pct": 10.0,
        "price_elasticity": 1.6,
        "response_rate_pct": 75.0,
        "description": (
            "Moderate price elasticity; responds effectively to basket-building discounts "
            "(10%-12%) to drive cross-category volume."
        ),
    },
    "3. Potential / Promising": {
        "discount_pct": 12.0,
        "price_elasticity": 2.1,
        "response_rate_pct": 65.0,
        "description": (
            "High price sensitivity (Elasticity ~ 2.1); structured price cuts trigger substantial "
            "demand expansion."
        ),
    },
    "4. At Risk / Hibernating": {
        "discount_pct": 15.0,
        "price_elasticity": 2.5,
        "response_rate_pct": 45.0,
        "description": (
            "Highly price-sensitive but lower response rate (~45%); win-back promotions require "
            "strict break-even volume oversight."
        ),
    },
    "All Segments (Mass Campaign)": {
        "discount_pct": 10.0,
        "price_elasticity": 1.8,
        "response_rate_pct": 65.0,
        "description": "Mass promotional campaign applied uniformly across the entire customer base.",
    },
}


def get_segment_prior(segment_name: str) -> dict:
    """Retrieve default economic assumptions (discount, elasticity, response rate) for a given segment."""
    if segment_name in DEFAULT_SEGMENT_PRIORS:
        return DEFAULT_SEGMENT_PRIORS[segment_name]

    # Match by prefix if exact segment name differs slightly
    for key, val in DEFAULT_SEGMENT_PRIORS.items():
        core_name = key.split("(")[0].strip()
        if core_name in segment_name:
            return val

    return DEFAULT_SEGMENT_PRIORS["All Segments (Mass Campaign)"]


def simulate_promotion_scenario(
    baseline_revenue: float,
    customer_count: int,
    discount_pct: float,
    price_elasticity: float,
    response_rate_pct: float,
    cogs_pct: float = 60.0,
    fixed_marketing_cost: float = 1000.0,
    cost_per_customer: float = 0.50,
) -> dict:
    """
    Simulate revenue, cost, profit lift, and break-even volume under a promotional discount.
    Returns financial metrics, variance vs baseline, and an automated decision status.
    """
    d = max(0.0, discount_pct / 100.0)
    r = np.clip(response_rate_pct / 100.0, 0.0, 1.0)
    c = np.clip(cogs_pct / 100.0, 0.01, 0.99)
    margin_0 = 1.0 - c

    # Baseline calculations
    baseline_cogs = baseline_revenue * c
    baseline_gross_profit = baseline_revenue * margin_0

    # Volume lift estimation based on price elasticity
    responder_volume_lift_ratio = price_elasticity * d
    overall_volume_lift_ratio = r * responder_volume_lift_ratio
    volume_multiplier = 1.0 + overall_volume_lift_ratio

    # Revenue modeling: non-responders pay full price, responders buy more at discounted price
    non_responder_revenue = baseline_revenue * (1.0 - r)
    responder_gross_sales_before_discount = baseline_revenue * r * (1.0 + responder_volume_lift_ratio)
    promo_discount_cost = responder_gross_sales_before_discount * d
    responder_net_revenue = responder_gross_sales_before_discount * (1.0 - d)

    simulated_revenue = non_responder_revenue + responder_net_revenue
    revenue_lift = simulated_revenue - baseline_revenue
    revenue_lift_pct = (revenue_lift / baseline_revenue * 100.0) if baseline_revenue > 0 else 0.0

    # COGS scales proportionally with unit volume
    simulated_cogs = baseline_cogs * volume_multiplier

    # Direct promotional marketing overhead
    direct_marketing_cost = fixed_marketing_cost + (customer_count * cost_per_customer)
    total_campaign_investment = direct_marketing_cost + promo_discount_cost

    simulated_net_profit = simulated_revenue - simulated_cogs - direct_marketing_cost
    net_profit_lift = simulated_net_profit - baseline_gross_profit
    net_profit_lift_pct = (
        (net_profit_lift / baseline_gross_profit * 100.0) if baseline_gross_profit > 0 else 0.0
    )

    # Return on investment (ROI)
    if total_campaign_investment > 0:
        roi_pct = (net_profit_lift / total_campaign_investment) * 100.0
    else:
        roi_pct = 0.0

    # Break-even volume calculation
    new_unit_margin = 1.0 - d - c
    if new_unit_margin <= 0:
        breakeven_volume_lift_pct = None
        is_margin_negative = True
    else:
        is_margin_negative = False
        required_extra_gross_sales = (
            (baseline_revenue * r * d) + direct_marketing_cost
        ) / new_unit_margin
        breakeven_volume_lift_pct = (
            (required_extra_gross_sales / baseline_revenue) * 100.0
            if baseline_revenue > 0
            else 0.0
        )

    # Decision evaluation logic
    expected_vol_lift_pct = overall_volume_lift_ratio * 100.0
    if is_margin_negative:
        status = "REJECT_CRITICAL"
        badge = "Reject: Negative Unit Margin"
        recommendation = (
            f"The discount ({discount_pct:.1f}%) exceeds baseline gross margin "
            f"({margin_0 * 100:.1f}%), resulting in negative unit margins. "
            f"Cap discount below {(margin_0 * 100 - 5):.1f}%."
        )
    elif net_profit_lift > 0 and roi_pct >= 15.0:
        status = "APPROVE_STRONG"
        badge = "Approve: High Economic Return"
        recommendation = (
            f"Favorable scenario: volume lift (+{expected_vol_lift_pct:.1f}%) exceeds "
            f"break-even hurdle (+{breakeven_volume_lift_pct:.1f}%). "
            f"Expected profit lift is +GBP {net_profit_lift:,.2f} with ROI of {roi_pct:.1f}%."
        )
    elif net_profit_lift > 0:
        status = "APPROVE_CAUTION"
        badge = "Caution: Modest Margin"
        recommendation = (
            f"Campaign is profitable (+GBP {net_profit_lift:,.2f}), but ROI ({roi_pct:.1f}%) is low. "
            f"Volume lift (+{expected_vol_lift_pct:.1f}%) is close to break-even (+{breakeven_volume_lift_pct:.1f}%). "
            f"Consider reducing marketing overhead."
        )
    else:
        status = "REJECT_UNPROFITABLE"
        badge = "Not Recommended: Unprofitable"
        recommendation = (
            f"Net profit drops by GBP {abs(net_profit_lift):,.2f} because volume lift (+{expected_vol_lift_pct:.1f}%) "
            f"does not cover the break-even hurdle (+{breakeven_volume_lift_pct:.1f}%). "
            f"Lower the discount or target segments with higher elasticity."
        )

    return {
        "baseline_revenue": round(float(baseline_revenue), 2),
        "baseline_cogs": round(float(baseline_cogs), 2),
        "baseline_gross_profit": round(float(baseline_gross_profit), 2),
        "simulated_revenue": round(float(simulated_revenue), 2),
        "simulated_cogs": round(float(simulated_cogs), 2),
        "direct_marketing_cost": round(float(direct_marketing_cost), 2),
        "promo_discount_cost": round(float(promo_discount_cost), 2),
        "total_campaign_investment": round(float(total_campaign_investment), 2),
        "simulated_net_profit": round(float(simulated_net_profit), 2),
        "revenue_lift": round(float(revenue_lift), 2),
        "revenue_lift_pct": round(float(revenue_lift_pct), 2),
        "expected_volume_lift_pct": round(float(expected_vol_lift_pct), 2),
        "breakeven_volume_lift_pct": (
            round(float(breakeven_volume_lift_pct), 2) if not is_margin_negative else None
        ),
        "net_profit_lift": round(float(net_profit_lift), 2),
        "net_profit_lift_pct": round(float(net_profit_lift_pct), 2),
        "roi_pct": round(float(roi_pct), 2),
        "is_margin_negative": is_margin_negative,
        "decision_status": status,
        "decision_badge": badge,
        "decision_recommendation": recommendation,
    }


def generate_sensitivity_matrix(
    baseline_revenue: float,
    customer_count: int,
    response_rate_pct: float = 70.0,
    cogs_pct: float = 60.0,
    fixed_marketing_cost: float = 1000.0,
    cost_per_customer: float = 0.50,
    discount_list: list[float] | None = None,
    elasticity_list: list[float] | None = None,
) -> pd.DataFrame:
    """Generate a 2D sensitivity matrix of net profit lift across discounts and price elasticities."""
    if discount_list is None:
        discount_list = [5.0, 8.0, 10.0, 12.0, 15.0, 20.0, 25.0, 30.0]
    if elasticity_list is None:
        elasticity_list = [0.8, 1.2, 1.5, 1.8, 2.2, 2.6, 3.0]

    matrix_data = {}
    for d_pct in discount_list:
        col_label = f"Discount {int(d_pct)}%"
        col_values = []
        for elas in elasticity_list:
            sim = simulate_promotion_scenario(
                baseline_revenue=baseline_revenue,
                customer_count=customer_count,
                discount_pct=d_pct,
                price_elasticity=elas,
                response_rate_pct=response_rate_pct,
                cogs_pct=cogs_pct,
                fixed_marketing_cost=fixed_marketing_cost,
                cost_per_customer=cost_per_customer,
            )
            col_values.append(sim["net_profit_lift"])
        matrix_data[col_label] = col_values

    index_labels = [f"Elasticity = {e:.1f}" for e in elasticity_list]
    return pd.DataFrame(matrix_data, index=index_labels)


def compare_all_segments_what_if(
    segment_summary_df: pd.DataFrame,
    discount_pct: float = 10.0,
    cogs_pct: float = 60.0,
    fixed_marketing_cost: float = 500.0,
    cost_per_customer: float = 0.50,
) -> pd.DataFrame:
    """Run promotion simulations across all segments, sorted descending by net profit lift."""
    rows = []
    for _, row in segment_summary_df.iterrows():
        seg_name = str(row["segment_name"])
        priors = get_segment_prior(seg_name)
        sim = simulate_promotion_scenario(
            baseline_revenue=float(row["total_revenue"]),
            customer_count=int(row["customer_count"]),
            discount_pct=discount_pct,
            price_elasticity=priors["price_elasticity"],
            response_rate_pct=priors["response_rate_pct"],
            cogs_pct=cogs_pct,
            fixed_marketing_cost=fixed_marketing_cost,
            cost_per_customer=cost_per_customer,
        )
        rows.append(
            {
                "segment_name": seg_name,
                "customer_count": int(row["customer_count"]),
                "assumed_elasticity": priors["price_elasticity"],
                "assumed_response_pct": priors["response_rate_pct"],
                "baseline_revenue": sim["baseline_revenue"],
                "simulated_revenue": sim["simulated_revenue"],
                "expected_volume_lift_pct": sim["expected_volume_lift_pct"],
                "breakeven_volume_lift_pct": sim["breakeven_volume_lift_pct"],
                "baseline_gross_profit": sim["baseline_gross_profit"],
                "simulated_net_profit": sim["simulated_net_profit"],
                "net_profit_lift": sim["net_profit_lift"],
                "roi_pct": sim["roi_pct"],
                "decision_badge": sim["decision_badge"],
            }
        )

    return pd.DataFrame(rows).sort_values("net_profit_lift", ascending=False).reset_index(drop=True)


if __name__ == "__main__":
    print("--- Testing Promotion Simulator ---")
    sample_res = simulate_promotion_scenario(
        baseline_revenue=1_500_000.0,
        customer_count=1200,
        discount_pct=12.0,
        price_elasticity=2.1,
        response_rate_pct=70.0,
        cogs_pct=60.0,
        fixed_marketing_cost=1000.0,
        cost_per_customer=0.50,
    )

    print(f"Decision: {sample_res['decision_badge']}")
    print(f"Recommendation: {sample_res['decision_recommendation']}")
    print(f"- Baseline Revenue: GBP {sample_res['baseline_revenue']:,.2f}")
    print(f"- Simulated Revenue: GBP {sample_res['simulated_revenue']:,.2f} ({sample_res['revenue_lift_pct']:+.1f}%)")
    print(f"- Volume Lift: +{sample_res['expected_volume_lift_pct']:.1f}%")
    print(f"- Break-Even Volume: +{sample_res['breakeven_volume_lift_pct']:.1f}%")
    print(f"- Baseline Gross Profit: GBP {sample_res['baseline_gross_profit']:,.2f}")
    print(f"- Simulated Net Profit: GBP {sample_res['simulated_net_profit']:,.2f}")
    print(f"- Profit Lift: GBP {sample_res['net_profit_lift']:+,.2f} ({sample_res['net_profit_lift_pct']:+.1f}%)")
    print(f"- ROI: {sample_res['roi_pct']:+.1f}%")

    print("\nSensitivity Matrix (Profit Lift):")
    sens_mat = generate_sensitivity_matrix(
        baseline_revenue=1_500_000.0,
        customer_count=1200,
        response_rate_pct=70.0,
        cogs_pct=60.0,
    )
    print(sens_mat.to_string())
    print("\nDone.")
