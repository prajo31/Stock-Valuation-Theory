"""
Dividend Growth Model (Gordon Growth Model) — Live Stock Valuation
-------------------------------------------------------------------
Intro finance (BA300 / MBA) teaching tool.

Core equation:   P0 = D1 / (r - g),   where  D1 = D0 * (1 + g)

Goal 1  Cost of equity, two ways: CAPM (r = Rf + beta*ERP) and DDM (r = D1/P0 + g).
Goal 2  Intrinsic price P0 = D1/(r - g), with guardrails:
          - g-ceiling check (g must be a sane perpetual rate)
          - fragile-zone warning when r - g is tiny
          - intrinsic-value RANGE + margin-of-safety band (not a single false-precision number)
Goal 3  Triangulate: check the GGM verdict against INDEPENDENT signals
          (analyst target, dividend yield vs its 5-yr average, P/E vs a benchmark).

Main file: ddm_valuation.py  (deploy this as the Streamlit entry point).
Live data via yfinance (runs server-side on Streamlit Cloud -- no API key).
"""

import datetime as dt

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Dividend Growth Model Valuation", page_icon="📈", layout="wide")


# ----------------------------------------------------------------------------
# Data helpers
# ----------------------------------------------------------------------------
@st.cache_data(ttl=900, show_spinner=False)
def load_stock(ticker: str):
    tk = yf.Ticker(ticker)
    price = currency = None
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
    currency = currency or info.get("currency", "USD")
    name = info.get("longName") or info.get("shortName") or ticker.upper()
    try:
        divs = tk.dividends
    except Exception:
        divs = pd.Series(dtype=float)
    d0 = 0.0
    if divs is not None and not divs.empty:
        cutoff = pd.Timestamp.now(tz=divs.index.tz) - pd.Timedelta(days=365)
        d0 = float(divs[divs.index >= cutoff].sum())
    if d0 == 0.0:
        d0 = float(info.get("trailingAnnualDividendRate") or info.get("dividendRate") or 0.0)
    return {
        "ticker": ticker.upper(), "name": name, "price": price, "currency": currency or "USD",
        "dividends": divs, "d0": d0,
        "roe": info.get("returnOnEquity"), "payout": info.get("payoutRatio"),
        "beta": info.get("beta"),
        "target": info.get("targetMeanPrice"), "n_analysts": info.get("numberOfAnalystOpinions"),
        "trailing_pe": info.get("trailingPE"), "forward_pe": info.get("forwardPE"),
        "avg_div_yield5": info.get("fiveYearAvgDividendYield"),  # percent, e.g. 3.05
    }


@st.cache_data(ttl=900, show_spinner=False)
def load_treasury():
    """Live 10-year US Treasury yield (^TNX) as a decimal, e.g. 0.045."""
    try:
        tnx = yf.Ticker("^TNX")
        raw = None
        try:
            raw = float(tnx.fast_info["last_price"])
        except Exception:
            hist = tnx.history(period="5d")
            if not hist.empty:
                raw = float(hist["Close"].dropna().iloc[-1])
        if raw is None:
            return None
        if raw > 20:            # guard the older x10 convention (~45)
            raw = raw / 10.0
        return raw / 100.0
    except Exception:
        return None


def annual_dividends(divs):
    if divs is None or divs.empty:
        return pd.Series(dtype=float)
    yearly = divs.groupby(divs.index.year).sum()
    if dt.date.today().year in yearly.index:
        yearly = yearly.drop(dt.date.today().year)
    return yearly


def historical_cagr(yearly, window):
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
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:,.2f} {cur}"


def ggm_price(d0, g, r):
    return (d0 * (1 + g)) / (r - g) if r > g else np.nan


def verdict_from_gap(gap, cheap_if_high=True, thr=0.10):
    """Classify a relative gap into Cheap / Fair / Expensive."""
    if gap is None or np.isnan(gap):
        return "—"
    hi, lo = ("🟢 Cheap", "🔴 Expensive") if cheap_if_high else ("🔴 Expensive", "🟢 Cheap")
    if gap > thr:
        return hi
    if gap < -thr:
        return lo
    return "🟡 Fair"


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
st.sidebar.title("📈 Inputs")
ticker = st.sidebar.text_input("Ticker symbol", value="KO").strip().upper()
go = st.sidebar.button("Fetch live data", type="primary", use_container_width=True)
st.sidebar.caption("Mature dividend payers work best (KO, PG, JNJ, PEP, MMM, XOM). "
                   "Non-dividend / high-growth stocks won't fit this model.")

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
    "One model, three goals: **estimate the required return** (CAPM & dividend-model), "
    "**estimate the intrinsic price** (with guardrails), and **triangulate** the verdict against "
    r"independent signals. Core: $P_0 = \dfrac{D_1}{r - g}$, $D_1 = D_0(1+g)$."
)

if not st.session_state.loaded:
    st.info("Enter a ticker in the sidebar and click **Fetch live data** to begin.")
    st.stop()

data = load_stock(st.session_state.ticker)
if data["price"] is None:
    st.error(f"Could not retrieve a price for **{st.session_state.ticker}**. "
             "Yahoo may be rate-limiting, or the ticker is invalid. Try again shortly.")
    st.stop()

cur = data["currency"]
c1, c2, c3 = st.columns([2, 1, 1])
c1.subheader(f"{data['name']}  ·  {data['ticker']}")
c2.metric("Live market price  P₀", money(data["price"], cur))
c3.metric("Trailing dividend  D₀", money(data["d0"], cur))

if data["d0"] <= 0:
    st.warning("This company shows **no trailing dividend**, so the Dividend Growth Model does not "
               "apply. Try a mature dividend payer.")
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
# SHARED 2 · Growth rate g  (+ g-ceiling guardrail)
# ----------------------------------------------------------------------------
st.header("Dividend growth rate  g")
st.caption("Estimated once, then used by both goals. Data behind each method is shown.")

window = st.slider("Years of history for CAGR", 3, 10, 5)
cagr, cagr_series = historical_cagr(yearly, window)
roe, payout = data["roe"], data["payout"]
sustainable = roe * (1 - payout) if (roe is not None and payout is not None and 0 <= payout <= 1) else None

m1, m2, m3 = st.columns(3)
with m1:
    st.markdown("**A. Historical CAGR**")
    st.caption("g = (D_end / D_start)^(1/n) − 1")
    if cagr is not None:
        st.metric("g (historical)", fmt_pct(cagr))
        n_years = int(cagr_series.index[-1] - cagr_series.index[0])
        st.caption(f"= ({cagr_series.iloc[-1]:.4f} / {cagr_series.iloc[0]:.4f})^(1/{n_years}) − 1\n\n"
                   f"D_start = {cagr_series.iloc[0]:.4f} ({int(cagr_series.index[0])})  ·  "
                   f"D_end = {cagr_series.iloc[-1]:.4f} ({int(cagr_series.index[-1])})  ·  n = {n_years} yrs")
    else:
        st.caption("Not enough dividend history for a CAGR.")
with m2:
    st.markdown("**B. Sustainable growth**")
    st.caption("g = ROE × (1 − payout ratio)")
    if sustainable is not None:
        st.metric("g (sustainable)", fmt_pct(sustainable))
        st.caption(f"= {fmt_pct(roe)} × (1 − {fmt_pct(payout)})\n\n"
                   f"ROE = {fmt_pct(roe)}  ·  payout = {fmt_pct(payout)}")
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

gc1, gc2 = st.columns([1, 2])
gdp_ceiling = gc1.number_input("Long-run growth ceiling (nominal-GDP proxy, %)",
                               value=4.5, step=0.25, format="%.2f") / 100
gc2.caption("No firm outgrows the whole economy forever, so a *perpetual* g should sit at or below "
            "roughly nominal GDP growth (~4–5%).")
st.success(f"**g in use = {fmt_pct(g)}**")
if g > gdp_ceiling:
    st.warning(f"⚠️ g in use ({fmt_pct(g)}) exceeds the {fmt_pct(gdp_ceiling)} long-run ceiling. "
               "As a perpetual rate this is likely too high — it can make r − g tiny and inflate P₀. "
               "Consider a lower terminal g.")

st.divider()

# ----------------------------------------------------------------------------
# TABS
# ----------------------------------------------------------------------------
tab_r, tab_p, tab_tri = st.tabs([
    "🎯 Goal 1 · Required Return", "🎯 Goal 2 · Valuation", "🔺 Goal 3 · Triangulate"])

p0 = None
gap = None
r = None

# ---- GOAL 1 ----------------------------------------------------------------
with tab_r:
    st.subheader("Cost of equity — two independent methods")
    d1 = data["d0"] * (1 + g)
    left, right = st.columns(2)
    with left:
        st.markdown("### A · CAPM")
        st.caption("r = R_f + β × ERP")
        live_rf = load_treasury()
        rf_default = round((live_rf if live_rf is not None else 0.045) * 100, 2)
        st.caption(f"Live 10-yr Treasury (^TNX) = **{fmt_pct(live_rf)}** — editable." if live_rf is not None
                   else "Live Treasury unavailable; 4.50% fallback — editable.")
        rf = st.number_input("Risk-free rate R_f (%)", value=rf_default, step=0.05, format="%.2f", key="rf") / 100
        beta_live = data["beta"]
        beta_default = round(beta_live, 2) if beta_live is not None else 1.00
        st.caption(f"Live beta (Yahoo) = **{beta_live:.2f}** — editable." if beta_live is not None
                   else "Beta unavailable; 1.00 — editable.")
        beta = st.number_input("Beta β", value=float(beta_default), step=0.05, format="%.2f", key="beta")
        erp = st.number_input("Equity risk premium ERP (%)", value=5.00, step=0.25, format="%.2f", key="erp",
                              help="An assumption, not a live figure. ~4.5–5.5% is common (Damodaran).") / 100
        r_capm = rf + beta * erp
        st.metric("Cost of equity  r (CAPM)", fmt_pct(r_capm))
        st.latex(r"r = R_f + \beta \times ERP = %.2f\%% + %.2f \times %.2f\%% = %.2f\%%"
                 % (rf * 100, beta, erp * 100, r_capm * 100))
    with right:
        st.markdown("### B · Dividend-model approach")
        st.caption("r = D₁/P₀ + g")
        div_yield = d1 / data["price"]
        r_ddm = div_yield + g
        st.metric("Cost of equity  r (DDM)", fmt_pct(r_ddm))
        st.latex(r"r = \frac{D_1}{P_0} + g = \frac{%.4f}{%.2f} + %.4f = %.2f\%%"
                 % (d1, data["price"], g, r_ddm * 100))
        st.caption(f"D₁ = {money(d1, cur)}  ·  live P₀ = {money(data['price'], cur)}  ·  "
                   f"yield = {fmt_pct(div_yield)}  ·  g = {fmt_pct(g)}")
    st.info(f"**CAPM {fmt_pct(r_capm)} vs. dividend model {fmt_pct(r_ddm)}** — gap {fmt_pct(abs(r_capm - r_ddm))}. "
            "Two independent methods disagreeing is itself informative. Pick which r to use on the Valuation tab.")

# ---- GOAL 2 ----------------------------------------------------------------
with tab_p:
    st.subheader("Intrinsic price — with guardrails")
    st.markdown(r"$P_0 = \dfrac{D_1}{r-g}$ — r is an input, P₀ is the output.")
    source = st.radio("Required return r to use:",
                      [f"CAPM  ({fmt_pct(r_capm)})", f"DDM approach  ({fmt_pct(r_ddm)})", "Manual"],
                      horizontal=True)
    if source.startswith("CAPM"):
        r = r_capm
        st.caption("CAPM r is independent of today's price — a clean input for valuation.")
    elif source.startswith("DDM"):
        r = r_ddm
        st.warning("The DDM-approach r came from today's price, so it will mechanically return that "
                   "price (circular) — it can't reveal mispricing.")
    else:
        r = st.number_input("Manual r (%)", value=9.0, step=0.25, format="%.2f") / 100

    if g >= r:
        st.error(f"**g ({fmt_pct(g)}) ≥ r ({fmt_pct(r)}).** Model undefined. Lower g or raise r.")
    else:
        d1 = data["d0"] * (1 + g)
        p0 = ggm_price(data["d0"], g, r)
        gap = (p0 - data["price"]) / data["price"]

        spread = r - g
        if spread < 0.02:
            st.warning(f"⚠️ **Fragile zone:** r − g = {fmt_pct(spread)} (below 2%). P₀ is hypersensitive "
                       "here — a small input error swings value sharply. Trust the range below, not the point.")

        v1, v2, v3, v4 = st.columns(4)
        v1.metric("D₁ = D₀ (1+g)", money(d1, cur))
        v2.metric("Intrinsic value  P₀", money(p0, cur))
        v3.metric("Live price", money(data["price"], cur))
        v4.metric("Gap vs price", f"{gap * 100:+.1f}%")
        st.latex(r"P_0 = \frac{D_1}{r - g} = \frac{%.4f}{%.4f - %.4f} = %.2f" % (d1, r, g, p0))

        if gap > 0.10:
            st.success(f"**Undervalued** by {gap*100:.1f}% (base case).")
        elif gap < -0.10:
            st.error(f"**Overvalued** by {abs(gap)*100:.1f}% (base case).")
        else:
            st.info(f"**Roughly fairly valued** (within 10%). Gap = {gap*100:+.1f}%.")

        # --- value range + margin of safety
        st.markdown("##### Intrinsic-value range & margin of safety")
        b1, b2 = st.columns(2)
        band = b1.number_input("Input band ± (pp on r and g)", value=1.0, step=0.25, format="%.2f") / 100
        mos = b2.number_input("Margin of safety (%)", value=25.0, step=5.0, format="%.1f") / 100
        p0_cons = ggm_price(data["d0"], g - band, r + band)          # pessimistic
        p0_opt = ggm_price(data["d0"], g + band, r - band)           # optimistic (may be undefined)
        rng1, rng2, rng3 = st.columns(3)
        rng1.metric("Conservative P₀", money(p0_cons, cur))
        rng2.metric("Base P₀", money(p0, cur))
        rng3.metric("Optimistic P₀", "undefined (r ≤ g)" if np.isnan(p0_opt) else money(p0_opt, cur))
        buy_below = p0 * (1 - mos)
        st.caption(f"Buy-below price at a {fmt_pct(mos)} margin of safety = base P₀ × (1 − MoS) "
                   f"= {money(buy_below, cur)}.")
        if data["price"] <= buy_below:
            st.success(f"Live price {money(data['price'], cur)} is **below** the buy-below threshold "
                       f"{money(buy_below, cur)} — clears the margin-of-safety test.")
        else:
            st.info(f"Live price {money(data['price'], cur)} is **above** the buy-below threshold "
                    f"{money(buy_below, cur)} — does **not** clear the margin of safety, even if the base "
                    "case looks cheap.")

        # --- sensitivity
        st.markdown("##### Sensitivity — how P₀ moves with r and g")
        st.caption("Blank = g ≥ r (undefined).")
        r_range = np.round(np.linspace(max(r - 0.02, 0.01), r + 0.02, 5), 4)
        g_range = np.round(np.linspace(max(g - 0.02, -0.01), g + 0.02, 5), 4)
        grid = pd.DataFrame(index=[f"g={gg*100:.1f}%" for gg in g_range],
                            columns=[f"r={rr*100:.1f}%" for rr in r_range], dtype=float)
        for gg in g_range:
            for rr in r_range:
                grid.loc[f"g={gg*100:.1f}%", f"r={rr*100:.1f}%"] = ggm_price(data["d0"], gg, rr)
        st.dataframe(grid.style.format("{:.2f}").background_gradient(cmap="RdYlGn", axis=None),
                     use_container_width=True)
        st.caption(f"Current live price for comparison: **{money(data['price'], cur)}**")

        # --- reverse check
        st.markdown("##### Reverse check — what growth is the market pricing in?")
        st.caption("g = (P₀·r − D₀) / (P₀ + D₀)")
        implied_g = (data["price"] * r - data["d0"]) / (data["price"] + data["d0"])
        st.latex(r"g = \frac{P_0 r - D_0}{P_0 + D_0} = \frac{%.2f \times %.4f - %.4f}{%.2f + %.4f} = %.2f\%%"
                 % (data["price"], r, data["d0"], data["price"], data["d0"], implied_g * 100))
        st.caption(f"The market implicitly assumes ~**{fmt_pct(implied_g)}** growth vs. your {fmt_pct(g)}. "
                   "If yours is far above the market's and above the historical/sustainable figures, the "
                   "'undervaluation' may just be an optimistic input.")

# ---- GOAL 3 · TRIANGULATE --------------------------------------------------
with tab_tri:
    st.subheader("Triangulate — does the GGM verdict survive independent checks?")
    st.caption("GGM is fragile, so don't let it be the sole verdict. These signals don't depend on r − g.")

    # --- live peer comparison ------------------------------------------------
    st.markdown("##### Peer comparison (live)")
    peer_str = st.text_input("Peer tickers (comma-separated, 2–3)", value="",
                             placeholder="e.g. PEP, KDP, MNST")
    peers = [p.strip().upper() for p in peer_str.split(",") if p.strip()]
    peers = [p for p in dict.fromkeys(peers) if p != data["ticker"]][:3]  # dedupe, drop self, cap 3

    main_yield = data["d0"] / data["price"] * 100
    comp_rows = [{"Ticker": f"{data['ticker']} (this)", "Name": (data["name"] or "")[:24],
                  "Price": data["price"], "Trailing P/E": data["trailing_pe"], "Div yield %": main_yield}]
    peer_pes, peer_yields = [], []
    for p in peers:
        try:
            pdat = load_stock(p)
            if pdat["price"]:
                py = pdat["d0"] / pdat["price"] * 100 if pdat["price"] else None
                comp_rows.append({"Ticker": p, "Name": (pdat["name"] or p)[:24],
                                  "Price": pdat["price"], "Trailing P/E": pdat["trailing_pe"],
                                  "Div yield %": py})
                if pdat["trailing_pe"]:
                    peer_pes.append(pdat["trailing_pe"])
                if py is not None:
                    peer_yields.append(py)
            else:
                comp_rows.append({"Ticker": p, "Name": "no price", "Price": None,
                                  "Trailing P/E": None, "Div yield %": None})
        except Exception:
            comp_rows.append({"Ticker": p, "Name": "fetch failed", "Price": None,
                              "Trailing P/E": None, "Div yield %": None})

    comp_df = pd.DataFrame(comp_rows)
    st.dataframe(
        comp_df.style.format({"Price": "{:.2f}", "Trailing P/E": "{:.1f}", "Div yield %": "{:.2f}"},
                             na_rep="—"),
        use_container_width=True, hide_index=True)

    peer_avg_pe = float(np.mean(peer_pes)) if peer_pes else None
    peer_avg_yield = float(np.mean(peer_yields)) if peer_yields else None
    if peer_avg_pe:
        st.caption(f"Peer-average trailing P/E = **{peer_avg_pe:.1f}**"
                   + (f"  ·  peer-average yield = **{peer_avg_yield:.2f}%**" if peer_avg_yield else "")
                   + " — used live as the P/E benchmark below.")

    st.markdown("##### Signal summary")
    rows = []

    # 1) GGM (from Goal 2)
    if gap is not None and not np.isnan(gap):
        rows.append(("Gordon model (GGM)", f"P₀ {money(p0, cur)} vs price {money(data['price'], cur)} "
                     f"({gap*100:+.1f}%)", verdict_from_gap(gap, cheap_if_high=True)))
    else:
        rows.append(("Gordon model (GGM)", "run Goal 2 first (g ≥ r or not computed)", "—"))

    # 2) Analyst consensus target
    target, n_an = data["target"], data["n_analysts"]
    if target:
        up = (target - data["price"]) / data["price"]
        rows.append(("Analyst target (consensus)",
                     f"target {money(target, cur)}  ({up*100:+.1f}%)"
                     + (f", n={int(n_an)}" if n_an else ""),
                     verdict_from_gap(up, cheap_if_high=True)))
    else:
        rows.append(("Analyst target (consensus)", "not available", "—"))

    # 3) Dividend yield vs its own 5-yr average
    cur_yield = data["d0"] / data["price"] * 100
    avg_y = data["avg_div_yield5"]
    if avg_y:
        yg = (cur_yield - avg_y) / avg_y
        rows.append(("Dividend yield vs 5-yr avg",
                     f"now {cur_yield:.2f}% vs avg {avg_y:.2f}%  ({yg*100:+.1f}%)",
                     verdict_from_gap(yg, cheap_if_high=True)))
    else:
        rows.append(("Dividend yield vs 5-yr avg",
                     f"now {cur_yield:.2f}% (no 5-yr avg available)", "—"))

    # 4) P/E vs peer average (live) — falls back to a manual benchmark if no peers
    tpe = data["trailing_pe"]
    if tpe and peer_avg_pe:
        pg = (tpe - peer_avg_pe) / peer_avg_pe
        rows.append(("P/E vs peer average (live)",
                     f"{tpe:.1f} vs peer avg {peer_avg_pe:.1f}  ({pg*100:+.1f}%)",
                     verdict_from_gap(pg, cheap_if_high=False)))
    else:
        bench_pe = st.number_input("No peers entered — manual benchmark P/E (0 = skip)",
                                   value=0.0, step=1.0, format="%.1f")
        if tpe and bench_pe > 0:
            pg = (tpe - bench_pe) / bench_pe
            rows.append(("P/E vs benchmark (manual)",
                         f"{tpe:.1f} vs {bench_pe:.1f}  ({pg*100:+.1f}%)",
                         verdict_from_gap(pg, cheap_if_high=False)))
        else:
            rows.append(("P/E vs peer/benchmark",
                         (f"trailing P/E {tpe:.1f}; add peers above to score" if tpe else "P/E unavailable"),
                         "—"))

    # 5) Yield vs peer average (live, informational bonus signal)
    if peer_avg_yield:
        ypg = (main_yield - peer_avg_yield) / peer_avg_yield
        rows.append(("Dividend yield vs peers (live)",
                     f"{main_yield:.2f}% vs peer avg {peer_avg_yield:.2f}%  ({ypg*100:+.1f}%)",
                     verdict_from_gap(ypg, cheap_if_high=True)))

    df = pd.DataFrame(rows, columns=["Signal", "Reading", "Verdict"])
    st.dataframe(df, use_container_width=True, hide_index=True)

    verdicts = [v for _, _, v in rows if v != "—"]
    cheap = sum("Cheap" in v for v in verdicts)
    exp = sum("Expensive" in v for v in verdicts)
    fair = sum("Fair" in v for v in verdicts)
    n = len(verdicts)
    if n:
        lead = ("cheap" if cheap > max(exp, fair) else "expensive" if exp > max(cheap, fair) else "mixed/fair")
        st.info(f"**{cheap} cheap · {fair} fair · {exp} expensive** out of {n} scored signals → overall read: "
                f"**{lead}**. When independent signals agree with the GGM verdict, trust it more; when only "
                "the fragile GGM says cheap, be skeptical — the market may be pricing in lower growth for a reason.")
    else:
        st.caption("No signals could be scored yet — run Goal 2 and/or add a benchmark P/E.")

# ----------------------------------------------------------------------------
with st.expander("⚠️  Model limitations & disclaimer"):
    st.markdown(
        "- Gordon assumes a stable dividend payer and one constant growth rate forever.\n"
        "- Output is **highly sensitive** to r and g; when r − g is small the point estimate is unreliable "
        "— use the range and margin of safety.\n"
        "- CAPM's ERP is an assumption and beta is noisy, so CAPM r is approximate.\n"
        "- Triangulation signals (analyst target, yield, P/E) are rough cross-checks, not proof.\n"
        "- Live Yahoo data can have gaps or delays.\n"
        "- **Educational tool, not investment advice.**"
    )
