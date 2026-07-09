[README.md](https://github.com/user-attachments/files/29859634/README.md)
Dividend Growth Model — Live Stock Valuation

A teaching app for intro finance (BA300 / MBA). It uses the **Gordon Growth Model**
with **live data** from Yahoo Finance to do two things, showing the actual numbers
behind every input.

> P₀ = D₁ / (r − g),  where  D₁ = D₀ (1 + g)

**Two goals, same model, separate tabs:**
- **Goal 1 — Required return (cost of equity):** solves the model for r → `r = D₁/P₀ + g`
  (dividend yield + growth). Live price is the input; r is the output. No CAPM.
- **Goal 2 — Stock valuation (intrinsic price):** solves the model for P₀ using an
  independent r you supply; compares P₀ to the live price with an under/fair/over verdict.

They are kept as separate tabs on purpose: the r from Goal 1 uses today's price, so
feeding it into Goal 2 would just return today's price (circular).

**Shared inputs (shown with live data):**
- **D₀** — trailing-12-month dividend, summed from real payment history
- **g** — three methods side by side: historical dividend CAGR, sustainable growth
  (ROE × (1 − payout)), or manual
- Plus a **sensitivity table** and a **reverse check** (what growth the market is pricing in) in Goal 2

## Files
```
app.py             # the Streamlit app
requirements.txt   # dependencies
README.md          # this file
```

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```
Then open the URL it prints (usually http://localhost:8501).

## Deploy free on Streamlit Community Cloud (recommended for a class)
1. Create a **public GitHub repo** and add these three files (`app.py`, `requirements.txt`, `README.md`).
2. Go to **https://share.streamlit.io** and sign in with GitHub.
3. Click **New app**, pick your repo/branch, set the main file to `app.py`, and **Deploy**.
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
