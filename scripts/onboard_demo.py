import json

from tenant_clinic.tenant_onboarding import TenantOnboardingRequest, build_workflow


def main() -> None:
    result = build_workflow().run(
        TenantOnboardingRequest(
            tenant_slug="harbor-pediatrics",
            appointment_id="appt_01J8Y4N2Q9",
            appointment_state="scheduled",
            asset_key="branding/logo.png",
            asset_content_type="image/png",
        )
    )
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()

