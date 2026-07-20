from __future__ import annotations

import time
import os
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import load_dotenv


load_dotenv()


PROTECTED_CREATE_TABLES = {
    "sys_update_set",
    "sys_script_include",
    "sys_script",
    "sys_script_client",
    "catalog_script_client",
}

PROTECTED_UPDATE_TABLES = {
    "sys_update_set",
    "sys_script_include",
    "sys_script",
    "sys_script_client",
    "catalog_script_client",
}


class ServiceNowError(RuntimeError):
    """Raised when the ServiceNow API returns an error."""


@dataclass(frozen=True)
class ServiceNowConfig:
    instance_url: str
    username: str | None
    password: str | None
    bearer_token: str | None
    oauth_client_id: str | None
    oauth_client_secret: str | None
    oauth_grant_type: str | None
    oauth_token_url: str | None
    oauth_scope: str | None
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "ServiceNowConfig":
        instance_url = os.getenv("SERVICENOW_INSTANCE_URL", "").strip().rstrip("/")
        username = os.getenv("SERVICENOW_USERNAME", "").strip() or None
        password = os.getenv("SERVICENOW_PASSWORD", "") or None
        bearer_token = os.getenv("SERVICENOW_BEARER_TOKEN", "").strip() or None
        oauth_client_id = os.getenv("SERVICENOW_OAUTH_CLIENT_ID", "").strip() or None
        oauth_client_secret = os.getenv("SERVICENOW_OAUTH_CLIENT_SECRET", "").strip() or None
        oauth_grant_type = os.getenv("SERVICENOW_OAUTH_GRANT_TYPE", "").strip() or None
        oauth_token_url = os.getenv("SERVICENOW_OAUTH_TOKEN_URL", "").strip() or None
        oauth_scope = os.getenv("SERVICENOW_OAUTH_SCOPE", "").strip() or None
        timeout_raw = os.getenv("SERVICENOW_TIMEOUT", "30").strip() or "30"

        if not instance_url:
            raise ServiceNowError("SERVICENOW_INSTANCE_URL is required.")

        if oauth_client_id and not oauth_client_secret:
            raise ServiceNowError("SERVICENOW_OAUTH_CLIENT_SECRET is required when SERVICENOW_OAUTH_CLIENT_ID is set.")

        if oauth_client_secret and not oauth_client_id:
            raise ServiceNowError("SERVICENOW_OAUTH_CLIENT_ID is required when SERVICENOW_OAUTH_CLIENT_SECRET is set.")

        if oauth_client_id and not oauth_grant_type:
            oauth_grant_type = "client_credentials"

        if oauth_client_id and not oauth_token_url:
            oauth_token_url = f"{instance_url}/oauth_token.do"

        if not bearer_token and not oauth_client_id and not (username and password):
            raise ServiceNowError(
                "Provide SERVICENOW_BEARER_TOKEN, OAuth client credentials, or both SERVICENOW_USERNAME and SERVICENOW_PASSWORD."
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
            oauth_client_id=oauth_client_id,
            oauth_client_secret=oauth_client_secret,
            oauth_grant_type=oauth_grant_type,
            oauth_token_url=oauth_token_url,
            oauth_scope=oauth_scope,
            timeout=timeout,
        )


class ServiceNowClient:
    def __init__(self, config: ServiceNowConfig) -> None:
        self._config = config
        self._oauth_access_token: str | None = None
        self._oauth_access_token_expires_at = 0.0

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

    def count_records(self, table: str, *, query: str | None = None) -> int:
        params = {"sysparm_count": "true"}
        if query:
            params["sysparm_query"] = query

        data = self._request("GET", f"/api/now/stats/{table}", params=params)
        result = data.get("result", {})
        stats = result.get("stats", {}) if isinstance(result, dict) else {}
        raw_count = stats.get("count") if isinstance(stats, dict) else None

        try:
            return int(raw_count)
        except (TypeError, ValueError) as exc:
            raise ServiceNowError(f"ServiceNow stats API returned an invalid count for table {table}.") from exc

    def create_record(
        self,
        table: str,
        payload: dict[str, Any],
        *,
        allow_protected_tables: bool = False,
    ) -> dict[str, Any]:
        if table in PROTECTED_CREATE_TABLES and not allow_protected_tables:
            raise ServiceNowError(
                f"Direct {table} creation is blocked. Use the dedicated strict server flow so naming convention validation is enforced."
            )
        return self._request("POST", f"/api/now/table/{table}", json=payload)

    def update_record(
        self,
        table: str,
        sys_id: str,
        payload: dict[str, Any],
        *,
        allow_protected_tables: bool = False,
    ) -> dict[str, Any]:
        if table in PROTECTED_UPDATE_TABLES and not allow_protected_tables:
            raise ServiceNowError(
                f"Direct {table} updates are blocked. Use the dedicated strict server flow so naming convention validation is enforced."
            )
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
        elif self._config.oauth_client_id and self._config.oauth_client_secret:
            headers["Authorization"] = f"Bearer {self._oauth_token()}"
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

    def _oauth_token(self) -> str:
        if self._oauth_access_token and time.time() < self._oauth_access_token_expires_at:
            return self._oauth_access_token

        token_url = self._config.oauth_token_url or f"{self._config.instance_url}/oauth_token.do"
        form_data = {
            "grant_type": self._config.oauth_grant_type or "client_credentials",
            "client_id": self._config.oauth_client_id or "",
            "client_secret": self._config.oauth_client_secret or "",
        }
        if self._config.oauth_scope:
            form_data["scope"] = self._config.oauth_scope

        headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}

        try:
            with httpx.Client(timeout=self._config.timeout, headers=headers) as client:
                response = client.post(token_url, data=form_data)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            detail = _extract_error_detail(exc.response)
            raise ServiceNowError(
                f"ServiceNow OAuth token request failed with status {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ServiceNowError(f"ServiceNow OAuth token request failed: {exc}") from exc

        if not isinstance(data, dict):
            raise ServiceNowError("ServiceNow OAuth token response was not a JSON object.")

        access_token = data.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            raise ServiceNowError("ServiceNow OAuth token response did not include an access_token.")

        expires_in = data.get("expires_in", 300)
        try:
            expires_in_seconds = int(expires_in)
        except (TypeError, ValueError) as exc:
            raise ServiceNowError("ServiceNow OAuth token response returned an invalid expires_in value.") from exc

        self._oauth_access_token = access_token.strip()
        self._oauth_access_token_expires_at = time.time() + max(expires_in_seconds - 30, 30)
        return self._oauth_access_token


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
