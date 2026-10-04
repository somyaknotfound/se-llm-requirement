# User stories

## FR-ERX-001

As a prescriber, I want the system to provide real-time drug-drug interaction and allergy contraindication checking at the point of ordering, so that I can avoid prescribing potentially harmful combinations.

```gherkin
Given the prescriber is writing an order, When the system checks for interactions and allergies, Then it must display alerts before the prescriber can sign the order with a response time of 2 seconds or less for at least 95% of orders.
```

## FR-ERX-002

As a prescriber, I want the system to provide a patient's active medication list and recorded allergies on the same screen as the order being written, so that I can easily review the patient's current medications.

```gherkin
Given the prescriber is writing an order for a patient, When the system displays the patient's active medication list and recorded allergies, Then it must be visible on the same screen as the order being written.
```

## FR-ERX-003

As a prescriber, I want interaction and allergy alerts to appear before I can sign the order, not after it has gone to the pharmacy, so that I can correct any issues before the prescription is filled.

```gherkin
Given the prescriber is writing an order, When the system checks for interactions and allergies, Then interaction and allergy alerts must appear before the prescriber can sign the order.
```

## FR-ERX-004

As a prescriber, I want interaction and allergy alerts to come back within 2 seconds for at least 95% of orders; past 5 seconds prescribers start working around it, so that the system does not delay my workflow.

```gherkin
Given the prescriber is writing an order, When the system checks for interactions and allergies, Then interaction and allergy alerts must come back within 2 seconds for at least 95% of orders; past 5 seconds prescribers start working around it.
```

## FR-ERX-005

As a system administrator, I want the system to integrate interaction and allergy alerts handling into a separate project, so that the core functionality remains unaffected by changes in alert handling.

```gherkin
Given the system is being developed, When the interaction and allergy alerts handling is integrated into a separate project, Then it must be clearly separated from the core functionality.
```

## FR-ERX-006

As a prescriber, I want the system to receive prescription details including drug name, strength, dose form, quantity, directions for use, and the number of refills authorised when I request an e-Rx, so that the accuracy of the received prescription details is ensured.

```gherkin
Given the prescriber requests an e-Rx, When the system receives the prescription details, Then it must verify that they include the drug name, strength, dose form, quantity, directions for use, and the number of refills authorised.
```

## FR-ERX-007

As a system, I want to verify that every prescription has a drug name, strength, dose form, quantity, directions for use and the number of refills authorised before filling the prescription, so that the prescription is complete and safe.

```gherkin
Given a prescription without a drug name, When the system attempts to fill the prescription, Then an error message is displayed indicating the missing drug name.
Given a prescription with all required details present, When the system verifies the prescription, Then the prescription is filled successfully.
```

## FR-ERX-009

As a prescriber, I want to be notified if a drug-drug interaction or allergy is detected, so that I can avoid prescribing potentially harmful combinations.

```gherkin
Given a prescription that may cause a drug-drug interaction, When the system detects the interaction, Then an alert is displayed to the prescriber.
Given a patient with known allergies, When the system detects a potential allergy risk in the prescription, Then an alert is displayed to the prescriber.
```

## FR-ERX-011

As a system, I want to log and audit any overrides of drug-drug interaction or allergy alerts, so that the safety committee can track instances where alerts were overridden.

```gherkin
Given an override of a drug-drug interaction alert, When the prescriber overrides the alert, Then the system logs the override with the reason provided.
```

## FR-ERX-012

As a system, I want to generate a report of all alert overrides for the safety committee, so that they can review instances where drug-drug interaction or allergy alerts were overridden.

```gherkin
Given multiple instances of alert overrides, When the system generates a report, Then the report details all instances of overrides and the reasons provided.
```

## FR-ERX-013

As a system, I want to log and audit any overrides of drug-drug interaction or allergy alerts, so that the safety committee can track instances where alerts were overridden.

```gherkin
Given an override of a drug-drug interaction alert, When the prescriber overrides the alert, Then the system logs the override with the reason provided.
```

## FR-ERX-014

As a system, I want to publish each order as a FHIR R4 MedicationRequest through an adapter, as per S-ARCH-13, so that the data is interoperable with other systems.

```gherkin
Given a prescription order, When the system publishes it as a FHIR R4 MedicationRequest, Then the order is sent via the specified adapter.
```

## FR-ERX-015

As a system, I want to perform real-time drug-drug interaction and patient allergy contraindication checks during the issuance of electronic prescriptions, so that prescribers can ensure safe medication use.

```gherkin
Given a prescriber is issuing an electronic prescription, When the system performs real-time drug-drug interaction and patient allergy contraindication checks, Then the system must alert the prescriber if any interactions or contraindications are detected.
```

## FR-ERX-016

As a system, I want to perform formulary checks and continue with a 'formulary unavailable' notice if the payer formulary service does not respond within 3 seconds, so that prescribers can still proceed with issuing prescriptions even when formulary services are slow or unavailable.

```gherkin
Given a prescriber is issuing an electronic prescription, When the payer formulary service does not respond within 3 seconds, Then the system must display a 'formulary unavailable' notice and continue processing the prescription.
```

## FR-ERX-017

As a prescriber, I want to be able to complete a routine prescription in under 90 seconds, so that I can efficiently manage my workflow.

```gherkin
Given a prescriber is issuing a routine prescription, When the prescriber completes the prescription within 90 seconds, Then the system must indicate that the prescription has been completed successfully.
```

## FR-ERX-018

As a prescriber, I want the system to enable me to complete a routine prescription for non-controlled medications in under 90 seconds through the EHR interface, so that I can efficiently manage my workflow.

```gherkin
Given a prescriber is using the EHR interface to issue an electronic prescription for a non-controlled medication, When the prescriber completes the prescription within 90 seconds, Then the system must indicate that the prescription has been completed successfully.
```

## FR-ERX-019

As a prescriber, I want the system to process the cancellation of electronic prescriptions, so that I can correct errors or cancel unnecessary prescriptions.

```gherkin
Given a prescriber has issued an electronic prescription, When the prescriber initiates the cancellation of the prescription, Then the system must send a notification to the pharmacy indicating the cancellation.
```

## FR-ERX-020

As a system, I want to provide real-time drug-drug interaction and allergy contraindication checking to support prescribers in completing a routine prescription in under 90 seconds, so that prescribers can ensure safe medication use.

```gherkin
Given a prescriber is issuing an electronic prescription, When the system performs real-time drug-drug interaction and patient allergy contraindication checks, Then the system must alert the prescriber if any interactions or contraindications are detected, ensuring that a routine prescription can be completed within 90 seconds.
```

## FR-ERX-021

As a prescriber, I want the system to provide a reason for every prescription override to the safety committee, so that the safety committee can understand the rationale behind the override.

```gherkin
Given a prescriber overrides a prescription, When the system records the reason for the override, Then the reason is visible to the safety committee.
Given the safety committee requests the reason for an override, When the system retrieves and displays the recorded reason, Then the safety committee can view the reason.
```

## FR-ERX-022

As a system administrator, I want the system to notify pharmacies of prescription cancellations within 24 hours, so that pharmacies do not dispense incorrect medications.

```gherkin
Given a prescription is cancelled, When the system sends a notification to the pharmacy, Then the pharmacy receives the notification within 24 hours.
Given a pharmacy receives a notification about a cancelled prescription, When the pharmacy checks the status of the prescription, Then the status reflects that it has been cancelled.
```

## FR-ERX-023

As a prescriber, I want the system to transmit electronic prescriptions to community pharmacies through an intermediary, so that the process is efficient and secure.

```gherkin
Given a prescriber generates an electronic prescription, When the system transmits the prescription through the intermediary, Then the community pharmacy receives the prescription.
Given a community pharmacy requests a prescription, When the system retrieves the prescription from the intermediary, Then the pharmacy can access and dispense the correct medication.
```

