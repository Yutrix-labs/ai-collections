"""Generate a realistic PTP training dataset.

The shipped Data_distribution.xlsx has near-zero correlation between features and
`ptp_kept` because the generator that produced it never wired in the response-rate and
paid-ratio relationships from Section 7 of the data spec. This module reproduces those
relationships faithfully so the targets carry genuine, learnable signal:

    ptp_given        ~ Bernoulli(base_p + response_uplift * response_rate)
    ptp_kept         ~ Beta(2,3) blended toward the customer's paid_ratio
                       (with mild delinquency / weak-credit penalties), 0 if no PTP
    broken_ptp_count ~ NegBinom whose mean grows with unkept promises

Features are bootstrapped from the source sample so realistic joint distributions and
inter-feature correlations are preserved; only the three PTP columns are regenerated.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from . import config


def _paid_ratio(payment_history: pd.Series) -> np.ndarray:
    """Share of 'P' (paid) markers in the 6-char payment-history string."""
    s = payment_history.fillna("").astype(str)
    length = s.str.len().replace(0, np.nan)
    return (s.str.count("P") / length).fillna(0.5).to_numpy()


def generate(n_rows: int = 5000, seed: int = config.RANDOM_SEED) -> pd.DataFrame:
    """Return a DataFrame of `n_rows` accounts with realistically-wired PTP targets."""
    rng = np.random.default_rng(seed)

    source = pd.read_excel(config.SOURCE_XLSX, sheet_name=config.SOURCE_SHEET)

    # Bootstrap feature rows (preserves real joint feature distributions).
    idx = rng.integers(0, len(source), size=n_rows)
    df = source.iloc[idx].reset_index(drop=True).copy()
    df["account_id"] = [f"ACC{1_000_000 + i}" for i in range(n_rows)]

    g_given = config.GEN_CONFIG["ptp_given"]
    g_kept = config.GEN_CONFIG["ptp_kept"]
    g_broken = config.GEN_CONFIG["broken_ptp_count"]

    response_rate = df["response_rate"].fillna(df["response_rate"].median()).to_numpy()
    paid_ratio = _paid_ratio(df["payment_history"])
    latest_dpd = df["latest_dpd"].fillna(0).to_numpy()
    cibil = df["cibil_score"].to_numpy()

    # --- ptp_given: Bernoulli, lifted by responsiveness -------------------- #
    p_given = g_given["base_p"] + g_given["response_uplift"] * response_rate
    p_given = np.clip(p_given, 0.02, 0.98)
    ptp_given = (rng.random(n_rows) < p_given).astype(int)

    # --- ptp_kept: Beta blended toward paid_ratio, penalised by risk ------- #
    beta_sample = rng.beta(g_kept["beta_alpha"], g_kept["beta_beta"], size=n_rows)
    w = g_kept["paid_ratio_uplift"]
    kept = (1.0 - w) * beta_sample + w * paid_ratio                 # convex blend
    kept = kept - g_kept["dpd_penalty"] * latest_dpd                # delinquency erodes
    low_cibil = (cibil > 0) & (cibil < 600)
    kept = kept - np.where(low_cibil, g_kept["low_cibil_penalty"], 0.0)
    kept = np.clip(kept, 0.0, 1.0)
    if g_kept["zero_when_no_ptp"]:
        kept = np.where(ptp_given == 1, kept, 0.0)
    ptp_kept = np.round(kept, 4)

    # --- broken_ptp_count: NegBinom, mean grows with unkept promises ------- #
    mu = (g_broken["mu_base"] + g_broken["mu_per_unkept"] * (1.0 - ptp_kept)) * ptp_given
    mu = np.maximum(mu, 1e-6)
    r = g_broken["r"]
    p_nb = r / (r + mu)                                             # numpy param: P(success)
    broken = rng.negative_binomial(r, p_nb)
    broken = np.minimum(broken, g_broken["max"])
    broken = np.where(ptp_given == 1, broken, 0).astype(int)

    df["ptp_given"] = ptp_given
    df["ptp_kept"] = ptp_kept
    df["broken_ptp_count"] = broken

    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate PTP training data with realistic signal.")
    parser.add_argument("-n", "--rows", type=int, default=5000, help="number of rows to generate")
    parser.add_argument("--seed", type=int, default=config.RANDOM_SEED)
    parser.add_argument("-o", "--out", type=str, default=str(config.TRAINING_CSV))
    args = parser.parse_args()

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = generate(n_rows=args.rows, seed=args.seed)
    df.to_csv(args.out, index=False)

    given = df["ptp_given"].mean()
    fulfilled = (df.loc[df["ptp_given"] == 1, "ptp_kept"] >= config.PTP_KEPT_THRESHOLD).mean()
    print(f"Wrote {len(df):,} rows -> {args.out}")
    print(f"  ptp_given rate       : {given:.3f}")
    print(f"  PTP-given accounts   : {(df['ptp_given'] == 1).sum():,}")
    print(f"  fulfilled (>= {config.PTP_KEPT_THRESHOLD}) : {fulfilled:.3f}  (positive-class rate among PTP-given)")


if __name__ == "__main__":
    main()
