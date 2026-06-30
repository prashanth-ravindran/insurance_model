from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from insurance_model.actuarial import build_reserving_analysis, train_actuarial_models
from insurance_model.capital import FULL_MODULE_CORRELATIONS, FULL_RISK_MODULES, calculate_full_scr
from insurance_model.config import (
    COUNTERPARTY_RATING_FACTORS,
    DATA_NOTICE,
    DECISION_THRESHOLDS,
    DEFAULT_MODULE_CORRELATIONS,
    LOB_CONFIG,
    LOBS,
    REGION_RISK,
)
from insurance_model.explainability import explain_policy_prediction, feature_importance_table
from insurance_model.model import train_ml_models
from insurance_model.pricing import price_policy
from insurance_model.rbc import aggregate_portfolio_scr, calculate_policy_scr
from insurance_model.scenarios import scenario_comparison
from insurance_model.simulation import SCENARIOS, generate_simulation_bundle, metadata_coverage
from insurance_model.underwriting import business_rule_descriptions

st.set_page_config(
    page_title="Saudi P&C Risk Model",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
    [data-testid="stMetricValue"] {font-size: 1.45rem;}
    .decision-badge {
        display: inline-flex;
        align-items: center;
        border-radius: 6px;
        padding: 0.35rem 0.65rem;
        font-weight: 700;
        letter-spacing: 0;
        color: white;
    }
    .decision-quote {background: #146c43;}
    .decision-refer {background: #9a6700;}
    .decision-decline {background: #b42318;}
    .small-note {font-size: 0.82rem; color: #5b6472;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def cached_simulation_bundle(rows: int, seed: int, scenario_name: str) -> dict[str, pd.DataFrame]:
    return generate_simulation_bundle(rows=rows, seed=seed, scenario_name=scenario_name)


@st.cache_resource(show_spinner=False)
def cached_model_bundle(rows: int, seed: int, scenario_name: str) -> dict:
    bundle = generate_simulation_bundle(rows=rows, seed=seed, scenario_name=scenario_name)
    return train_ml_models(bundle["policies"], artifact_dir=None, random_state=seed)


@st.cache_resource(show_spinner=False)
def cached_actuarial_bundle(rows: int, seed: int, scenario_name: str) -> dict:
    bundle = generate_simulation_bundle(rows=rows, seed=seed, scenario_name=scenario_name)
    return train_actuarial_models(bundle)


@st.cache_data(show_spinner=False)
def cached_reserving(rows: int, seed: int, scenario_name: str) -> dict:
    bundle = generate_simulation_bundle(rows=rows, seed=seed, scenario_name=scenario_name)
    return build_reserving_analysis(bundle)


@st.cache_data(show_spinner=False)
def cached_full_capital(rows: int, seed: int, scenario_name: str) -> dict:
    bundle = generate_simulation_bundle(rows=rows, seed=seed, scenario_name=scenario_name)
    reserving = build_reserving_analysis(bundle)
    return calculate_full_scr(bundle, reserving)


@st.cache_data(show_spinner=False)
def cached_scenario_comparison(rows: int, seed: int) -> pd.DataFrame:
    return scenario_comparison(rows=rows, seed=seed)


def sar(value: float | None) -> str:
    if value is None:
        return "Not offered"
    abs_value = abs(float(value))
    if abs_value >= 1_000_000_000:
        return f"SAR {float(value) / 1_000_000_000:,.2f}B"
    if abs_value >= 1_000_000:
        return f"SAR {float(value) / 1_000_000:,.2f}M"
    if abs_value >= 1_000:
        return f"SAR {float(value) / 1_000:,.1f}K"
    return f"SAR {float(value):,.0f}"


def decision_badge(decision: str) -> None:
    css_class = {
        "quote": "decision-quote",
        "refer": "decision-refer",
        "decline": "decision-decline",
    }[decision]
    label = "REQUIRES REVIEW" if decision == "refer" else decision.upper()
    st.markdown(f'<span class="decision-badge {css_class}">{label}</span>', unsafe_allow_html=True)


def default_exposure(lob: str) -> float:
    return {
        "Motor": 120_000.0,
        "Property & Fire": 120_000_000.0,
        "Engineering & Construction": 900_000_000.0,
        "Marine & Cargo": 25_000_000.0,
        "Casualty/Liability": 90_000_000.0,
    }[lob]


def default_limit(lob: str) -> float:
    return {
        "Motor": 1_000_000.0,
        "Property & Fire": 90_000_000.0,
        "Engineering & Construction": 650_000_000.0,
        "Marine & Cargo": 20_000_000.0,
        "Casualty/Liability": 25_000_000.0,
    }[lob]


def default_deductible(lob: str) -> float:
    return {
        "Motor": 1_500.0,
        "Property & Fire": 150_000.0,
        "Engineering & Construction": 1_500_000.0,
        "Marine & Cargo": 50_000.0,
        "Casualty/Liability": 75_000.0,
    }[lob]


def build_policy_controls() -> dict:
    top_left, top_mid, top_right = st.columns([1.1, 1, 1])
    with top_left:
        lob = st.selectbox("Line of business", LOBS, index=0)
    with top_mid:
        region = st.selectbox("Region", list(REGION_RISK), index=0)
    with top_right:
        rating = st.selectbox("Reinsurer rating", list(COUNTERPARTY_RATING_FACTORS), index=2)

    cfg = LOB_CONFIG[lob]
    region_cfg = REGION_RISK[region]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        exposure = st.number_input("Exposure value", min_value=10_000.0, value=default_exposure(lob), step=10_000.0, format="%.0f")
    with c2:
        limit = st.number_input("Coverage limit", min_value=100_000.0, value=default_limit(lob), step=100_000.0, format="%.0f")
    with c3:
        deductible = st.number_input("Deductible", min_value=0.0, value=default_deductible(lob), step=1_000.0, format="%.0f")
    with c4:
        term = st.selectbox("Term", [6, 12, 18, 24], index=1, format_func=lambda x: f"{x} months")

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        prior_claims = st.number_input("Prior claims, 3Y", min_value=0, max_value=10, value=0, step=1)
    with c6:
        controls = st.slider("Risk controls", min_value=0, max_value=100, value=70, step=1)
    with c7:
        ceded = st.slider("Reinsurance ceded", min_value=0, max_value=95, value=25, step=1) / 100
    with c8:
        accumulation = st.slider("Event accumulation", min_value=0, max_value=100, value=25, step=1) / 100

    policy = {
        "lob": lob,
        "region": region,
        "counterparty_rating": rating,
        "exposure_value_sar": exposure,
        "limit_sar": limit,
        "deductible_sar": deductible,
        "term_months": term,
        "prior_claims_3y": prior_claims,
        "risk_control_score": controls,
        "reinsurance_ceded_pct": ceded,
        "event_accumulation_score": accumulation,
        "traffic_density_score": region_cfg["traffic_density_score"],
        "flood_zone_score": region_cfg["flood_zone_score"],
        "sandstorm_score": region_cfg["sandstorm_score"],
        "industrial_zone_score": region_cfg["industrial_zone_score"],
        "base_rate": cfg["base_rate"],
    }

    st.divider()
    if lob == "Motor":
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            policy["policy_type"] = st.selectbox("Policy type", ["Comprehensive", "Compulsory"])
        with m2:
            policy["vehicle_class"] = st.selectbox("Vehicle class", ["Private car", "SUV", "Taxi/ride-hailing", "Light commercial", "Heavy truck"])
        with m3:
            policy["driver_age"] = st.number_input("Driver age", min_value=18, max_value=90, value=35)
        with m4:
            policy["vehicle_age"] = st.number_input("Vehicle age", min_value=0, max_value=30, value=4)
        with m5:
            policy["fleet_size"] = st.number_input("Fleet size", min_value=1, max_value=500, value=1)

    elif lob == "Property & Fire":
        hazard_map = {"Residential": 0.25, "Retail": 0.38, "Warehouse": 0.52, "Manufacturing": 0.70, "Petrochemical support": 0.86}
        p1, p2, p3, p4 = st.columns(4)
        with p1:
            occupancy = st.selectbox("Occupancy", list(hazard_map), index=2)
        with p2:
            fire = st.slider("Fire protection", 0, 100, 72) / 100
        with p3:
            construction = st.slider("Construction quality", 0, 100, 70) / 100
        with p4:
            hazard = st.slider("Hazard score", 0, 100, int(hazard_map[occupancy] * 100)) / 100
        policy.update({"policy_type": "Commercial property", "occupancy_type": occupancy, "occupancy_hazard_score": hazard, "fire_protection_score": fire, "construction_quality_score": construction})

    elif lob == "Engineering & Construction":
        project_map = {"Civil works": 0.36, "Power/renewables": 0.48, "Metro/rail": 0.62, "Industrial plant": 0.76, "Giga-project package": 0.84}
        e1, e2, e3, e4 = st.columns(4)
        with e1:
            project = st.selectbox("Project type", list(project_map), index=4)
        with e2:
            duration = st.selectbox("Duration", [12, 18, 24, 36, 48, 60], index=3, format_func=lambda x: f"{x} months")
        with e3:
            experience = st.number_input("Contractor experience", min_value=1, max_value=40, value=10)
        with e4:
            complexity = st.slider("Complexity score", 0, 100, int(project_map[project] * 100)) / 100
        policy.update({"policy_type": "CAR/EAR", "project_type": project, "project_complexity_score": complexity, "project_duration_months": duration, "contractor_experience_years": experience})

    elif lob == "Marine & Cargo":
        cargo_map = {"General cargo": 0.30, "Electronics": 0.48, "Pharma/cold chain": 0.58, "Project cargo": 0.66, "Hazardous cargo": 0.82}
        g1, g2, g3, g4 = st.columns(4)
        with g1:
            cargo = st.selectbox("Cargo type", list(cargo_map), index=0)
        with g2:
            distance = st.number_input("Transit distance", min_value=25, max_value=6000, value=800)
        with g3:
            storage = st.number_input("Storage days", min_value=0, max_value=90, value=4)
        with g4:
            cargo_risk = st.slider("Cargo risk", 0, 100, int(cargo_map[cargo] * 100)) / 100
        policy.update({"policy_type": "Single transit/open cover", "cargo_type": cargo, "cargo_type_risk_score": cargo_risk, "transit_distance_km": distance, "storage_days": storage})

    else:
        liability_map = {"General liability": 0.34, "Professional indemnity": 0.62, "D&O": 0.72, "Product liability": 0.56}
        l1, l2, l3, l4 = st.columns(4)
        with l1:
            liability = st.selectbox("Liability type", list(liability_map), index=0)
        with l2:
            revenue = st.number_input("Annual revenue", min_value=1_000_000.0, value=90_000_000.0, step=1_000_000.0, format="%.0f")
        with l3:
            limit_factor = st.slider("Limit intensity", 0, 100, 45) / 100
        with l4:
            professional = st.slider("Professional risk", 0, 100, int(liability_map[liability] * 100)) / 100
        policy.update({"policy_type": "Liability", "liability_type": liability, "annual_revenue_sar": revenue, "liability_limit_factor": limit_factor, "professional_risk_score": professional})

    return policy


def premium_breakdown_chart(result: dict) -> go.Figure:
    labels = ["Expected loss", "Cat load", "Capital load", "Expense load", "Profit margin"]
    values = [result["expected_loss_sar"], result["cat_load_sar"], result["capital_load_sar"], result["expense_load_sar"], result["profit_margin_sar"]]
    fig = go.Figure(data=[go.Bar(x=labels, y=values, marker_color=["#2f6f8f", "#b95f24", "#7557a6", "#607d3b", "#8a4a5f"])])
    fig.update_layout(height=310, margin=dict(l=10, r=10, t=20, b=10), yaxis_title="SAR", xaxis_title=None, showlegend=False)
    return fig


def policy_rbc_module_chart(scr: dict) -> go.Figure:
    modules = scr["module_capitals"]
    fig = go.Figure(data=[go.Bar(x=["Underwriting", "Catastrophe", "Market & Credit"], y=[modules["underwriting"], modules["catastrophe"], modules["market_credit"]], marker_color=["#2f6f8f", "#b95f24", "#607d3b"])])
    fig.update_layout(height=310, margin=dict(l=10, r=10, t=20, b=10), yaxis_title="SAR", xaxis_title=None, showlegend=False)
    return fig


def build_portfolio_capital(df: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    sample = df.sample(min(len(df), 900), random_state=19)
    lob_rows = []
    portfolio_scrs = []
    for lob, group in sample.groupby("lob"):
        scrs = [calculate_policy_scr(row.to_dict(), row["technical_premium_sar"], row["expected_loss_sar"]) for _, row in group.iterrows()]
        group_agg = aggregate_portfolio_scr(scrs)
        portfolio_scrs.extend(scrs)
        lob_rows.append({"LOB": lob, "Sample policies": len(group), "Standalone capital": group_agg["standalone_sum_sar"], "Diversified SCR": group_agg["diversified_scr_sar"], "Diversification benefit": group_agg["diversification_benefit_sar"]})
    return aggregate_portfolio_scr(portfolio_scrs), pd.DataFrame(lob_rows)


with st.sidebar:
    st.header("Model Run")
    rows = st.slider("Data rows", min_value=1000, max_value=20000, value=5000, step=1000)
    seed = st.number_input("Random seed", min_value=1, max_value=9999, value=42, step=1)
    scenario_name = st.selectbox("Scenario", list(SCENARIOS), index=0)
    st.caption(str(SCENARIOS[scenario_name]["description"]))
    st.caption(DATA_NOTICE)

with st.spinner("Preparing data feeds and training models"):
    bundle = cached_simulation_bundle(rows, int(seed), scenario_name)
    portfolio_df = bundle["policies"]
    model_bundle = cached_model_bundle(rows, int(seed), scenario_name)
    actuarial_bundle = cached_actuarial_bundle(rows, int(seed), scenario_name)
    reserving_result = cached_reserving(rows, int(seed), scenario_name)
    full_capital = cached_full_capital(rows, int(seed), scenario_name)

st.title("Saudi P&C Portfolio Risk Model")
st.caption("Pricing, underwriting, reserving, and proxy RBC analytics for Saudi Arabia P&C portfolios ahead of Jan 1, 2027.")

quote_tab, data_tab, actuarial_tab, diagnostics_tab, reserving_tab, capital_tab, scenarios_tab, rules_tab, config_tab = st.tabs(
    ["Underwriting", "Data", "Actuarial", "Model Diagnostics", "Reserving", "Capital", "Scenarios", "Rules", "Proxy Factors"]
)

with quote_tab:
    policy = build_policy_controls()
    result = price_policy(policy, model_bundle=model_bundle, actuarial_bundle=actuarial_bundle)

    st.divider()
    a, b, c, d, e = st.columns([0.9, 1.05, 1, 1, 1])
    with a:
        decision_badge(result["decision"])
    with b:
        st.metric("Offered premium", sar(result["recommended_premium_sar"]))
    with c:
        st.metric("Risk score", f"{result['risk_score']:.1f}/100")
    with d:
        st.metric("Expected loss", sar(result["expected_loss_sar"]))
    with e:
        st.metric("SCR impact", sar(result["scr_impact_sar"]))

    left, right = st.columns([1.05, 0.95])
    with left:
        st.subheader("Premium")
        st.plotly_chart(premium_breakdown_chart(result), width="stretch")
        breakdown = pd.DataFrame(
            [
                ("Expected loss", result["expected_loss_sar"]),
                ("Cat load", result["cat_load_sar"]),
                ("Capital load", result["capital_load_sar"]),
                ("Expense load", result["expense_load_sar"]),
                ("Profit margin", result["profit_margin_sar"]),
                ("Technical premium", result["technical_premium_sar"]),
            ],
            columns=["Component", "Amount SAR"],
        )
        st.dataframe(breakdown, width="stretch", hide_index=True, column_config={"Amount SAR": st.column_config.NumberColumn(format="SAR %.0f")})

        st.subheader("Pricing reconciliation")
        st.dataframe(
            pd.DataFrame(result["pricing_reconciliation"]),
            width="stretch",
            hide_index=True,
            column_config={
                "expected_loss_sar": st.column_config.NumberColumn(format="SAR %.0f"),
                "difference_from_selected_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            },
        )
    with right:
        st.subheader("Capital")
        st.plotly_chart(policy_rbc_module_chart(result["rbc"]), width="stretch")
        st.metric("Diversification benefit", sar(result["rbc"]["diversification_benefit_sar"]))
        explanation = result["decision_explanation"]
        st.markdown("**Decision reasons**")
        for reason in result["decision_reasons"]:
            st.write(f"- {reason}")

        st.markdown("**Detailed explanation**")
        st.caption(explanation["summary"])
        for driver in explanation["drivers"]:
            st.write(f"- {driver}")

        st.markdown("**What can make it acceptable**")
        for action in explanation["recommended_actions"]:
            st.write(f"- {action}")

        with st.expander("Rule checks", expanded=True):
            st.dataframe(pd.DataFrame(explanation["rule_evaluations"]), width="stretch", hide_index=True)

        st.markdown(f'<p class="small-note">{result["model_basis"]} {result["rbc"]["proxy_basis"]}</p>', unsafe_allow_html=True)

with data_tab:
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Policies", f"{len(portfolio_df):,}")
    d2.metric("Claim rate", f"{portfolio_df['had_claim'].mean() * 100:.1f}%")
    d3.metric("Mean technical premium", sar(portfolio_df["technical_premium_sar"].mean()))
    d4.metric("Mean expected loss", sar(portfolio_df["expected_loss_sar"].mean()))

    table_names = list(bundle)
    selected_table = st.selectbox("Data feed", table_names, index=table_names.index("policies"))
    st.dataframe(metadata_coverage(bundle), width="stretch", hide_index=True)

    chart_left, chart_right = st.columns(2)
    with chart_left:
        lob_counts = portfolio_df["lob"].value_counts().rename_axis("LOB").reset_index(name="Policies")
        fig = px.bar(lob_counts, x="LOB", y="Policies", color="LOB", height=330)
        fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, width="stretch")
    with chart_right:
        fig = px.histogram(portfolio_df, x="loss_ratio", color="lob", nbins=45, height=330, labels={"loss_ratio": "Observed loss ratio"})
        fig.update_layout(margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, width="stretch")

    st.subheader(f"{selected_table.replace('_', ' ').title()} feed")
    st.dataframe(bundle[selected_table].head(250), width="stretch", hide_index=True)

with actuarial_tab:
    st.subheader("GLM baseline")
    st.dataframe(actuarial_bundle["diagnostics"], width="stretch", hide_index=True)
    indications = actuarial_bundle["indications"]
    indication_summary = indications.groupby("lob", as_index=False).agg(
        policies=("policy_id", "count"),
        avg_frequency=("glm_claim_frequency", "mean"),
        avg_severity_sar=("glm_claim_severity_sar", "mean"),
        avg_expected_loss_sar=("glm_expected_loss_sar", "mean"),
        avg_premium_sar=("glm_technical_premium_sar", "mean"),
    )
    st.dataframe(
        indication_summary,
        width="stretch",
        hide_index=True,
        column_config={
            "avg_frequency": st.column_config.NumberColumn(format="%.3f"),
            "avg_severity_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            "avg_expected_loss_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            "avg_premium_sar": st.column_config.NumberColumn(format="SAR %.0f"),
        },
    )
    fig = px.scatter(indications.sample(min(len(indications), 1000), random_state=9), x="glm_expected_loss_sar", y="glm_technical_premium_sar", color="lob", height=380)
    fig.update_layout(margin=dict(l=10, r=10, t=20, b=10), xaxis_title="GLM expected loss SAR", yaxis_title="GLM technical premium SAR")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(indications.head(200), width="stretch", hide_index=True)

with diagnostics_tab:
    diagnostics = pd.DataFrame([model_bundle["diagnostics"]]).T.reset_index()
    diagnostics.columns = ["Metric", "Value"]
    diagnostics["Value"] = diagnostics["Value"].astype(str)
    st.subheader("Predictive ML diagnostics")
    st.dataframe(diagnostics, width="stretch", hide_index=True)

    f1, f2 = st.columns(2)
    with f1:
        st.markdown("**Frequency model importance**")
        freq_importance = feature_importance_table(model_bundle, "frequency", 15)
        st.dataframe(freq_importance, width="stretch", hide_index=True)
    with f2:
        st.markdown("**Severity model importance**")
        loss_importance = feature_importance_table(model_bundle, "loss", 15)
        st.dataframe(loss_importance, width="stretch", hide_index=True)

    st.subheader("SHAP explanation for current quote")
    shap_result = explain_policy_prediction(policy, model_bundle, portfolio_df, max_features=10)
    st.caption(shap_result["method"] if shap_result["error"] is None else f"{shap_result['method']}: {shap_result['error']}")
    shap_df = shap_result["top_features"]
    st.dataframe(shap_df, width="stretch", hide_index=True)
    if "contribution" in shap_df:
        fig = px.bar(shap_df.sort_values("absolute_contribution"), x="contribution", y="feature", orientation="h", height=360)
        fig.update_layout(margin=dict(l=10, r=10, t=20, b=10), xaxis_title="SHAP contribution", yaxis_title=None)
        st.plotly_chart(fig, width="stretch")

with reserving_tab:
    st.subheader("Reserve summary")
    reserve_summary = reserving_result["reserve_summary"]
    st.dataframe(
        reserve_summary,
        width="stretch",
        hide_index=True,
        column_config={
            "paid_loss_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            "incurred_loss_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            "case_reserve_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            "chain_ladder_reserve_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            "bornhuetter_ferguson_reserve_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            "selected_reserve_sar": st.column_config.NumberColumn(format="SAR %.0f"),
        },
    )
    t1, t2, t3 = st.tabs(["Paid triangle", "Incurred triangle", "Link ratios"])
    with t1:
        st.dataframe(reserving_result["paid_triangle"], width="stretch", hide_index=True)
    with t2:
        st.dataframe(reserving_result["incurred_triangle"], width="stretch", hide_index=True)
    with t3:
        st.dataframe(reserving_result["link_ratios"], width="stretch", hide_index=True)

with capital_tab:
    c1, c2, c3 = st.columns(3)
    c1.metric("Standalone capital", sar(full_capital["standalone_sum_sar"]))
    c2.metric("Diversified SCR", sar(full_capital["diversified_scr_sar"]))
    c3.metric("Diversification benefit", sar(full_capital["diversification_benefit_sar"]))

    module_df = full_capital["module_table"].copy()
    module_df["module_label"] = module_df["module"].str.replace("_", " ").str.title()
    fig = px.bar(module_df, x="module_label", y="capital_sar", color="module_label", height=340)
    fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=20, b=10), xaxis_title=None, yaxis_title="SAR")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(module_df[["module_label", "capital_sar"]], width="stretch", hide_index=True, column_config={"capital_sar": st.column_config.NumberColumn(format="SAR %.0f")})

    detail_name = st.selectbox("Capital detail", list(full_capital["details"]), format_func=lambda x: x.replace("_", " ").title())
    st.dataframe(full_capital["details"][detail_name], width="stretch", hide_index=True)

    st.subheader("Expanded module correlations")
    st.dataframe(full_capital["correlation_matrix"], width="stretch")

    st.subheader("Legacy three-module policy sample")
    portfolio_scr, lob_capital = build_portfolio_capital(portfolio_df)
    st.dataframe(
        lob_capital,
        width="stretch",
        hide_index=True,
        column_config={
            "Standalone capital": st.column_config.NumberColumn(format="SAR %.0f"),
            "Diversified SCR": st.column_config.NumberColumn(format="SAR %.0f"),
            "Diversification benefit": st.column_config.NumberColumn(format="SAR %.0f"),
        },
    )
    st.caption(f"Legacy sample diversified SCR: {sar(portfolio_scr['diversified_scr_sar'])}")

with scenarios_tab:
    st.subheader("Scenario comparison")
    comparison = cached_scenario_comparison(rows, int(seed))
    base_scr = float(comparison.loc[comparison["scenario"] == "Base", "diversified_scr_sar"].iloc[0])
    comparison["change_vs_base_sar"] = comparison["diversified_scr_sar"] - base_scr
    comparison["change_vs_base_pct"] = comparison["change_vs_base_sar"] / max(base_scr, 1.0)
    fig = px.bar(comparison, x="scenario", y="diversified_scr_sar", color="scenario", height=360)
    fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=20, b=10), xaxis_title=None, yaxis_title="Diversified SCR SAR")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(
        comparison,
        width="stretch",
        hide_index=True,
        column_config={
            "standalone_sum_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            "diversified_scr_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            "diversification_benefit_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            "premium_risk_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            "reserve_risk_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            "catastrophe_risk_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            "reinsurance_credit_risk_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            "market_risk_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            "change_vs_base_sar": st.column_config.NumberColumn(format="SAR %.0f"),
            "change_vs_base_pct": st.column_config.NumberColumn(format="%.1%"),
        },
    )

with rules_tab:
    st.subheader("Business rules in natural language")
    st.dataframe(pd.DataFrame(business_rule_descriptions()), width="stretch", hide_index=True)

    st.subheader("Decision thresholds")
    thresholds_df = pd.DataFrame(
        [
            {"Threshold": "Straight-through quote maximum score", "Value": DECISION_THRESHOLDS["quote_max_score"], "Meaning": "Scores at or below this value can be quoted if no hard decline or review rule fires."},
            {"Threshold": "Automatic decline score", "Value": DECISION_THRESHOLDS["refer_max_score"], "Meaning": "Scores at or above this value are outside current proxy appetite."},
            {"Threshold": "SCR-to-premium review", "Value": DECISION_THRESHOLDS["refer_scr_to_premium"], "Meaning": "Capital strain above this ratio requires review."},
            {"Threshold": "Control score decline floor", "Value": DECISION_THRESHOLDS["decline_min_control_score"], "Meaning": "Very weak controls can trigger decline when combined with an extreme score."},
            {"Threshold": "Accumulation review", "Value": DECISION_THRESHOLDS["refer_accumulation_score"], "Meaning": "High event accumulation or clash-risk concentration requires review."},
            {"Threshold": "High cession review", "Value": DECISION_THRESHOLDS["refer_reinsurance_ceded_pct"], "Meaning": "Heavy dependence on reinsurance support requires reinsurance security review."},
        ]
    )
    st.dataframe(thresholds_df, width="stretch", hide_index=True)

    st.subheader("LOB appetite limits")
    appetite_df = pd.DataFrame(
        [
            {"LOB": lob, "Maximum gross limit": cfg["max_limit"], "Minimum premium": cfg["min_premium"], "Expense ratio": cfg["expense_ratio"], "Profit margin": cfg["profit_margin"], "Cost of capital": cfg["cost_of_capital"]}
            for lob, cfg in LOB_CONFIG.items()
        ]
    )
    st.dataframe(
        appetite_df,
        width="stretch",
        hide_index=True,
        column_config={
            "Maximum gross limit": st.column_config.NumberColumn(format="SAR %.0f"),
            "Minimum premium": st.column_config.NumberColumn(format="SAR %.0f"),
            "Expense ratio": st.column_config.NumberColumn(format="%.2f"),
            "Profit margin": st.column_config.NumberColumn(format="%.2f"),
            "Cost of capital": st.column_config.NumberColumn(format="%.3f"),
        },
    )
    st.caption(DATA_NOTICE)

with config_tab:
    st.subheader("LOB factors")
    lob_factor_df = pd.DataFrame.from_dict(LOB_CONFIG, orient="index").reset_index(names="LOB")
    st.dataframe(lob_factor_df, width="stretch", hide_index=True)

    st.subheader("Three-module policy correlations")
    corr_df = pd.DataFrame(DEFAULT_MODULE_CORRELATIONS).loc[["underwriting", "catastrophe", "market_credit"], ["underwriting", "catastrophe", "market_credit"]]
    st.dataframe(corr_df, width="stretch")

    st.subheader("Expanded SCR correlations")
    st.dataframe(pd.DataFrame(FULL_MODULE_CORRELATIONS).loc[FULL_RISK_MODULES, FULL_RISK_MODULES], width="stretch")

    st.subheader("Scenario assumptions")
    scenario_df = pd.DataFrame.from_dict(SCENARIOS, orient="index").reset_index(names="Scenario")
    st.dataframe(scenario_df, width="stretch", hide_index=True)

    st.subheader("Generated RBC factor feed")
    st.dataframe(bundle["rbc_factors"], width="stretch", hide_index=True)
    st.caption(DATA_NOTICE)
