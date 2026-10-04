# SDLC recommendation

**Recommended:** Agile (62.5%) — runner-up DevSecOps. Status: pending approval by project manager, architect, security officer, compliance officer.

| Rank | Model | Suitability | Supporting rules |
|---|---|---|---|
| 1 | Agile | 62.5% | — |
| 2 | DevSecOps | 62.5% | — |
| 3 | Hybrid | 43.8% | — |
| 4 | Waterfall | 39.6% | — |
| 5 | Spiral | 37.5% | — |
| 6 | V-Model | 32.5% | — |

## Decision factors (median of both models)

| Factor | Score |
|---|---|
| requirement_instability | 2.5 |
| regulatory_criticality | 3 |
| security_risk | 3.5 |
| project_complexity | 2.5 |
| system_size | 1.5 |
| legacy_dependence | 1 |
| change_frequency | 3.5 |
| continuous_delivery_need | 3.5 |
| stakeholder_availability | 3 |
| documentation_rigour | 2.5 |
| schedule_budget_rigidity | 2 |
| formal_verification_need | 2 |
| failure_consequence | 3 |

Contested (models differ by 2+ points): regulatory_criticality, continuous_delivery_need, stakeholder_availability, formal_verification_need, failure_consequence

**Escalated:** no brief rule supports the top-ranked model (Agile); near tie: Agile 62.5% vs DevSecOps 62.5%; the two models disagree by 2+ points on: regulatory_criticality, continuous_delivery_need, stakeholder_availability, formal_verification_need, failure_consequence

## Justification

Agile ranks first for this project due to its high requirement instability, frequent changes, and the need for continuous delivery. The feature's moderate complexity and integration with an existing mobile app support weekly releases, aligning well with Agile practices. DevSecOps is the runner-up because it addresses the security risks associated with handling protected health information on personal devices, ensuring that security is integrated throughout the development lifecycle. However, the low clinical risk and well-defined requirements make formal verification less critical, which slightly favors Agile.

Strongest argument against: While Agile excels in handling frequent changes and requirement instability, its informal testing approach may not fully address the moderate security risks associated with the system handling protected health information on personal devices.


## Project workflow — Agile

| # | Phase | Activities | Roles | Deliverables | Security | Compliance checkpoints | Exit criterion | Approval gate |
|---|---|---|---|---|---|---|---|---|
| 1 | Inception | Product vision; Initial backlog; Select SDLC | product_owner, team | Product vision; Initial backlog; SDLC decision record |  |  | Vision agreed | project_manager, architect, security_officer, compliance_officer (RTM checked) |
| 2 | Backlog refinement | Write and refine user stories with acceptance criteria; Clinical hazard identification | product_owner, team | Ready backlog items |  | HIPAA risk analysis completed and approved (45 CFR 164.308(a)(1)(ii)(A)) | Stories meet definition of ready | product_owner, compliance_officer (RTM checked) |
| 3 | Sprint | Design, build and test stories | team | Potentially shippable increment | Static application security testing on every build |  | Definition of done met |  |
| 4 | Sprint review | Demonstrate to stakeholders; Adapt the backlog; Clinical validation of alerts and workflows with prescribers | product_owner, stakeholders | Review notes; Updated backlog |  |  | Increment accepted |  |
| 5 | Release | Release accepted increments; Clinical safety case approved | product_owner, operations | Release notes | Security sign-off | ONC certification testing passed for the applicable 45 CFR 170.315 criteria | Released | project_manager, clinical_safety_officer, security_officer, compliance_officer (RTM checked) |
| 6 | Operations and feedback | Monitor usage; Collect feedback into the backlog | operations, product_owner | Usage and feedback reports | Security monitoring and incident response | Security documentation retained for 6 years (45 CFR 164.316(b)(2)(i)) | Continuous |  |

```mermaid
flowchart LR
    P0{{"Inception"}}
    P1{{"Backlog refinement"}}
    P0 --> P1
    P2["Sprint"]
    P1 --> P2
    P3["Sprint review"]
    P2 --> P3
    P4{{"Release"}}
    P3 --> P4
    P5["Operations and feedback"]
    P4 --> P5
```

## Project-specific activities

- **Inception:** Identify key stakeholders and their roles in the clinical validation process (e.g., prescribers, pharmacists, caregivers)
- **Inception:** Develop a high-level workflow diagram for medication refill reminders and renewal requests
- **Backlog refinement:** Conduct a clinical hazard analysis to identify potential risks associated with medication refill reminders and renewal requests
- **Backlog refinement:** Create user personas for patients, caregivers, and prescribers to ensure the system meets their needs
- **Sprint:** Prototype the user interface for medication refill reminders and renewal requests, focusing on ease of use and patient consent
- **Sprint:** Develop a test plan to validate the system's ability to notify patients when their medication is ready for pickup or delivery
- **Sprint review:** Conduct a clinical validation session with prescribers to ensure the system's workflows and alerts are safe and effective
- **Sprint review:** Gather feedback from patients on the usability of the medication refill reminders and renewal requests feature
- **Release:** Prepare a clinical safety case to document the system's compliance with regulatory standards for medication management
- **Release:** Deploy the system in a controlled environment to monitor its performance and gather initial feedback
- **Operations and feedback:** Monitor the system's usage patterns to identify any issues or areas for improvement
- **Operations and feedback:** Collect user feedback through surveys or direct communication and update the backlog as necessary
