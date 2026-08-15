from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from webapp.databricks_client import (
    fetch_kpis,
    fetch_system_availability,
    fetch_fuel_availability,
    fetch_fuel_revisions_24h,
    fetch_revision_direction_counts,
    fetch_revision_signals_24h,
    fetch_top_unit_revisions_24h,
)


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="GB Generation Availability Intelligence",
    version="1.0.0",
)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)

templates = Jinja2Templates(
    directory=BASE_DIR / "templates"
)


@app.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "service": "gb-generation-availability-intelligence",
    }


@app.get("/api/kpis")
def api_kpis():
    try:
        return fetch_kpis()

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Unable to query Databricks KPI data",
        ) from exc


@app.get("/api/system-availability")
def api_system_availability():
    try:
        return fetch_system_availability()

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Unable to query system availability data",
        ) from exc


@app.get("/api/fuel-availability")
def api_fuel_availability():
    try:
        return fetch_fuel_availability()

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Unable to query fuel availability data",
        ) from exc


@app.get("/api/fuel-revisions")
def api_fuel_revisions():
    try:
        return fetch_fuel_revisions_24h()

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Unable to query fuel revision data",
        ) from exc


@app.get("/api/revision-directions")
def api_revision_directions():
    try:
        return fetch_revision_direction_counts()

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Unable to query revision direction data",
        ) from exc


@app.get("/api/revision-signals")
def api_revision_signals():
    try:
        return fetch_revision_signals_24h()

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Unable to query revision intelligence",
        ) from exc



@app.get("/api/stability-intelligence")
def api_stability_intelligence():
    """
    Build a stakeholder-facing availability stability indicator
    from the revision intelligence already produced by the
    Databricks analytical layer.

    This is a custom analytical indicator. It is not an official
    Elexon or NESO adequacy, margin or reliability metric.
    """

    try:
        directions = fetch_revision_direction_counts()
        fuel_revisions = fetch_fuel_revisions_24h()
        signals = fetch_revision_signals_24h()

        if not directions:
            raise ValueError(
                "Revision direction history is unavailable"
            )

        direction_lookup = {
            str(row["direction"]).lower(): row
            for row in directions
        }

        unchanged_row = direction_lookup.get(
            "unchanged",
            {}
        )

        stability_score = float(
            unchanged_row.get(
                "share_pct",
                0.0
            )
        )

        changed_share = max(
            0.0,
            100.0 - stability_score
        )

        if stability_score >= 95:
            stability_band = "Highly stable"

        elif stability_score >= 90:
            stability_band = "Stable"

        elif stability_score >= 80:
            stability_band = "Moderately stable"

        else:
            stability_band = "High revision activity"


        net_revision_mw = sum(
            float(
                row.get(
                    "net_revision_mw",
                    0.0
                )
                or 0.0
            )
            for row in fuel_revisions
        )


        if net_revision_mw > 0:
            watch_status = "UPWARD BIAS"

            watch_tone = "positive"

            watch_detail = (
                "Latest 24-hour revision activity is "
                "net positive across the represented "
                "fuel categories."
            )

        elif net_revision_mw < 0:
            watch_status = "DOWNWARD WATCH"

            watch_tone = "negative"

            watch_detail = (
                "Latest 24-hour revision activity is "
                "net negative across the represented "
                "fuel categories."
            )

        else:
            watch_status = "BALANCED"

            watch_tone = "neutral"

            watch_detail = (
                "Latest 24-hour upward and downward "
                "revision movements are broadly balanced."
            )


        most_revised_fuel = (
            signals.get(
                "most_revised_fuel",
                {}
            )
            if signals
            else {}
        )


        return {
            "stability_score": round(
                stability_score,
                2
            ),

            "stability_band":
                stability_band,

            "changed_revision_share_pct": round(
                changed_share,
                2
            ),

            "net_revision_mw_24h": round(
                net_revision_mw,
                1
            ),

            "watch_status":
                watch_status,

            "watch_tone":
                watch_tone,

            "watch_detail":
                watch_detail,

            "most_revised_fuel": (
                most_revised_fuel.get(
                    "fuel_label"
                )
                or most_revised_fuel.get(
                    "fuel_type"
                )
                or "Unavailable"
            ),

            "most_revised_fuel_abs_mw": float(
                most_revised_fuel.get(
                    "absolute_revision_mw",
                    0.0
                )
                or 0.0
            ),

            "latest_publication": (
                signals.get(
                    "latest_publication"
                )
                if signals
                else None
            ),

            "methodology": (
                "Custom analytical stability indicator "
                "derived from publication-to-publication "
                "revision behaviour. It is not an official "
                "Elexon or NESO adequacy metric."
            ),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Unable to calculate availability "
                "stability intelligence"
            ),
        ) from exc


@app.get("/api/top-unit-revisions")
def api_top_unit_revisions():
    try:
        return fetch_top_unit_revisions_24h(limit=10)

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Unable to query top unit revisions",
        ) from exc


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title":
                "GB Generation Availability Intelligence",
        },
    )
