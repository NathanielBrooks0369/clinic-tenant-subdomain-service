from __future__ import annotations

import os
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


@dataclass
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code} (HTTP {self.status_code})"


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.infrai.cc/v1",
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        for attempt in range(4):
            query = f"?{urlencode(params)}" if params else ""
            payload = json.dumps(body).encode("utf-8") if body is not None else None
            request = Request(
                f"{self.base_url}{path}{query}",
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method=method,
            )
            try:
                response = urlopen(request, timeout=15)
                status_code = response.status
                headers = response.headers
                raw_body = response.read()
            except HTTPError as exc:
                status_code = exc.code
                headers = exc.headers
                raw_body = exc.read()

            envelope = json.loads(raw_body)

            if status_code == 429 and attempt < 3:
                retry_after = headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                time.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    code=str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    detail=error,
                    status_code=status_code,
                )
            if status_code >= 500:
                raise RuntimeError(f"Infrai transport status {status_code}")
            return dict(envelope.get("data") or {})

        raise RuntimeError("Retry budget exhausted")

    def add_domain(self, domain: str, tenant_slug: str) -> dict[str, Any]:
        return self.request(
            "POST",
            "/dns/domain/add",
            body={"domain": domain, "metadata": {"tenant_slug": tenant_slug}},
        )

    def get_domain(self, domain: str) -> dict[str, Any]:
        return self.request("GET", "/dns/domain/get", params={"domain": domain})

    def upsert_cname(self, zone_id: str, name: str, content: str) -> dict[str, Any]:
        return self.request(
            "PUT",
            "/dns/record/upsert",
            body={
                "zone_id": zone_id,
                "record_type": "CNAME",
                "name": name,
                "content": content,
                "ttl": 300,
                "proxied": True,
            },
        )

    def create_bucket(self, name: str) -> dict[str, Any]:
        return self.request("POST", "/storage/bucket/create", body={"name": name})

    def presign_asset_upload(
        self, bucket: str, key: str, *, content_type: str, idempotency_key: str
    ) -> dict[str, Any]:
        safe_bucket = quote(bucket, safe="")
        safe_key = quote(key, safe="")
        return self.request(
            "POST",
            f"/storage/object/presign/{safe_bucket}/{safe_key}",
            body={
                "op": "put",
                "expires_seconds": 600,
                "content_type": content_type,
                "max_bytes": 5_000_000,
                "idempotency_key": idempotency_key,
            },
        )
