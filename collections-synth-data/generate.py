"""
generate.py
CLI entrypoint for the Fintaar Collections Synthetic Data Generator (Phase 1).

# SYNTHETIC DATA — NOT REAL PII

Usage:
    py generate.py                          # uses config_default.json
    py generate.py --config my_config.json
    py generate.py --records 50000 --seed 99
    py generate.py --records 10000 --output my_outputs/
"""

import argparse
import json
import time
from phase1_faker_generator import generate_dataset
from ml_exporter import split_dataset, export_csv, export_excel, export_feature_manifest


def load_config(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description="Fintaar Collections Synthetic Data Generator v1.0"
    )
    parser.add_argument("--config",  default="config_default.json",
                        help="Path to config JSON (default: config_default.json)")
    parser.add_argument("--records", type=int,
                        help="Override record count from config")
    parser.add_argument("--seed",    type=int,
                        help="Override random seed from config")
    parser.add_argument("--output",  default="outputs",
                        help="Output directory (default: outputs/)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    n    = args.records or cfg["record_count"]
    seed = args.seed    or cfg.get("random_seed", 42)
    fmt  = cfg.get("output_format", "both")
    modules = cfg.get("schema_modules", ["demographic", "bureau"])
    balance = cfg.get("class_balance_target", 0.80)
    dpd_weights = cfg.get("dpd_weights")
    seg_weights = cfg.get("segment_weights")

    print(f"\nFintaar Collections Synthetic Data Generator")
    print(f"  Records:  {n:,}")
    print(f"  Seed:     {seed}")
    print(f"  Modules:  {modules}")
    print(f"  Balance:  {balance:.0%} paid target")
    print(f"  Output:   {args.output}/\n")

    t0 = time.time()
    print("Generating records...", end=" ", flush=True)
    df = generate_dataset(
        n=n,
        seed=seed,
        schema_modules=modules,
        class_balance_target=balance,
        dpd_weights=dpd_weights,
        segment_weights=seg_weights,
    )
    print(f"done ({time.time()-t0:.1f}s)")

    print("Splitting dataset...", end=" ", flush=True)
    train, val, test = split_dataset(df, seed=seed)
    print(f"done  [train={len(train):,} | val={len(val):,} | test={len(test):,}]")

    if fmt in ("csv", "both"):
        print("Exporting CSV...", end=" ", flush=True)
        export_csv(train, val, test, output_dir=args.output)
        print("done")

    if fmt in ("excel", "both"):
        print("Exporting Excel...", end=" ", flush=True)
        export_excel(train, val, test, df, output_dir=args.output)
        print("done")

    print("Writing feature manifest...", end=" ", flush=True)
    export_feature_manifest(df, output_dir=args.output)
    print("done")

    paid_rate = df["target_paid_30d"].mean()
    elapsed = time.time() - t0
    print(f"\nSummary:")
    print(f"  Total records:   {len(df):,}")
    print(f"  Paid rate:       {paid_rate:.1%}")
    print(f"  Elapsed:         {elapsed:.1f}s")
    print(f"  Output dir:      {args.output}/")
    print(f"\n# SYNTHETIC DATA — NOT REAL PII\n")


if __name__ == "__main__":
    main()
