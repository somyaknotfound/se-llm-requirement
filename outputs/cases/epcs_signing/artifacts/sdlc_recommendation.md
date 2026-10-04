# SDLC recommendation

**Recommended:** Waterfall (87.5%) — runner-up V-Model. Status: pending approval by project manager, architect, security officer, compliance officer.

| Rank | Model | Suitability | Supporting rules |
|---|---|---|---|
| 1 | Waterfall | 87.5% | R-WF |
| 2 | V-Model | 85.0% | R-V |
| 3 | Hybrid | 75.0% | — |
| 4 | Spiral | 52.5% | — |
| 5 | DevSecOps | 37.5% | — |
| 6 | Agile | 25.0% | — |

## Decision factors (median of both models)

| Factor | Score |
|---|---|
| requirement_instability | 1 |
| regulatory_criticality | 5 |
| security_risk | 5 |
| project_complexity | 3 |
| system_size | 3 |
| legacy_dependence | 1.5 |
| change_frequency | 1.5 |
| continuous_delivery_need | 1 |
| stakeholder_availability | 4 |
| documentation_rigour | 4.5 |
| schedule_budget_rigidity | 5 |
| formal_verification_need | 5 |
| failure_consequence | 5 |

Contested (models differ by 2+ points): system_size, stakeholder_availability

**Escalated:** near tie: Waterfall 87.5% vs V-Model 85.0%; the two models disagree by 2+ points on: system_size, stakeholder_availability

## Justification

Waterfall ranks first for this project due to its stable requirements and extensive approvals, which align well with the regulatory criticality and formal verification needs of the EPCS extension. The project's fixed date and budget, as well as the necessity for formal verification and validation, make Waterfall a suitable choice. V-Model is the runner-up because it emphasizes strict verification and validation, which are also critical for this project. However, the project's requirement instability and change frequency, despite being low, could pose challenges in adhering strictly to the Waterfall methodology.

Strongest argument against: The strongest argument against Waterfall is its potential difficulty in managing the project's fixed date and budget, especially given the regulatory constraints that may require flexibility in response to unforeseen issues or changes.


## Project workflow — Waterfall

| # | Phase | Activities | Roles | Deliverables | Security | Compliance checkpoints | Exit criterion | Approval gate |
|---|---|---|---|---|---|---|---|---|
| 1 | Initiation | Define scope and objectives; Select SDLC and plan | project_manager, product_owner | Project charter; SDLC decision record |  |  | Charter and SDLC decision approved | project_manager, architect, security_officer, compliance_officer (RTM checked) |
| 2 | Requirements | Elicit and analyse requirements; Baseline the SRS; Clinical hazard identification | business_analyst, product_owner, compliance_officer | SRS baseline; Traceability matrix |  | HIPAA risk analysis completed and approved (45 CFR 164.308(a)(1)(ii)(A)) | SRS baselined | product_owner, compliance_officer (RTM checked) |
| 3 | Design | Architecture and detailed design | architect | Design specification | Threat modelling (STRIDE) of the functionality; Security requirements review |  | Design approved | architect, security_officer (RTM checked) |
| 4 | Implementation | Build to the design; Unit test | developer | Code; Unit test results | Static application security testing on every build; Dependency and secret scanning |  | Code complete |  |
| 5 | Verification | Integration and system test against the SRS | tester | Test report | Dynamic application security testing; Penetration test before release |  | All requirements verified |  |
| 6 | Deployment | Release and hand-over; Clinical safety case approved | operations, project_manager | Release notes | Security sign-off | ONC certification testing passed for the applicable 45 CFR 170.315 criteria; Third-party EPCS audit or certification passed before use (21 CFR 1311.300) | Accepted into service | project_manager, clinical_safety_officer, security_officer, compliance_officer (RTM checked) |
| 7 | Maintenance | Corrective maintenance; Change control | operations | Change log | Security monitoring and incident response; Vulnerability patching to an agreed timescale | Security documentation retained for 6 years (45 CFR 164.316(b)(2)(i)); Daily audit-trail analysis with incident reporting within one business day (21 CFR 1311.150); Re-audit when signing functionality changes or every two years (21 CFR 1311.300) | Retirement |  |

```mermaid
flowchart LR
    P0{{"Initiation"}}
    P1{{"Requirements"}}
    P0 --> P1
    P2{{"Design"}}
    P1 --> P2
    P3["Implementation"]
    P2 --> P3
    P4["Verification"]
    P3 --> P4
    P5{{"Deployment"}}
    P4 --> P5
    P6["Maintenance"]
    P5 --> P6
```

## Project-specific activities

- **Initiation:** Identify key stakeholders and their roles in the EPCS system implementation (NFR-EPCS-009, NFR-EPCS-010)
- **Requirements:** Conduct a clinical hazard analysis to identify risks associated with EPCS (FR-EPCS-001, NFR-EPCS-002, NFR-EPCS-003, NFR-EPCS-004, NFR-EPCS-005, NFR-EPCS-006, NFR-EPCS-007, NFR-EPCS-008, NFR-EPCS-009, NFR-EPCS-010, NFR-EPCS-011, NFR-EPCS-012, NFR-EPCS-013, NFR-EPCS-014)
- **Requirements:** Validate the EPCS requirements with clinical staff and IT security experts (FR-EPCS-001, NFR-EPCS-002, NFR-EPCS-003, NFR-EPCS-004, NFR-EPCS-005, NFR-EPCS-006, NFR-EPCS-007, NFR-EPCS-008, NFR-EPCS-009, NFR-EPCS-010, NFR-EPCS-011, NFR-EPCS-012, NFR-EPCS-013, NFR-EPCS-014)
- **Design:** Develop a detailed design for the identity proofing and credential issuance process (NFR-EPCS-009, NFR-EPCS-010, NFR-EPCS-011, NFR-EPCS-012, NFR-EPCS-013, NFR-EPCS-014)
- **Design:** Design the two-factor authentication mechanism for the signing function (NFR-EPCS-002, NFR-EPCS-012)
- **Implementation:** Implement the two-factor authentication mechanism for the signing function (NFR-EPCS-002, NFR-EPCS-012)
- **Implementation:** Integrate the identity proofing and credential issuance process into the system (NFR-EPCS-009, NFR-EPCS-010, NFR-EPCS-011, NFR-EPCS-013, NFR-EPCS-014)
- **Verification:** Test the two-factor authentication mechanism for the signing function (NFR-EPCS-002, NFR-EPCS-012)
- **Verification:** Validate the identity proofing and credential issuance process (NFR-EPCS-009, NFR-EPCS-010, NFR-EPCS-011, NFR-EPCS-013, NFR-EPCS-014)
- **Deployment:** Conduct a third-party audit to ensure compliance with EPCS requirements (NFR-EPCS-014)
- **Maintenance:** Monitor the internal audit trail for daily analysis and incident reporting (FR-EPCS-007)
- **Maintenance:** Generate monthly prescription logs for controlled substances (FR-EPCS-008)
