# User stories

## FR-REF-001

As a system, I want to remind the patient 7 days before any of their medications runs out, so that the patient can reorder in time.

```gherkin
Given the system has a patient's medication schedule
When the system detects a medication is running low in 7 days
Then the system sends a reminder to the patient 7 days before the medication's supply is expected to run out
```

## FR-REF-002

As a patient, I want to request a prescription renewal with one tap from the reminder, so that I can easily reorder my medications.

```gherkin
Given the system sends a reminder to the patient about a medication running low
When the patient taps on the reminder notification
Then the system verifies the patient's identity and initiates a prescription renewal request
```

## FR-REF-003

As a system, I want to notify the patient S-PAT-16 when their medication is ready for pickup at the pharmacy, so that the patient can collect it promptly.

```gherkin
Given the system has information about medication pickup readiness
When the medication is ready for pickup
Then the system sends a notification to the patient S-PAT-16
```

## FR-REF-004

As a system, I want to remind the patient 7 days before their medication runs out, so that the patient can reorder in time.

```gherkin
Given the system has a patient's medication schedule
When the system detects a medication is running low in 7 days
Then the system sends a reminder to the patient 7 days before the medication's supply is expected to run out
```

## FR-REF-005

As a system, I want to name the medication that is running low in the reminder notification so the patient knows which one to reorder, so that the patient can easily identify the medication.

```gherkin
Given the system detects a medication is running low
When the system sends a reminder to the patient
Then the reminder notification includes the name of the medication that is running low
```

## FR-REF-006

As a system, I want to notify the patient with a text message when their medication is running low, prompting them to reorder, so that the patient can be reminded even if they miss the reminder notification.

```gherkin
Given the system detects a medication is running low
When the system sends a text message to the patient
Then the text message prompts the patient to reorder their medication
```

## FR-REF-007

As a system, I want to not make prescribing decisions, so that it remains within the scope of medical professionals.

```gherkin
Given the system is operational and a patient requests a prescription renewal, When the system receives the request, Then the system should only facilitate the request for renewal and not generate or approve any prescriptions.
```

## FR-REF-008

As a system, I want to remind the patient before their medication supply runs out, so that they can plan for refills.

```gherkin
Given the system has access to the patient's medication schedule and the current supply status, When the medication supply is expected to run out in 7 days, Then the system should send a reminder to the patient's mobile app.
```

## FR-REF-009

As a patient, I want to request a prescription renewal and view reminders for my caregiver, but only if I've given consent in the app, so that my privacy is respected.

```gherkin
Given the patient has given consent in the app, When the patient requests a prescription renewal, Then the system should allow the patient to initiate the request through the mobile app.
Given the patient has given consent in the app, When the patient views reminders for their caregiver, Then the system should display the reminders.
```

## FR-REF-010

As a system, I want to notify the patient when the pharmacy has the medication ready, so that the patient can plan accordingly.

```gherkin
Given the pharmacy has prepared the medication for pickup or delivery, When the system receives confirmation from the pharmacy, Then the system should send a notification to the patient's mobile app.
```

## FR-REF-011

As a patient, I want the system to allow a caregiver to access and view my medication reminders only if I've given explicit consent in the app, so that my privacy is respected.

```gherkin
Given the patient has given explicit consent in the app for a specific caregiver, When the caregiver attempts to view the patient's medication reminders, Then the system should allow the caregiver to access the reminders.
```

## FR-REF-012

As a patient, I want the system to allow me to withdraw consent for a caregiver at any time, so that I can control who has access to my information.

```gherkin
Given the patient has given consent in the app for a specific caregiver, When the patient withdraws consent through the app, Then the system should immediately stop all related activities involving the caregiver.
```

## FR-REF-013

As a system, I want to remind patients before their medication supply runs out, so that 30% of eligible patients use the renewal request feature within six months.

```gherkin
Given a patient with an upcoming medication supply expiration date
When the system sends a reminder notification one week before the supply is expected to run out
Then the patient should receive the notification and potentially use the renewal request feature
```

## FR-REF-014

As a system, I want to change reminder timing and wording based on the results of A/B testing, with the frequency determined by the outcomes of the tests, so that the system can switch between different reminder wordings and timings for testing purposes.

```gherkin
Given the system is conducting A/B testing for reminder wording and timing
When the system receives test results indicating a preference for a new reminder wording and timing
Then the system should implement the new reminder wording and timing
```

## FR-REF-015

As a system, I want to notify patients when the pharmacy has the medication ready, so that 30% of eligible patients using renewal requests within six months.

```gherkin
Given a patient with a prescription that is ready at the pharmacy
When the system receives confirmation from the pharmacy that the medication is ready
Then the system should notify the patient that their medication is ready for pickup
```

## FR-REF-016

As a patient, I want to request a prescription renewal, so that I can ensure my medication supply does not run out.

```gherkin
Given a patient with an expired or nearly expired prescription
When the patient requests a renewal through the system
Then the system should process the request and notify the pharmacy to prepare the medication
```

## FR-REF-017

As a system, I want to notify patients of reminder timing and wording changes based on feedback, with A/B testing support for reminder wording to ensure 30% of eligible patients use renewal requests within six months, so that the system can adjust reminders according to patient feedback and support testing.

```gherkin
Given the system has conducted A/B testing for reminder wording and timing
When the system receives feedback indicating a preference for a new reminder wording and timing
Then the system should implement the new reminder wording and timing and notify patients of these changes
```

## FR-REF-018

As a system, I want to remind patients before their medication supply runs out, so that patients receive a notification at least one week before their medication supply is expected to run out.

```gherkin
Given a patient with an upcoming medication supply expiration date
When the system sends a reminder notification one week before the supply is expected to run out
Then the patient should receive the notification and be reminded of the impending supply expiration
```

## FR-REF-019

As a patient, I want to request a prescription renewal through the mobile app, so that my medication supply is not interrupted.

```gherkin
Given a patient has a current prescription and their medication supply is running low, When the patient requests a renewal from the app, Then the system should confirm they are still taking the medication before sending the renewal request to the prescriber for approval.
Given a patient has requested a prescription renewal, When the prescriber approves the request, Then the system should automatically generate and send a refill order to the pharmacy.
```

## FR-REF-020

As a prescriber, I want to be notified when a patient requests a prescription renewal, so that I can review and approve the request promptly.

```gherkin
Given a patient has requested a prescription renewal through the app, When the system receives the request, Then it should notify the prescriber via their EHR interface or email.
Given a prescriber has received a notification about a prescription renewal request, When they log into their EHR, Then they should see the request in their pending tasks list.
```

## FR-REF-021

As a patient, I want to be notified when my medication is ready for pickup or delivery, so that I can plan accordingly.

```gherkin
Given a patient has requested a prescription renewal and the refill order has been processed, When the pharmacy prepares the medication, Then the system should send a notification to the patient via the app.
Given a patient has requested a prescription for home delivery, When the pharmacy packages the medication, Then the system should notify the patient that their medication is ready for pickup or delivery.
```

## FR-REF-022

As a caregiver, I want to act on behalf of a patient with their consent, so that I can ensure they receive their medication.

```gherkin
Given a patient has given explicit consent for a caregiver to submit refill requests on their behalf, When the caregiver logs into the app and submits a refill request, Then the system should send the request to the prescriber for approval.
Given a prescriber has approved a refill request submitted by a caregiver, When the pharmacy processes the order, Then the system should notify both the patient and the caregiver that the medication is ready.
```

## FR-REF-024

As a patient, I want to receive reminders before my medication supply runs out, so that I can refill it in time.

```gherkin
Given a patient has a current prescription and their medication supply is running low, When the system calculates that the supply will run out within 7 days, Then it should send a reminder notification to the patient via the app.
Given a patient has received a reminder notification, When they open the app, Then they should see a message indicating that their medication supply is running low and prompting them to request a refill.
```

## FR-REF-025

As a patient, I want to be able to request a prescription renewal, so that my medication supply is not interrupted.

```gherkin
Given a patient has a current prescription and their medication supply is running low, When the patient requests a renewal from the app, Then the system should allow them to submit the request.
Given a patient has requested a prescription renewal, When the prescriber approves the request, Then the system should automatically generate and send a refill order to the pharmacy.
```

## FR-REF-026

As a system, I want to notify patients when the pharmacy has the medication ready, except through lock-screen notifications as per S-SEC-14, so that patients receive timely information.

```gherkin
Given the patient's medication is ready at the pharmacy
When the system checks the status of the medication
Then the system sends a notification to the patient's mobile app, excluding lock-screen notifications
```

## FR-REF-027

As a system, I want to allow caregivers to act on the patient's behalf with the patient's consent, so that caregivers can perform actions on the patient's behalf.

```gherkin
Given a caregiver has the patient's explicit consent
When the caregiver logs into the system using the patient's credentials
Then the system allows the caregiver to perform actions on the patient's behalf
```

## FR-REF-028

As a system, I want to support secure messaging for patient communication, ensuring that as little information as possible is stored on the phone, as per S-SEC-16, so that patient data is protected.

```gherkin
Given a patient and their prescriber are using the secure messaging feature
When messages are exchanged between them
Then minimal data is stored on the device
```

## FR-REF-029

As a system, I want to remind the patient one week before their medication supply runs out, so that patients can plan for refills.

```gherkin
Given the system has access to the patient's medication schedule
When the medication supply is expected to run out in one week
Then the system sends a reminder to the patient's mobile app
```

## FR-REF-030

As a patient, I want to request a prescription renewal, so that I can manage my medication supply.

```gherkin
Given 30% of eligible patients are using the renewal request feature
When the feature is deployed for six months
Then 30% of eligible patients have used the renewal request feature
```

## FR-REF-031

As a system, I want to notify the patient when their pharmacy has the medication ready, so that patients can plan for pickup or delivery.

```gherkin
Given the patient's medication is ready at the pharmacy
When the system checks the status of the medication
Then the system sends a notification to the patient's mobile app
```

## FR-REF-032

As a caregiver, I want to initiate a prescription renewal request on behalf of the patient, so that the patient's medication supply is not interrupted.

```gherkin
Given the patient has given explicit consent for the caregiver to act on their behalf
When the caregiver logs into the system and requests a prescription renewal
Then the system should allow the caregiver to initiate the request
```

## FR-REF-033

As a patient, I want to be reminded before my medication supply runs out, so that I can refill it in time.

```gherkin
Given the system has access to my medication refill schedule
When the medication supply is expected to run out within 7 days
Then the app should send a reminder to my mobile device
```

## FR-REF-034

As a patient, I want to request a prescription renewal, so that I can ensure my medication supply is continuous.

```gherkin
Given the system has a renewal request feature
When I use the renewal request feature
Then 30% of eligible patients should use the feature within six months
```

## FR-REF-035

As a patient, I want to be notified when my medication is ready at the pharmacy, so that I can pick it up or have it delivered.

```gherkin
Given the pharmacy has the medication ready for pickup or delivery
When the pharmacy updates the system with this information
Then the app should send a notification to my mobile device
```

## FR-REF-036

As a caregiver, I want to view the patient's medication refills, so that I can monitor their health and ensure they are taking their medications as prescribed.

```gherkin
Given the patient has given explicit consent for the caregiver to view their medication refills
When the caregiver logs into the system
Then the app should allow the caregiver to view the patient's medication refills
```

## FR-REF-037

As a patient, I want to see my latest lab results, so that I can understand my health status and discuss it with my healthcare provider.

```gherkin
Given the system has access to my lab results
When I request to view my latest lab results or the prescriber specifies regular intervals for updates
Then the app should display my latest lab results
```

## FR-REF-038

As a system, I want to remind the patient before their medication supply runs out, so that the patient can refill their prescription in time.

```gherkin
Given the patient's medication supply is set to run out in 14 days, When the system calculates that there are 7 days left until the supply runs out, Then the app sends a reminder to the patient's mobile device.
Given the patient has not interacted with the app for 2 weeks, When the system detects that the medication supply is due to run out in 7 days, Then the app sends a notification to the patient's mobile device.
```

## FR-REF-039

As a patient, I want to request a prescription renewal when my supply runs out, so that I can continue receiving my medication without interruption.

```gherkin
Given the patient's medication supply is set to run out in 7 days, When the patient initiates a renewal request through the app, Then the system records this action for future reference and sends the request to the pharmacy.
Given the patient has a valid prescription, When the patient clicks on the 'Request Renewal' button in the app, Then the app automatically generates and submits the renewal request.
```

## FR-REF-040

As a system, I want to notify the patient when the pharmacy has the medication ready, so that the patient can pick up their prescription promptly.

```gherkin
Given the pharmacy has dispensed the medication for the patient, When the system receives confirmation from the pharmacy, Then the app sends a notification to the patient's mobile device.
Given the patient's medication is ready at the pharmacy, When the pharmacy updates the status in the system, Then the app sends a push notification to the patient's mobile device.
```

## FR-REF-041

As a system, I want to allow a caregiver to act on the patient's behalf with the patient's consent, so that the caregiver can manage the patient's medication needs.

```gherkin
Given the patient has given explicit consent for a specific caregiver to act on their behalf, When the caregiver logs into the app and requests a prescription renewal, Then the system allows the caregiver to perform this action.
Given the patient has granted permission to a caregiver, When the caregiver uses the 'Request Renewal' feature in the app, Then the system records the action as performed by the caregiver.
```

## FR-REF-043

As a system, I want to remind the patient before their medication supply runs out, so that the patient can refill their prescription in time.

```gherkin
Given the patient's medication supply is set to run out in 14 days, When the system calculates that there are 7 days left until the supply runs out, Then the app sends a reminder to the patient's mobile device.
Given the patient has not interacted with the app for 2 weeks, When the system detects that the medication supply is due to run out in 7 days, Then the app sends a notification to the patient's mobile device.
```

## FR-REF-044

As a patient, I want to request a prescription renewal, so that I can continue receiving my medication without interruption.

```gherkin
Given the patient has a valid prescription, When the patient clicks on the 'Request Renewal' button in the app, Then the app automatically generates and submits the renewal request.
Given the patient's medication supply is set to run out soon, When the patient initiates a renewal request through the app, Then the system records this action for future reference.
```

## FR-REF-045

As a patient, I want the system to notify me when the pharmacy has my medication ready, so that I can plan to pick it up or have it delivered.

```gherkin
Given the patient has an active prescription and the pharmacy has prepared the medication for pickup or delivery
When the system detects that the medication is ready at the pharmacy
Then the system sends a notification to the patient's mobile app with details of the medication and the pickup/delivery options
```

## FR-REF-046

As a caregiver, I want the system to allow me to act on the patient's behalf with their consent, so that I can manage their prescriptions.

```gherkin
Given the patient has granted proxy access to a specific caregiver through the app or portal
When the caregiver logs into the system and requests a prescription renewal on the patient's behalf
Then the system allows the caregiver to perform the action, and sends a notification to the patient confirming the request
```

