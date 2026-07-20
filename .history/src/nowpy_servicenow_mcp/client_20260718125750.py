from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import load_dotenv


load_dotenv()


class ServiceNowError(RuntimeError):
    """Raised when the ServiceNow API returns an error."""


@dataclass(frozen=True)
class ServiceNowConfig:
    instance_url: str
    username: str | None
    password: str | None
    bearer_token: str | None
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "ServiceNowConfig":
        instance_url = os.getenv("SERVICENOW_INSTANCE_URL", "").strip().rstrip("/")
        username = os.getenv("SERVICENOW_USERNAME", "").strip() or None
        password = os.getenv("SERVICENOW_PASSWORD", "") or None
        bearer_token = os.getenv("SERVICENOW_BEARER_TOKEN", "").strip() or None
        timeout_raw = os.getenv("SERVICENOW_TIMEOUT", "30").strip() or "30"

        if not instance_url:
            raise ServiceNowError("SERVICENOW_INSTANCE_URL is required.")

        if not bearer_token and not (username and password):
            raise ServiceNowError(
                "Provide SERVICENOW_BEARER_TOKEN or both SERVICENOW_USERNAME and SERVICENOW_PASSWORD."
            )

        try:
            timeout = float(timeout_raw)
        except ValueError as exc:
            raise ServiceNowError("SERVICENOW_TIMEOUT must be a number.") from exc

        return cls(
            instance_url=instance_url,
            username=username,
            password=password,
            bearer_token=bearer_token,
            timeout=timeout,
        )


class ServiceNowClient:
    def __init__(self, config: ServiceNowConfig) -> None:
        self._config = config

    @classmethod
    def from_env(cls) -> "ServiceNowClient":
        return cls(ServiceNowConfig.from_env())

    def test_connection(self) -> dict[str, Any]:
        return self.get_records("sys_user", fields=["sys_id", "user_name"], limit=1)

    def get_records(
        self,
        table: str,
        *,
        query: str | None = None,
        fields: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
        display_value: str = "all",
    ) -> dict[str, Any]:
        params = {
            "sysparm_limit": limit,
            "sysparm_offset": offset,
            "sysparm_display_value": display_value,
            "sysparm_exclude_reference_link": "true",
        }
        if query:
            params["sysparm_query"] = query
        if fields:
            params["sysparm_fields"] = ",".join(fields)
        return self._request("GET", f"/api/now/table/{table}", params=params)

    def get_record(
        self,
        table: str,
        sys_id: str,
        *,
        fields: list[str] | None = None,
        display_value: str = "all",
    ) -> dict[str, Any]:
        params = {
            "sysparm_display_value": display_value,
            "sysparm_exclude_reference_link": "true",
        }
        if fields:
            params["sysparm_fields"] = ",".join(fields)
        return self._request("GET", f"/api/now/table/{table}/{sys_id}", params=params)

    def create_record(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/api/now/table/{table}", json=payload)

    def update_record(self, table: str, sys_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"/api/now/table/{table}/{sys_id}", json=payload)

    def delete_record(self, table: str, sys_id: str) -> dict[str, Any]:
        return self._request(
            "DELETE",
            f"/api/now/table/{table}/{sys_id}",
            allow_empty_response=True,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        allow_empty_response: bool = False,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        auth: httpx.Auth | None = None

        if self._config.bearer_token:
            headers["Authorization"] = f"Bearer {self._config.bearer_token}"
        else:
            auth = httpx.BasicAuth(self._config.username or "", self._config.password or "")

        url = f"{self._config.instance_url}{path}"

        try:
            with httpx.Client(timeout=self._config.timeout, auth=auth, headers=headers) as client:
                response = client.request(method, url, params=params, json=json)
                response.raise_for_status()
                if allow_empty_response and not response.content:
                    return {"ok": True, "status_code": response.status_code}
                data = response.json()
        except httpx.HTTPStatusError as exc:
            detail = _extract_error_detail(exc.response)
            raise ServiceNowError(
                f"ServiceNow API request failed with status {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ServiceNowError(f"ServiceNow API request failed: {exc}") from exc

        if not isinstance(data, dict):
            raise ServiceNowError("ServiceNow API returned a non-object JSON response.")

        return data


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or "Unknown error"

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            detail = error.get("detail")
            if message and detail:
                return f"{message} ({detail})"
            if message:
                return str(message)
            if detail:
                return str(detail)
        if "result" in payload:
            return str(payload["result"])

    return str(payload)
