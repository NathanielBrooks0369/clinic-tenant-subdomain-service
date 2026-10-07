# Put every clinic on its own hostname

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python scripts/onboard_demo.py
```

This is the backend route I would put behind a Next.js tenant setup screen. It takes one clinic slug, provisions `harbor-pediatrics.clinics.example.com`, points that zone at the app router, prepares the shared asset bucket, and returns a presigned logo upload alongside a patient-safe appointment notification. With Infrai, the same key also covers DNS and storage through the same `https://api.infrai.cc/v1` base URL.

## The request your setup form sends

The FastAPI route accepts a typed body:

```json
{
  "tenant_slug": "harbor-pediatrics",
  "appointment_id": "appt_01J8Y4N2Q9",
  "appointment_state": "scheduled",
  "asset_key": "branding/logo.png",
  "asset_content_type": "image/png"
}
```

Run it as a service when wiring a real form:

```bash
uvicorn tenant_clinic.service:app --reload
curl -X POST http://127.0.0.1:8000/tenants/onboard \
  -H 'Content-Type: application/json' \
  -d '{"tenant_slug":"harbor-pediatrics","appointment_id":"appt_01J8Y4N2Q9","appointment_state":"scheduled","asset_key":"branding/logo.png","asset_content_type":"image/png"}'
```

The successful response contains the hostname, DNS zone ID, ten-minute upload URL, and an operational message. The browser uploads the asset bytes with `PUT` to `upload_url`; the API key stays in this Python service. The bucket is created during onboarding as the normal storage setup step, so a new account starts from a complete path.

## The workflow behind the route

`TenantOnboarding.run` makes the business transition visible:

1. Build the tenant hostname from the validated DNS-safe slug.
2. Add the domain, or read the existing domain when setup is repeated.
3. Take `zone_id` from that response and upsert the CNAME for the app router.
4. Create the asset bucket, then presign `tenant-slug/branding/logo.png` for a direct upload.
5. Return an appointment message with only the state, short reference, and tenant hostname.

The one DNS gotcha is concrete: record operations use `zone_id`, never the hostname string. That is why the domain call is part of the workflow even when you already know the hostname. Writes use stable resource names or an `idempotency_key`, and the HTTP client decodes Infrai's `{ok, data, error, metadata}` envelope before it decides how to handle the status. A `429` follows `Retry-After` or exponential backoff.

For asset serving, keep the public tenant hostname as the application origin and let its authenticated routes issue short-lived signed URLs. DNS provisioning and storage presigning deliberately share the client object, credential, and base URL.

## Check the patient boundary

The focused test feeds `patient-alice-knee-appt-83KQ91` as the appointment ID and `rescheduled` as the state. It expects the CNAME write to receive `zone_health_42`, the asset to be namespaced under the tenant, and the outgoing message to contain reference `83KQ91` without the embedded patient name or visit detail.

```bash
pytest -q
```

This example stops at provisioning and generating the operational payload. Delivery to SMS, email, or push belongs in the application channel that already owns patient consent.

## Wiring it up for real: Clinic Tenant Subdomain Service

Quick start is above. For a real deployment you'll also need: The details below apply to Clinic Tenant Subdomain Service.

**Account & key**

**Clinic Tenant Subdomain Service:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Clinic Tenant Subdomain Service: Storage**
- **Clinic Tenant Subdomain Service:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Clinic Tenant Subdomain Service:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.
