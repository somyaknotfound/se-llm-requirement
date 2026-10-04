# Use cases

## UC-1 Issuing an Electronic Prescription with Real-Time Interaction and Allergy Checks

- Primary actor: Prescriber
- Realises: FR-ERX-001, FR-ERX-002, FR-ERX-003, FR-ERX-004, FR-ERX-005, FR-ERX-006, FR-ERX-007, FR-ERX-011, FR-ERX-012, FR-ERX-013, FR-ERX-014, FR-ERX-015
- Preconditions: The prescriber is logged into the EHR system.; The patient's active medication list and recorded allergies are available in the system.

Main success scenario:

1. The prescriber selects a patient from the EHR interface.
2. The prescriber chooses to issue an electronic prescription.
3. The system displays the patient's active medication list and recorded allergies on the same screen as the order being written.
4. The prescriber enters the drug name, strength, dose form, quantity, directions for use, and number of refills authorised.
5. The system performs real-time drug-drug interaction and allergy contraindication checks.
6. If any interactions or allergies are detected, the system displays an alert to the prescriber.
7. The prescriber reviews the alerts and decides whether to override them or proceed with the prescription.
8. The prescriber signs the order.
9. The system logs and audits any overrides of drug-drug interaction or allergy alerts.
10. The system generates a report of all alert overrides for the safety committee.
11. The system publishes each order as a FHIR R4 MedicationRequest through an adapter.

Alternate and exception flows:

- If no interactions or allergies are detected, the prescriber signs the order without any alerts.
- If the prescriber overrides an alert, the system logs the reason for the override and includes it in the report.

Postconditions: The electronic prescription is issued and transmitted to the pharmacy.; The prescriber can see the pharmacy's response to the cancellation request if applicable.; The safety committee has a record of all alert overrides.

## UC-2 Cancelling an Electronic Prescription and Notifying the Pharmacy

- Primary actor: Prescriber
- Realises: FR-ERX-019, FR-ERX-022
- Preconditions: The prescriber is logged into the EHR system.; An electronic prescription has been issued.

Main success scenario:

1. The prescriber selects a patient from the EHR interface.
2. The prescriber chooses to cancel an electronic prescription.
3. The system sends an electronic CancelRx message to the pharmacy.
4. The prescriber can see the pharmacy's response to the cancellation request.
5. The system logs the cancellation and includes it in the audit trail.

Alternate and exception flows:

- If the pharmacy does not respond within 24 hours, the system sends a notification to the prescriber.

Postconditions: The electronic prescription is cancelled.; The prescriber is informed of the pharmacy's response.; The safety committee has a record of all prescription cancellations.

## UC-3 Transmitting an Electronic Prescription to a Community Pharmacy

- Primary actor: Prescriber
- Realises: FR-ERX-016, FR-ERX-023
- Preconditions: The prescriber is logged into the EHR system.; An electronic prescription has been issued.

Main success scenario:

1. The prescriber selects a patient from the EHR interface.
2. The prescriber chooses to transmit an electronic prescription.
3. The system performs formulary checks and continues with a 'formulary unavailable' notice if the payer formulary service does not respond within 3 seconds.
4. The system transmits the electronic prescription to the community pharmacy through the intermediary.
5. The system logs the transmission and includes it in the audit trail.

Alternate and exception flows:

- If the formulary check is unavailable, the prescriber is notified and can proceed with the transmission.
- If the transmission fails, the system retries the transmission up to three times before logging a failure.

Postconditions: The electronic prescription is transmitted to the community pharmacy.; The prescriber is informed of the transmission status.; The safety committee has a record of all prescription transmissions.

## UC-4 Completing a Routine Prescription in Under 90 Seconds

- Primary actor: Prescriber
- Realises: FR-ERX-017, FR-ERX-018
- Preconditions: The prescriber is logged into the EHR system.; A patient's active medication list and recorded allergies are available in the system.

Main success scenario:

1. The prescriber selects a patient from the EHR interface.
2. The prescriber chooses to issue an electronic prescription.
3. The system displays the patient's active medication list and recorded allergies on the same screen as the order being written.
4. The prescriber enters the drug name, strength, dose form, quantity, directions for use, and number of refills authorised.
5. The system performs real-time drug-drug interaction and allergy contraindication checks.
6. If no interactions or allergies are detected, the prescriber signs the order within 90 seconds.
7. The system logs the completion time of the prescription.

Alternate and exception flows:

- If any interactions or allergies are detected, the prescriber reviews the alerts and decides whether to override them or proceed with the prescription within 90 seconds.

Postconditions: The electronic prescription is issued and transmitted to the pharmacy.; The prescriber is informed of the completion time.; The safety committee has a record of all prescription completions.

