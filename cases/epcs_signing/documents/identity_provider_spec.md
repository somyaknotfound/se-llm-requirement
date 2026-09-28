# Identity provider integration — EPCS signing

- Workforce sign-in uses the network identity provider (OpenID Connect).
- The EPCS signing step is a separate authentication performed by the e-prescribing
  application at the moment of signing; the day's single sign-on session does not
  count as a signing factor.
- Supported second factors: the vendor OTP hard token (FIPS 140-2 Level 1) and, on
  managed workstations only, a fingerprint reader.
- The identity provider exposes a revocation webhook; the application must remove
  signing permission within 15 minutes of receiving a revocation event.
- All calls between the application and the identity provider use mutual TLS.
