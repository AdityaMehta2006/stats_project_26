# Quantitative Anomalies & Financial Analytics Dashboard

An interactive quantitative finance dashboard for detecting statistical market anomalies, fitting volatility models, evaluating cointegration for pair trading strategies, and pricing options using stochastic differential equations. Built with a **FastAPI** backend and a **React 19 + Vite** frontend.

---

## Key Features & Pillars

### 1. Macro Factor & Lag Regression
- **OLS Lagged Regression**: Regresses asset returns against lagged macroeconomic indicators (S&P 500, Treasury yields, VIX, WTI Crude, Gold, DXY).
- **Granger Causality**: Tests whether macroeconomic shifts lead asset price movements.
- **Cross-Correlation Heatmaps**: Evaluates dynamic lead-lag correlations across multiple lags.

### 2. Volatility Clustering & GARCH Modeling
- **GARCH(1,1) Dynamics**: Fits conditional variance models with Gaussian, Student-t, and Skewed-t innovation distributions.
- **Clustering & Fat Tails**: Diagnostics for autocorrelation in squared residuals (Ljung-Box test, ACF) and kurtosis evaluation.

### 3. Forex Pair Trading & Cointegration
- **Engle-Granger Cointegration**: Identifies stationary linear combinations among major currency pairs (EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, USD/CHF).
- **Mean-Reversion Dynamics**: Calculates spread half-life ($\ln(2)/\kappa$) and real-time Z-scores for statistical arbitrage signaling.

### 4. Option Pricing & Stochastic Models
- **Analytical Pricing**: Black-Scholes-Merton (Equity), Garman-Kohlhagen (FX), Black-76 (Commodities/Futures), Bachelier (Normal model).
- **Lattice Models**: Cox-Ross-Rubinstein Binomial Tree for European and American early-exercise options.
- **Stochastic Volatility & Jumps**: Merton Jump-Diffusion, Heston Stochastic Volatility, and Longstaff-Schwartz Monte Carlo for American options.
- **Implied Volatility Smile & Surface**: Calibrates IV smiles to live market quotes and model parameters.

### 5. Stochastic Processes & Simulation
- **Sample Path Generation**: Wiener process, Geometric Brownian Motion (GBM), Ornstein-Uhlenbeck (OU), Cox-Ingersoll-Ross (CIR).
- **Convergence & Variance Reduction**: Compares Euler-Maruyama vs. Milstein vs. exact schemes, and evaluates Antithetic and Control Variate techniques.

### 6. Detection & Rule-Based Decision Engine
- **13 Deterministic Detectors**: Trend, breakout, 12-1 momentum, relative performance, RSI mean-reversion, pair cointegration, volatility regime, tail events, options mispricing, macro dislocation, volume, correlation regime, and seasonality.
- **Rule-Based Decision Layer**: Nets signals into a single stance, conviction and position size — weighting by reliability, discounting redundant signals within families, separating direction from size, and demoting conviction on genuine conflict rather than averaging it away. Fully deterministic and auditable.
- **AI Explanation Layer (optional)**: The LLM receives the detections *and* the computed decision, and is barred from changing either. The system's output is identical whether or not a model is available.

---

## Verification

The numerical work is checked rather than trusted. These checks run at request time and are returned in the API response:

| Check | Result |
| :--- | :--- |
| Put-call parity (model-free arbitrage identity) | violation `0.0` |
| Analytical Greeks vs central finite differences | max difference `4.6e-7` |
| Merton Monte Carlo vs exact Poisson series | within 3 standard errors |
| Heston Monte Carlo vs Fourier inversion | within 3 standard errors |
| Heston with vol-of-vol → 0 must equal Black-Scholes | Δ `3e-6` |
| Binomial lattice error vs `1/N` | halves per step doubling |
| American call premium with no dividend | exactly `0.0` |
| Longstaff-Schwartz vs 800-step lattice | within 1 standard error |
| Black-Scholes implied-vol spread across strikes | `0.000` (flat by construction) |

Monte Carlo variance-reduction efficiency is measured, not asserted: plain `1.00×`, antithetic `1.97×`, control variate `5.01×`, both combined **`19.27×`**.

---

## Tech Stack & Architecture

- **Backend**: Python 3.10+, FastAPI, Uvicorn, Pandas, NumPy, Statsmodels, ARCH, SciPy, YFinance.
- **Frontend**: React 19, Vite, Recharts (Data Visualization), Framer Motion (Animations), Lucide Icons, Vanilla CSS design tokens.

```
stats_project_26/
├── backend/
│   ├── main.py              # FastAPI router & REST API endpoints
│   ├── data_loader.py       # Live market data fetcher & FRED integration
│   ├── llm_client.py        # Local/remote LLM interface
│   ├── requirements.txt     # Python backend dependencies
│   └── analysis/            # Quantitative modules (GARCH, Pairs, Options, Stochastic)
├── frontend/
│   ├── src/                 # React UI components & hooks
│   ├── package.json         # Node dependencies & Vite scripts
│   └── vite.config.js       # Vite configuration
├── docs/                    # Project documentation, LaTeX sources, slides & review
└── README.md                # Project documentation entry point
```

---

## Quick Start

### Run Entire App (Single Command)

```bash
# Run launcher script directly
./scripts/run.sh

# Or via npm from root directory
npm start
```
This starts both the FastAPI backend and Vite frontend, outputting the URLs:
- **Frontend Dashboard**: `http://localhost:5173`
- **Backend API**: `http://127.0.0.1:8000`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`

---

### Manual Setup (Step-by-Step)

```bash
# Navigate to project root and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Start FastAPI server
python3 -m uvicorn backend.main:app --reload --port 8000
```
The API documentation will be available at `http://localhost:8000/docs`.

### 2. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## Quality & Code Verification

To build and check code quality:

```bash
# Run ESLint on frontend
cd frontend
npm run lint

# Build production bundle
npm run build
```

---

## Documentation

Detailed documentation and mathematical formulations are stored in the [`docs/`](docs/) directory:

- [Project Technical Documentation](docs/DOCUMENTATION.md) (`docs/DOCUMENTATION.md`)
- [Literature Review & Theoretical Background](docs/LITERATURE_REVIEW.md) (`docs/LITERATURE_REVIEW.md`)
- [Presentation Outline & Overview](docs/PRESENTATION.md) (`docs/PRESENTATION.md`)
- [Presentation Parts & Script](docs/PRESENTATION_PARTS.md) (`docs/PRESENTATION_PARTS.md`)
- [Project TODO & Roadmap](docs/TODO.md) (`docs/TODO.md`)
- [LaTeX Report & Slides](docs/) (`docs/DOCUMENTATION.tex`, `docs/PRESENTATION.tex`)
