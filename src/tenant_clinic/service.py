from fastapi import FastAPI, HTTPException

from .infrai_client import InfraiError
from .tenant_onboarding import (
    TenantOnboardingRequest,
    TenantOnboardingResult,
    build_workflow,
)

app = FastAPI(title="Tenant clinic onboarding")


@app.post("/tenants/onboard", response_model=TenantOnboardingResult)
def onboard_tenant(payload: TenantOnboardingRequest) -> TenantOnboardingResult:
    try:
        return build_workflow().run(payload)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": exc.code, "message": exc.detail.get("message", str(exc))},
        ) from exc

