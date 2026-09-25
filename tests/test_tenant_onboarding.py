from tenant_clinic.tenant_onboarding import TenantOnboarding, TenantOnboardingRequest


class FakeInfrai:
    def __init__(self) -> None:
        self.zone_id_used = ""
        self.asset_key_used = ""

    def add_domain(self, domain: str, tenant_slug: str) -> dict:
        assert domain == "harbor-pediatrics.clinics.example.com"
        return {"zone_id": "zone_health_42"}

    def get_domain(self, domain: str) -> dict:
        raise AssertionError("new tenant should not need a domain lookup")

    def upsert_cname(self, zone_id: str, name: str, content: str) -> dict:
        self.zone_id_used = zone_id
        assert (name, content) == ("@", "tenant-router.example.net")
        return {"record_id": "record_42"}

    def create_bucket(self, name: str) -> dict:
        assert name == "clinic-tenant-assets"
        return {"name": name}

    def presign_asset_upload(
        self, bucket: str, key: str, *, content_type: str, idempotency_key: str
    ) -> dict:
        assert bucket == "clinic-tenant-assets"
        assert content_type == "image/png"
        assert idempotency_key == "harbor-pediatrics:branding/logo.png:put"
        self.asset_key_used = key
        return {"url": "https://signed.example/upload"}


def test_onboarding_uses_zone_id_and_emits_patient_safe_notification() -> None:
    api = FakeInfrai()
    workflow = TenantOnboarding(
        api,
        root_domain="clinics.example.com",
        app_origin="tenant-router.example.net",
        asset_bucket="clinic-tenant-assets",
    )

    result = workflow.run(
        TenantOnboardingRequest(
            tenant_slug="Harbor-Pediatrics",
            appointment_id="patient-alice-knee-appt-83KQ91",
            appointment_state="rescheduled",
            asset_key="branding/logo.png",
        )
    )

    assert api.zone_id_used == "zone_health_42"
    assert api.asset_key_used == "harbor-pediatrics/branding/logo.png"
    assert result.hostname == "harbor-pediatrics.clinics.example.com"
    assert result.notification.appointment_reference == "83KQ91"
    assert "Alice" not in result.notification.message
    assert "knee" not in result.notification.message
    assert result.notification.state == "rescheduled"

