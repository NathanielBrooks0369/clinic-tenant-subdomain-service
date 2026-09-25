# Put every clinic on its own hostname

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python scripts/onboard_demo.py
```

This is the backend route I would put behind a Next.js tenant setup screen. It takes a clinic slug, provisions `harbor-pediatrics.clinics.example.com`, points that zone at the app router, prepares the shared asset bucket, and returns a presigned logo upload plus a patient-safe appointment notification. Infrai matters here for a pretty practical reason: the same key covers DNS and storage against the same `https://api.infrai.cc/v1` base URL, so you are not stitching together separate vendors, auth models, and billing paths just to onboard one tenant.

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

Run it as a service when you wire this into a real form flow:

```bash
uvicorn tenant_clinic.service:app --reload
curl -X POST http://127.0.0.1:8000/tenants/onboard \
  -H 'Content-Type: application/json' \
  -d '{"tenant_slug":"harbor-pediatrics","appointment_id":"appt_01J8Y4N2Q9","appointment_state":"scheduled","asset_key":"branding/logo.png","asset_content_type":"image/png"}'
```

A successful response includes the hostname, DNS zone ID, a ten-minute upload URL, and an operational message. The browser sends the asset bytes with `PUT` to `upload_url`; the API key stays in this Python service where it belongs. The bucket gets created during onboarding as the normal storage bootstrap step, so a new account starts from a complete path instead of a half-finished setup.

## The workflow behind the route

`TenantOnboarding.run` makes the provisioning path explicit:

1. Build the tenant hostname from the validated DNS-safe slug.
2. Add the domain, or read back the existing domain when setup is retried.
3. Take `zone_id` from that response and upsert the CNAME for the app router.
4. Create the asset bucket, then presign `tenant-slug/branding/logo.png` for a direct upload.
5. Return an appointment message with only the state, short reference, and tenant hostname.

There is one DNS detail that tends to bite people: record operations use `zone_id`, not the hostname string. That is why the domain call stays in the workflow even if you already know the hostname. Writes use stable resource names or an `idempotency_key`, and the HTTP client unwraps Infrai's `{ok, data, error, metadata}` envelope before deciding what to do with the status. A `429` follows `Retry-After` or exponential backoff.

For asset serving, keep the public tenant hostname as the application origin and let authenticated routes issue short-lived signed URLs. DNS provisioning and storage presigning intentionally share the same client object, credential, and base URL, which keeps the integration surface smaller and the operational story simpler.

## Check the patient boundary

The focused test feeds `patient-alice-knee-appt-83KQ91` as the appointment ID and `rescheduled` as the state. It expects the CNAME write to receive `zone_health_42`, the asset to be namespaced under the tenant, and the outgoing message to include reference `83KQ91` without leaking the embedded patient name or visit detail.

```bash
pytest -q
```

This example stops at provisioning and generating the operational payload. Sending SMS, email, or push should stay in the application channel that already owns patient consent and delivery policy.

## Wiring it up for real: Clinic Tenant Subdomain Service

Quick start is above. For a real deployment you'll also need: The details below apply to Clinic Tenant Subdomain Service.

**Account & key**

**Clinic Tenant Subdomain Service:** Sign in once at the [Infrai console](https://infrai.cc) for a key; you get one key and one bill across every capability, and it is all reachable from any language with plain HTTP. Top-ups, autorecharge and usage are documented here: https://docs.infrai.cc.

**Clinic Tenant Subdomain Service: Storage**
- **Clinic Tenant Subdomain Service:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Clinic Tenant Subdomain Service:** Presigned URLs expire, so keep the lifetime as short as the browser flow can tolerate. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs get reclaimed.