# Use cases

## UC-1 Patient Requests Prescription Renewal

- Primary actor: Patient
- Realises: FR-REF-001, FR-REF-002, FR-REF-019, FR-REF-020
- Preconditions: The patient has a pending prescription that needs renewal.; The patient has the hospital network's mobile app installed and is logged in.

Main success scenario:

1. The system reminds the patient 7 days before their medication supply runs out.
2. The patient taps on the reminder to request a prescription renewal.
3. The system prompts the patient to confirm they are still taking the medication.
4. The patient confirms and submits the renewal request.
5. The system sends the renewal request to the prescriber for approval.

Alternate and exception flows:

- If the patient does not confirm, the system does not send the renewal request.
- If the prescriber rejects the renewal request, the system notifies the patient and provides reasons.

Postconditions: The prescriber receives a renewal request.; The patient is informed of the status of their renewal request.

## UC-2 Patient Receives Medication Ready Notification

- Primary actor: Patient
- Realises: FR-REF-003, FR-REF-015, FR-REF-026
- Preconditions: The patient has a medication that is ready for pickup at the pharmacy.; The patient has the hospital network's mobile app installed and is logged in.

Main success scenario:

1. The system notifies the patient when their medication is ready for pickup.
2. The patient receives a text message with the notification.
3. The patient views the notification in the app.

Alternate and exception flows:

- If the patient does not receive the text message, they can check the app for the notification.

Postconditions: The patient is informed that their medication is ready for pickup.

## UC-3 Caregiver Acts on Patient's Behalf

- Primary actor: Caregiver
- Realises: FR-REF-011, FR-REF-022, FR-REF-027
- Preconditions: The patient has given explicit consent for the caregiver to act on their behalf.; The caregiver has the hospital network's mobile app installed and is logged in.

Main success scenario:

1. The system displays medication reminders for the patient.
2. The caregiver taps on a reminder to act on the patient's behalf.
3. The system prompts the caregiver to confirm the action.
4. The caregiver confirms and performs the action (e.g., requesting a prescription renewal).

Alternate and exception flows:

- If the caregiver does not confirm, the system does not perform the action.

Postconditions: The action is performed on behalf of the patient.; The patient is informed of the action taken by the caregiver.

## UC-4 Patient Withdraws Consent for Caregiver

- Primary actor: Patient
- Realises: FR-REF-012
- Preconditions: The patient has given explicit consent for a caregiver to act on their behalf.; The patient has the hospital network's mobile app installed and is logged in.

Main success scenario:

1. The system displays the option to withdraw consent for a caregiver.
2. The patient taps on the option to withdraw consent.
3. The system prompts the patient to confirm the withdrawal of consent.
4. The patient confirms and withdraws consent.

Alternate and exception flows:

- If the patient does not confirm, the system retains the existing consent.

Postconditions: The patient's consent for the caregiver is withdrawn.; The caregiver can no longer act on the patient's behalf.

