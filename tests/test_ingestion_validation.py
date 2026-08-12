import pandas as pd
import pytest

from src.ingestion.collect_uou2t14d import (
    DUPLICATE_KEY,
    REQUIRED_COLUMNS,
    get_publication_time,
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
