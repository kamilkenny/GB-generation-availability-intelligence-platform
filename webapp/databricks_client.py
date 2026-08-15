import os

from databricks import sql
from databricks.sdk.core import Config, oauth_service_principal


HTTP_PATH = os.getenv(
    "DATABRICKS_HTTP_PATH",
    "/sql/1.0/warehouses/68afda64ba895950",
)


def get_connection():
    """
    Create a Databricks SQL connection.

    Azure production:
        OAuth machine-to-machine authentication using a
        Databricks service principal.

    Local development:
        Fall back to the existing gb-energy-sql CLI profile.
    """

    server_hostname = os.getenv(
        "DATABRICKS_SERVER_HOSTNAME"
    )

    client_id = os.getenv(
        "DATABRICKS_CLIENT_ID"
    )

    client_secret = os.getenv(
        "DATABRICKS_CLIENT_SECRET"
    )

    # ---------------------------------------------------------
    # AZURE / PRODUCTION OAUTH M2M
    # ---------------------------------------------------------

    if (
        server_hostname
        and client_id
        and client_secret
    ):
        server_hostname = (
            server_hostname
            .replace("https://", "")
            .rstrip("/")
        )

        def credential_provider():
            config = Config(
                host=f"https://{server_hostname}",
                client_id=client_id,
                client_secret=client_secret,
            )

            return oauth_service_principal(
                config
            )

        return sql.connect(
            server_hostname=server_hostname,
            http_path=HTTP_PATH,
            credentials_provider=credential_provider,
            catalog="workspace",
            schema="gb_generation",
        )

    # ---------------------------------------------------------
    # LOCAL DEVELOPMENT PROFILE
    # ---------------------------------------------------------

    profile = os.getenv(
        "DATABRICKS_PROFILE",
        "gb-energy-sql",
    )

    cfg = Config(
        profile=profile
    )

    server_hostname = (
        cfg.host
        .replace("https://", "")
        .rstrip("/")
    )

    return sql.connect(
        server_hostname=server_hostname,
        http_path=HTTP_PATH,
        access_token=cfg.token,
        catalog="workspace",
        schema="gb_generation",
    )


def fetch_kpis():
    query = """
    WITH latest_system_publication AS (
        SELECT
            MAX(publishTime) AS latest_publication
        FROM workspace.gb_generation.system_availability_history
    ),

    nearest_forecast AS (
        SELECT
            MIN(s.forecastDate) AS nearest_forecast_date
        FROM workspace.gb_generation.system_availability_history s
        CROSS JOIN latest_system_publication l
        WHERE s.publishTime = l.latest_publication
          AND s.forecastDate >= l.latest_publication
    ),

    latest_system_mw AS (
        SELECT
            MAX(s.availableMW) AS system_available_mw
        FROM workspace.gb_generation.system_availability_history s
        CROSS JOIN latest_system_publication l
        CROSS JOIN nearest_forecast n
        WHERE s.publishTime = l.latest_publication
          AND s.forecastDate = n.nearest_forecast_date
    )

    SELECT
        l.latest_publication,
        m.system_available_mw,

        (
            SELECT COUNT(DISTINCT publishTime)
            FROM workspace.gb_generation.system_availability_history
        ) AS publications_loaded,

        (
            SELECT COUNT(DISTINCT fuelType)
            FROM workspace.gb_generation.fuel_availability_history
        ) AS fuel_types_tracked

    FROM latest_system_publication l
    CROSS JOIN latest_system_mw m
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

    latest_publication = row[0]

    return {
        "latest_publication": (
            latest_publication.isoformat()
            if latest_publication is not None
            else None
        ),
        "system_available_mw": (
            float(row[1])
            if row[1] is not None
            else None
        ),
        "publications_loaded": int(row[2]),
        "fuel_types_tracked": int(row[3]),
    }


def fetch_system_availability():
    """
    Return the forward system availability profile
    from the latest publication.
    """

    query = """
    WITH latest_publication AS (
        SELECT
            MAX(publishTime) AS publishTime
        FROM workspace.gb_generation.system_availability_history
    )

    SELECT
        s.forecastDate,
        MAX(s.availableMW) AS availableMW
    FROM workspace.gb_generation.system_availability_history s
    CROSS JOIN latest_publication l
    WHERE s.publishTime = l.publishTime
    GROUP BY
        s.forecastDate
    ORDER BY
        s.forecastDate
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    return [
        {
            "forecast_date": (
                row[0].isoformat()
                if row[0] is not None
                else None
            ),
            "available_mw": (
                float(row[1])
                if row[1] is not None
                else None
            ),
        }
        for row in rows
    ]



FUEL_TYPE_LABELS = {
    "CCGT": "Combined Cycle Gas Turbine",
    "OCGT": "Open Cycle Gas Turbine",
    "PS": "Pumped Storage Hydro",
    "NPSHYD": "Non-Pumped Storage Hydro",

    "NUCLEAR": "Nuclear",
    "WIND": "Wind",
    "BIOMASS": "Biomass",
    "COAL": "Coal",
    "OIL": "Oil",
    "OTHER": "Other Generation",

    "INTFR": "IFA Interconnector, France",
    "INTIFA2": "IFA2 Interconnector, France",
    "INTELEC": "ElecLink Interconnector, France",

    "INTIRL": "Moyle Interconnector, Ireland",
    "INTEW": "East-West Interconnector, Ireland",
    "INTGRNL": "Greenlink Interconnector, Ireland",

    "INTNED": "Netherlands Interconnector",
    "INTNEM": "Nemo Link, Belgium",
    "INTNSL": "North Sea Link, Norway",
    "INTVKL": "Viking Link, Denmark",
}

def fetch_fuel_availability():
    """
    Return available generation MW by fuel type for the
    nearest forecast point in the latest publication.
    """

    query = """
    WITH latest_publication AS (
        SELECT
            MAX(publishTime) AS publishTime
        FROM workspace.gb_generation.fuel_availability_history
    ),

    nearest_forecast AS (
        SELECT
            MIN(f.forecastDate) AS forecastDate
        FROM workspace.gb_generation.fuel_availability_history f
        CROSS JOIN latest_publication l
        WHERE f.publishTime = l.publishTime
          AND f.forecastDate >= l.publishTime
    )

    SELECT
        f.fuelType,
        SUM(f.availableMW) AS availableMW
    FROM workspace.gb_generation.fuel_availability_history f
    CROSS JOIN latest_publication l
    CROSS JOIN nearest_forecast n
    WHERE f.publishTime = l.publishTime
      AND f.forecastDate = n.forecastDate
    GROUP BY
        f.fuelType
    ORDER BY
        availableMW DESC,
        f.fuelType
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    result = [
        {
            "fuel_type": str(row[0]),

            "fuel_label": (
                f"{FUEL_TYPE_LABELS.get(str(row[0]), str(row[0]))} "
                f"({str(row[0])})"
            ),

            "available_mw": (
                float(row[1])
                if row[1] is not None
                else 0.0
            ),
        }
        for row in rows
    ]

    total_mw = sum(
        item["available_mw"]
        for item in result
    )

    for item in result:
        item["share_pct"] = (
            round(
                item["available_mw"]
                / total_mw
                * 100,
                1,
            )
            if total_mw > 0
            else 0.0
        )

    return result


def fetch_fuel_revisions_24h():
    """
    Return net availability revisions by fuel type
    across the latest 24-hour publication window.
    """

    query = """
    WITH latest_publication AS (
        SELECT
            MAX(latestPublishTime) AS latestPublishTime
        FROM workspace.gb_generation.fuel_revision_history
    )

    SELECT
        r.fuelType,
        SUM(r.revisionMW) AS netRevisionMW
    FROM workspace.gb_generation.fuel_revision_history r
    CROSS JOIN latest_publication l
    WHERE r.latestPublishTime > (
        l.latestPublishTime - INTERVAL 24 HOURS
    )
      AND r.latestPublishTime <= l.latestPublishTime
    GROUP BY
        r.fuelType
    HAVING
        ABS(SUM(r.revisionMW)) > 0
    ORDER BY
        ABS(netRevisionMW) DESC,
        r.fuelType
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    return [
        {
            "fuel_type": str(row[0]),

            "fuel_label": (
                f"{FUEL_TYPE_LABELS.get(str(row[0]), str(row[0]))} "
                f"({str(row[0])})"
            ),

            "net_revision_mw": (
                float(row[1])
                if row[1] is not None
                else 0.0
            ),
        }
        for row in rows
    ]


def fetch_revision_direction_counts():
    """
    Return historical unit revision counts by direction.
    """

    query = """
    SELECT
        revisionDirection,
        COUNT(*) AS revisionCount
    FROM workspace.gb_generation.unit_revision_history
    GROUP BY revisionDirection
    ORDER BY revisionCount DESC
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    total_count = sum(
        int(row[1])
        for row in rows
    )

    return [
        {
            "direction": str(row[0]),
            "count": int(row[1]),
            "share_pct": (
                round(
                    int(row[1])
                    / total_count
                    * 100,
                    2,
                )
                if total_count > 0
                else 0.0
            ),
        }
        for row in rows
    ]



def fetch_revision_signals_24h():
    """
    Return headline unit and fuel revision intelligence
    across the latest 24-hour publication window.
    """

    latest_query = """
    SELECT
        MAX(latestPublishTime) AS latestPublishTime
    FROM workspace.gb_generation.unit_revision_history
    """

    upward_query = """
    WITH latest_publication AS (
        SELECT
            MAX(latestPublishTime) AS latestPublishTime
        FROM workspace.gb_generation.unit_revision_history
    )
    SELECT
        COALESCE(
            r.nationalGridBmUnit,
            r.bmUnit,
            'Unknown unit'
        ) AS unitName,
        r.fuelType,
        r.revisionMW,
        r.forecastDate,
        r.latestPublishTime
    FROM workspace.gb_generation.unit_revision_history r
    CROSS JOIN latest_publication l
    WHERE r.latestPublishTime > (
        l.latestPublishTime - INTERVAL 24 HOURS
    )
      AND r.latestPublishTime <= l.latestPublishTime
      AND r.revisionMW > 0
    ORDER BY
        r.revisionMW DESC
    LIMIT 1
    """

    downward_query = """
    WITH latest_publication AS (
        SELECT
            MAX(latestPublishTime) AS latestPublishTime
        FROM workspace.gb_generation.unit_revision_history
    )
    SELECT
        COALESCE(
            r.nationalGridBmUnit,
            r.bmUnit,
            'Unknown unit'
        ) AS unitName,
        r.fuelType,
        r.revisionMW,
        r.forecastDate,
        r.latestPublishTime
    FROM workspace.gb_generation.unit_revision_history r
    CROSS JOIN latest_publication l
    WHERE r.latestPublishTime > (
        l.latestPublishTime - INTERVAL 24 HOURS
    )
      AND r.latestPublishTime <= l.latestPublishTime
      AND r.revisionMW < 0
    ORDER BY
        r.revisionMW ASC
    LIMIT 1
    """

    fuel_query = """
    WITH latest_publication AS (
        SELECT
            MAX(latestPublishTime) AS latestPublishTime
        FROM workspace.gb_generation.unit_revision_history
    )
    SELECT
        r.fuelType,
        SUM(ABS(r.revisionMW)) AS absoluteRevisionMW,
        SUM(r.revisionMW) AS netRevisionMW,
        COUNT(*) AS revisionRecords
    FROM workspace.gb_generation.unit_revision_history r
    CROSS JOIN latest_publication l
    WHERE r.latestPublishTime > (
        l.latestPublishTime - INTERVAL 24 HOURS
    )
      AND r.latestPublishTime <= l.latestPublishTime
      AND r.revisionMW <> 0
    GROUP BY
        r.fuelType
    ORDER BY
        absoluteRevisionMW DESC
    LIMIT 1
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(latest_query)
            latest_row = cursor.fetchone()

            cursor.execute(upward_query)
            upward_row = cursor.fetchone()

            cursor.execute(downward_query)
            downward_row = cursor.fetchone()

            cursor.execute(fuel_query)
            fuel_row = cursor.fetchone()

    def unit_signal(row):
        if row is None:
            return None

        fuel_type = (
            str(row[1])
            if row[1] is not None
            else "Unknown"
        )

        return {
            "unit": str(row[0]),
            "fuel_type": fuel_type,
            "fuel_label": FUEL_TYPE_LABELS.get(
                fuel_type,
                fuel_type,
            ),
            "revision_mw": float(row[2]),
            "forecast_date": (
                row[3].isoformat()
                if row[3] is not None
                else None
            ),
            "publication_time": (
                row[4].isoformat()
                if row[4] is not None
                else None
            ),
        }

    most_revised_fuel = None

    if fuel_row is not None:
        fuel_type = (
            str(fuel_row[0])
            if fuel_row[0] is not None
            else "Unknown"
        )

        most_revised_fuel = {
            "fuel_type": fuel_type,
            "fuel_label": FUEL_TYPE_LABELS.get(
                fuel_type,
                fuel_type,
            ),
            "absolute_revision_mw": float(fuel_row[1]),
            "net_revision_mw": float(fuel_row[2]),
            "revision_records": int(fuel_row[3]),
        }

    return {
        "latest_publication": (
            latest_row[0].isoformat()
            if latest_row
            and latest_row[0] is not None
            else None
        ),
        "largest_upward": unit_signal(upward_row),
        "largest_downward": unit_signal(downward_row),
        "most_revised_fuel": most_revised_fuel,
    }


def fetch_top_unit_revisions_24h(limit=10):
    """
    Return the largest individual unit availability revisions
    from the latest 24-hour publication window.
    """

    query = f"""
    WITH latest_publication AS (
        SELECT
            MAX(latestPublishTime) AS latestPublishTime
        FROM workspace.gb_generation.unit_revision_history
    )

    SELECT
        COALESCE(
            r.nationalGridBmUnit,
            r.bmUnit,
            'Unknown unit'
        ) AS unitName,
        r.fuelType,
        r.revisionDirection,
        r.revisionMW,
        r.forecastDate,
        r.latestPublishTime
    FROM workspace.gb_generation.unit_revision_history r
    CROSS JOIN latest_publication l
    WHERE r.latestPublishTime > (
        l.latestPublishTime - INTERVAL 24 HOURS
    )
      AND r.latestPublishTime <= l.latestPublishTime
      AND r.revisionMW <> 0
    ORDER BY
        ABS(r.revisionMW) DESC,
        r.latestPublishTime DESC
    LIMIT {int(limit)}
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    result = []

    for row in rows:
        fuel_type = (
            str(row[1])
            if row[1] is not None
            else "Unknown"
        )

        result.append(
            {
                "unit": str(row[0]),

                "fuel_type": fuel_type,

                "fuel_label": (
                    FUEL_TYPE_LABELS.get(
                        fuel_type,
                        fuel_type,
                    )
                ),

                "direction": str(row[2]),

                "revision_mw": float(row[3]),

                "forecast_date": (
                    row[4].isoformat()
                    if row[4] is not None
                    else None
                ),

                "publication_time": (
                    row[5].isoformat()
                    if row[5] is not None
                    else None
                ),
            }
        )

    return result
