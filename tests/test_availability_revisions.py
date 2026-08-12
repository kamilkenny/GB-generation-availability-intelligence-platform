import pandas as pd
import pytest

from src.analytics.build_availability_revisions import (
    build_fuel_revisions,
    build_system_revisions,
    build_unit_revisions,
)


FORECAST_DATE = pd.Timestamp(
    "2026-08-14"
)

PREVIOUS_PUBLICATION = pd.Timestamp(
    "2026-08-12T00:00:00Z"
)

LATEST_PUBLICATION = pd.Timestamp(
    "2026-08-12T01:00:00Z"
)


def make_publication(
    publish_time,
    values,
):
    """Build a small synthetic availability publication."""

    rows = []

    for (
        unit,
        fuel_type,
        availability,
    ) in values:

        rows.append(
            {
                "nationalGridBmUnit": unit,
                "fuelType": fuel_type,
                "forecastDate": FORECAST_DATE,
                "publishTime": publish_time,
                "outputUsable": availability,
            }
        )

    return pd.DataFrame(rows)


def revision_inputs():
    previous = make_publication(
        PREVIOUS_PUBLICATION,
        [
            ("UNIT-A", "CCGT", 100),
            ("UNIT-B", "WIND", 50),
            ("UNIT-C", "CCGT", 0),
            ("UNIT-D", "NUCLEAR", 25),
        ],
    )

    latest = make_publication(
        LATEST_PUBLICATION,
        [
            ("UNIT-A", "CCGT", 130),
            ("UNIT-B", "WIND", 0),
            ("UNIT-C", "CCGT", 40),
            ("UNIT-D", "NUCLEAR", 25),
        ],
    )

    return previous, latest


def get_unit_row(
    revisions,
    unit,
):
    return revisions[
        revisions["nationalGridBmUnit"]
        == unit
    ].iloc[0]


def test_unit_revision_calculations():
    previous, latest = revision_inputs()

    result = build_unit_revisions(
        previous,
        latest,
    )

    assert len(result) == 4

    unit_a = get_unit_row(
        result,
        "UNIT-A",
    )

    assert unit_a["previousAvailableMW"] == 100
    assert unit_a["latestAvailableMW"] == 130
    assert unit_a["revisionMW"] == 30
    assert unit_a["absoluteRevisionMW"] == 30
    assert unit_a["changeDirection"] == "UP"


def test_became_unavailable_is_identified():
    previous, latest = revision_inputs()

    result = build_unit_revisions(
        previous,
        latest,
    )

    unit_b = get_unit_row(
        result,
        "UNIT-B",
    )

    assert unit_b["revisionMW"] == -50
    assert unit_b["changeDirection"] == "DOWN"
    assert bool(
        unit_b["becameUnavailable"]
    ) is True
    assert bool(
        unit_b["returnedAvailable"]
    ) is False


def test_returned_available_is_identified():
    previous, latest = revision_inputs()

    result = build_unit_revisions(
        previous,
        latest,
    )

    unit_c = get_unit_row(
        result,
        "UNIT-C",
    )

    assert unit_c["revisionMW"] == 40
    assert unit_c["changeDirection"] == "UP"
    assert bool(
        unit_c["returnedAvailable"]
    ) is True
    assert bool(
        unit_c["becameUnavailable"]
    ) is False


def test_unchanged_unit_is_identified():
    previous, latest = revision_inputs()

    result = build_unit_revisions(
        previous,
        latest,
    )

    unit_d = get_unit_row(
        result,
        "UNIT-D",
    )

    assert unit_d["revisionMW"] == 0
    assert (
        unit_d["changeDirection"]
        == "UNCHANGED"
    )
    assert bool(
        unit_d["becameUnavailable"]
    ) is False
    assert bool(
        unit_d["returnedAvailable"]
    ) is False


def test_fuel_revision_aggregation():
    previous, latest = revision_inputs()

    unit_revisions = build_unit_revisions(
        previous,
        latest,
    )

    result = build_fuel_revisions(
        unit_revisions
    )

    ccgt = result[
        result["fuelType"] == "CCGT"
    ].iloc[0]

    assert ccgt["previousAvailableMW"] == 100
    assert ccgt["latestAvailableMW"] == 170
    assert ccgt["revisionMW"] == 70
    assert ccgt["changedUnits"] == 2
    assert ccgt["becameUnavailableUnits"] == 0
    assert ccgt["returnedAvailableUnits"] == 1

    wind = result[
        result["fuelType"] == "WIND"
    ].iloc[0]

    assert wind["previousAvailableMW"] == 50
    assert wind["latestAvailableMW"] == 0
    assert wind["revisionMW"] == -50
    assert wind["changedUnits"] == 1
    assert wind["becameUnavailableUnits"] == 1


def test_system_revision_aggregation():
    previous, latest = revision_inputs()

    unit_revisions = build_unit_revisions(
        previous,
        latest,
    )

    result = build_system_revisions(
        unit_revisions
    )

    assert len(result) == 1

    row = result.iloc[0]

    assert row["previousAvailableMW"] == 175
    assert row["latestAvailableMW"] == 195
    assert row["revisionMW"] == 20
    assert row["changedUnits"] == 3
    assert row["becameUnavailableUnits"] == 1
    assert row["returnedAvailableUnits"] == 1


def test_unit_fuel_and_system_revisions_reconcile():
    previous, latest = revision_inputs()

    unit_revisions = build_unit_revisions(
        previous,
        latest,
    )

    fuel_revisions = build_fuel_revisions(
        unit_revisions
    )

    system_revisions = build_system_revisions(
        unit_revisions
    )

    unit_total = unit_revisions[
        "revisionMW"
    ].sum()

    fuel_total = fuel_revisions[
        "revisionMW"
    ].sum()

    system_total = system_revisions[
        "revisionMW"
    ].sum()

    assert unit_total == 20
    assert fuel_total == unit_total
    assert system_total == unit_total


def test_no_overlapping_forecast_dates_raises_error():
    previous = make_publication(
        PREVIOUS_PUBLICATION,
        [
            ("UNIT-A", "CCGT", 100),
        ],
    )

    latest = make_publication(
        LATEST_PUBLICATION,
        [
            ("UNIT-A", "CCGT", 120),
        ],
    )

    latest["forecastDate"] = pd.Timestamp(
        "2026-08-20"
    )

    with pytest.raises(
        ValueError,
        match="no overlapping forecast dates",
    ):
        build_unit_revisions(
            previous,
            latest,
        )
