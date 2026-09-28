# Legacy order interface — integration notes

## Current state

- The EHR emits pharmacy orders as HL7 v2.5.1 RDE^O11 messages over MLLP.
- Each message carries one order: RXE segment (give code, amount, units, dosage
  form), RXR (route), and TQ1 (timing).
- Order status updates return as RRE^O12 messages.

## Target state

- An adapter converts each RDE^O11 into a FHIR R4 MedicationRequest and publishes it
  to the new ordering service.
- The ordering service sends outpatient prescriptions to the e-prescribing
  intermediary as NCPDP SCRIPT messages and receives Status, Error and Verify
  responses.

## Volumes and budgets

- Peak: 1,200 orders per hour across the network (Monday mornings).
- End-to-end budget from "sign" to intermediary acknowledgement: 10 seconds at the
  95th percentile.
- The adapter must not lose an order: every RDE^O11 is acknowledged only after the
  MedicationRequest is persisted.

## Constraints

- The EHR cannot be modified for this release; all translation happens in the adapter.
- The intermediary requires a trusted connection with mutual TLS.
