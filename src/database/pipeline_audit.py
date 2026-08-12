from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from src.database.postgres import get_engine


def start_pipeline_run(
    pipeline_name: str,
    source_dataset: str,
) -> int:
    """Create a new RUNNING pipeline audit record."""

    engine = get_engine()

    with engine.begin() as connection:
        run_id = connection.execute(
            text(
                """
                INSERT INTO governance.pipeline_run (
                    pipeline_name,
                    source_dataset,
                    status
                )
                VALUES (
                    :pipeline_name,
                    :source_dataset,
                    'RUNNING'
                )
                RETURNING pipeline_run_id
                """
            ),
            {
                "pipeline_name": pipeline_name,
                "source_dataset": source_dataset,
            },
        ).scalar_one()

    return int(run_id)


def complete_pipeline_run(
    pipeline_run_id: int,
    source_publish_time: datetime,
    rows_processed: int,
) -> None:
    """Mark an existing pipeline run as successful."""

    engine = get_engine()

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE governance.pipeline_run
                SET
                    source_publish_time = :source_publish_time,
                    completed_at = NOW(),
                    rows_processed = :rows_processed,
                    status = 'SUCCEEDED',
                    error_message = NULL
                WHERE pipeline_run_id = :pipeline_run_id
                """
            ),
            {
                "pipeline_run_id": pipeline_run_id,
                "source_publish_time": source_publish_time,
                "rows_processed": rows_processed,
            },
        )


def fail_pipeline_run(
    pipeline_run_id: int,
    error_message: str,
    source_publish_time: datetime | None = None,
) -> None:
    """Mark an existing pipeline run as failed."""

    engine = get_engine()

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE governance.pipeline_run
                SET
                    source_publish_time = COALESCE(
                        :source_publish_time,
                        source_publish_time
                    ),
                    completed_at = NOW(),
                    status = 'FAILED',
                    error_message = :error_message
                WHERE pipeline_run_id = :pipeline_run_id
                """
            ),
            {
                "pipeline_run_id": pipeline_run_id,
                "source_publish_time": source_publish_time,
                "error_message": error_message[:5000],
            },
        )
