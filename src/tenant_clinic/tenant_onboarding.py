from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .infrai_client import InfraiClient, InfraiError


@dataclass
class TenantOnboardingRequest:
    tenant_slug: str
    appointment_id: str
    appointment_state: Literal["requested", "scheduled", "rescheduled", "cancelled"]
    asset_key: str
    asset_content_type: str = "image/png"

    def __post_init__(self) -> None:
        for name, minimum, maximum in (
            ("tenant_slug", 2, 48),
            ("appointment_id", 6, 80),
            ("asset_key", 1, 240),
            ("asset_content_type", 3, 100),
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not minimum <= len(value) <= maximum:
                raise ValueError(f"{name} must be between {minimum} and {maximum} characters")
        if self.appointment_state not in ("requested", "scheduled", "rescheduled", "cancelled"):
            raise ValueError("invalid appointment_state")
        normalized = self.tenant_slug.lower().strip()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized):
            raise ValueError("tenant_slug must be a DNS-safe slug")
        self.tenant_slug = normalized

        cleaned = self.asset_key.strip().lstrip("/")
        if not cleaned or ".." in cleaned.split("/"):
            raise ValueError("asset_key must be a relative object key")
        self.asset_key = cleaned


@dataclass
class SafeNotification:
    appointment_reference: str
    state: str
    message: str


@dataclass
class TenantOnboardingResult:
    hostname: str
    zone_id: str
    upload_url: str
    upload_expires_seconds: int
    notification: SafeNotification


def patient_safe_notification(
    appointment_id: str, state: str, hostname: str
) -> SafeNotification:
    reference = appointment_id[-6:].upper()
    messages = {
        "requested": "Your appointment request was received.",
        "scheduled": "Your appointment is scheduled.",
        "rescheduled": "Your appointment time was updated.",
        "cancelled": "Your appointment was cancelled.",
    }
    return SafeNotification(
        appointment_reference=reference,
        state=state,
        message=f"{messages[state]} Reference {reference}. Manage it at https://{hostname}.",
    )


class TenantOnboarding:
    def __init__(
        self,
        infrai: InfraiClient,
        *,
        root_domain: str,
        app_origin: str,
        asset_bucket: str,
    ) -> None:
        self.infrai = infrai
        self.root_domain = root_domain
        self.app_origin = app_origin
        self.asset_bucket = asset_bucket

    def run(self, request: TenantOnboardingRequest) -> TenantOnboardingResult:
        hostname = f"{request.tenant_slug}.{self.root_domain}"
        try:
            domain = self.infrai.add_domain(hostname, request.tenant_slug)
        except InfraiError as exc:
            if exc.status_code != 409:
                raise
            domain = self.infrai.get_domain(hostname)

        zone_id = str(domain["zone_id"])
        self.infrai.upsert_cname(zone_id, "@", self.app_origin)

        try:
            self.infrai.create_bucket(self.asset_bucket)
        except InfraiError as exc:
            if exc.status_code != 409:
                raise

        presign = self.infrai.presign_asset_upload(
            self.asset_bucket,
            f"{request.tenant_slug}/{request.asset_key}",
            content_type=request.asset_content_type,
            idempotency_key=f"{request.tenant_slug}:{request.asset_key}:put",
        )
        return TenantOnboardingResult(
            hostname=hostname,
            zone_id=zone_id,
            upload_url=str(presign["url"]),
            upload_expires_seconds=600,
            notification=patient_safe_notification(
                request.appointment_id, request.appointment_state, hostname
            ),
        )


def build_workflow() -> TenantOnboarding:
    return TenantOnboarding(
        InfraiClient(),
        root_domain="clinics.example.com",
        app_origin="tenant-router.example.net",
        asset_bucket="clinic-tenant-assets",
    )
