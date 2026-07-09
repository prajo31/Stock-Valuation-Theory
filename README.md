# Dividend Growth Model — Live Stock Valuation

A teaching app for intro finance (BA300 / MBA). It uses the **Gordon Growth Model**
with **live data** from Yahoo Finance to do two things, showing the actual numbers
behind every input.

> P₀ = D₁ / (r − g),  where  D₁ = D₀ (1 + g)

**Two goals, same model, separate tabs:**
- **Goal 1 — Required return (cost of equity), estimated two ways side by side:**
  - **CAPM:** `r = R_f + β × ERP`, using the **live 10-year Treasury yield** (`^TNX`), the
    **live beta** (Yahoo), and an editable equity-risk-premium assumption (~5%). Every term is
    shown and editable, with the plugged-in line displayed.
  - **Dividend-model approach:** `r = D₁/P₀ + g` (dividend yield + growth), using the live price.
  - Comparing the two is the point — where they disagree is the insight.
- **Goal 2 — Stock valuation (intrinsic price):** `P₀ = D₁/(r − g)`. You pick which r to use
  (CAPM, DDM approach, or manual) and compare P₀ to the live price. Includes guardrails against the
  ways Gordon misleads: a **g-ceiling check** (perpetual g shouldn't exceed ~nominal GDP), a
  **fragile-zone warning** when r − g falls below ~2% (the point estimate becomes unreliable), and an
  **intrinsic-value range plus margin-of-safety band** instead of a single false-precision number.
- **Goal 3 — Triangulate:** cross-checks the GGM verdict against **independent** signals that don't
  depend on r − g — analyst consensus target vs. price, current dividend yield vs. the stock's own
  5-year average, and P/E vs. a benchmark you enter — then reports how many agree. When independent
  signals line up with GGM, trust it more; when only the fragile GGM says "cheap," be skeptical.

**Shared inputs (shown with live data and the arithmetic):**
- **D₀** — trailing-12-month dividend, summed from real payment history
- **g** — three methods with their calculations shown: historical dividend CAGR
  `(D_end/D_start)^(1/n) − 1`, sustainable growth `ROE × (1 − payout)`, or manual
- Plus a **sensitivity table** and a **reverse check** (implied growth) in Goal 2

Live risk-free rate note: Yahoo quotes `^TNX` directly as a percent (~4.5). The app divides by 100,
guards against the older ×10 convention, and lets you override the value.

## Files
```
ddm_valuation.py   # the Streamlit app (entry point)
requirements.txt   # dependencies
README.md          # this file
```

## Run locally
```bash
pip install -r requirements.txt
streamlit run ddm_valuation.py
```
Then open the URL it prints (usually http://localhost:8501).

## Deploy free on Streamlit Community Cloud (recommended for a class)
1. Create a **public GitHub repo** and add these three files (`ddm_valuation.py`, `requirements.txt`, `README.md`).
2. Go to **https://share.streamlit.io** and sign in with GitHub.
3. Click **New app**, pick your repo/branch, set the main file to `ddm_valuation.py`, and **Deploy**.
4. Share the resulting URL with students. No API keys, no accounts for them.

## Notes & known limitations
- **Yahoo rate-limiting:** Streamlit Cloud's shared IPs are occasionally throttled by Yahoo.
  The app caches results for 15 minutes to reduce this. If a fetch fails, wait a moment and retry.
- The model only suits **stable dividend payers**; it is undefined for non-payers or when g ≥ r
  (the app guards against both).
- Output is **very sensitive** to r and g — that's the point of the sensitivity table.
- **Educational tool, not investment advice.**

## Ideas for extension (kept intro-appropriate)
- Add a peer comparison (value several tickers at once).
- Let students save valuations to a CSV to track how their estimate drifts over time.
- Add a bond-yield-plus-risk-premium helper for r, as an alternative to a pure guess.
