from __future__ import annotations

from typing import Optional

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import ELEXON_BASE_URL


class ElexonAPIError(Exception):
    """Raised when an Elexon API request cannot be completed."""


class ElexonClient:
    """Client for retrieving data from the Elexon Insights API."""

    def __init__(
        self,
        base_url: str = ELEXON_BASE_URL,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": (
                    "GB-Generation-Availability-Intelligence-Platform/1.0"
                ),
            }
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def _get(
        self,
        endpoint: str,
        params: Optional[dict] = None,
    ):
        """Perform a GET request with automatic retry."""

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        response = self.session.get(
            url,
            params=params,
            timeout=self.timeout,
        )

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise ElexonAPIError(
                f"Elexon request failed with HTTP "
                f"{response.status_code}: {response.text[:500]}"
            ) from exc

        return response

    def health_check(self) -> dict:
        """Check whether the Elexon API is reachable."""

        response = self._get("/health")

        try:
            return response.json()
        except ValueError:
            return {
                "status_code": response.status_code,
                "response": response.text,
            }

    def get_latest_generation_availability(
        self,
        fuel_types: Optional[list[str]] = None,
        bm_units: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """
        Retrieve latest UOU2T14D generation availability data.

        Parameters
        ----------
        fuel_types:
            Optional list of fuel types to filter.

        bm_units:
            Optional list of BM Units to filter.

        Returns
        -------
        pandas.DataFrame
            Latest 2-to-14-day generation availability records.
        """

        params = {}

        if fuel_types:
            params["fuelType"] = fuel_types

        if bm_units:
            params["bmUnit"] = bm_units

        response = self._get(
            "/datasets/UOU2T14D/stream",
            params=params or None,
        )

        payload = response.json()

        if not isinstance(payload, list):
            raise ElexonAPIError(
                "Unexpected UOU2T14D response format. "
                "Expected a JSON list."
            )

        df = pd.DataFrame(payload)

        if df.empty:
            return df

        if "publishTime" in df.columns:
            df["publishTime"] = pd.to_datetime(
                df["publishTime"],
                utc=True,
                errors="coerce",
            )

        if "forecastDate" in df.columns:
            df["forecastDate"] = pd.to_datetime(
                df["forecastDate"],
                errors="coerce",
            )

        df["collectedAt"] = pd.Timestamp.now(tz="UTC")

        return df


    def get_generation_availability_by_publish_time(
        self,
        publish_datetime_from,
        publish_datetime_to,
        fuel_types: Optional[list[str]] = None,
        bm_units: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """
        Retrieve UOU2T14D records for a publication-time range.

        Both publication boundaries are normalised to UTC
        before being sent to the Elexon Insights API.
        """

        start = pd.Timestamp(
            publish_datetime_from
        )

        end = pd.Timestamp(
            publish_datetime_to
        )

        if start.tzinfo is None:
            start = start.tz_localize("UTC")
        else:
            start = start.tz_convert("UTC")

        if end.tzinfo is None:
            end = end.tz_localize("UTC")
        else:
            end = end.tz_convert("UTC")

        if start >= end:
            raise ValueError(
                "publish_datetime_from must be earlier "
                "than publish_datetime_to."
            )

        params = {
            "publishDateTimeFrom": (
                start.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            ),
            "publishDateTimeTo": (
                end.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            ),
        }

        if fuel_types:
            params["fuelType"] = fuel_types

        if bm_units:
            params["bmUnit"] = bm_units

        response = self._get(
            "/datasets/UOU2T14D/stream",
            params=params,
        )

        payload = response.json()

        if not isinstance(payload, list):
            raise ElexonAPIError(
                "Unexpected UOU2T14D response format. "
                "Expected a JSON list."
            )

        df = pd.DataFrame(payload)

        if df.empty:
            return df

        if "publishTime" in df.columns:
            df["publishTime"] = pd.to_datetime(
                df["publishTime"],
                utc=True,
                errors="coerce",
            )

        if "forecastDate" in df.columns:
            df["forecastDate"] = pd.to_datetime(
                df["forecastDate"],
                errors="coerce",
            )

        df["collectedAt"] = pd.Timestamp.now(
            tz="UTC"
        )

        return df
