import pandas as pd
import pytest

from src.ingestion.collect_uou2t14d import (
    DUPLICATE_KEY,
    REQUIRED_COLUMNS,
    get_publication_time,
    save_snapshot,
    validate_dataframe,
)


def make_row(**overrides):
    """Create one valid synthetic UOU2T14D row."""

    defaults = {
        column: f"value_{column}"
        for column in REQUIRED_COLUMNS
    }

    defaults.update(
        {
            "dataset": "UOU2T14D",
            "fuelType": "CCGT",
            "nationalGridBmUnit": "UNIT-1",
            "bmUnit": None,
            "publishTime": pd.Timestamp(
                "2026-08-12T01:00:00Z"
            ),
            "forecastDate": pd.Timestamp(
                "2026-08-14"
            ),
            "outputUsable": 100,
        }
    )

    defaults.update(overrides)

    return {
        column: defaults[column]
        for column in REQUIRED_COLUMNS
    }


def test_valid_dataframe_passes_validation():
    df = pd.DataFrame(
        [
            make_row(
                nationalGridBmUnit="UNIT-1",
                outputUsable=100,
            ),
            make_row(
                nationalGridBmUnit="UNIT-2",
                outputUsable=50,
            ),
        ]
    )

    result = validate_dataframe(df)

    assert result["row_count"] == 2
    assert result["duplicate_key_rows"] == 0
    assert result["negative_output_usable_rows"] == 0


def test_null_bm_unit_does_not_create_false_duplicate():
    df = pd.DataFrame(
        [
            make_row(
                nationalGridBmUnit="UNIT-1",
                bmUnit=None,
            ),
            make_row(
                nationalGridBmUnit="UNIT-2",
                bmUnit=None,
            ),
        ]
    )

    result = validate_dataframe(df)

    assert result["duplicate_key_rows"] == 0

    if "bmUnit" in REQUIRED_COLUMNS:
        assert result["null_counts"]["bmUnit"] == 2


def test_duplicate_source_key_raises_value_error():
    row = make_row(
        nationalGridBmUnit="UNIT-DUPLICATE"
    )

    df = pd.DataFrame(
        [
            row,
            row.copy(),
        ]
    )

    with pytest.raises(
        ValueError,
        match="duplicate source keys",
    ):
        validate_dataframe(df)


def test_missing_required_column_raises_value_error():
    df = pd.DataFrame(
        [
            make_row(),
        ]
    )

    column_to_remove = REQUIRED_COLUMNS[0]

    df = df.drop(
        columns=[column_to_remove]
    )

    with pytest.raises(
        ValueError,
        match="Required columns missing",
    ):
        validate_dataframe(df)


def test_negative_output_is_reported():
    df = pd.DataFrame(
        [
            make_row(
                nationalGridBmUnit="UNIT-1",
                outputUsable=-10,
            ),
        ]
    )

    result = validate_dataframe(df)

    assert (
        result["negative_output_usable_rows"]
        == 1
    )


def test_publication_time_is_returned_in_utc():
    df = pd.DataFrame(
        [
            make_row(
                nationalGridBmUnit="UNIT-1",
            ),
            make_row(
                nationalGridBmUnit="UNIT-2",
            ),
        ]
    )

    publication_time = get_publication_time(
        df
    )

    assert publication_time == pd.Timestamp(
        "2026-08-12T01:00:00Z"
    )


def test_multiple_publication_times_raise_error():
    df = pd.DataFrame(
        [
            make_row(
                nationalGridBmUnit="UNIT-1",
                publishTime=pd.Timestamp(
                    "2026-08-12T01:00:00Z"
                ),
            ),
            make_row(
                nationalGridBmUnit="UNIT-2",
                publishTime=pd.Timestamp(
                    "2026-08-12T02:00:00Z"
                ),
            ),
        ]
    )

    with pytest.raises(
        ValueError,
        match="Expected exactly one publishTime",
    ):
        get_publication_time(df)


def test_duplicate_key_definition_uses_national_grid_unit():
    assert "nationalGridBmUnit" in DUPLICATE_KEY
    assert "publishTime" in DUPLICATE_KEY
    assert "forecastDate" in DUPLICATE_KEY


def test_snapshot_can_use_custom_directory(tmp_path):
    df = pd.DataFrame(
        [
            make_row(
                nationalGridBmUnit="UNIT-CUSTOM",
            ),
        ]
    )

    validation = validate_dataframe(df)

    parquet_path, metadata_path, created = save_snapshot(
        df,
        validation,
        snapshot_directory=tmp_path,
    )

    assert created is True
    assert parquet_path.parent == tmp_path
    assert metadata_path.parent == tmp_path
    assert parquet_path.exists()
    assert metadata_path.exists()

    _, _, created_again = save_snapshot(
        df,
        validation,
        snapshot_directory=tmp_path,
    )

    assert created_again is False


def test_repair_converts_nanosecond_parquet_to_microseconds(
    tmp_path,
):
    import pyarrow as pa
    import pyarrow.parquet as pq

    from src.ingestion.collect_uou2t14d import (
        repair_spark_compatible_parquet,
    )

    parquet_path = (
        tmp_path
        / "uou2t14d_publish_20260812T220000Z.parquet"
    )

    table = pa.table(
        {
            "publishTime": pa.array(
                [
                    pd.Timestamp(
                        "2026-08-12T22:00:00.123456789Z"
                    )
                ],
                type=pa.timestamp(
                    "ns",
                    tz="UTC",
                ),
            ),
        }
    )

    pq.write_table(
        table,
        parquet_path,
        version="2.6",
    )

    before = pq.read_schema(
        parquet_path
    )

    assert (
        before.field("publishTime").type.unit
        == "ns"
    )

    repaired = (
        repair_spark_compatible_parquet(
            parquet_path
        )
    )

    after = pq.read_schema(
        parquet_path
    )

    assert repaired is True
    assert (
        after.field("publishTime").type.unit
        == "us"
    )

    repaired_again = (
        repair_spark_compatible_parquet(
            parquet_path
        )
    )

    assert repaired_again is False
