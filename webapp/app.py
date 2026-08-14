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
