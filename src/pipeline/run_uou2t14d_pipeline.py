from __future__ import annotations

import pandas as pd

from src.analytics.build_availability_revisions import (
    main as build_revisions,
)
from src.database.load_silver_availability import (
    main as load_silver,
)
from src.database.load_revision_analytics import (
    main as load_revision_analytics,
)
from src.database.load_uou2t14d import (
    latest_canonical_publication,
    load_publication,
)
from src.database.pipeline_audit import (
    complete_pipeline_run,
    fail_pipeline_run,
    start_pipeline_run,
)
from src.ingestion.collect_uou2t14d import (
    main as collect_uou2t14d,
)
from src.transformation.transform_uou2t14d import (
    main as transform_uou2t14d,
)


PIPELINE_NAME = "uou2t14d_end_to_end"
SOURCE_DATASET = "UOU2T14D"


def get_source_details():
    """Read publication metadata from the latest canonical snapshot."""

    file_path = latest_canonical_publication()

    df = pd.read_parquet(file_path)

    if df.empty:
        raise ValueError(
            "Latest canonical UOU2T14D publication is empty."
        )

    publish_times = pd.to_datetime(
        df["publishTime"],
        utc=True,
        errors="coerce",
    ).dropna().unique()

    if len(publish_times) != 1:
        raise ValueError(
            "Expected exactly one source publication time "
            "in the canonical snapshot."
        )

    source_publish_time = pd.Timestamp(
        publish_times[0]
    ).to_pydatetime()

    return (
        file_path,
        source_publish_time,
        int(len(df)),
    )


def main() -> None:
    """Run the governed UOU2T14D pipeline."""

    run_id = start_pipeline_run(
        pipeline_name=PIPELINE_NAME,
        source_dataset=SOURCE_DATASET,
    )

    source_publish_time = None
    rows_processed = 0
    current_stage = "initialisation"

    print()
    print("GB GENERATION AVAILABILITY PIPELINE")
    print("-----------------------------------")
    print("Pipeline run ID:", run_id)

    try:
        current_stage = "Elexon ingestion"
        print()
        print("[1/6] Elexon ingestion")
        collect_uou2t14d()

        (
            source_file,
            source_publish_time,
            rows_processed,
        ) = get_source_details()

        print("Canonical source:", source_file)
        print(
            "Source publication:",
            source_publish_time,
        )
        print(
            "Source rows:",
            f"{rows_processed:,}",
        )

        current_stage = "availability transformation"
        print()
        print("[2/6] Availability transformation")
        transform_uou2t14d()

        current_stage = "Raw PostgreSQL load"
        print()
        print("[3/6] Raw PostgreSQL load")
        load_publication()

        current_stage = "Silver PostgreSQL load"
        print()
        print("[4/6] Silver PostgreSQL load")
        load_silver()

        current_stage = "revision intelligence"
        print()
        print("[5/6] Revision intelligence")
        build_revisions()

        publication_count = len(
            list(
                source_file.parent.glob(
                    "uou2t14d_publish_*.parquet"
                )
            )
        )

        current_stage = (
            "Revision Analytics PostgreSQL load"
        )

        print()
        print(
            "[6/6] Revision Analytics "
            "PostgreSQL load"
        )

        if publication_count >= 2:
            load_revision_analytics()
        else:
            print(
                "Skipped: fewer than two canonical "
                "Elexon publications are available."
            )

        complete_pipeline_run(
            pipeline_run_id=run_id,
            source_publish_time=source_publish_time,
            rows_processed=rows_processed,
        )

        print()
        print("PIPELINE COMPLETE")
        print("-----------------")
        print("Status: SUCCEEDED")
        print("Pipeline run ID:", run_id)
        print(
            "Source publication:",
            source_publish_time,
        )
        print(
            "Rows processed:",
            f"{rows_processed:,}",
        )

    except Exception as exc:
        error_message = (
            f"Stage '{current_stage}' failed: {exc}"
        )

        fail_pipeline_run(
            pipeline_run_id=run_id,
            source_publish_time=source_publish_time,
            error_message=error_message,
        )

        print()
        print("PIPELINE FAILED")
        print("---------------")
        print("Pipeline run ID:", run_id)
        print("Stage:", current_stage)
        print("Error:", exc)

        raise


if __name__ == "__main__":
    main()
