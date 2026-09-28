# Incident report IR-2026-0314 (adverse drug event, moderate harm)

**Patient:** Jane Holloway, MRN: 00482913, DOB: 04/12/1961
**Reporting clinician:** Dr. Alan Brooks, DEA AB1234563, NPI 1234567893,
phone (555) 201-3344, alan.brooks@example-hospital.org

## What happened

The patient was discharged with a new prescription for warfarin while an active
outpatient prescription for another anticoagulant remained on her medication list.
The duplicate-therapy alert fired at ordering and was overridden with no reason
recorded. The patient was readmitted with a bleed four days later.

## Contributing factors

- The override required no reason, so the safety committee could not tell whether
  the duplication was intended.
- The alert did not distinguish the duplicate anticoagulant from routine low-severity
  notices, and the prescriber had seen eleven alerts on that order session.
- The pharmacy received the new prescription without any indication that an alert
  had been overridden.

## Recommendations

1. Require a documented reason for overriding duplicate-therapy and high-severity
   interaction alerts.
2. Visually separate high-severity alerts from low-severity notices.
3. Send override information to the dispensing pharmacy.
