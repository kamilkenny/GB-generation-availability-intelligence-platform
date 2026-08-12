from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

import src.pipeline.run_uou2t14d_pipeline as pipeline


SOURCE_TIME = datetime(
    2026,
    8,
    12,
    1,
    0,
    tzinfo=timezone.utc,
)


def configure_pipeline_mocks(
    monkeypatch,
    tmp_path,
    publication_count=2,
):
    """Replace external pipeline stages with controlled mocks."""

    for index in range(publication_count):
        (
            tmp_path
            / f"uou2t14d_publish_test_{index}.parquet"
        ).touch()

    source_file = (
        tmp_path
        / "uou2t14d_publish_test_0.parquet"
    )

    mocks = {
        "start_pipeline_run": Mock(
            return_value=101
        ),
        "collect_uou2t14d": Mock(),
        "get_source_details": Mock(
            return_value=(
                source_file,
                SOURCE_TIME,
                7150,
            )
        ),
        "transform_uou2t14d": Mock(),
        "load_publication": Mock(),
        "load_silver": Mock(),
        "build_revisions": Mock(),
        "load_revision_analytics": Mock(),
        "complete_pipeline_run": Mock(),
        "fail_pipeline_run": Mock(),
    }

    for name, mock in mocks.items():
        monkeypatch.setattr(
            pipeline,
            name,
            mock,
        )

    return mocks


def test_pipeline_success_runs_all_six_stages(
    monkeypatch,
    tmp_path,
):
    mocks = configure_pipeline_mocks(
        monkeypatch,
        tmp_path,
        publication_count=2,
    )

    pipeline.main()

    mocks[
        "start_pipeline_run"
    ].assert_called_once_with(
        pipeline_name=(
            pipeline.PIPELINE_NAME
        ),
        source_dataset=(
            pipeline.SOURCE_DATASET
        ),
    )

    mocks[
        "collect_uou2t14d"
    ].assert_called_once()

    mocks[
        "transform_uou2t14d"
    ].assert_called_once()

    mocks[
        "load_publication"
    ].assert_called_once()

    mocks[
        "load_silver"
    ].assert_called_once()

    mocks[
        "build_revisions"
    ].assert_called_once()

    mocks[
        "load_revision_analytics"
    ].assert_called_once()

    mocks[
        "complete_pipeline_run"
    ].assert_called_once_with(
        pipeline_run_id=101,
        source_publish_time=SOURCE_TIME,
        rows_processed=7150,
    )

    mocks[
        "fail_pipeline_run"
    ].assert_not_called()


def test_pipeline_skips_revision_analytics_with_one_publication(
    monkeypatch,
    tmp_path,
):
    mocks = configure_pipeline_mocks(
        monkeypatch,
        tmp_path,
        publication_count=1,
    )

    pipeline.main()

    mocks[
        "build_revisions"
    ].assert_called_once()

    mocks[
        "load_revision_analytics"
    ].assert_not_called()

    mocks[
        "complete_pipeline_run"
    ].assert_called_once()

    mocks[
        "fail_pipeline_run"
    ].assert_not_called()


def test_pipeline_failure_is_recorded_with_stage(
    monkeypatch,
    tmp_path,
):
    mocks = configure_pipeline_mocks(
        monkeypatch,
        tmp_path,
        publication_count=2,
    )

    mocks[
        "transform_uou2t14d"
    ].side_effect = RuntimeError(
        "Synthetic transformation failure"
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic transformation failure",
    ):
        pipeline.main()

    mocks[
        "fail_pipeline_run"
    ].assert_called_once()

    failure_call = mocks[
        "fail_pipeline_run"
    ].call_args.kwargs

    assert (
        failure_call["pipeline_run_id"]
        == 101
    )

    assert (
        failure_call["source_publish_time"]
        == SOURCE_TIME
    )

    assert (
        "availability transformation"
        in failure_call["error_message"]
    )

    assert (
        "Synthetic transformation failure"
        in failure_call["error_message"]
    )

    mocks[
        "complete_pipeline_run"
    ].assert_not_called()

    mocks[
        "load_publication"
    ].assert_not_called()

    mocks[
        "load_silver"
    ].assert_not_called()

    mocks[
        "build_revisions"
    ].assert_not_called()

    mocks[
        "load_revision_analytics"
    ].assert_not_called()


def test_analytics_failure_is_recorded_with_stage(
    monkeypatch,
    tmp_path,
):
    mocks = configure_pipeline_mocks(
        monkeypatch,
        tmp_path,
        publication_count=2,
    )

    mocks[
        "load_revision_analytics"
    ].side_effect = RuntimeError(
        "Synthetic Analytics failure"
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic Analytics failure",
    ):
        pipeline.main()

    mocks[
        "fail_pipeline_run"
    ].assert_called_once()

    failure_call = mocks[
        "fail_pipeline_run"
    ].call_args.kwargs

    assert (
        failure_call["pipeline_run_id"]
        == 101
    )

    assert (
        "Revision Analytics PostgreSQL load"
        in failure_call["error_message"]
    )

    assert (
        "Synthetic Analytics failure"
        in failure_call["error_message"]
    )

    mocks[
        "complete_pipeline_run"
    ].assert_not_called()
