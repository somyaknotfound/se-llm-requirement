# User stories

## FR-EPCS-001

As a prescriber, I want to sign multiple controlled prescriptions for a single patient in one signing action within 20 seconds, so that I can efficiently manage my workflow.

```gherkin
Given the prescriber has multiple controlled prescriptions for a single patient, When the prescriber initiates the signing function, Then the system should allow signing all prescriptions in one action and complete within 20 seconds.
```

## FR-EPCS-002

As a system, I want to time and date stamp the prescription within 20 seconds when the signing function is used, so that the timestamp accurately reflects when the prescription was signed.

```gherkin
Given the prescriber has initiated the signing function, When the signing action is completed, Then the system should automatically add a time and date stamp to the prescription.
```

## FR-EPCS-003

As a system, I want to generate and transmit a controlled substance prescription, including the two-factor step, in no more than 20 seconds, so that the prescription can be quickly and securely sent to the pharmacy.

```gherkin
Given the prescriber has initiated the signing function for a controlled substance prescription, When the signing action is completed, Then the system should generate and transmit the prescription within 20 seconds.
```

## FR-EPCS-004

As a system, I want to include the patient's DEA registration information on the prescription and ask which DEA registration to use when the patient has more than one, as stated in S-PRES-30, so that the correct DEA registration is used for the prescription.

```gherkin
Given the patient has multiple DEA registrations, When the prescriber initiates the signing function, Then the system should display a list of DEA registrations and ask which one to use.
Given the prescriber selects a DEA registration, When the signing action is completed, Then the selected DEA registration information should be included on the prescription.
```

## FR-EPCS-005

As a system, I want to allow printing of a prescription after transmission only if it is clearly labeled as a copy not for dispensing, so that the printed prescription cannot be used for dispensing.

```gherkin
Given the prescription has been transmitted and marked as a copy not for dispensing, When the prescriber attempts to print the prescription, Then the system should allow printing only if the prescription is labeled as a copy not for dispensing.
```

## FR-EPCS-006

As a system, I want to transmit signed controlled substances prescriptions to the pharmacy, so that the pharmacy can dispense the medication.

```gherkin
Given the prescriber has signed a controlled substance prescription, When the transmission function is initiated, Then the system should send the digitally signed prescription record to the pharmacy for dispensing.
```

## FR-EPCS-007

As a system, I want to maintain an internal audit trail with daily analysis and incident reporting for controlled substances prescriptions, so that all activities related to these prescriptions are logged and incidents can be tracked.

```gherkin
Given the system is operational and a prescriber signs a prescription for a controlled substance
When the signing action occurs
Then the system logs the signing action and includes it in the daily analysis report
```

## FR-EPCS-008

As a system, I want to generate monthly prescription logs for controlled substances, so that historical data can be reviewed and analyzed.

```gherkin
Given the system is operational and the current date is within the last month of a previously generated log
When the system generates a new monthly prescription log
Then the log includes all controlled substances prescriptions issued in the last month
```

## FR-EPCS-009

As a prescriber, I want each signing action to cover prescriptions for a single patient only, so that patient-specific information is accurately recorded.

```gherkin
Given a prescriber signs a prescription for a patient
When the signing action occurs
Then the system associates the signing action with only one patient's prescription
```

## FR-EPCS-010

As a system, I want to transmit signed prescriptions to the pharmacy, so that the pharmacy can dispense the medication.

```gherkin
Given a prescriber signs a prescription for a controlled substance
When the signing action occurs
Then the system transmits the signed prescription to the designated pharmacy
```

## FR-EPCS-011

As a system, I want to ensure that the electronic prescription is transmitted as soon as possible after signature by the practitioner, so that there is minimal delay in medication dispensing.

```gherkin
Given a prescriber signs a prescription for a controlled substance
When the signing action occurs
Then the system transmits the electronic prescription within 1 minute of the practitioner's signature
```

## FR-EPCS-012

As a system, I want to print a prescription only if an intermediary or the designated pharmacy notifies a practitioner that an electronic prescription was not successfully delivered to the designated pharmacy, so that a backup can be provided in case of transmission failure.

```gherkin
Given an electronic prescription is not successfully delivered to the designated pharmacy
When the intermediary or pharmacy notifies the prescriber of the failure
Then the system prints the prescription with a note indicating the original transmission and failure
```

## FR-EPCS-013

As a prescribing practitioner, I want the system to indicate that I have signed every controlled prescription, so that the system is compliant with 21 CFR 1311 and indicates a signed prescription for controlled substance prescriptions.

```gherkin
Given a controlled prescription has been issued by a prescribing practitioner
When the prescription is signed by the practitioner
Then the system should indicate that the prescription has been signed
```

## FR-EPCS-014

As a pharmacy staff member, I want the system to ensure that each prescription received is not a fax converted from an electronic original, so that the system maintains the integrity of the e-prescribing process.

```gherkin
Given a prescription is received by the system
When the system checks the origin of the prescription
Then the system should reject any prescription that is a fax converted from an electronic original
```

## FR-EPCS-015

As a hospital administrator, I want the system to extend the e-prescribing module to support specific Schedule II-V controlled substances as defined by regulatory authorities, so that the hospital can comply with the regulations for prescribing these substances.

```gherkin
Given the e-prescribing module is extended
When a prescribing practitioner attempts to prescribe a specific Schedule II-V controlled substance
Then the system should support the prescription of that substance
```

## FR-EPCS-016

As a prescribing practitioner, I want the system to use a password and a hard token for two-factor authentication, so that prescriptions are signed using a secure method as stated in S-PRES-34.

```gherkin
Given a prescribing practitioner attempts to sign a prescription
When the system requires two-factor authentication
Then the system should prompt the practitioner to enter a password and use a hard token
```

## FR-EPCS-017

As a pharmacy staff member, I want the system to transmit signed prescriptions to the pharmacy, so that the pharmacy can process the prescription.

```gherkin
Given a signed prescription has been issued by a prescribing practitioner
When the system transmits the prescription to the pharmacy
Then the pharmacy should receive the signed prescription
```

## FR-EPCS-018

As a prescribing practitioner, I want the system to extend the e-prescribing module to support the classification of controlled substances as per Schedule II-V, so that the system can accurately categorize and manage these prescriptions.

```gherkin
Given the e-prescribing module is extended to support Schedule II-V
When a prescribing practitioner attempts to prescribe a controlled substance
Then the system should classify the prescription according to its Schedule
```

## FR-EPCS-019

As a system administrator, I want the system to provide identity proofing and credential issuance for practitioners, so that we can ensure only authorized individuals have access.

```gherkin
Given a practitioner requests a credential, When the system performs identity proofing and successfully verifies the practitioner's identity, Then the system should issue the appropriate credentials.
```

## FR-EPCS-020

As a system administrator, I want the system to enforce logical access control over the signing function using two individuals, so that we can ensure the integrity of the signing process.

```gherkin
Given two authorized individuals are required for the signing function, When both individuals complete their respective steps in the signing process, Then the system should allow the record to be signed.
```

## FR-EPCS-021

As a system administrator, I want the system to implement two-factor authentication using a password and a hard token at the signing step, as stated in S-PRES-40, so that we can enhance security during the signing process.

```gherkin
Given a user attempts to sign a record, When the user enters their password and inserts a valid hard token, Then the system should allow the signing process to proceed.
```

## FR-EPCS-022

As a system administrator, I want the system to use digital signatures and archiving of the signed record, so that we can ensure the integrity and non-repudiation of the records.

```gherkin
Given a record is signed, When the system applies a digital signature and archives the signed record, Then the system should store the record with its corresponding signature.
```

## FR-EPCS-023

As a system administrator, I want the system to transmit the signed record to the pharmacy, so that we can ensure timely and accurate delivery of the signed records.

```gherkin
Given a signed record is generated, When the system transmits the signed record to the pharmacy, Then the pharmacy should receive the signed record.
```

## FR-EPCS-024

As a system administrator, I want the system to maintain an internal audit trail as implied by S-PRES-41, so that we can track and verify the history of actions taken on records.

```gherkin
Given a record is signed, When the system maintains an internal audit trail, Then the system should log all actions related to the record.
```

## FR-EPCS-025

As a system administrator, I want the system to generate monthly prescription logs, so that I can review and audit the prescriptions.

```gherkin
Given the system is running and configured for monthly log generation
When the end of the month is reached
Then the system generates a monthly prescription log
```

