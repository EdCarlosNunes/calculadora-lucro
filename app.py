import math
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import time
import google.generativeai as genai
import os

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Calculadora de Lucro | Marketplace",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "saved_simulations" not in st.session_state:
    st.session_state["saved_simulations"] = []


# ─────────────────────────────────────────────────────────────
# MARKETPLACE FEE DATA
# ─────────────────────────────────────────────────────────────
MERCADO_LIVRE = {
    "name": "Mercado Livre",
    "icon": "🟡",
    "ad_types": {
        "Clássico": {
            "Acessórios para Veículos": 13.0,
            "Alimentos e Bebidas": 12.0,
            "Bebês": 14.0,
            "Beleza e Cuidado Pessoal": 14.0,
            "Brinquedos e Hobbies": 14.0,
            "Calçados, Roupas e Bolsas": 14.0,
            "Casa, Móveis e Decoração": 13.0,
            "Celulares e Telefones": 12.0,
            "Eletrodomésticos": 11.0,
            "Eletrônicos, Áudio e Vídeo": 12.0,
            "Esportes e Fitness": 14.0,
            "Ferramentas": 12.0,
            "Games": 12.0,
            "Informática": 12.0,
            "Instrumentos Musicais": 12.0,
            "Livros, Revistas e Comics": 16.0,
            "Saúde": 14.0,
            "Outros": 13.0,
        },
        "Premium": {
            "Acessórios para Veículos": 18.0,
            "Alimentos e Bebidas": 17.0,
            "Bebês": 18.0,
            "Beleza e Cuidado Pessoal": 18.0,
            "Brinquedos e Hobbies": 18.0,
            "Calçados, Roupas e Bolsas": 18.0,
            "Casa, Móveis e Decoração": 18.0,
            "Celulares e Telefones": 16.0,
            "Eletrodomésticos": 16.0,
            "Eletrônicos, Áudio e Vídeo": 16.0,
            "Esportes e Fitness": 18.0,
            "Ferramentas": 17.0,
            "Games": 17.0,
            "Informática": 16.0,
            "Instrumentos Musicais": 17.0,
            "Livros, Revistas e Comics": 19.0,
            "Saúde": 18.0,
            "Outros": 17.0,
        },
    },
    "fixed_fees": [
        (29.0, 6.25),
        (50.0, 6.50),
        (79.0, 6.75),
    ],
}

AMAZON = {
    "name": "Amazon",
    "icon": "📦",
    "logistics": {
        "FBM (Vendedor envia)": "fbm",
        "DBA (Amazon envia)": "dba",
    },
    "dba_fees": {
        "fixed": [ # For price < 79.00
            (30.00, 4.50),
            (49.99, 6.50),
            (78.99, 6.75),
        ],
        "weight": [ # For price >= 79.00 (Standard size examples - SP Capital base)
            (250, 19.95),
            (500, 20.45),
            (1000, 21.45),
            (2000, 22.45),
            (5000, 23.45),
            (9000, 25.45),
            (13000, 28.45),
            (17000, 31.45),
            (23000, 35.45),
            (30000, 39.45), # Cap at 30kg for simplicity in example
        ]
    },
    "categories": {
        "Automotivo": 12.0,
        "Bebês": 12.0,
        "Beleza": 12.0,
        "Brinquedos e Jogos": 13.0,
        "Casa": 12.0,
        "Computadores": 12.0,
        "Cozinha": 12.0,
        "Eletrônicos": 12.0,
        "Esportes e Aventura": 12.0,
        "Ferramentas e Construção": 12.0,
        "Games e Consoles": 12.0,
        "Instrumentos Musicais": 12.0,
        "Livros": 15.0,
        "Moda": 13.0,
        "Pet Shop": 12.0,
        "Papelaria e Escritório": 12.0,
        "Saúde": 10.0,
        "Outros": 12.0,
    },
}

SHOPEE = {
    "name": "Shopee",
    "icon": "🟠",
    "base_commission": 14.0,
    "free_shipping_extra": 6.0,
    "fixed_fee": 4.0,
    "cnpj_transaction_fee": 2.0,
    "categories": {
        "Acessórios de Moda": 14.0,
        "Beleza e Saúde": 14.0,
        "Brinquedos": 14.0,
        "Casa e Decoração": 14.0,
        "Celulares e Acessórios": 14.0,
        "Eletrônicos": 14.0,
        "Esportes e Lazer": 14.0,
        "Ferramentas": 14.0,
        "Informática": 14.0,
        "Livros": 14.0,
        "Moda Feminina": 14.0,
        "Moda Masculina": 14.0,
        "Pet Shop": 14.0,
        "Bebês e Crianças": 14.0,
        "Outros": 14.0,
    },
}


# ─────────────────────────────────────────────────────────────
# CALCULATION ENGINE
# ─────────────────────────────────────────────────────────────
def calc_ml_fixed_fee(sale_price: float) -> float:
    """Calculate Mercado Livre fixed fee based on price range."""
    if sale_price >= 79.0:
        return 0.0
    for threshold, fee in MERCADO_LIVRE["fixed_fees"]:
        if sale_price <= threshold:
            return fee
    return 0.0


def calculate_mercado_livre(
    cost: float,
    ad_type: str,
    category: str,
    extra_cost: float,
    shipping_cost: float, # Cost if Free Shipping applies (>= 79)
    tax_pct: float,
    fixed_expenses_per_unit: float,
    desired_margin_pct: float,
    other_pct: float,
    include_fixed_fee: bool = True,
) -> dict:
    commission_pct = MERCADO_LIVRE["ad_types"][ad_type][category]
    
    def get_fixed_fee(p):
        if p >= 79.00: return 0.0
        for threshold, fee in MERCADO_LIVRE["fixed_fees"]:
            if p <= threshold: return fee
        return 0.0

    tax_factor = tax_pct / 100
    commission_factor = commission_pct / 100
    other_factor = other_pct / 100
    margin_factor = desired_margin_pct / 100
    
    divisor = 1 - (commission_factor + tax_factor + margin_factor + other_factor)
    
    suggested_price = 0.0
    
    if divisor > 0.01:
        # Regime 1: Price < 79. Check tiers.
        # Tier 1: <= 29. Fee 6.25. No Shipping.
        fee_tier1 = 6.25 if include_fixed_fee else 0.0
        p1 = (cost + extra_cost + fixed_expenses_per_unit + fee_tier1) / divisor
        if p1 <= 29.00:
            suggested_price = p1
        else:
            # Tier 2: 29 < p <= 50. Fee 6.50.
            fee_tier2 = 6.50 if include_fixed_fee else 0.0
            p2 = (cost + extra_cost + fixed_expenses_per_unit + fee_tier2) / divisor
            if p2 <= 50.00:
                suggested_price = p2
            else:
                # Tier 3: 50 < p < 79. Fee 6.75.
                fee_tier3 = 6.75 if include_fixed_fee else 0.0
                p3 = (cost + extra_cost + fixed_expenses_per_unit + fee_tier3) / divisor
                if p3 < 79.00:
                    suggested_price = p3
                else:
                    # Regime 2: >= 79. No Fixed Fee. YES Shipping deduction.
                    # Standard logic: Fee is 0 if price >= 79. So include_fixed_fee doesn't matter here for the fee itself,
                    # but logic says "No Fixed Fee". 
                    p4 = (cost + extra_cost + fixed_expenses_per_unit + shipping_cost) / divisor
                    suggested_price = max(79.00, p4)
                    
    final_price = round(suggested_price, 2)
    
    # Recalculate actuals
    real_fixed_fee = get_fixed_fee(final_price) if include_fixed_fee else 0.0
    real_shipping = shipping_cost if final_price >= 79.00 else 0.0
    
    commission = final_price * commission_factor
    tax = final_price * tax_factor
    other = final_price * other_factor
    
    total_fees = commission + real_fixed_fee + other
    
    # Total Cost = Product + Extra + FixedExp + Shipping + Fees + Tax
    total_cost = cost + extra_cost + fixed_expenses_per_unit + real_shipping + total_fees + tax
    profit = final_price - total_cost
    
    margin = (profit / final_price * 100) if final_price > 0 else 0
    roi_base = cost + extra_cost + real_shipping + fixed_expenses_per_unit
    roi = (profit / roi_base * 100) if roi_base > 0 else 0

    return {
        "profit": profit,
        "margin": margin,
        "roi": roi,
        "total_fees": total_fees + tax,
        "commission": commission,
        "commission_pct": commission_pct,
        "fixed_fee": real_fixed_fee,
        "shipping_cost": real_shipping, # Add this for specific display if needed
        "tax": tax,
        "you_receive": final_price - total_fees - tax - real_shipping,
        "suggested_price": final_price,
        "total_cost": total_cost,
    }


def calculate_amazon(
    cost: float,
    logistics: str, # "dba" or "fbm"
    category: str,
    extra_cost: float,
    shipping_cost: float,
    weight_g: float,
    tax_pct: float,
    fixed_expenses_per_unit: float,
    desired_margin_pct: float,
    other_pct: float,
) -> dict:
    commission_pct = AMAZON["categories"][category]

    def get_dba_fee(price, weight):
        if price < 79.00:
            if price <= 30.00: return AMAZON["dba_fees"]["fixed"][0][1]
            if price <= 49.99: return AMAZON["dba_fees"]["fixed"][1][1]
            return AMAZON["dba_fees"]["fixed"][2][1]
        else:
            for w, fee in AMAZON["dba_fees"]["weight"]:
                if weight <= w: return fee
            return AMAZON["dba_fees"]["weight"][-1][1]

    suggested_price = 0.0
    tax_factor = tax_pct / 100
    commission_factor = commission_pct / 100
    other_factor = other_pct / 100
    margin_factor = desired_margin_pct / 100
    
    divisor = 1 - (commission_factor + tax_factor + margin_factor + other_factor)
    
    if divisor <= 0.01:
        suggested_price = 0.0
    else:
        if logistics == "dba":
            # Iterative check for tiers
            p_check = (cost + extra_cost + fixed_expenses_per_unit + 4.50) / divisor
            if p_check <= 30.00:
                suggested_price = p_check
            else:
                p_check = (cost + extra_cost + fixed_expenses_per_unit + 6.50) / divisor
                if p_check <= 49.99:
                    suggested_price = p_check
                else:
                    p_check = (cost + extra_cost + fixed_expenses_per_unit + 6.75) / divisor
                    if p_check < 79.00:
                        suggested_price = p_check
                    else:
                        w_fee = 0.0
                        for w, fee in AMAZON["dba_fees"]["weight"]:
                            if weight_g <= w: 
                                w_fee = fee
                                break
                        else:
                            w_fee = AMAZON["dba_fees"]["weight"][-1][1]
                        suggested_price = max(79.00, (cost + extra_cost + fixed_expenses_per_unit + w_fee) / divisor)
        else:
            suggested_price = (cost + extra_cost + fixed_expenses_per_unit + shipping_cost) / divisor

    final_price = round(suggested_price, 2)
    
    logistics_fee = 0.0
    if logistics == "dba":
        logistics_fee = get_dba_fee(final_price, weight_g)

    commission = final_price * commission_factor
    tax = final_price * tax_factor
    other = final_price * other_factor
    
    total_fees = commission + logistics_fee + other
    fbm_cost = shipping_cost if logistics == "fbm" else 0.0
    
    # Revenue - Expenses
    profit = final_price - (cost + extra_cost + fixed_expenses_per_unit + fbm_cost + total_fees + tax)
    
    margin = (profit / final_price * 100) if final_price > 0 else 0
    roi_base = cost + extra_cost + fbm_cost
    roi = (profit / roi_base * 100) if roi_base > 0 else 0

    return {
        "profit": profit,
        "margin": margin,
        "roi": roi,
        "total_fees": total_fees + tax,
        "commission": commission,
        "commission_pct": commission_pct,
        "plan_fee": logistics_fee,
        "tax": tax,
        "you_receive": final_price - total_fees - tax,
        "suggested_price": final_price,
        "total_cost": roi_base + total_fees + tax + fixed_expenses_per_unit, 
    }


def calculate_shopee(
    cost: float,
    category: str,
    seller_type: str,
    free_shipping: bool,
    extra_cost: float,
    shipping_cost: float,
    tax_pct: float,
    fixed_expenses_per_unit: float,
    desired_margin_pct: float,
    other_pct: float,
) -> dict:
    commission_pct = SHOPEE["categories"][category] # Base commission
    
    if free_shipping:
        commission_pct += 6.0 # Add 6% for free shipping program
        
    # Iterative Price Calc
    tax_factor = tax_pct / 100
    commission_factor = commission_pct / 100
    other_factor = other_pct / 100
    margin_factor = desired_margin_pct / 100
    
    # Try Standard Fee (4.00)
    divisor_std = 1 - (commission_factor + tax_factor + margin_factor + other_factor)
    suggested_price = 0.0
    
    if divisor_std > 0.01:
        p_std = (cost + extra_cost + shipping_cost + fixed_expenses_per_unit + 4.00) / divisor_std
        if p_std >= 8.00:
            suggested_price = p_std
        else:
            # Try Small Item Fee (50% of Price)
            # Price = (Costs) / (1 - VarFees - 0.5)
            # VarFees includes Commission!
            # Example: 14% comm + 50% fixed = 64% fees
            divisor_small = 1 - (commission_factor + tax_factor + margin_factor + other_factor + 0.5)
            if divisor_small > 0.01:
                p_small = (cost + extra_cost + shipping_cost + fixed_expenses_per_unit) / divisor_small
                suggested_price = p_small
            else:
                suggested_price = 0.0 
    
    final_price = round(suggested_price, 2)
    
    # Metrics
    if final_price > 0 and final_price < 8.00:
        real_fixed_fee = final_price * 0.5
    else:
        real_fixed_fee = 4.00
        
    commission = final_price * commission_factor
    tax = final_price * tax_factor
    other = final_price * other_factor
    
    total_fees = commission + real_fixed_fee + other
    total_cost = cost + extra_cost + shipping_cost + fixed_expenses_per_unit + total_fees + tax
    profit = final_price - total_cost
    
    margin = (profit / final_price * 100) if final_price > 0 else 0
    roi_base = cost + extra_cost + shipping_cost + fixed_expenses_per_unit
    roi = (profit / roi_base * 100) if roi_base > 0 else 0

    return {
        "profit": profit,
        "margin": margin,
        "roi": roi,
        "total_fees": total_fees + tax,
        "commission": commission,
        "commission_pct": commission_pct,
        "fixed_fee": real_fixed_fee,
        "tax": tax,
        "you_receive": final_price - total_fees - tax,
        "suggested_price": final_price,
        "total_cost": total_cost,
    }


 



# ─────────────────────────────────────────────────────────────
# CHART BUILDERS
# ─────────────────────────────────────────────────────────────
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, SF Pro Display, -apple-system, sans-serif", color="#e0e0e0", size=13),
    margin=dict(l=20, r=20, t=40, b=40),
    xaxis=dict(
        showgrid=False,
        showline=False,
        zeroline=False,
        tickfont=dict(size=12, color="#a0a0a0"),
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.06)",
        showline=False,
        zeroline=False,
        tickfont=dict(size=12, color="#a0a0a0"),
        tickprefix="R$ ",
    ),
    hoverlabel=dict(
        bgcolor="rgba(30,30,40,0.95)",
        bordercolor="rgba(255,255,255,0.1)",
        font_size=13,
        font_color="#fff",
    ),
    bargap=0.35,
)

UNITS_PER_DAY = [5, 10, 20, 30, 50, 100]


def build_projection_chart(
    profit_per_unit: float,
    title: str,
    color_gradient: list[str],
) -> go.Figure:
    """Build a bar chart showing monthly profit projections."""
    monthly = [profit_per_unit * u * 30 for u in UNITS_PER_DAY]
    labels = [f"{u} vendas/dia" for u in UNITS_PER_DAY]

    colors = []
    for val in monthly:
        if val >= 0:
            colors.append(color_gradient[0])
        else:
            colors.append("#ff4d6a")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=labels,
            y=monthly,
            marker=dict(
                color=colors,
                cornerradius=8,
                line=dict(width=0),
            ),
            text=[f"R$ {v:,.2f}" for v in monthly],
            textposition="outside",
            textfont=dict(size=12, color="#e0e0e0"),
            hovertemplate="<b>%{x}</b><br>Lucro mensal: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color="#fff"), x=0, xanchor="left"),
        height=380,
        **CHART_LAYOUT,
    )
    return fig


def build_comparison_chart(
    profit_without: float,
    profit_with: float,
) -> go.Figure:
    """Build a grouped bar chart comparing profit with/without fixed expenses."""
    monthly_without = [profit_without * u * 30 for u in UNITS_PER_DAY]
    monthly_with = [profit_with * u * 30 for u in UNITS_PER_DAY]
    labels = [f"{u}/dia" for u in UNITS_PER_DAY]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Sem despesas fixas",
            x=labels,
            y=monthly_without,
            marker=dict(color="rgba(0, 210, 140, 0.85)", cornerradius=6),
            hovertemplate="<b>Sem desp. fixas</b><br>%{x}: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Com despesas fixas",
            x=labels,
            y=monthly_with,
            marker=dict(color="rgba(0, 150, 255, 0.85)", cornerradius=6),
            hovertemplate="<b>Com desp. fixas</b><br>%{x}: R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(
            text="📊 Comparativo: Com vs Sem Despesas Fixas (Lucro Mensal)",
            font=dict(size=16, color="#fff"),
            x=0,
            xanchor="left",
        ),
        barmode="group",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=12, color="#ccc"),
            bgcolor="rgba(0,0,0,0)",
        ),
        height=400,
        **CHART_LAYOUT,
    )
    return fig


def build_breakeven_chart(
    fixed_costs: float,
    contribution_margin: float,
) -> go.Figure:
    """Build a chart visualizing the break-even point."""
    if contribution_margin <= 0:
        return None

    breakeven_units = fixed_costs / contribution_margin if contribution_margin > 0 else 0
    
    # Create a range of units around the break-even point
    max_units = max(int(breakeven_units * 2), 50)
    step = max(1, max_units // 20)
    units_range = list(range(0, max_units + step, step))
    
    # Calculate profit for each unit count
    # Profit = (Margin * Units) - Fixed Costs
    profits = [(contribution_margin * u) - fixed_costs for u in units_range]
    
    # Colors: Red below zero, Green above
    colors = ["#ff453a" if p < 0 else "#30d158" for p in profits]

    fig = go.Figure()
    
    # Add Profit Line
    fig.add_trace(
        go.Scatter(
            x=units_range,
            y=profits,
            mode="lines+markers",
            line=dict(color="#0a84ff", width=3),
            marker=dict(size=6, color=colors, line=dict(color="#fff", width=1)),
            name="Lucro Líquido",
            hovertemplate="<b>%{x} vendas</b><br>Lucro: R$ %{y:,.2f}<extra></extra>",
        )
    )
    
    # Add Break-even Line (Zero)
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="rgba(255,255,255,0.3)",
        annotation_text="Ponto de Equilíbrio",
        annotation_position="bottom right",
    )
    
    # Add Vertical Line at Break-even units
    fig.add_vline(
        x=breakeven_units,
        line_dash="dot",
        line_color="#ffd60a",
        annotation_text=f"Breakeven: {int(math.ceil(breakeven_units))} un.",
        annotation_position="top left",
    )

    fig.update_layout(
        title=dict(
            text=f"🎯 Ponto de Equilíbrio: {int(math.ceil(breakeven_units))} vendas/mês",
            font=dict(size=16, color="#fff"),
            x=0,
            xanchor="left",
        ),
        xaxis_title="Quantidade de Vendas",
        yaxis_title="Lucro Líquido (R$)",
        height=400,
        **CHART_LAYOUT,
    )
    return fig


# ─────────────────────────────────────────────────────────────
# iOS 26 LIQUID GLASS CSS
# ─────────────────────────────────────────────────────────────
def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600&display=swap');

        /* ── Root variables (iOS 26 Theme) ────── */
        :root {
            --glass-bg: rgba(255, 255, 255, 0.65);
            --glass-border: rgba(255, 255, 255, 0.4);
            --glass-shadow: 0 10px 40px rgba(0, 0, 0, 0.05);
            --glass-blur: blur(24px);
            --text-primary: #1d1d1f;
            --text-secondary: #86868b;
            --accent-green: #34c759;
            --accent-red: #ff3b30;
            --accent-blue: #007aff;
            --accent-orange: #ff9500;
            --accent-yellow: #ffcc00;
            --radius-lg: 24px;
            --radius-md: 18px;
            --radius-sm: 12px;
            --bg-gradient: radial-gradient(circle at top left, #fbfbfd 0%, #f5f5f7 100%);
        }



        /* ── Global resets ────────────────────── */
        html, body, [data-testid="stAppViewContainer"] {
            background: var(--bg-gradient) !important;
            color: var(--text-primary) !important;
            font-family: 'SF Pro Display', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
            -webkit-font-smoothing: antialiased;
        }

        [data-testid="stHeader"] {
            background: transparent !important;
        }

        [data-testid="stSidebar"] {
            background: var(--glass-bg) !important;
            backdrop-filter: var(--glass-blur) !important;
            border-right: 1px solid var(--glass-border) !important;
        }

        /* ── Streamlit tab overrides ──────────── */
        .stTabs [data-baseweb="tab-list"] {
            background: rgba(118, 118, 128, 0.12) !important;
            backdrop-filter: blur(10px) !important;
            border-radius: 99px !important; /* Pill shape */
            padding: 4px !important;
            gap: 2px !important;
            border: none !important;
            box-shadow: none !important;
            width: fit-content;
            margin: 0 auto 20px auto;
        }

        .stTabs [data-baseweb="tab"] {
            background: transparent !important;
            color: var(--text-secondary) !important;
            border-radius: 99px !important;
            border: none !important;
            padding: 8px 24px !important;
            font-weight: 500 !important;
            font-size: 14px !important;
            transition: all 0.3s cubic-bezier(0.25, 0.1, 0.25, 1) !important;
        }

        .stTabs [aria-selected="true"] {
            background: #fff !important; /* Light mode pill */
            color: #000 !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.12) !important;
        }



        .stTabs [data-baseweb="tab-highlight"],
        .stTabs [data-baseweb="tab-border"] {
            display: none !important;
        }

        /* ── Input fields ─────────────────────── */
        .stNumberInput > div > div > input,
        .stSelectbox > div > div,
        .stTextInput > div > div > input {
            background: rgba(118, 118, 128, 0.06) !important;
            border: 1px solid transparent !important;
            border-radius: var(--radius-sm) !important;
            color: var(--text-primary) !important;
            font-size: 15px !important;
            transition: all 0.2s ease !important;
            padding-left: 12px;
        }

        .stNumberInput > div > div > input:focus,
        .stTextInput > div > div > input:focus {
            background: rgba(118, 118, 128, 0.03) !important;
            border-color: var(--accent-blue) !important;
            box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.1) !important;
        }
        
        /* Remove +/- buttons on number input for cleaner look (optional, but requested cleaner) */
        /* Actually keeping them but styling them minimalist */
        .stNumberInput button {
             background: transparent !important;
             border: none !important;
             color: var(--text-secondary) !important;
        }
        .stNumberInput button:hover {
            color: var(--text-primary) !important;
        }

        /* ── Expander ────────────────────────── */
        .streamlit-expanderHeader {
            background: var(--glass-bg) !important;
            backdrop-filter: var(--glass-blur) !important;
            border: 1px solid var(--glass-border) !important;
            border-radius: var(--radius-md) !important;
            color: var(--text-primary) !important;
        }
        
        [data-testid="stExpander"] {
            border: none !important;
            box-shadow: var(--glass-shadow) !important;
            border-radius: var(--radius-lg) !important;
            background: var(--glass-bg);
        }

        /* ── Plotly chart containers ──────────── */
        .stPlotlyChart {
            background: var(--glass-bg) !important;
            backdrop-filter: var(--glass-blur) !important;
            border: 1px solid var(--glass-border) !important;
            border-radius: var(--radius-lg) !important;
            padding: 20px !important;
            box-shadow: var(--glass-shadow) !important;
        }

        /* ── Custom result cards ──────────────── */
        /* Remove top padding from Streamlit content and hide header */
        .block-container {
            padding-top: 0rem !important;
            padding-bottom: 5rem !important;
        }
        header[data-testid="stHeader"] {
            display: none;
        }
        
        /* Navbar */
        .navbar {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); /* Light Gray */
            padding: 15px 25px;
            border-radius: 0 0 12px 12px; /* Rounded only at bottom */
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
            color: #343a40; /* Dark Gray/Black for contrast */
            margin-bottom: 25px;
            margin-top: -1rem; /* Pull up to cover any remaining gap if standard padding persists */
            display: flex;
            align-items: center;
            justify-content: flex-start; /* Left align */
            gap: 15px;
            border-bottom: 1px solid #dee2e6; /* Gray border bottom only */
            border-left: 1px solid #dee2e6;
            border-right: 1px solid #dee2e6;
        }
        .navbar-logo {
            font-size: 28px;
            background: #fff;
            width: 45px;
            height: 45px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }
        .navbar-title {
            font-size: 20px;
            font-weight: 700;
            letter-spacing: -0.01em;
            color: #212529; /* Almost Black */
        }

        .results-container {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }

        .results-row-2 {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-bottom: 20px;
            width: 100%;
        }

        /* Mobile responsive */
        @media (max-width: 768px) {
            .results-container, .results-row-2 {
                grid-template-columns: 1fr;
            }
        }


        .result-card {
            background: #ffffff; /* Explicitly white as per screenshot */
            /* backdrop-filter: var(--glass-blur); Removed for solid white look */
            border: 1px solid rgba(0,0,0,0.05);
            border-radius: 20px; /* Slightly more rounded as per screenshot */
            padding: 24px 20px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05); /* Soft shadow */
            text-align: center;
            transition: transform 0.3s ease;
            flex: 1 1 100px; /* Allow shrinking */
            min-width: 0; /* Remove fixed minimum width to allow grid flex */
            width: 100%; /* Ensure it fills the grid cell */
        }

        .result-card:hover {
            transform: scale(1.02);
            z-index: 2;
        }

        .result-label {
            font-size: 12px !important;
            font-weight: 700 !important;
            color: #000000 !important; /* Force Black */
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
            margin-bottom: 8px !important;
            white-space: normal !important; /* Allow wrapping */
            word-wrap: break-word !important;
        }

        .result-value {
            font-size: 28px !important;
            font-weight: 800 !important;
            letter-spacing: -0.02em !important;
            color: #000000 !important; /* Force Black */
            white-space: normal !important; /* Allow wrapping */
            word-wrap: break-word !important;
            line-height: 1.1 !important;
        }
        
        .result-sub {
            font-size: 13px !important;
            color: #444444 !important; /* Dark Grey */
            margin-top: 4px !important;
            font-weight: 500 !important;
        }

        /* Stronger colors for white background */
        .positive { color: #198754 !important; } /* Green */
        .negative { color: #dc3545 !important; } /* Red */
        .neutral { color: #0d6efd !important; } /* Blue */
        .orange { color: #fd7e14 !important; } /* Orange */
        .yellow { color: #ffc107 !important; } /* Yellow */

        /* ── Hero header ──────────────────────── */
        .hero-title {
            font-size: 42px;
            font-weight: 700;
            letter-spacing: -0.02em;
            background: linear-gradient(180deg, var(--text-primary) 0%, var(--text-secondary) 150%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-align: center;
            margin-bottom: 6px;
        }
        
        /* ── Helpers ──────────────────────────── */
        hr { border-color: rgba(118, 118, 128, 0.2) !important; }
        
        </style>
        """,
        unsafe_allow_html=True,
    )





# ─────────────────────────────────────────────────────────────
# UI COMPONENTS
# ─────────────────────────────────────────────────────────────
def render_result_card(label: str, value: str, color_class: str, sub: str = "") -> str:
    sub_html = f'<div class="result-sub">{sub}</div>' if sub else ""
    return f"""
<div class="result-card">
    <div class="result-label">{label}</div>
    <div class="result-value {color_class}">{value}</div>
    {sub_html}
</div>
"""


def render_results(result: dict, title: str = "📊 Resultados por Venda"):
    """Render result cards and charts."""
    profit = result["profit"]
    color = "positive" if profit >= 0 else "negative"

    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)

    # Accumulate HTML for cards
    cards_html = ""
    
    
    # 5 Card Layout (3 up, 2 down)
    
    # Top Row (3 cards)
    row1_html = ""
    row1_html += render_result_card(
        "Lucro Líquido",
        f"R$ {profit:,.2f}",
        color,
        "por venda",
    )
    row1_html += render_result_card(
        "Preço Sugerido",
        f"R$ {result['suggested_price']:,.2f}",
        "neutral",
        "baseado na margem",
    )
    row1_html += render_result_card(
        "Margem Líquida",
        f"{result['margin']:.1f}%",
        color,
    )

    # Bottom Row (2 cards)
    row2_html = ""
    row2_html += render_result_card(
        "Tarifas Totais",
        f"R$ {result['total_fees']:,.2f}",
        "orange",
        f"{result['commission_pct']:.0f}% comissão",
    )
    row2_html += render_result_card(
        "Você Recebe",
        f"R$ {result['you_receive']:,.2f}",
        "yellow",
        "após tarifas",
    )

    # Render containers
    st.markdown(f'<div class="results-container">{row1_html}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="results-row-2">{row2_html}</div>', unsafe_allow_html=True)


def render_charts(
    result_no_fixed: dict,
    result_with_fixed: dict | None,
    has_fixed_expenses: bool,
    total_fixed_expenses: float = 0.0,
):
    """Render projection charts."""
    st.markdown("---")
    
    st.markdown(
        '<div class="section-title">📈 Projeção de Lucro Mensal</div>',
        unsafe_allow_html=True,
    )

    fig1 = build_projection_chart(
        result_no_fixed["profit"],
        "💰 Projeção Mensal (Margem de Contribuição)",
        ["rgba(48, 209, 88, 0.8)"],
    )
    st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})



    if has_fixed_expenses and result_with_fixed is not None:
        st.markdown("---")
        c_chart1, c_chart2 = st.columns(2)
        
        with c_chart1:
             fig2 = build_comparison_chart(
                result_no_fixed["profit"],
                result_with_fixed["profit"],
            )
             st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
             
        with c_chart2:
             # Contribution margin is the profit without fixed expenses
             contribution_margin = result_no_fixed["profit"]
             fig3 = build_breakeven_chart(total_fixed_expenses, contribution_margin)
             if fig3:
                 st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})
             else:
                 st.info("Margem de contribuição negativa ou zero. Impossível calcular ponto de equilíbrio.")


def render_fixed_expenses() -> dict:
    """Render optional fixed monthly expenses section and return values."""
    with st.expander("💼 Despesas Fixas Mensais (opcional)", expanded=False):
        st.markdown(
            """
            <div style="font-size:13px; color:#a1a1aa; margin-bottom:12px;">
                Informe seus gastos fixos mensais. Eles serão rateados por unidade vendida
                nas projeções com despesas fixas.
            </div>
            """,
            unsafe_allow_html=True,
        )
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            mei = st.number_input(
                "MEI (R$/mês)",
                min_value=0.0,
                value=0.0,
                step=10.0,
                format="%.2f",
                key="mei",
                help="Contribuição mensal do MEI",
            )
        with fc2:
            platform = st.number_input(
                "Plataforma / NF-e (R$/mês)",
                min_value=0.0,
                value=0.0,
                step=10.0,
                format="%.2f",
                key="platform",
                help="Plataforma de nota fiscal / integração",
            )
        with fc3:
            supplier = st.number_input(
                "Assinatura Fornecedor (R$/mês)",
                min_value=0.0,
                value=0.0,
                step=10.0,
                format="%.2f",
                key="supplier",
                help="Assinatura mensal do fornecedor",
            )

        fc4, fc5, _ = st.columns(3)
        with fc4:
            other_fixed = st.number_input(
                "Outros Custos Fixos (R$/mês)",
                min_value=0.0,
                value=0.0,
                step=10.0,
                format="%.2f",
                key="other_fixed",
                help="Internet, luz, marketing fixo, etc.",
            )
        with fc5:
            estimated_sales = st.number_input(
                "Vendas estimadas/mês (para rateio)",
                min_value=1,
                value=30,
                step=5,
                key="estimated_sales",
                help="Quantidade estimada de vendas por mês para calcular o custo fixo por unidade",
            )
            
        st.markdown("---")
        st.markdown(
            """
            <div style="font-size:13px; color:#a1a1aa; margin-bottom:12px;">
                <b>Taxas e Custos Operacionais (% sobre a venda)</b><br>
                Valores percentuais que incidem sobre o preço de venda ou custos variáveis.
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        op1, op2, op3 = st.columns(3)
        with op1:
            marketing_pct = st.number_input(
                "Marketing / Ads (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.5,
                format="%.1f",
                key="marketing_pct",
                help="ACOS médio ou % investido em publicidade",
            )
        with op2:
            antecipation_pct = st.number_input(
                "Antecipação / Financeiro (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.1,
                format="%.1f",
                key="antecipation_pct",
                help="Taxa para antecipar recebíveis (se houver)",
            )
        with op3:
            losses_pct = st.number_input(
                "Perdas / Devoluções (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.1,
                format="%.1f",
                key="losses_pct",
                help="Provisão para extravios e devoluções",
            )
            
        op4, _, _ = st.columns(3)
        with op4:
            other_taxes_pct = st.number_input(
                "Outros Impostos (DIFAL/ST) (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.1,
                format="%.1f",
                key="other_taxes_pct",
                help="Percentual estimado para DIFAL, ICMS-ST ou outros impostos",
            )

    total_fixed = mei + platform + supplier + other_fixed
    fixed_per_unit = total_fixed / estimated_sales if estimated_sales > 0 else 0
    total_other_pct = marketing_pct + antecipation_pct + losses_pct + other_taxes_pct

    return {
        "total_monthly": total_fixed,
        "per_unit": fixed_per_unit,
        "estimated_sales": estimated_sales,
        "has_expenses": total_fixed > 0 or total_other_pct > 0,
        "other_pct": total_other_pct,
        "total_monthly_fixed": total_fixed, # explicit key for charts
    }


# ─────────────────────────────────────────────────────────────
# MARKETPLACE TABS
# ─────────────────────────────────────────────────────────────
def tab_mercado_livre(fixed: dict, product_name: str):
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        # ─────────────────────────────────────────────────────────────
        # 1. DADOS DO PRODUTO
        # ─────────────────────────────────────────────────────────────
        with st.expander("📦 Dados do Produto", expanded=True):
            col_prod1, col_prod2 = st.columns(2)
            with col_prod1:
                cost = st.number_input(
                    "Preço de Custo (R$)",
                    min_value=0.0,
                    value=50.0,
                    step=0.01,
                    format="%.2f",
                    key="ml_cost",
                    help="Quanto você pagou para comprar ou produzir o produto.",
                )
            with col_prod2:
                # We need to get the category keys based on a default or current selection.
                # However, category depends on ad_type. 
                # To avoid refreshing issues, we can put ad_type here or keep category generic?
                # The prompt asks for: "Dados do Produto: (Preço de Custo, Categoria, Peso/Dimensões)"
                # But Category in ML depends on Ad Type (Classic/Premium) for the *rate*.
                # Actually, the dict `MERCADO_LIVRE["ad_types"]` keys are the Ad Types.
                # The *categories* are the keys inside that. They are the same for both ad types in the dict structure (mostly).
                # Let's check the dict structure again.
                # Yes, "Clássico" and "Premium" have the same keys.
                # So we can list categories from one of them.
                categories_list = list(MERCADO_LIVRE["ad_types"]["Clássico"].keys())
                category = st.selectbox(
                    "Categoria",
                    categories_list,
                    key="ml_category",
                    help="Escolha a categoria correta, pois a comissão do Mercado Livre muda dependendo dela.",
                )

        # ─────────────────────────────────────────────────────────────
        # 2. CONFIGURAÇÃO DA VENDA
        # ─────────────────────────────────────────────────────────────
        with st.expander("🛒 Configuração da Venda", expanded=True):
            col_sale1, col_sale2 = st.columns(2)
            with col_sale1:
                ad_type = st.selectbox(
                    "Tipo de Anúncio",
                    list(MERCADO_LIVRE["ad_types"].keys()),
                    key="ml_ad_type",
                    help="Clássico tem taxa menor mas menos exposição. Premium tem taxa maior mas parcela sem juros.",
                )
            with col_sale2:
                desired_margin = st.number_input(
                    "Margem Desejada (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=1.0,
                    format="%.1f",
                    key="ml_desired_margin",
                    help="A porcentagem de lucro que você quer colocar no bolso depois de pagar tudo.",
                )


            col_sale3, col_sale4 = st.columns(2)
            with col_sale3:
                shipping = st.number_input(
                    "Frete do Vendedor (R$)",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                    key="ml_shipping",
                    help="Se o produto for acima de R$79, você paga uma parte do frete. Coloque esse valor aqui."
                )
            with col_sale4:
                st.write("") # Spacer
                include_fixed_fee = st.checkbox(
                    "Cobrar Taxa Fixa?",
                    value=True,
                    key="ml_fixed_fee",
                    help="Desmarque se quiser simular isenção da taxa fixa (R$6.xx) para produtos abaixo de R$79.",
                )

        # ─────────────────────────────────────────────────────────────
        # 3. IMPOSTOS E CUSTOS EXTRAS
        # ─────────────────────────────────────────────────────────────
        with st.expander("🧾 Impostos e Custos Extras", expanded=False):
            col_tax1, col_tax2 = st.columns(2)
            with col_tax1:
                tax_pct = st.number_input(
                    "Imposto / Nota Fiscal (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=0.1,
                    format="%.1f",
                    key="ml_tax",
                    help="Imposto sobre a nota fiscal (ex: DAS).",
                )
            with col_tax2:
                 extra_cost = st.number_input(
                    "Custo Extra / Embalagem (R$)",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                    key="ml_extra",
                    help="Gastos a mais por venda: Embalagem, fita, etiqueta, brinde, etc.",
                )

    result_no_fixed = calculate_mercado_livre(
        cost, ad_type, category, extra_cost, shipping, tax_pct, 0.0, desired_margin, 0.0, include_fixed_fee
    )

    result_with_fixed = None
    if fixed["has_expenses"]:
        result_with_fixed = calculate_mercado_livre(
            cost, ad_type, category, extra_cost, shipping, tax_pct, fixed["per_unit"], desired_margin, fixed["other_pct"], include_fixed_fee
        )

    with col2:
        render_results(result_no_fixed, "📊 Resultados (Sem Despesas Fixas)")
        if result_with_fixed:
            # Removed separator
            render_results(result_with_fixed, "💼 Resultados (Com Despesas Fixas)")

    render_charts(result_no_fixed, result_with_fixed, fixed["has_expenses"], fixed["total_monthly_fixed"])

    if st.button("💾 Salvar Simulação (Mercado Livre)", type="primary", use_container_width=True):
        save_simulation(
            "Mercado Livre", 
            product_name, 
            result_no_fixed, 
            result_with_fixed if fixed["has_expenses"] else None
        )
        st.success("✅ Simulação salva com sucesso!")


def tab_amazon(fixed: dict, product_name: str):
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        # ─────────────────────────────────────────────────────────────
        # 1. DADOS DO PRODUTO
        # ─────────────────────────────────────────────────────────────
        with st.expander("📦 Dados do Produto", expanded=True):
            col_prod1, col_prod2 = st.columns(2)
            with col_prod1:
                cost = st.number_input(
                    "Preço de Custo (R$)",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                    key="amz_cost",
                    help="Quanto você pagou para comprar ou produzir o produto.",
                )
            with col_prod2:
                category = st.selectbox(
                    "Categoria",
                    list(AMAZON["categories"].keys()),
                    key="amz_category",
                    help="A comissão da Amazon varia conforme a categoria do produto.",
                )

        # ─────────────────────────────────────────────────────────────
        # 2. CONFIGURAÇÃO DA VENDA
        # ─────────────────────────────────────────────────────────────
        with st.expander("🛒 Configuração da Venda", expanded=True):
            col_sale1, col_sale2 = st.columns(2)
            with col_sale1:
                logistics_display = st.selectbox(
                    "Logística",
                    list(AMAZON["logistics"].keys()),
                    key="amz_logistics",
                    help="DBA: A Amazon ou parceiro entrega. FBM: Você envia.",
                )
                logistics = AMAZON["logistics"][logistics_display]
            with col_sale2:
                desired_margin = st.number_input(
                    "Margem Desejada (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=1.0,
                    format="%.1f",
                    key="amz_desired_margin",
                    help="A porcentagem de lucro que você quer colocar no bolso depois de pagar tudo.",
                )

            # Dynamic fields based on logistics
            col_sale3, col_sale4 = st.columns(2)
            weight_g = 0.0
            shipping_cost = 0.0
            
            if logistics == "dba":
                with col_sale3:
                    weight_g = st.number_input(
                        "Peso (gramas)",
                        min_value=0.0,
                        value=0.0,
                        step=50.0,
                        key="amz_weight",
                        help="Peso do produto embalado (DBA).",
                    )
            else:
                with col_sale3:
                    shipping_cost = st.number_input(
                        "Frete do Vendedor (R$)",
                        min_value=0.0,
                        value=0.0,
                        step=0.01,
                        format="%.2f",
                        key="amz_shipping",
                        help="Quanto você paga nos Correios/Transportadora para enviar.",
                    )

        # ─────────────────────────────────────────────────────────────
        # 3. IMPOSTOS E CUSTOS EXTRAS
        # ─────────────────────────────────────────────────────────────
        with st.expander("🧾 Impostos e Custos Extras", expanded=False):
            col_tax1, col_tax2 = st.columns(2)
            with col_tax1:
                tax_pct = st.number_input(
                    "Imposto / Nota Fiscal (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0, 
                    step=0.1,
                    format="%.1f",
                    key="amz_tax",
                    help="Imposto sobre a nota fiscal (ex: Simples Nacional).",
                )
            with col_tax2:
                extra_cost = st.number_input(
                    "Custo Extra / Embalagem (R$)",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                    key="amz_extra",
                    help="Gastos a mais por venda: Embalagem, fita, etiqueta, brinde, etc.",
                )

    result_no_fixed = calculate_amazon(
        cost, logistics, category, extra_cost, shipping_cost, weight_g, tax_pct, 0.0, desired_margin, 0.0
    )

    result_with_fixed = None
    if fixed["has_expenses"]:
        result_with_fixed = calculate_amazon(
            cost, logistics, category, extra_cost, shipping_cost, weight_g, tax_pct, fixed["per_unit"], desired_margin, fixed["other_pct"]
        )

    with col2:
        render_results(result_no_fixed, "📊 Resultados (Sem Despesas Fixas)")
        if result_with_fixed:
            # Removed separator
            render_results(result_with_fixed, "💼 Resultados (Com Despesas Fixas)")

    render_charts(result_no_fixed, result_with_fixed, fixed["has_expenses"], fixed["total_monthly_fixed"])

    if st.button("💾 Salvar Simulação (Amazon)", type="primary", use_container_width=True):
        save_simulation(
            "Amazon", 
            product_name, 
            result_no_fixed, 
            result_with_fixed if fixed["has_expenses"] else None
        )
        st.success("✅ Simulação salva com sucesso!")


def tab_shopee(fixed: dict, product_name: str):
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        # ─────────────────────────────────────────────────────────────
        # 1. DADOS DO PRODUTO
        # ─────────────────────────────────────────────────────────────
        with st.expander("📦 Dados do Produto", expanded=True):
            col_prod1, col_prod2 = st.columns(2)
            with col_prod1:
                cost = st.number_input(
                    "Preço de Custo (R$)",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                    key="sp_cost",
                    help="Quanto você pagou para comprar ou produzir o produto.",
                )
            with col_prod2:
                category = st.selectbox(
                    "Categoria",
                    list(SHOPEE["categories"].keys()),
                    key="sp_category",
                    help="Escolha a categoria para o cálculo das taxas.",
                )

        # ─────────────────────────────────────────────────────────────
        # 2. CONFIGURAÇÃO DA VENDA
        # ─────────────────────────────────────────────────────────────
        with st.expander("🛒 Configuração da Venda", expanded=True):
            col_sale1, col_sale2 = st.columns(2)
            with col_sale1:
                seller_type = st.radio(
                    "Tipo de Vendedor",
                    ["CPF", "CNPJ"],
                    horizontal=True,
                    key="sp_seller",
                    help="Taxa extra de R$3 se for CPF e vender mais de R$900/mês (estimado).",
                )
            with col_sale2:
                desired_margin = st.number_input(
                    "Margem Desejada (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=1.0,
                    format="%.1f",
                    key="sp_desired_margin",
                    help="A porcentagem de lucro que você quer colocar no bolso depois de pagar tudo.",
                )

            col_sale3, col_sale4 = st.columns(2)
            with col_sale3:
                shipping = st.number_input(
                    "Frete do Vendedor (R$)",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                    key="sp_shipping",
                    help="Coloque aqui se você paga alguma parte do frete para a Shopee."
                )
            with col_sale4:
                st.write("") # Spacer
                free_shipping = st.checkbox(
                    "Programa Frete Grátis (+6%)",
                    value=True,
                    key="sp_free_ship",
                    help="Marque se você participa do programa de Frete Grátis Extra.",
                )

        # ─────────────────────────────────────────────────────────────
        # 3. IMPOSTOS E CUSTOS EXTRAS
        # ─────────────────────────────────────────────────────────────
        with st.expander("🧾 Impostos e Custos Extras", expanded=False):
            col_tax1, col_tax2 = st.columns(2)
            with col_tax1:
                tax_pct = st.number_input(
                    "Imposto / Nota Fiscal (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=0.1,
                    format="%.1f",
                    key="sp_tax",
                    help="Imposto sobre a nota fiscal (ex: Simples Nacional).",
                )
            with col_tax2:
                extra_cost = st.number_input(
                    "Custo Extra / Embalagem (R$)",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                    key="sp_extra",
                    help="Gastos a mais por venda: Embalagem, fita, etiqueta, brinde, etc.",
                )

    result_no_fixed = calculate_shopee(
        cost, category, seller_type, free_shipping, extra_cost, shipping, tax_pct, 0.0, desired_margin, 0.0
    )

    result_with_fixed = None
    if fixed["has_expenses"]:
        result_with_fixed = calculate_shopee(
            cost, category, seller_type, free_shipping, extra_cost, shipping, tax_pct, fixed["per_unit"], desired_margin, fixed["other_pct"]
        )

    with col2:
        render_results(result_no_fixed, "📊 Resultados (Sem Despesas Fixas)")
        if result_with_fixed:
            # Removed separator
            render_results(result_with_fixed, "💼 Resultados (Com Despesas Fixas)")

    render_charts(result_no_fixed, result_with_fixed, fixed["has_expenses"], fixed["total_monthly_fixed"])

    if st.button("💾 Salvar Simulação (Shopee)", type="primary", use_container_width=True):
        save_simulation(
            "Shopee", 
            product_name, 
            result_no_fixed, 
            result_with_fixed if fixed["has_expenses"] else None
        )
        st.success("✅ Simulação salva com sucesso!")


# ─────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────
def save_simulation(platform: str, product_name: str, result_no_fixed: dict, result_with_fixed: dict | None):
    """Save the current simulation to session state."""
    
    # Determine which result to use (prefer with fixed expenses if available)
    target_result = result_with_fixed if result_with_fixed else result_no_fixed
    
    # Current timestamp
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Create record
    record = {
        "Data/Hora": timestamp,
        "Produto": product_name if product_name else "Produto Sem Nome",
        "Plataforma": platform,
        "Custo (R$)": round(target_result["total_cost"] - target_result["total_fees"] - target_result["tax"], 2), # Approx raw cost
        "Venda (R$)": target_result.get("suggested_price", 0.0), # This might be wrong, need actual sale price
        # Actually, the result dicts don't store the input sale_price directly, 
        # but we can infer it or just store what we have. 
        # Wait, the result dict DOES NOT have the sale_price input.
        # I should probably pass the sale_price to save_simulation or retrieve it from keys.
        # However, looking at the code, `result_no_fixed` has `profit`, `margin`, `total_cost`.
        # Profit = Sale - Cost. So Sale = Profit + Cost.
        "Venda (R$)": round(target_result["total_cost"] + target_result["profit"], 2),
        "Lucro (R$)": round(target_result["profit"], 2),
        "Margem (%)": round(target_result["margin"], 2),
        "ROI (%)": round(target_result["roi"], 2),
        "Custo Total (R$)": round(target_result["total_cost"], 2),
        "Taxas (R$)": round(target_result["total_fees"], 2),
        "Imposto (R$)": round(target_result["tax"], 2),
    }
    
    st.session_state["saved_simulations"].append(record)


def render_saved_simulations():
    """Render the section with saved simulations and export options."""
    st.markdown("---")
    st.markdown("## 📋 Simulações Salvas")

    if not st.session_state["saved_simulations"]:
        st.info("Nenhuma simulação salva ainda. Faça um cálculo e clique em 'Salvar Simulação'.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(st.session_state["saved_simulations"])
    
    # Reorder columns for better readability if they exist
    cols = [
        "Data/Hora", "Produto", "Plataforma", 
        "Custo (R$)", "Venda (R$)", "Lucro (R$)", 
        "Margem (%)", "ROI (%)", "Custo Total (R$)"
    ]
    # Filter only columns that actually exist in df
    cols = [c for c in cols if c in df.columns]
    # Add remaining columns
    remaining = [c for c in df.columns if c not in cols]
    df = df[cols + remaining]

    st.dataframe(df, use_container_width=True)

    c1, c2 = st.columns([1, 4])
    with c1:
        # Export button
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar CSV",
            data=csv,
            file_name=f"simulacoes_lucro_{int(time.time())}.csv",
            mime="text/csv",
        )
    with c2:
        if st.button("🗑️ Limpar Lista"):
            st.session_state["saved_simulations"] = []
            st.rerun()


def render_calculator_view(product_name: str):
    # inject_css() -> Moved to main()

    # Hero header
    # Navbar -> Moved to main() as interactive components

    # Global Inputs
    # Global Inputs (Moved outside if shared, or kept here if specific)
    # The prompt implies these are part of the "Calculadora de Venda".
    # I'll keep them here for now, but `product_name` was passed in.
    # Actually, `product_name` definition was inside main. 
    # I should remove the argument from my new function and keep it inside?
    # Or pass it? The original `main` had it inside.
    # Let's keep it inside `render_calculator_view` for now, but user might want it shared?
    # User said "queria criar uma outra aba para outro programa".
    # So "Organização" is likely independent of the "Product" being calculated.
    # I will keep `product_name` inside `render_calculator_view`.
    
    # Wait, I replaced `def main():` with `def render_calculator_view(product_name: str):`.
    # But `product_name` is defined INSIDE.
    # So I should remove the arg from the signature I just proposed.
    pass

    with st.container():
        st.markdown('<div class="glass-container">', unsafe_allow_html=True)
        # Re-defining product_name here as it was in original
        product_name_input = st.text_input(
            "📦 Nome do Produto / SKU (Opcional)", 
            placeholder="Ex: Fone Bluetooth XYZ", 
            help="Nome para você identificar este cálculo depois na lista de simulações salvas.",
            value=product_name if product_name else ""
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
    product_name = product_name_input

    # Fixed expenses section (shared across all tabs)
    fixed = render_fixed_expenses()

    if fixed["has_expenses"]:
        st.markdown(
            f"""
            <div class="glass-container" style="text-align:center; padding:14px 24px;">
                <span style="color:#a1a1aa; font-size:13px;">
                    Despesas fixas: <b style="color:#ff9f0a;">R$ {fixed['total_monthly']:,.2f}/mês</b>
                    &nbsp;→&nbsp; Custo por unidade:
                    <b style="color:#0a84ff;">R$ {fixed['per_unit']:,.2f}</b>
                    <span style="color:#666; font-size:12px;">
                        (baseado em {fixed['estimated_sales']} vendas/mês)
                    </span>
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    # Tabs
    tab1, tab2, tab3 = st.tabs(["Mercado Livre", "Amazon", "Shopee"])

    with tab1:
        tab_mercado_livre(fixed, product_name)
    with tab2:
        tab_amazon(fixed, product_name)
    with tab3:
        tab_shopee(fixed, product_name)
        
    # Saved Simulations Section
    render_saved_simulations()

    # Footer
    # Footer -> Moved to main()



def render_financial_view():
    st.markdown("## 📂 Organização Financeira")
    st.info("Faça upload de uma planilha (CSV) para análise de gastos com IA.")

    # 1. Upload
    uploaded_file = st.file_uploader("Upload CSV Financeiro", type=["csv"])
    
    # 2. API Key (Password)
    api_key = st.text_input("🔑 Google Gemini API Key", type="password", help="Obtenha sua chave no Google AI Studio.")
    
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
            st.write("### 🔍 Prévia dos Dados")
            st.dataframe(df.head(), use_container_width=True)
            
            if api_key and st.button("🚀 Analisar com IA", type="primary"):
                with st.spinner("🤖 A IA está analisando seus gastos..."):
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-1.5-pro')
                    
                    # Convert sample to CSV string for prompt
                    csv_string = df.to_csv(index=False)
                    
                    prompt = f"""
                    Você é um analista financeiro experiente. Analise os dados financeiros abaixo (formato CSV).
                    
                    TAREFAS:
                    1. Identifique as colunas de 'Descrição/Empresa' e 'Valor'. Se não estiver claro, tente inferir.
                    2. Categorize cada transação em categorias úteis (ex: Marketing, Fornecedores, Impostos, Logística, Pessoal, Outros).
                    3. Gere um resumo com:
                       - Total Gasto
                       - Maior Despesa (Nome e Valor)
                       - Gasto por Categoria (Totais)
                    
                    DADOS CSV:
                    {csv_string}
                    
                    FORMATO DE RESPOSTA (JSON):
                    Retorne APENAS um JSON válido seguindo esta estrutura, sem markdown (```json ... ```):
                    {{
                        "total_spent": float,
                        "biggest_expense": {{ "name": string, "value": float }},
                        "categories": {{ "Category Name": float, ... }},
                        "analysis_summary": "Breve texto descrevendo os principais insights."
                    }}
                    """
                    
                    try:
                        response = model.generate_content(prompt)
                        result_text = response.text
                        
                        # Cleanup markdown code blocks if present
                        if "```json" in result_text:
                            import re
                            match = re.search(r"```json\s*(.*?)\s*```", result_text, re.DOTALL)
                            if match:
                                result_text = match.group(1)
                        elif "```" in result_text:
                             match = re.search(r"```\s*(.*?)\s*```", result_text, re.DOTALL)
                             if match:
                                result_text = match.group(1)
                                
                        import json
                        data = json.loads(result_text)
                        
                        # Display Results
                        st.divider()
                        st.subheader("📊 Relatório Financeiro Inteligente")
                        
                        kpi1, kpi2 = st.columns(2)
                        with kpi1:
                            st.metric("Total Gasto", f"R$ {data.get('total_spent', 0):,.2f}")
                        with kpi2:
                            biggest = data.get('biggest_expense', {})
                            st.metric("Maior Despesa", f"{biggest.get('name', 'N/A')}", f"R$ {biggest.get('value', 0):,.2f}")
                            
                        st.caption(data.get("analysis_summary", ""))
                        
                        # Charts
                        cats = data.get("categories", {})
                        if cats:
                            # Convert to DF for chart
                            cat_df = pd.DataFrame(list(cats.items()), columns=["Categoria", "Valor"])
                            
                            fig = go.Figure(data=[go.Pie(labels=cat_df["Categoria"], values=cat_df["Valor"], hole=.3)])
                            fig.update_layout(title_text="Distribuição de Gastos por Categoria", **CHART_LAYOUT)
                            st.plotly_chart(fig, use_container_width=True)
                            
                            st.bar_chart(cat_df.set_index("Categoria"))

                    except Exception as e:
                        st.error(f"Erro na análise da IA: {e}")
                        
        except Exception as e:
            st.error(f"Erro ao ler CSV: {e}")


def main():
    inject_css()
    
    if "current_view" not in st.session_state:
        st.session_state["current_view"] = "calculator"

    # Navbar Logic
    # We use columns to create buttons that look like a navbar
    st.markdown(
        """
        <style>
        div.row-widget.stButton > button {
            width: 100%;
            border-radius: 0px;
            height: 3em;
            background-color: transparent;
            border: none;
            border-bottom: 2px solid transparent;
            color: #555;
            font-weight: 600;
        }
        div.row-widget.stButton > button:hover {
            color: #000;
            background-color: #f0f2f6;
        }
        div.row-widget.stButton > button:focus {
            box-shadow: none;
            color: #000;
        }
        </style>
        """, unsafe_allow_html=True
    )
    
    # Header/Navbar
    # Using a container with custom styling for the navbar background
    with st.container():
        st.markdown('<div class="navbar" style="padding-bottom: 0px; margin-bottom: 10px; display:block;">', unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns([1, 2, 2])
        
        with c1:
             st.markdown('<div style="font-size: 24px;">🧮</div>', unsafe_allow_html=True)
             
        with c2:
            if st.button("Calculadora de Venda", type="primary" if st.session_state["current_view"] == "calculator" else "secondary", use_container_width=True):
                st.session_state["current_view"] = "calculator"
                st.rerun()
                
        with c3:
            if st.button("Organização Financeira", type="primary" if st.session_state["current_view"] == "financial" else "secondary", use_container_width=True):
                st.session_state["current_view"] = "financial"
                st.rerun()
                
        st.markdown('</div>', unsafe_allow_html=True)

    # View Routing
    if st.session_state["current_view"] == "calculator":
        render_calculator_view("") # Pass empty string or handle logic inside
    elif st.session_state["current_view"] == "financial":
        render_financial_view()

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; color: #666; font-size: 12px;">
            <p>
                Calculadora de Lucro & Organização Financeira. 
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()



