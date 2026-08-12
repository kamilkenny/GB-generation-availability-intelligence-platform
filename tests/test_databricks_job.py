import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

JOB_PATH = (
    PROJECT_ROOT
    / "databricks"
    / "availability_history_job.py"
)

SPEC = importlib.util.spec_from_file_location(
    "availability_history_job",
    JOB_PATH,
)

assert SPEC is not None
assert SPEC.loader is not None

JOB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(JOB)


def test_parse_args_accepts_storage_paths(
    monkeypatch,
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "availability_history_job.py",
            "--raw-directory",
            "/Volumes/energy/raw/uou2t14d",
            "--output-directory",
            "/Volumes/energy/processed/uou2t14d",
        ],
    )

    args = JOB.parse_args()

    assert (
        args.raw_directory
        == "/Volumes/energy/raw/uou2t14d"
    )

    assert (
        args.output_directory
        == "/Volumes/energy/processed/uou2t14d"
    )


def test_execute_job_uses_shared_pipeline(
    monkeypatch,
):
    captured = {}

    expected_result = {
        "quality": {
            "rows": 10,
        },
        "row_counts": {
            "system_availability_history": 2,
        },
    }

    def fake_run_spark_pipeline(
        spark,
        raw_directory,
        output_directory,
    ):
        captured["spark"] = spark
        captured["raw_directory"] = (
            raw_directory
        )
        captured["output_directory"] = (
            output_directory
        )

        return expected_result

    monkeypatch.setattr(
        JOB,
        "run_spark_pipeline",
        fake_run_spark_pipeline,
    )

    fake_spark = object()

    result = JOB.execute_job(
        fake_spark,
        raw_directory="/raw/uou2t14d",
        output_directory="/processed/uou2t14d",
    )

    assert result == expected_result
    assert captured["spark"] is fake_spark

    assert (
        captured["raw_directory"]
        == Path("/raw/uou2t14d")
    )

    assert (
        captured["output_directory"]
        == Path("/processed/uou2t14d")
    )


def test_get_spark_session_reuses_active_session(
    monkeypatch,
):
    configuration = {}

    class FakeConf:
        def set(
            self,
            key,
            value,
        ):
            configuration[key] = value

    class FakeSpark:
        conf = FakeConf()

    active_spark = FakeSpark()

    monkeypatch.setattr(
        JOB.SparkSession,
        "getActiveSession",
        staticmethod(
            lambda: active_spark
        ),
    )

    spark, created_locally = (
        JOB.get_spark_session()
    )

    assert spark is active_spark
    assert created_locally is False

    assert configuration[
        "spark.sql.session.timeZone"
    ] == "UTC"
