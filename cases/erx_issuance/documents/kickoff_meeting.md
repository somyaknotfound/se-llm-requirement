# E-prescribing programme — kickoff meeting notes

**Attendees:** product owner, lead architect, clinical safety officer, compliance officer,
information security officer, two hospitalists, outpatient pharmacy manager.

## Scope agreed

- Outpatient e-prescribing for non-controlled medications at all four hospitals.
- Controlled substances are excluded from this release and move to the EPCS project.
- Paper and fax prescriptions are to be retired once the module is live everywhere.

## Discussion

The product owner restated the adoption target: no paper or faxed outpatient
prescriptions within a year of go-live. The hospitalists said adoption depends
entirely on speed; last year's pilot of a vendor module was abandoned because alerts
took several seconds and interrupted every order.

The clinical safety officer presented last quarter's adverse drug event review. Two
events involved interaction alerts that were overridden with no recorded reason.
She asked that the new module make the reason for every override visible to the
safety committee.

The pharmacy manager reported that pharmacies currently learn about cancelled
prescriptions by phone, sometimes after the medication has been dispensed.

Compliance confirmed that certification against the ONC criteria is a condition of
go-live, and that the go-live date is tied to the certification calendar and cannot
move.

## Actions

1. Architect to document the legacy order interface and the intermediary connection.
2. Clinical safety officer to circulate the medication ordering policy.
3. Security officer to confirm session and audit requirements.
4. Product owner to schedule stakeholder interviews for the requirements phase.
