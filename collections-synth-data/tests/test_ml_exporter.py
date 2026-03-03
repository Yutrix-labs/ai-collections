import pytest
import json
import tempfile
import os
import pandas as pd
from ml_exporter import split_dataset, export_csv, export_feature_manifest, export_excel
from phase1_faker_generator import generate_dataset


@pytest.fixture(scope="module")
def sample_df():
    return generate_dataset(n=1000, seed=42, schema_modules=["demographic", "bureau"])


def test_split_returns_three_dataframes(sample_df):
    train, val, test = split_dataset(sample_df)
    assert isinstance(train, pd.DataFrame)
    assert isinstance(val, pd.DataFrame)
    assert isinstance(test, pd.DataFrame)


def test_split_sizes_approximate_70_20_10(sample_df):
    train, val, test = split_dataset(sample_df)
    n = len(sample_df)
    assert abs(len(train) / n - 0.70) < 0.05
    assert abs(len(val)   / n - 0.20) < 0.05
    assert abs(len(test)  / n - 0.10) < 0.05


def test_split_no_overlap(sample_df):
    train, val, test = split_dataset(sample_df)
    train_ids = set(train["customer_id"])
    val_ids   = set(val["customer_id"])
    test_ids  = set(test["customer_id"])
    assert len(train_ids & val_ids) == 0
    assert len(train_ids & test_ids) == 0
    assert len(val_ids & test_ids) == 0


def test_split_covers_all_records(sample_df):
    train, val, test = split_dataset(sample_df)
    assert len(train) + len(val) + len(test) == len(sample_df)


def test_class_balance_preserved_across_splits(sample_df):
    train, val, test = split_dataset(sample_df)
    overall_rate = sample_df["target_paid_30d"].mean()
    for name, split in [("train", train), ("val", val), ("test", test)]:
        split_rate = split["target_paid_30d"].mean()
        assert abs(split_rate - overall_rate) < 0.08, (
            f"{name} paid rate {split_rate:.2f} diverges from overall {overall_rate:.2f}"
        )


def test_export_csv_creates_files(sample_df):
    with tempfile.TemporaryDirectory() as tmpdir:
        train, val, test = split_dataset(sample_df)
        export_csv(train, val, test, output_dir=tmpdir)
        assert os.path.exists(os.path.join(tmpdir, "train.csv"))
        assert os.path.exists(os.path.join(tmpdir, "val.csv"))
        assert os.path.exists(os.path.join(tmpdir, "test.csv"))
        assert os.path.exists(os.path.join(tmpdir, "synthetic_collections.csv"))


def test_feature_manifest_is_valid_json(sample_df):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = export_feature_manifest(sample_df, output_dir=tmpdir)
        with open(path) as f:
            manifest = json.load(f)
        assert "features" in manifest
        assert "target" in manifest
        assert "record_count" in manifest
        assert manifest["target"] == "target_paid_30d"
        assert manifest["record_count"] == len(sample_df)


def test_export_excel_creates_workbook(sample_df):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        train, val, test = split_dataset(sample_df)
        path = export_excel(train, val, test, sample_df, output_dir=tmpdir)
        assert os.path.exists(path)
        with pd.ExcelFile(path) as xl:
            assert "train" in xl.sheet_names
            assert "val" in xl.sheet_names
            assert "test" in xl.sheet_names
            assert "summary" in xl.sheet_names


def test_list_columns_serialised_as_json_in_csv(tmp_path):
    """action_history and payment_history must be valid JSON strings in CSV."""
    import sys, os, json as _json
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from phase1_faker_generator import generate_dataset
    from ml_exporter import split_dataset, export_csv
    import pandas as pd

    df = generate_dataset(n=50, seed=1, schema_modules=["interactions"])
    train, val, test = split_dataset(df)
    export_csv(train, val, test, str(tmp_path))

    full_csv = pd.read_csv(tmp_path / "synthetic_collections.csv")
    assert "action_history" in full_csv.columns
    for val_str in full_csv["action_history"].dropna():
        parsed = _json.loads(val_str)
        assert isinstance(parsed, list)
