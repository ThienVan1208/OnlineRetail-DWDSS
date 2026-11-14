"""DSS view components for the Online Retail analytical dashboard.
Implements Tab 3 (Customer segmentation via RFM & K-Means) and Tab 4 (What-If promotion simulation DSS)
matching Member 3's clean, native Streamlit styling.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from src.app.components.db_connector import get_db_engine
from src.dss.rfm_clustering import (
    evaluate_optimal_k,
    extract_rfm_from_db,
    preprocess_rfm,
    run_kmeans_clustering,
)
from src.dss.promotion_simulator import (
    compare_all_segments_what_if,
    generate_sensitivity_matrix,
    get_segment_prior,
    simulate_promotion_scenario,
)


@st.cache_data(ttl=600, show_spinner=False)
def cached_rfm_table(years: tuple, country: str | None):
    """Extract raw RFM customer records from warehouse and cache for 10 minutes."""
    engine = get_db_engine()
    countries = [country] if country and country != "All countries" else None
    return extract_rfm_from_db(
        engine,
        years=list(years) if years else None,
        countries=countries,
    )


@st.cache_data(ttl=600, show_spinner=False)
def cached_kmeans_model(years: tuple, country: str | None, n_clusters: int):
    """Run K-Means clustering and return clustered dataframe, segment summary profile, and metrics."""
    rfm_df = cached_rfm_table(years, country)
    if rfm_df.empty or len(rfm_df) < n_clusters:
        return pd.DataFrame(), pd.DataFrame(), {}
    return run_kmeans_clustering(rfm_df, n_clusters=n_clusters)


@st.cache_data(ttl=600, show_spinner=False)
def cached_k_diagnostics(years: tuple, country: str | None):
    """Compute Inertia (Elbow) and Silhouette scores across K=2..7 independently."""
    rfm_df = cached_rfm_table(years, country)
    if rfm_df.empty or len(rfm_df) < 3:
        return pd.DataFrame()
    scaled_matrix, _, _ = preprocess_rfm(rfm_df)
    return evaluate_optimal_k(scaled_matrix, k_min=2, k_max=7)


def render_segmentation_tab(years: tuple, country: str | None):
    """Tab 3: Customer segmentation via RFM and K-Means++ clustering."""
    st.subheader("Customer segmentation (RFM & K-Means)")

    col_k, _ = st.columns([1, 2])
    with col_k:
        n_clusters = st.slider(
            "Number of clusters (K):",
            min_value=2,
            max_value=6,
            value=4,
            step=1,
            help="Default K=4 segments customers into Champions (VIP), Loyal, Potential, and At Risk.",
        )

    with st.spinner("Extracting RFM data and training K-Means model..."):
        clustered_df, summary_df, metrics = cached_kmeans_model(years, country, n_clusters)

    if clustered_df.empty:
        st.warning("Insufficient customer transaction history to perform clustering for the selected filters.")
        return

    st.session_state["dss_segment_summary"] = summary_df
    st.session_state["dss_n_clusters"] = n_clusters

    # 1. Diagnostic metrics matching Member 3's native metric row
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Segmented customers", f"{metrics['total_customers']:,}")
    m2.metric("Segmented revenue", f"£{metrics['total_revenue']:,.2f}")
    m3.metric("Clusters (K)", f"{metrics['n_clusters']}")
    m4.metric("Silhouette score", f"{metrics['silhouette_score']:.4f}")

    st.divider()

    # 2. Segment summary profile table
    st.subheader("Customer segment profile & strategies")
    display_profile = summary_df[
        [
            "segment_name",
            "customer_count",
            "customer_share_pct",
            "avg_recency",
            "avg_frequency",
            "avg_monetary",
            "total_revenue",
            "revenue_share_pct",
            "recommended_strategy",
        ]
    ].rename(
        columns={
            "segment_name": "Segment",
            "customer_count": "Customers",
            "customer_share_pct": "% Customers",
            "avg_recency": "Avg Recency (Days)",
            "avg_frequency": "Avg Frequency (Orders)",
            "avg_monetary": "Avg Monetary (£)",
            "total_revenue": "Total Revenue (£)",
            "revenue_share_pct": "% Revenue",
            "recommended_strategy": "Recommended strategy",
        }
    )
    st.dataframe(display_profile, use_container_width=True, hide_index=True)

    # 3. Visualizations: Revenue Share Donut & Z-Score Radar
    c_left, c_right = st.columns(2)

    with c_left:
        st.subheader("Revenue distribution by segment")
        fig_donut = px.pie(
            summary_df,
            names="segment_name",
            values="total_revenue",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Bold,
        )
        fig_donut.update_traces(textposition="inside", textinfo="percent+label")
        fig_donut.update_layout(
            height=380,
            margin=dict(l=10, r=10, t=20, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with c_right:
        st.subheader("Standardized centroid profile (Z-Score)")
        fig_radar = go.Figure()
        categories = ["Recency (-Z)", "Frequency (+Z)", "Monetary (+Z)"]
        for _, seg_row in summary_df.iterrows():
            r_vals = [
                -float(seg_row["z_recency"]),
                float(seg_row["z_frequency"]),
                float(seg_row["z_monetary"]),
            ]
            r_vals.append(r_vals[0])
            fig_radar.add_trace(
                go.Scatterpolar(
                    r=r_vals,
                    theta=categories + [categories[0]],
                    fill="toself",
                    name=seg_row["segment_name"],
                )
            )
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True)),
            height=380,
            margin=dict(l=20, r=20, t=20, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    # 4. 3D Cluster Scatter Plot
    st.subheader("3D RFM feature space")
    use_log = st.checkbox("Display coordinates on log scale ln(x+1) to prevent outlier distortion", value=True)
    x_col = "log_recency" if use_log else "recency"
    y_col = "log_frequency" if use_log else "frequency"
    z_col = "log_monetary" if use_log else "monetary"

    fig_3d = px.scatter_3d(
        clustered_df,
        x=x_col,
        y=y_col,
        z=z_col,
        color="segment_name",
        hover_data=["customer_id", "country", "recency", "frequency", "monetary"],
        opacity=0.75,
        color_discrete_sequence=px.colors.qualitative.Bold,
        height=520,
    )
    fig_3d.update_traces(marker=dict(size=3.5))
    fig_3d.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_3d, use_container_width=True)

    # 5. Customer Segment Lookup and CSV Export
    st.subheader("Customer segment lookup & export")
    seg_filter = st.selectbox(
        "Filter customers by segment:",
        options=["All segments"] + summary_df["segment_name"].tolist(),
    )
    filtered_customers = (
        clustered_df
        if seg_filter == "All segments"
        else clustered_df[clustered_df["segment_name"] == seg_filter]
    )
    export_cols = [
        "customer_id",
        "country",
        "segment_name",
        "recency",
        "frequency",
        "monetary",
        "avg_order_value",
        "total_items",
        "last_purchase_date",
    ]
    st.dataframe(filtered_customers[export_cols].head(100), use_container_width=True, hide_index=True)

    csv_data = filtered_customers[export_cols].to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=f"Download customer segment CSV ({len(filtered_customers):,} customers)",
        data=csv_data,
        file_name="rfm_customer_segments.csv",
        mime="text/csv",
    )

    # 6. Separate Optimal K diagnostics in Expander (Fast on demand)
    with st.expander("Optimal K evaluation (Elbow & Silhouette diagnostics)"):
        k_eval_df = cached_k_diagnostics(years, country)
        if not k_eval_df.empty:
            fig_k = make_subplots(specs=[[{"secondary_y": True}]])
            fig_k.add_trace(
                go.Scatter(
                    x=k_eval_df["k"],
                    y=k_eval_df["inertia"],
                    name="Inertia / WCSS (Elbow)",
                    mode="lines+markers",
                    line=dict(color="#3B82F6", width=2.5),
                ),
                secondary_y=False,
            )
            fig_k.add_trace(
                go.Scatter(
                    x=k_eval_df["k"],
                    y=k_eval_df["silhouette_score"],
                    name="Silhouette score",
                    mode="lines+markers",
                    line=dict(color="#10B981", width=2.5, dash="dot"),
                ),
                secondary_y=True,
            )
            fig_k.update_layout(
                height=350,
                margin=dict(l=10, r=10, t=25, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            fig_k.update_xaxes(title_text="Number of clusters (K)")
            fig_k.update_yaxes(title_text="Inertia (WCSS)", secondary_y=False, showgrid=True, gridcolor="rgba(128,128,128,0.15)")
            fig_k.update_yaxes(title_text="Silhouette Score", secondary_y=True, showgrid=False)
            st.plotly_chart(fig_k, use_container_width=True)
            st.dataframe(k_eval_df, use_container_width=True, hide_index=True)


def render_what_if_tab(years: tuple, country: str | None):
    """Tab 4: What-If promotion simulation, break-even goal-seeking, and sensitivity analysis."""
    st.subheader("Promotional campaign simulation (What-If DSS)")

    n_clusters = st.session_state.get("dss_n_clusters", 4)
    _, summary_df, _ = cached_kmeans_model(years, country, n_clusters)

    if summary_df.empty:
        st.warning("Please compute customer segmentation in Tab 3 before running What-If simulations.")
        return

    # 1. Target segment selection
    segment_options = summary_df["segment_name"].tolist() + ["All Segments (Mass Campaign)"]
    selected_target = st.selectbox(
        "Select target customer segment for campaign:",
        options=segment_options,
        index=0,
    )

    if selected_target == "All Segments (Mass Campaign)":
        base_rev = float(summary_df["total_revenue"].sum())
        cust_cnt = int(summary_df["customer_count"].sum())
    else:
        seg_row = summary_df[summary_df["segment_name"] == selected_target].iloc[0]
        base_rev = float(seg_row["total_revenue"])
        cust_cnt = int(seg_row["customer_count"])

    priors = get_segment_prior(selected_target)

    st.divider()

    # 2. Parameters Form matching Member 3's clean layout
    st.subheader("Scenario parameters")
    with st.form(key=f"what_if_form_{selected_target}"):
        c_dec, c_mkt = st.columns(2)

        with c_dec:
            st.markdown("**Decision variables:**")
            input_discount = st.slider(
                "Discount rate (%):",
                min_value=1.0,
                max_value=35.0,
                value=float(priors["discount_pct"]),
                step=1.0,
            )
            input_fixed_cost = st.number_input(
                "Fixed marketing budget (£):",
                min_value=0.0,
                max_value=100000.0,
                value=1000.0,
                step=250.0,
            )
            input_cost_per_cust = st.number_input(
                "Cost per customer outreach (£):",
                min_value=0.0,
                max_value=50.0,
                value=0.50,
                step=0.10,
            )

        with c_mkt:
            st.markdown("**Market & cost assumptions:**")
            input_elasticity = st.slider(
                "Price elasticity of demand (ε):",
                min_value=0.5,
                max_value=3.5,
                value=float(priors["price_elasticity"]),
                step=0.1,
                help="ε = 1.8 implies a 10% discount stimulates an 18% demand lift among responders.",
            )
            input_response_rate = st.slider(
                "Campaign response rate (%):",
                min_value=10.0,
                max_value=100.0,
                value=float(priors["response_rate_pct"]),
                step=5.0,
            )
            input_cogs_pct = st.slider(
                "Cost of goods sold - COGS (%):",
                min_value=30.0,
                max_value=85.0,
                value=60.0,
                step=1.0,
                help="60% COGS represents a 40% baseline gross margin.",
            )

        submitted = st.form_submit_button("Run What-If simulation", type="primary", use_container_width=True)

    # Keep active parameters synchronized
    active_params = {
        "discount_pct": input_discount,
        "fixed_cost": input_fixed_cost,
        "cost_per_cust": input_cost_per_cust,
        "elasticity": input_elasticity,
        "response_rate": input_response_rate,
        "cogs_pct": input_cogs_pct,
    }

    sim = simulate_promotion_scenario(
        baseline_revenue=base_rev,
        customer_count=cust_cnt,
        discount_pct=active_params["discount_pct"],
        price_elasticity=active_params["elasticity"],
        response_rate_pct=active_params["response_rate"],
        cogs_pct=active_params["cogs_pct"],
        fixed_marketing_cost=active_params["fixed_cost"],
        cost_per_customer=active_params["cost_per_cust"],
    )

    st.divider()

    # 3. Projected Financial Results and Decision Status
    st.subheader("Projected results & managerial recommendation")

    # Managerial recommendation alert
    if sim["decision_status"] == "APPROVE_STRONG":
        st.success(f"**Recommendation: {sim['decision_badge']}**\n\n{sim['decision_recommendation']}")
    elif sim["decision_status"] == "APPROVE_CAUTION":
        st.warning(f"**Recommendation: {sim['decision_badge']}**\n\n{sim['decision_recommendation']}")
    else:
        st.error(f"**Recommendation: {sim['decision_badge']}**\n\n{sim['decision_recommendation']}")

    # 4 Financial Metric cards
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Projected revenue",
        f"£{sim['simulated_revenue']:,.2f}",
        delta=f"{sim['revenue_lift']:+,.2f} £ ({sim['revenue_lift_pct']:+.1f}%)",
    )
    be_str = (
        f"Break-even hurdle: +{sim['breakeven_volume_lift_pct']:.1f}%"
        if sim["breakeven_volume_lift_pct"] is not None
        else "Negative gross margin!"
    )
    k2.metric(
        "Expected volume lift",
        f"+{sim['expected_volume_lift_pct']:.1f}%",
        delta=be_str,
        delta_color="normal" if not sim["is_margin_negative"] else "inverse",
    )
    k3.metric(
        "Simulated net profit",
        f"£{sim['simulated_net_profit']:,.2f}",
        delta=f"{sim['net_profit_lift']:+,.2f} £ ({sim['net_profit_lift_pct']:+.1f}%)",
    )
    k4.metric(
        "Campaign ROI",
        f"{sim['roi_pct']:+.1f}%",
        delta=f"Total cost: £{sim['total_campaign_investment']:,.0f}",
        delta_color="off",
    )

    # 4. Comparative Bar Chart & 2D Sensitivity Matrix
    c_bar, c_heat = st.columns(2)

    with c_bar:
        st.subheader("Financial structure: Baseline vs Simulated")
        comp_df = pd.DataFrame(
            {
                "Financial Metric": ["Net Revenue", "COGS", "Net Profit"],
                "Baseline": [
                    sim["baseline_revenue"],
                    sim["baseline_cogs"],
                    sim["baseline_gross_profit"],
                ],
                "Simulated": [
                    sim["simulated_revenue"],
                    sim["simulated_cogs"],
                    sim["simulated_net_profit"],
                ],
            }
        )
        comp_melt = comp_df.melt(id_vars="Financial Metric", var_name="Scenario", value_name="Amount (£)")
        fig_comp = px.bar(
            comp_melt,
            x="Financial Metric",
            y="Amount (£)",
            color="Scenario",
            barmode="group",
            text_auto=".3s",
            color_discrete_map={"Baseline": "#64748B", "Simulated": "#3B82F6"},
        )
        fig_comp.update_layout(
            height=400,
            margin=dict(l=10, r=10, t=20, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_comp, use_container_width=True)

    with c_heat:
        st.subheader("2D Net profit sensitivity matrix (£)")
        sens_matrix = generate_sensitivity_matrix(
            baseline_revenue=base_rev,
            customer_count=cust_cnt,
            response_rate_pct=active_params["response_rate"],
            cogs_pct=active_params["cogs_pct"],
            fixed_marketing_cost=active_params["fixed_cost"],
            cost_per_customer=active_params["cost_per_cust"],
        )
        fig_sens = px.imshow(
            sens_matrix,
            text_auto=".2s",
            aspect="auto",
            color_continuous_scale="RdYlGn",
            color_continuous_midpoint=0,
        )
        fig_sens.update_layout(
            height=400,
            xaxis_title="Discount rate",
            yaxis_title="Price elasticity (ε)",
            margin=dict(l=10, r=10, t=20, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_sens, use_container_width=True)

    # 5. Cross-segment strategy comparison table (Single execution, no duplicates)
    st.subheader(f"Cross-segment strategy ranking ({active_params['discount_pct']:.0f}% discount)")
    multi_df = compare_all_segments_what_if(
        segment_summary_df=summary_df,
        discount_pct=active_params["discount_pct"],
        cogs_pct=active_params["cogs_pct"],
        fixed_marketing_cost=active_params["fixed_cost"],
        cost_per_customer=active_params["cost_per_cust"],
    )
    st.dataframe(
        multi_df.rename(
            columns={
                "segment_name": "Segment",
                "customer_count": "Customers",
                "assumed_elasticity": "Elasticity (ε)",
                "assumed_response_pct": "% Response",
                "baseline_revenue": "Baseline Revenue (£)",
                "simulated_revenue": "Simulated Revenue (£)",
                "expected_volume_lift_pct": "% Volume Lift",
                "breakeven_volume_lift_pct": "% Break-even Lift",
                "baseline_gross_profit": "Baseline Profit (£)",
                "simulated_net_profit": "Simulated Profit (£)",
                "net_profit_lift": "Profit Lift ΔΠ (£)",
                "roi_pct": "ROI (%)",
                "decision_badge": "Evaluation",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
