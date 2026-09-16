import math
from dataclasses import dataclass

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Portugal Real Estate Deal Evaluator",
    page_icon="🏛️",
    layout="wide",
)

st.markdown("""
<style>
    .block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1400px;}
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #18212a, #111820);
        border: 1px solid #344654;
        border-left: 4px solid #d6a85f;
        padding: 18px;
        border-radius: 12px;
        min-height: 124px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22);
    }
    [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {
        color: #aebbc6 !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricValue"], [data-testid="stMetricValue"] * {
        color: #f5f2e9 !important;
        font-weight: 750 !important;
    }
    [data-testid="stMetricDelta"] {font-weight: 650 !important;}
    .decision {padding: 18px 22px; border-radius: 12px; margin: 8px 0 20px 0; font-weight: 700; font-size: 1.15rem;}
    .pass {background: #e8f5ee; color: #176b42; border: 1px solid #b9e2ca;}
    .review {background: #fff4d9; color: #7a5700; border: 1px solid #efd48e;}
    .reject {background: #fdeaea; color: #9a2d2d; border: 1px solid #efbcbc;}
</style>
""", unsafe_allow_html=True)


def eur(value: float) -> str:
    return f"€{value:,.0f}"


def pct(value: float) -> str:
    return f"{value:.1%}"


def pmt(principal: float, annual_rate: float, years: int) -> float:
    months = max(int(years * 12), 1)
    rate = annual_rate / 12
    if principal <= 0:
        return 0.0
    if rate == 0:
        return principal / months
    return principal * rate * (1 + rate) ** months / ((1 + rate) ** months - 1)


def balance_after(principal: float, annual_rate: float, years: int, elapsed_months: int) -> float:
    payment = pmt(principal, annual_rate, years)
    rate = annual_rate / 12
    n = min(max(elapsed_months, 0), years * 12)
    if rate == 0:
        return max(0.0, principal - payment * n)
    return max(0.0, principal * (1 + rate) ** n - payment * (((1 + rate) ** n - 1) / rate))


def imt_mainland(base: float, category: str) -> float:
    """2026 mainland brackets reproduced from the source workbook."""
    if base <= 0:
        return 0.0
    if category == "Other urban":
        return base * 0.065
    if category == "Rustic":
        return base * 0.05
    if category == "Primary residence (HPP)":
        brackets = [
            (106_346, 0.00, 0.00), (145_470, 0.02, 2_126.92),
            (198_347, 0.05, 6_491.02), (330_539, 0.07, 10_457.96),
            (660_982, 0.08, 13_763.35), (1_150_853, 0.06, 0.00),
            (math.inf, 0.075, 0.00),
        ]
    else:
        brackets = [
            (106_346, 0.01, 0.00), (145_470, 0.02, 1_063.46),
            (198_347, 0.05, 5_427.56), (330_539, 0.07, 9_394.50),
            (633_931, 0.08, 12_699.89), (1_150_853, 0.06, 0.00),
            (math.inf, 0.075, 0.00),
        ]
    for limit, rate, deduction in brackets:
        if base <= limit:
            return max(0.0, base * rate - deduction)
    return 0.0


@dataclass
class Result:
    purchase_costs: float
    acquisition_cost: float
    acquisition_loan: float
    acquisition_equity: float
    monthly_payment: float
    acquisition_interest_to_exit: float
    acquisition_balance_exit: float
    renovation_budget: float
    renovation_loan: float
    renovation_equity: float
    renovation_finance_cost: float
    project_cost: float
    total_debt: float
    total_equity: float
    gross_exit: float
    selling_costs: float
    net_profit: float
    margin: float
    roi: float
    roe: float
    annualized_roe: float
    ltc: float
    break_even_sqm: float


def calculate(x: dict) -> Result:
    tax_base = x["imt_base"] or x["purchase_price"]
    imt = x["imt_override"] if x["imt_override"] > 0 else imt_mainland(tax_base, x["imt_category"])
    stamp = tax_base * 0.008
    purchase_costs = imt + stamp + x["legal_fees"] + x["bank_fees"] + x["brokerage"]
    acquisition_cost = x["purchase_price"] + purchase_costs
    acquisition_loan = x["purchase_price"] * x["acq_financing"]
    acquisition_equity = acquisition_cost - acquisition_loan
    monthly_payment = pmt(acquisition_loan, x["acq_rate"], x["loan_term"])
    acquisition_balance_exit = balance_after(acquisition_loan, x["acq_rate"], x["loan_term"], x["timeline"])
    acquisition_interest_to_exit = max(0.0, monthly_payment * min(x["timeline"], x["loan_term"] * 12) - (acquisition_loan - acquisition_balance_exit))

    reno_base = x["reno_area"] * x["reno_cost_sqm"]
    subtotal = reno_base * (1 + x["contingency"]) + x["architect"] + x["licensing"]
    renovation_budget = subtotal * (1 + x["vat_rate"])
    renovation_loan = renovation_budget * x["reno_financing"]
    renovation_equity = renovation_budget - renovation_loan
    if x["draw_type"] == "Phased":
        # Even monthly draws; interest accrues on the average outstanding draw.
        renovation_finance_cost = renovation_loan * x["reno_rate"] * ((x["reno_months"] + 1) / 24)
    else:
        renovation_finance_cost = renovation_loan * x["reno_rate"] * x["reno_months"] / 12

    project_cost = acquisition_cost + renovation_budget + acquisition_interest_to_exit + renovation_finance_cost
    total_debt = acquisition_loan + renovation_loan
    total_equity = acquisition_equity + renovation_equity + acquisition_interest_to_exit + renovation_finance_cost
    gross_exit = x["saleable_area"] * x["exit_price_sqm"]
    selling_costs = gross_exit * x["sales_costs"]
    net_profit = gross_exit - selling_costs - project_cost
    margin = net_profit / gross_exit if gross_exit else 0.0
    roi = net_profit / project_cost if project_cost else 0.0
    roe = net_profit / total_equity if total_equity else 0.0
    annualized_roe = (1 + roe) ** (12 / x["timeline"]) - 1 if x["timeline"] and roe > -1 else -1.0
    ltc = total_debt / project_cost if project_cost else 0.0
    break_even_sqm = project_cost / (x["saleable_area"] * (1 - x["sales_costs"])) if x["saleable_area"] and x["sales_costs"] < 1 else 0.0
    return Result(purchase_costs, acquisition_cost, acquisition_loan, acquisition_equity,
                  monthly_payment, acquisition_interest_to_exit, acquisition_balance_exit,
                  renovation_budget, renovation_loan, renovation_equity, renovation_finance_cost,
                  project_cost, total_debt, total_equity, gross_exit, selling_costs, net_profit,
                  margin, roi, roe, annualized_roe, ltc, break_even_sqm)


st.title("Portugal Real Estate Deal Evaluator")
st.caption("Acquisition · Renovation · Financing · Resale · Stress testing")

with st.sidebar:
    st.header("Deal identity")
    project_name = st.text_input("Project name", "Porto Opportunity")
    location = st.text_input("Location", "Porto")
    st.caption("Model values are estimates. Confirm taxes, financing and legal treatment with Portuguese professionals before committing capital.")

tabs = st.tabs(["Deal inputs", "Results", "Sensitivity & risk"])

with tabs[0]:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Purchase")
        purchase_price = st.number_input("Purchase price (€)", min_value=0.0, value=250_000.0, step=5_000.0)
        market_value = st.number_input("Current / market value (€)", min_value=0.0, value=300_000.0, step=5_000.0)
        imt_category = st.selectbox("IMT category", ["Secondary residence", "Primary residence (HPP)", "Other urban", "Rustic"])
        imt_base = st.number_input("IMT tax-base override (€)", min_value=0.0, value=0.0, help="Leave at zero to use the purchase price.")
        imt_override = st.number_input("IMT amount override (€)", min_value=0.0, value=0.0, help="Leave at zero for automatic calculation.")
        legal_fees = st.number_input("Legal + notary + registry (€)", min_value=0.0, value=2_000.0, step=250.0)
        bank_fees = st.number_input("Bank / valuation fees (€)", min_value=0.0, value=480.0, step=50.0)
        brokerage = st.number_input("Purchase brokerage / other fees (€)", min_value=0.0, value=0.0, step=250.0)
    with c2:
        st.subheader("Financing & renovation")
        acq_financing = st.slider("Purchase financing", 0, 100, 70, format="%d%%") / 100
        acq_rate = st.number_input("Acquisition interest rate (%)", min_value=0.0, value=4.0, step=0.1) / 100
        loan_term = st.number_input("Acquisition loan term (years)", min_value=1, value=30, step=1)
        reno_area = st.number_input("Renovation area (m²)", min_value=0.0, value=100.0, step=5.0)
        reno_cost_sqm = st.number_input("Renovation hard cost (€/m²)", min_value=0.0, value=900.0, step=50.0)
        contingency = st.number_input("Contingency (%)", min_value=0.0, value=10.0, step=1.0) / 100
        architect = st.number_input("Architecture / consultants (€)", min_value=0.0, value=7_500.0, step=500.0)
        licensing = st.number_input("Licensing (€)", min_value=0.0, value=2_500.0, step=500.0)
        vat_mode = st.selectbox("Renovation VAT", ["Standard – 23%", "ARU / qualifying works – 6%", "Manual"])
        vat_rate = {"Standard – 23%": 0.23, "ARU / qualifying works – 6%": 0.06}.get(vat_mode)
        if vat_rate is None:
            vat_rate = st.number_input("Manual VAT rate (%)", min_value=0.0, value=23.0, step=1.0) / 100
        reno_financing = st.slider("Renovation financing", 0, 100, 0, format="%d%%") / 100
        reno_rate = st.number_input("Renovation interest rate (%)", min_value=0.0, value=6.0, step=0.1) / 100
        reno_months = st.number_input("Renovation duration (months)", min_value=1, value=6, step=1)
        draw_type = st.selectbox("Renovation draw type", ["Phased", "One-time"])
    with c3:
        st.subheader("Exit & targets")
        saleable_area = st.number_input("Saleable area (m²)", min_value=0.0, value=100.0, step=5.0)
        exit_price_sqm = st.number_input("Expected sale price (€/m²)", min_value=0.0, value=4_800.0, step=100.0)
        sales_costs = st.number_input("Selling costs (%)", min_value=0.0, value=3.0, step=0.5) / 100
        licensing_months = st.number_input("Licensing duration (months)", min_value=0, value=2, step=1)
        sale_months = st.number_input("Sale period (months)", min_value=0, value=3, step=1)
        timeline = st.number_input("Total timeline (months)", min_value=1, value=int(licensing_months + reno_months + sale_months + 2), step=1)
        min_roi = st.number_input("Minimum target ROI (%)", min_value=0.0, value=15.0, step=1.0) / 100
        min_roe = st.number_input("Minimum target ROE (%)", min_value=0.0, value=20.0, step=1.0) / 100
        max_ltc = st.number_input("Maximum target LTC (%)", min_value=0.0, value=75.0, step=1.0) / 100

x = locals().copy()
r = calculate(x)

with tabs[1]:
    failed = sum([r.roi < min_roi, r.roe < min_roe, r.ltc > max_ltc, r.net_profit < 0])
    if r.net_profit < 0:
        decision, css = "REJECT — negative expected profit", "reject"
    elif failed:
        decision, css = "REVIEW — one or more targets are missed", "review"
    else:
        decision, css = "PASS — base case meets your targets", "pass"
    st.markdown(f'<div class="decision {css}">{project_name} · {location}: {decision}</div>', unsafe_allow_html=True)
    a, b, c, d = st.columns(4)
    a.metric("Net profit", eur(r.net_profit))
    b.metric("ROI", pct(r.roi), f"Target {pct(min_roi)}")
    c.metric("ROE", pct(r.roe), f"Target {pct(min_roe)}")
    d.metric("Profit margin", pct(r.margin))
    a, b, c, d = st.columns(4)
    a.metric("Total project cost", eur(r.project_cost))
    b.metric("Gross exit value", eur(r.gross_exit))
    c.metric("Total equity", eur(r.total_equity))
    d.metric("LTC", pct(r.ltc), f"Maximum {pct(max_ltc)}")

    st.subheader("Capital and cost breakdown")
    breakdown = pd.DataFrame({
        "Item": ["Purchase price", "Purchase costs", "Acquisition interest to exit", "Renovation incl. VAT", "Renovation finance cost", "Selling costs"],
        "Amount (€)": [purchase_price, r.purchase_costs, r.acquisition_interest_to_exit, r.renovation_budget, r.renovation_finance_cost, r.selling_costs],
    })
    st.bar_chart(breakdown.set_index("Item"))
    left, right = st.columns(2)
    with left:
        st.dataframe(pd.DataFrame({"Metric": ["Monthly acquisition payment", "Acquisition debt at exit", "Renovation loan", "Break-even sale price / m²", "Annualized ROE"], "Value": [eur(r.monthly_payment), eur(r.acquisition_balance_exit), eur(r.renovation_loan), eur(r.break_even_sqm), pct(r.annualized_roe)]}), hide_index=True, use_container_width=True)
    with right:
        st.dataframe(pd.DataFrame({"Metric": ["Acquisition equity", "Renovation equity", "Total debt", "Total equity", "Timeline"], "Value": [eur(r.acquisition_equity), eur(r.renovation_equity), eur(r.total_debt), eur(r.total_equity), f"{timeline} months"]}), hide_index=True, use_container_width=True)

with tabs[2]:
    st.subheader("Exit-price sensitivity")
    rows = []
    for variation in [-0.20, -0.15, -0.10, -0.05, 0, 0.05, 0.10, 0.15, 0.20]:
        sale_price = exit_price_sqm * (1 + variation)
        exit_value = saleable_area * sale_price
        profit = exit_value * (1 - sales_costs) - r.project_cost
        rows.append({"Variation": f"{variation:+.0%}", "Sale price / m²": sale_price, "Net profit": profit, "ROI": profit / r.project_cost if r.project_cost else 0, "ROE": profit / r.total_equity if r.total_equity else 0})
    sensitivity = pd.DataFrame(rows)
    st.dataframe(sensitivity.style.format({"Sale price / m²": "€{:,.0f}", "Net profit": "€{:,.0f}", "ROI": "{:.1%}", "ROE": "{:.1%}"}), hide_index=True, use_container_width=True)

    st.subheader("Stress test")
    s1, s2, s3, s4 = st.columns(4)
    sale_downside = s1.number_input("Sale-price downside (%)", min_value=0.0, value=10.0, step=1.0) / 100
    cost_overrun = s2.number_input("Renovation overrun (%)", min_value=0.0, value=10.0, step=1.0) / 100
    rate_shock = s3.number_input("Interest-rate shock (points)", min_value=0.0, value=2.0, step=0.25) / 100
    delay = s4.number_input("Extra delay (months)", min_value=0, value=6, step=1)
    stressed_exit = r.gross_exit * (1 - sale_downside)
    extra_reno = r.renovation_budget * cost_overrun
    extra_acq_interest = r.acquisition_balance_exit * (acq_rate + rate_shock) / 12 * delay + r.acquisition_loan * rate_shock / 12 * min(timeline, loan_term * 12)
    extra_reno_interest = r.renovation_loan * (reno_rate + rate_shock) / 12 * delay + r.renovation_loan * rate_shock * reno_months / 24
    stressed_cost = r.project_cost + extra_reno + extra_acq_interest + extra_reno_interest
    stressed_profit = stressed_exit * (1 - sales_costs) - stressed_cost
    stressed_roi = stressed_profit / stressed_cost if stressed_cost else 0
    stressed_roe = stressed_profit / r.total_equity if r.total_equity else 0
    status = "REJECT" if stressed_profit < 0 else ("REVIEW" if stressed_roi < min_roi / 2 else "PASS")
    a, b, c, d = st.columns(4)
    a.metric("Stress status", status)
    b.metric("Stressed profit", eur(stressed_profit), eur(stressed_profit - r.net_profit))
    c.metric("Stressed ROI", pct(stressed_roi))
    d.metric("Stressed ROE", pct(stressed_roe))
