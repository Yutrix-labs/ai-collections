"""
ml_exporter.py
Stratified train/val/test splitting and CSV/Excel export for ML pipelines.
"""

import json
import os
import pandas as pd
from sklearn.model_selection import train_test_split


def split_dataset(
    df: pd.DataFrame,
    train_frac: float = 0.70,
    val_frac: float = 0.20,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Stratified 70/20/10 split preserving target_paid_30d class balance."""
    # First split: train vs (val + test)
    train, temp = train_test_split(
        df,
        test_size=(1 - train_frac),
        stratify=df["target_paid_30d"],
        random_state=seed,
    )
    # Second split: val vs test
    relative_val = val_frac / (1 - train_frac)
    val, test = train_test_split(
        temp,
        test_size=(1 - relative_val),
        stratify=temp["target_paid_30d"],
        random_state=seed,
    )
    return train.reset_index(drop=True), val.reset_index(drop=True), test.reset_index(drop=True)


def export_csv(
    train: pd.DataFrame,
    val: pd.DataFrame,
    test: pd.DataFrame,
    output_dir: str = "outputs",
) -> None:
    """Write train/val/test and full dataset CSVs to output_dir.

    List-valued columns (e.g., action_history, payment_history) are serialised
    to JSON strings so the CSV is machine-readable.
    """
    os.makedirs(output_dir, exist_ok=True)

    full = pd.concat([train, val, test], ignore_index=True)

    def _serialise_lists(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in df.columns:
            first_val = df[col].dropna().iloc[0] if df[col].notna().any() else None
            if isinstance(first_val, list):
                df[col] = df[col].apply(lambda v: json.dumps(v) if isinstance(v, list) else v)
        return df

    _serialise_lists(full).to_csv(os.path.join(output_dir, "synthetic_collections.csv"), index=False)
    _serialise_lists(train).to_csv(os.path.join(output_dir, "train.csv"), index=False)
    _serialise_lists(val).to_csv(os.path.join(output_dir, "val.csv"), index=False)
    _serialise_lists(test).to_csv(os.path.join(output_dir, "test.csv"), index=False)


def export_feature_manifest(
    df: pd.DataFrame,
    output_dir: str = "outputs",
) -> str:
    """Write feature_report.json with column metadata."""
    os.makedirs(output_dir, exist_ok=True)

    target = "target_paid_30d"
    features = [c for c in df.columns if c != target]

    def _unique_count(series: pd.Series) -> int:
        """Return nunique(), falling back to -1 for unhashable types (e.g. list columns)."""
        try:
            return int(series.nunique())
        except TypeError:
            return -1

    manifest = {
        "record_count": len(df),
        "target": target,
        "class_balance": float(df[target].mean()),
        "features": [
            {
                "name": col,
                "dtype": str(df[col].dtype),
                "null_count": int(df[col].isna().sum()),
                "unique_count": _unique_count(df[col]),
            }
            for col in features
        ],
    }

    path = os.path.join(output_dir, "feature_report.json")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    return path


def export_excel(
    train: pd.DataFrame,
    val: pd.DataFrame,
    test: pd.DataFrame,
    full: pd.DataFrame,
    output_dir: str = "outputs",
) -> str:
    """Write formatted Excel workbook with train/val/test sheets and a summary."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "synthetic_collections.xlsx")

    summary = pd.DataFrame({
        "Split":     ["train", "val", "test", "total"],
        "Records":   [len(train), len(val), len(test), len(full)],
        "Paid Rate": [
            round(train["target_paid_30d"].mean(), 3),
            round(val["target_paid_30d"].mean(), 3),
            round(test["target_paid_30d"].mean(), 3),
            round(full["target_paid_30d"].mean(), 3),
        ],
    })

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="summary", index=False)
        train.to_excel(writer, sheet_name="train", index=False)
        val.to_excel(writer, sheet_name="val", index=False)
        test.to_excel(writer, sheet_name="test", index=False)

    return path
