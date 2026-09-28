# FHIR API gateway — endpoints available to the patient app

- `GET /MedicationRequest?patient={id}&status=active` returns the patient's active
  prescriptions, including `dispenseRequest.quantity`,
  `dispenseRequest.expectedSupplyDuration` and
  `dispenseRequest.numberOfRepeatsAllowed`.
- `POST /Task` with code `renewal-request` and `focus` = the MedicationRequest creates
  a renewal request in the EHR renewal queue.
- Fill status arrives as `MedicationDispense` resources with `status=completed` when
  the pharmacy has dispensed.
- Authentication: OAuth 2.0 with SMART on FHIR patient scopes
  (`patient/MedicationRequest.read`, `patient/Task.write`). A proxy (caregiver) token
  carries the patient's id and the proxy's own identity.
- Rate limit: 60 requests per minute per user.
- Every call is logged by the gateway as a FHIR AuditEvent.
