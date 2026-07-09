"""
Dividend Growth Model (Gordon Growth Model) — Live Stock Valuation
-------------------------------------------------------------------
Intro finance (BA300 / MBA) teaching tool.

Core equation (used everywhere in this app):
        P0 = D1 / (r - g),   where  D1 = D0 * (1 + g)

Two goals, both handled with the SAME dividend model:

  GOAL 1  Estimate the required return (cost of equity):
          solve the model for r  ->   r = D1 / P0 + g   (dividend yield + growth)
          Live market price is the INPUT; r is the OUTPUT. No CAPM needed.

  GOAL 2  Determine the intrinsic market price (valuation):
          solve the model for P0 ->   P0 = D1 / (r - g)
          r is an INPUT (given/assumed, independent of today's price); P0 is the OUTPUT.

  Why separate tabs? If you take r from Goal 1 (which used today's price) and plug it
  back into Goal 2, you just recover today's price -- circular. So they are kept apart.

Live data via yfinance (runs server-side on Streamlit Cloud -- no API key).
"""

import datetime as dt

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Dividend Growth Model Valuation", page_icon="📈", layout="wide")


# ----------------------------------------------------------------------------
# Data helpers (cached to reduce Yahoo rate-limiting during a class demo)
# ----------------------------------------------------------------------------
@st.cache_data(ttl=900, show_spinner=False)
def load_stock(ticker: str):
    """Fetch everything we need for one ticker. Returns a dict of raw data."""
    tk = yf.Ticker(ticker)

    price = None
    currency = None
    try:
        price = float(tk.fast_info["last_price"])
        currency = tk.fast_info.get("currency")
    except Exception:
        pass

    info = {}
    try:
        info = tk.info or {}
    except Exception:
        info = {}

    if price is None:
        price = info.get("currentPrice") or info.get("regularMarketPrice")
    if price is None:
        try:
            hist = tk.history(period="5d")
            if not hist.empty:
                price = float(hist["Close"].dropna().iloc[-1])
        except Exception:
            pass
    if currency is None:
        currency = info.get("currency", "USD")

    name = info.get("longName") or info.get("shortName") or ticker.upper()

    try:
        divs = tk.dividends
    except Exception:
        divs = pd.Series(dtype=float)

    # trailing 12-month dividend (D0): sum of payments in the last 365 days
    d0 = 0.0
    if divs is not None and not divs.empty:
        cutoff = pd.Timestamp.now(tz=divs.index.tz) - pd.Timedelta(days=365)
        d0 = float(divs[divs.index >= cutoff].sum())
    if d0 == 0.0:
        d0 = float(info.get("trailingAnnualDividendRate") or info.get("dividendRate") or 0.0)

    return {
        "ticker": ticker.upper(),
        "name": name,
        "price": price,
        "currency": currency or "USD",
        "dividends": divs,
        "d0": d0,
        "roe": info.get("returnOnEquity"),
        "payout": info.get("payoutRatio"),
    }


def annual_dividends(divs: pd.Series) -> pd.Series:
    """Sum dividend payments by calendar year, dropping the current (incomplete) year."""
    if divs is None or divs.empty:
        return pd.Series(dtype=float)
    yearly = divs.groupby(divs.index.year).sum()
    this_year = dt.date.today().year
    if this_year in yearly.index:
        yearly = yearly.drop(this_year)
    return yearly


def historical_cagr(yearly: pd.Series, window: int):
    """Compound annual growth rate of dividends over the last `window` full years."""
    if yearly is None or len(yearly) < 2:
        return None, None
    series = yearly.tail(window + 1)
    series = series[series > 0]
    if len(series) < 2:
        return None, None
    start, end = series.iloc[0], series.iloc[-1]
    years = series.index[-1] - series.index[0]
    if start <= 0 or years <= 0:
        return None, None
    return (end / start) ** (1 / years) - 1, series


def fmt_pct(x):
    return "—" if x is None else f"{x * 100:.2f}%"


def money(x, cur="USD"):
    return "—" if x is None else f"{x:,.2f} {cur}"


# ----------------------------------------------------------------------------
# Sidebar — inputs
# ----------------------------------------------------------------------------
st.sidebar.title("📈 Inputs")
ticker = st.sidebar.text_input("Ticker symbol", value="KO").strip().upper()
go = st.sidebar.button("Fetch live data", type="primary", use_container_width=True)
st.sidebar.caption(
    "Dividend-paying, mature companies work best (e.g. KO, PG, JNJ, PEP, MMM, XOM). "
    "High-growth / non-dividend stocks won't fit this model."
)

if "loaded" not in st.session_state:
    st.session_state.loaded = False
if go and ticker:
    st.session_state.loaded = True
    st.session_state.ticker = ticker

# ----------------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------------
st.title("Dividend Growth Model — Live Stock Valuation")
st.markdown(
    "One model, two goals: **estimate the required return** *and* **estimate the intrinsic price**, "
    r"both from $P_0 = \dfrac{D_1}{r - g}$ with $D_1 = D_0(1+g)$. "
    "Every input is shown with the **actual live data** used."
)

if not st.session_state.loaded:
    st.info("Enter a ticker in the sidebar and click **Fetch live data** to begin.")
    st.stop()

data = load_stock(st.session_state.ticker)
if data["price"] is None:
    st.error(f"Could not retrieve a price for **{st.session_state.ticker}**. "
             "Yahoo may be rate-limiting, or the ticker is invalid. Try again in a moment.")
    st.stop()

cur = data["currency"]

c1, c2, c3 = st.columns([2, 1, 1])
c1.subheader(f"{data['name']}  ·  {data['ticker']}")
c2.metric("Live market price  P₀", money(data["price"], cur))
c3.metric("Trailing dividend  D₀", money(data["d0"], cur))

if data["d0"] <= 0:
    st.warning(
        "This company shows **no trailing dividend**, so the Dividend Growth Model does not apply. "
        "Try a mature dividend payer."
    )
    st.stop()

st.divider()

# ----------------------------------------------------------------------------
# SHARED 1 · Dividend data
# ----------------------------------------------------------------------------
st.header("Dividend data (the raw inputs)")
yearly = annual_dividends(data["dividends"])
col_a, col_b = st.columns([1, 1])
with col_a:
    st.markdown(f"**Trailing 12-month dividend D₀ = {money(data['d0'], cur)}**")
    st.caption("Sum of the actual dividend payments over the last 365 days.")
    if not yearly.empty:
        tbl = yearly.rename("Dividend / share").to_frame()
        tbl.index.name = "Year"
        st.dataframe(tbl.style.format("{:.4f}"), use_container_width=True, height=240)
with col_b:
    if not yearly.empty:
        st.markdown("**Dividend per share by year**")
        st.bar_chart(yearly, height=300)
    else:
        st.caption("No multi-year dividend history available from the data source.")

st.divider()

# ----------------------------------------------------------------------------
# SHARED 2 · Growth rate g (feeds BOTH goals)
# ----------------------------------------------------------------------------
st.header("Dividend growth rate  g")
st.caption("Estimated once, then used by both goals below. Data behind each method is shown.")

window = st.slider("Years of history for CAGR", 3, 10, 5)
cagr, cagr_series = historical_cagr(yearly, window)

roe, payout = data["roe"], data["payout"]
sustainable = roe * (1 - payout) if (roe is not None and payout is not None and 0 <= payout <= 1) else None

m1, m2, m3 = st.columns(3)
with m1:
    st.markdown("**A. Historical CAGR**")
    if cagr is not None:
        st.metric("g (historical)", fmt_pct(cagr))
        st.caption(f"From {int(cagr_series.index[0])} ({cagr_series.iloc[0]:.4f}) "
                   f"to {int(cagr_series.index[-1])} ({cagr_series.iloc[-1]:.4f}).")
    else:
        st.caption("Not enough dividend history for a CAGR.")
with m2:
    st.markdown("**B. Sustainable growth**")
    st.caption("g = ROE × (1 − payout ratio)")
    if sustainable is not None:
        st.metric("g (sustainable)", fmt_pct(sustainable))
        st.caption(f"ROE = {fmt_pct(roe)}  ·  payout = {fmt_pct(payout)}")
    else:
        st.caption("ROE or payout ratio unavailable from the data source.")
with m3:
    st.markdown("**C. Manual**")
    st.caption("Your own / analyst estimate.")
    manual_g = st.number_input("g (manual, %)", value=5.0, step=0.25, format="%.2f") / 100

method = st.radio("Use this growth rate:",
                  ["Historical CAGR", "Sustainable growth", "Manual"], horizontal=True)
if method == "Historical CAGR" and cagr is not None:
    g = cagr
elif method == "Sustainable growth" and sustainable is not None:
    g = sustainable
else:
    g = manual_g
    if method != "Manual":
        st.info("Selected method has no data available; falling back to the manual value.")
st.success(f"**g in use = {fmt_pct(g)}**")

st.divider()

# ----------------------------------------------------------------------------
# THE TWO GOALS
# ----------------------------------------------------------------------------
tab_r, tab_p = st.tabs(["🎯 Goal 1 · Required Return (Cost of Equity)",
                        "🎯 Goal 2 · Stock Valuation (Intrinsic Price)"])

# ---- GOAL 1: required return -----------------------------------------------
with tab_r:
    st.subheader("Estimate the required return with the dividend model")
    st.markdown(
        r"Rearranging $P_0 = \dfrac{D_1}{r-g}$ for $r$ gives the "
        r"**dividend-growth-model cost of equity**:  $r = \dfrac{D_1}{P_0} + g$ "
        "(expected dividend yield + growth). The live price is the input; **r is the output**. "
        "This is a standard alternative to CAPM."
    )

    d1 = data["d0"] * (1 + g)
    div_yield = d1 / data["price"]
    r_est = div_yield + g

    x1, x2, x3, x4 = st.columns(4)
    x1.metric("D₁ = D₀ (1+g)", money(d1, cur))
    x2.metric("Live price  P₀", money(data["price"], cur))
    x3.metric("Dividend yield  D₁/P₀", fmt_pct(div_yield))
    x4.metric("Required return  r", fmt_pct(r_est))

    st.latex(r"r = \frac{D_1}{P_0} + g = \frac{%.4f}{%.2f} + %.4f = %.2f\%%"
             % (d1, data["price"], g, r_est * 100))

    st.info(
        "This r is the total return the market currently offers on the stock, given your g. "
        "**Do not** turn around and plug this r into Goal 2 to value the same stock at today's price — "
        "you would just recover the current price (that's the circularity we avoid by separating the goals)."
    )

# ---- GOAL 2: valuation -----------------------------------------------------
with tab_p:
    st.subheader("Estimate the intrinsic price with the dividend model")
    st.markdown(
        r"$P_0 = \dfrac{D_1}{r-g}$. Here **r is an input** — enter an instructor-given or assumed "
        "required return that does **not** come from today's price — and **P₀ is the output**, "
        "which we compare to the live market price."
    )

    rc1, rc2 = st.columns([1, 1])
    with rc1:
        r = st.number_input("Required return r (%)", value=9.0, step=0.25, format="%.2f") / 100
    with rc2:
        st.caption("Use a rate independent of today's price: instructor-given, a class assumption, "
                   "or a bond-yield-plus-premium rule. (CAPM is one common source, but not used here.)")

    if g >= r:
        st.error(
            f"**g ({fmt_pct(g)}) ≥ r ({fmt_pct(r)}).** The model is undefined "
            "(it assumes growth stays below the required return forever). Lower g or raise r."
        )
    else:
        d1 = data["d0"] * (1 + g)
        p0 = d1 / (r - g)
        gap = (p0 - data["price"]) / data["price"]

        v1, v2, v3, v4 = st.columns(4)
        v1.metric("D₁ = D₀ (1+g)", money(d1, cur))
        v2.metric("Intrinsic value  P₀", money(p0, cur))
        v3.metric("Live price", money(data["price"], cur))
        v4.metric("Gap vs price", f"{gap * 100:+.1f}%")

        st.latex(r"P_0 = \frac{D_1}{r - g} = \frac{%.4f}{%.4f - %.4f} = %.2f"
                 % (d1, r, g, p0))

        if gap > 0.10:
            st.success(f"**Undervalued** by {gap*100:.1f}% — model value exceeds market price.")
        elif gap < -0.10:
            st.error(f"**Overvalued** by {abs(gap)*100:.1f}% — model value below market price.")
        else:
            st.info(f"**Roughly fairly valued** (within 10%). Gap = {gap*100:+.1f}%.")

        st.markdown("##### Sensitivity — how P₀ moves with r and g")
        st.caption("Gordon's output swings a lot with small input changes. Blank = g ≥ r (undefined).")
        r_range = np.round(np.linspace(max(r - 0.02, 0.01), r + 0.02, 5), 4)
        g_range = np.round(np.linspace(max(g - 0.02, -0.01), g + 0.02, 5), 4)
        grid = pd.DataFrame(index=[f"g={gg*100:.1f}%" for gg in g_range],
                            columns=[f"r={rr*100:.1f}%" for rr in r_range], dtype=float)
        for gg in g_range:
            for rr in r_range:
                grid.loc[f"g={gg*100:.1f}%", f"r={rr*100:.1f}%"] = (
                    (data["d0"] * (1 + gg)) / (rr - gg) if rr > gg else np.nan)
        st.dataframe(grid.style.format("{:.2f}").background_gradient(cmap="RdYlGn", axis=None),
                     use_container_width=True)
        st.caption(f"Current live price for comparison: **{money(data['price'], cur)}**")

        st.markdown("##### Reverse check — what growth is the market pricing in?")
        implied_g = (data["price"] * r - data["d0"]) / (data["price"] + data["d0"])
        ig1, ig2 = st.columns([1, 2])
        ig1.metric("Implied growth  g", fmt_pct(implied_g))
        ig2.caption(
            f"Given the live price and r = {fmt_pct(r)}, the market implicitly assumes dividends grow "
            f"about **{fmt_pct(implied_g)}** forever. Compare to the historical and sustainable "
            "estimates above — an unrealistic implied growth is your mispricing signal."
        )

# ----------------------------------------------------------------------------
with st.expander("⚠️  Model limitations & disclaimer"):
    st.markdown(
        "- The Gordon Growth Model assumes a stable dividend payer and one constant growth rate forever.\n"
        "- Output is **highly sensitive** to r and g (see the sensitivity table).\n"
        "- It breaks down for non-payers and whenever g ≥ r.\n"
        "- Live Yahoo data can have gaps or delays.\n"
        "- **Educational tool, not investment advice.**"
    )
