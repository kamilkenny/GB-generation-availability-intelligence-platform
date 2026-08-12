from unittest.mock import Mock

import pandas as pd
import pytest

import src.ingestion.backfill_uou2t14d as backfill
from src.ingestion.elexon_client import (
    ElexonClient,
)


def historical_dataframe():
    rows = []

    for publish_time in [
        pd.Timestamp(
            "2026-08-12T00:00:00Z"
        ),
        pd.Timestamp(
            "2026-08-12T01:00:00Z"
        ),
    ]:
        for unit, fuel, output in [
            ("UNIT-1", "CCGT", 100),
            ("UNIT-2", "WIND", 50),
        ]:
            rows.append(
                {
                    "dataset": "UOU2T14D",
                    "fuelType": fuel,
                    "nationalGridBmUnit": unit,
                    "bmUnit": None,
                    "publishTime": publish_time,
                    "forecastDate": pd.Timestamp(
                        "2026-08-14"
                    ),
                    "outputUsable": output,
                    "collectedAt": pd.Timestamp(
                        "2026-08-12T03:00:00Z"
                    ),
                }
            )

    return pd.DataFrame(rows)


def test_split_publications_returns_one_frame_per_publish_time():
    df = historical_dataframe()

    publications = backfill.split_publications(
        df
    )

    assert len(publications) == 2

    assert (
        publications[0]["publishTime"]
        .nunique()
        == 1
    )

    assert (
        publications[1]["publishTime"]
        .nunique()
        == 1
    )

    assert len(publications[0]) == 2
    assert len(publications[1]) == 2


def test_split_publications_returns_empty_list_for_empty_frame():
    result = backfill.split_publications(
        pd.DataFrame()
    )

    assert result == []


def test_split_publications_requires_publish_time():
    df = pd.DataFrame(
        {
            "nationalGridBmUnit": [
                "UNIT-1"
            ]
        }
    )

    with pytest.raises(
        ValueError,
        match="does not contain publishTime",
    ):
        backfill.split_publications(df)


def test_backfill_range_saves_each_publication_once(
    monkeypatch,
):
    df = historical_dataframe()

    fake_client = Mock()

    fake_client.get_generation_availability_by_publish_time.return_value = (
        df
    )

    monkeypatch.setattr(
        backfill,
        "ElexonClient",
        Mock(
            return_value=fake_client
        ),
    )

    save_results = [
        (
            Mock(),
            Mock(),
            True,
        ),
        (
            Mock(),
            Mock(),
            False,
        ),
    ]

    save_mock = Mock(
        side_effect=save_results
    )

    monkeypatch.setattr(
        backfill,
        "save_snapshot",
        save_mock,
    )

    result = backfill.backfill_range(
        "2026-08-12T00:00:00Z",
        "2026-08-12T01:00:00Z",
    )

    assert result[
        "rows_returned"
    ] == 4

    assert result[
        "publications_found"
    ] == 2

    assert result[
        "publications_created"
    ] == 1

    assert result[
        "publications_existing"
    ] == 1

    assert save_mock.call_count == 2


def test_historical_client_rejects_invalid_range():
    client = ElexonClient()

    with pytest.raises(
        ValueError,
        match=(
            "publish_datetime_from must be earlier"
        ),
    ):
        client.get_generation_availability_by_publish_time(
            "2026-08-12T02:00:00Z",
            "2026-08-12T01:00:00Z",
        )


def test_historical_client_builds_utc_range_parameters(
    monkeypatch,
):
    client = ElexonClient()

    response = Mock()
    response.json.return_value = []

    get_mock = Mock(
        return_value=response
    )

    monkeypatch.setattr(
        client,
        "_get",
        get_mock,
    )

    result = (
        client
        .get_generation_availability_by_publish_time(
            "2026-08-12T00:00:00+01:00",
            "2026-08-12T02:00:00+01:00",
        )
    )

    assert result.empty

    get_mock.assert_called_once_with(
        "/datasets/UOU2T14D/stream",
        params={
            "publishDateTimeFrom":
                "2026-08-11T23:00:00Z",
            "publishDateTimeTo":
                "2026-08-12T01:00:00Z",
        },
    )


def test_historical_client_builds_utc_range_parameters(
    monkeypatch,
):
    client = ElexonClient()

    response = Mock()
    response.json.return_value = []

    get_mock = Mock(
        return_value=response
    )

    monkeypatch.setattr(
        client,
        "_get",
        get_mock,
    )

    result = (
        client
        .get_generation_availability_by_publish_time(
            "2026-08-12T00:00:00+01:00",
            "2026-08-12T02:00:00+01:00",
        )
    )

    assert result.empty

    get_mock.assert_called_once_with(
        "/datasets/UOU2T14D/stream",
        params={
            "publishDateTimeFrom":
                "2026-08-11T23:00:00Z",
            "publishDateTimeTo":
                "2026-08-12T01:00:00Z",
        },
    )
