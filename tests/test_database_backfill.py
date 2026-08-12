from pathlib import Path
from unittest.mock import MagicMock, Mock, call

import pandas as pd
import pytest

import src.pipeline.backfill_uou2t14d_database as backfill


def publication_dataframe(
    publish_time: str,
    output_usable: float = 100.0,
) -> pd.DataFrame:
    """Create a minimal canonical publication for tests."""

    return pd.DataFrame(
        {
            "dataset": ["UOU2T14D"],
            "fuelType": ["CCGT"],
            "nationalGridBmUnit": ["UNIT-1"],
            "bmUnit": [None],
            "publishTime": [
                pd.Timestamp(publish_time)
            ],
            "forecastDate": [
                pd.Timestamp("2026-08-14")
            ],
            "outputUsable": [
                output_usable
            ],
            "collectedAt": [
                pd.Timestamp(
                    "2026-08-12T04:00:00Z"
                )
            ],
        }
    )


def test_get_publication_files_returns_chronological_files(
    monkeypatch,
    tmp_path,
):
    files = [
        tmp_path
        / "uou2t14d_publish_20260812T020000Z.parquet",
        tmp_path
        / "uou2t14d_publish_20260811T230000Z.parquet",
        tmp_path
        / "uou2t14d_publish_20260812T010000Z.parquet",
    ]

    for file_path in files:
        file_path.touch()

    monkeypatch.setattr(
        backfill,
        "RAW_DIRECTORY",
        tmp_path,
    )

    result = backfill.get_publication_files()

    assert [
        path.name
        for path in result
    ] == [
        "uou2t14d_publish_20260811T230000Z.parquet",
        "uou2t14d_publish_20260812T010000Z.parquet",
        "uou2t14d_publish_20260812T020000Z.parquet",
    ]


def test_get_publication_files_requires_canonical_files(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        backfill,
        "RAW_DIRECTORY",
        tmp_path,
    )

    with pytest.raises(
        FileNotFoundError,
        match="No canonical UOU2T14D publications found",
    ):
        backfill.get_publication_files()


def test_load_silver_dataframes_rejects_empty_fuel(
    monkeypatch,
):
    monkeypatch.setattr(
        backfill,
        "prepare_fuel_dataframe",
        lambda df: df,
    )

    monkeypatch.setattr(
        backfill,
        "prepare_system_dataframe",
        lambda df: df,
    )

    fuel_df = pd.DataFrame()

    system_df = pd.DataFrame(
        {
            "publish_time": [
                pd.Timestamp(
                    "2026-08-12T02:00:00Z"
                )
            ]
        }
    )

    with pytest.raises(
        ValueError,
        match="Fuel availability DataFrame is empty",
    ):
        backfill.load_silver_dataframes(
            Mock(),
            fuel_df,
            system_df,
        )


def test_load_silver_dataframes_requires_matching_publications(
    monkeypatch,
):
    monkeypatch.setattr(
        backfill,
        "prepare_fuel_dataframe",
        lambda df: df,
    )

    monkeypatch.setattr(
        backfill,
        "prepare_system_dataframe",
        lambda df: df,
    )

    fuel_df = pd.DataFrame(
        {
            "publish_time": [
                pd.Timestamp(
                    "2026-08-12T01:00:00Z"
                )
            ]
        }
    )

    system_df = pd.DataFrame(
        {
            "publish_time": [
                pd.Timestamp(
                    "2026-08-12T02:00:00Z"
                )
            ]
        }
    )

    with pytest.raises(
        ValueError,
        match=(
            "Fuel and system publication times "
            "do not match"
        ),
    ):
        backfill.load_silver_dataframes(
            Mock(),
            fuel_df,
            system_df,
        )


def test_load_silver_dataframes_routes_upserts(
    monkeypatch,
):
    publication_time = pd.Timestamp(
        "2026-08-12T02:00:00Z"
    )

    fuel_df = pd.DataFrame(
        {
            "publish_time": [
                publication_time
            ]
        }
    )

    system_df = pd.DataFrame(
        {
            "publish_time": [
                publication_time
            ]
        }
    )

    fuel_upsert = Mock(
        return_value=247
    )

    system_upsert = Mock(
        return_value=13
    )

    verify = Mock(
        return_value={
            "fuel_rows": 247,
            "system_rows": 13,
        }
    )

    monkeypatch.setattr(
        backfill,
        "prepare_fuel_dataframe",
        lambda df: df,
    )

    monkeypatch.setattr(
        backfill,
        "prepare_system_dataframe",
        lambda df: df,
    )

    monkeypatch.setattr(
        backfill,
        "upsert_fuel_availability",
        fuel_upsert,
    )

    monkeypatch.setattr(
        backfill,
        "upsert_system_availability",
        system_upsert,
    )

    monkeypatch.setattr(
        backfill,
        "verify_database",
        verify,
    )

    connection = Mock()

    result = backfill.load_silver_dataframes(
        connection,
        fuel_df,
        system_df,
    )

    fuel_upsert.assert_called_once_with(
        connection,
        fuel_df,
    )

    system_upsert.assert_called_once_with(
        connection,
        system_df,
    )

    verify.assert_called_once()

    assert result[
        "fuel_rows_processed"
    ] == 247

    assert result[
        "system_rows_processed"
    ] == 13

    assert result[
        "fuel_rows_database"
    ] == 247

    assert result[
        "system_rows_database"
    ] == 13


def test_load_analytics_dataframes_routes_three_upserts(
    monkeypatch,
):
    unit_df = pd.DataFrame(
        {"value": [1]}
    )

    fuel_df = pd.DataFrame(
        {"value": [1]}
    )

    system_df = pd.DataFrame(
        {"value": [1]}
    )

    monkeypatch.setattr(
        backfill,
        "prepare_unit_revisions",
        lambda df: df,
    )

    monkeypatch.setattr(
        backfill,
        "prepare_fuel_revisions",
        lambda df: df,
    )

    monkeypatch.setattr(
        backfill,
        "prepare_system_revisions",
        lambda df: df,
    )

    upsert = Mock(
        side_effect=[
            7150,
            247,
            13,
        ]
    )

    monkeypatch.setattr(
        backfill,
        "upsert_dataframe",
        upsert,
    )

    connection = Mock()

    result = (
        backfill.load_analytics_dataframes(
            connection,
            unit_df,
            fuel_df,
            system_df,
        )
    )

    assert upsert.call_count == 3

    assert (
        upsert.call_args_list[0].kwargs[
            "table_name"
        ]
        == "unit_availability_revision"
    )

    assert (
        upsert.call_args_list[1].kwargs[
            "table_name"
        ]
        == "fuel_availability_revision"
    )

    assert (
        upsert.call_args_list[2].kwargs[
            "table_name"
        ]
        == "system_availability_revision"
    )

    assert result == {
        "unit_rows": 7150,
        "fuel_rows": 247,
        "system_rows": 13,
    }


def test_backfill_database_processes_publications_and_adjacent_pairs(
    monkeypatch,
    tmp_path,
):
    file_23 = (
        tmp_path
        / "uou2t14d_publish_20260811T230000Z.parquet"
    )

    file_00 = (
        tmp_path
        / "uou2t14d_publish_20260812T000000Z.parquet"
    )

    file_01 = (
        tmp_path
        / "uou2t14d_publish_20260812T010000Z.parquet"
    )

    files = [
        file_23,
        file_00,
        file_01,
    ]

    publications = {
        file_23:
            publication_dataframe(
                "2026-08-11T23:00:00Z",
                100,
            ),
        file_00:
            publication_dataframe(
                "2026-08-12T00:00:00Z",
                110,
            ),
        file_01:
            publication_dataframe(
                "2026-08-12T01:00:00Z",
                90,
            ),
    }

    monkeypatch.setattr(
        backfill,
        "get_publication_files",
        Mock(
            return_value=files
        ),
    )

    raw_loader = Mock(
        side_effect=lambda path: {
            "status": "already_loaded",
            "file_path": path,
            "rows": 1,
        }
    )

    monkeypatch.setattr(
        backfill,
        "load_raw_publication_file",
        raw_loader,
    )

    transform = Mock(
        side_effect=lambda path: (
            publications[path],
            pd.DataFrame({"fuel": [1]}),
            pd.DataFrame({"system": [1]}),
        )
    )

    monkeypatch.setattr(
        backfill,
        "transform_publication_file",
        transform,
    )

    silver_loader = Mock(
        return_value={
            "fuel_rows_database": 1,
            "system_rows_database": 1,
        }
    )

    monkeypatch.setattr(
        backfill,
        "load_silver_dataframes",
        silver_loader,
    )

    publication_loader = Mock(
        side_effect=lambda path:
            publications[path].copy()
    )

    monkeypatch.setattr(
        backfill,
        "load_transformation_publication_file",
        publication_loader,
    )

    save_outputs = Mock()

    monkeypatch.setattr(
        backfill,
        "save_outputs",
        save_outputs,
    )

    analytics_loader = Mock(
        return_value={
            "unit_rows": 1,
            "fuel_rows": 1,
            "system_rows": 1,
        }
    )

    monkeypatch.setattr(
        backfill,
        "load_analytics_dataframes",
        analytics_loader,
    )

    connection = Mock()

    engine = MagicMock()

    engine.begin.return_value.__enter__.return_value = (
        connection
    )

    monkeypatch.setattr(
        backfill,
        "get_engine",
        Mock(return_value=engine),
    )

    result = backfill.backfill_database()

    assert len(
        result["publications"]
    ) == 3

    assert len(
        result["revision_pairs"]
    ) == 2

    assert raw_loader.call_count == 3
    assert transform.call_count == 3
    assert silver_loader.call_count == 3

    assert publication_loader.call_args_list == [
        call(file_23),
        call(file_00),
        call(file_00),
        call(file_01),
    ]

    assert analytics_loader.call_count == 2
    assert save_outputs.call_count == 2

    assert [
        pair["changed_rows"]
        for pair in result["revision_pairs"]
    ] == [
        1,
        1,
    ]
