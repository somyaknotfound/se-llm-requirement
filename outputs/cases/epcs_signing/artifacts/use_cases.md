# Use cases

## UC-1 Prescribing a Controlled Substance Prescription

- Primary actor: Prescribing Practitioner
- Realises: FR-EPCS-001, FR-EPCS-002, FR-EPCS-003, FR-EPCS-004, FR-EPCS-006, FR-EPCS-007, FR-EPCS-024
- Preconditions: The prescriber has been identity-proofed and issued credentials.; The prescriber is logged into the EPCS system.; The patient has at least one DEA registration.

Main success scenario:

1. The prescriber selects a patient from the system.
2. The system displays the patient's DEA registrations.
3. The prescriber chooses the appropriate DEA registration.
4. The prescriber enters the prescription details, including dosage and duration.
5. The system times and dates the prescription.
6. The prescriber signs the prescription using two-factor authentication.
7. The system transmits the signed prescription to the pharmacy.
8. The system generates an internal audit trail.

Alternate and exception flows:

- If the prescriber has multiple DEA registrations, they must select the correct one before signing.
- If the prescriber signs a prescription for more than one patient, the system prompts them to sign each prescription separately.

Postconditions: The prescription is transmitted to the pharmacy.; An internal audit trail is generated and stored.; The prescriber's actions are logged.

## UC-2 Printing a Controlled Substance Prescription

- Primary actor: Prescribing Practitioner
- Realises: FR-EPCS-005
- Preconditions: The prescriber has been identity-proofed and issued credentials.; The prescriber is logged into the EPCS system.; The prescription has been signed.

Main success scenario:

1. The prescriber requests a printout of the signed prescription.
2. The system generates a copy labeled as 'Not for Dispensing'.
3. The prescriber prints the copy.

Alternate and exception flows:

- If the prescription has not been signed, the system prompts the prescriber to sign it first.
- If the prescriber requests multiple copies, the system generates and prints each one labeled as 'Not for Dispensing'.

Postconditions: A copy of the prescription is printed and labeled as 'Not for Dispensing'.; The print request is logged.

## UC-3 Generating Monthly Prescription Logs

- Primary actor: System Administrator
- Realises: FR-EPCS-025
- Preconditions: The system has been configured to generate logs.; The current month has ended.

Main success scenario:

1. The administrator initiates the log generation process.
2. The system generates a report of all signed prescriptions for the month.
3. The report is stored and can be accessed by authorized personnel.

Alternate and exception flows:

- If there are no signed prescriptions for the month, the system logs this fact.

Postconditions: A monthly prescription log is generated and stored.; The log is accessible to authorized personnel.

## UC-4 Two-Factor Authentication for Signing Prescriptions

- Primary actor: Prescribing Practitioner
- Realises: FR-EPCS-016, FR-EPCS-021
- Preconditions: The prescriber has been identity-proofed and issued credentials.; The prescriber is logged into the EPCS system.

Main success scenario:

1. The prescriber selects a patient to prescribe a controlled substance.
2. The system prompts for two-factor authentication.
3. The prescriber enters their password and inserts the hard token.
4. The system verifies the credentials and allows the prescriber to sign the prescription.

Alternate and exception flows:

- If the prescriber's credentials are invalid, the system denies access and logs the attempt.
- If the prescriber does not insert the hard token within a specified time, the system times out and logs the attempt.

Postconditions: The prescription is signed using two-factor authentication.; The signing action is logged.

