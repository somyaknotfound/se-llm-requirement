# Data requirements

| Requirement | Statement | Acceptance criteria | Sources |
|---|---|---|---|
| NFR-EPCS-004 | The system shall archive the digitally signed record of the prescription. | The system archives the digitally signed record of the prescription. | S-PRES-01; S-PRES-02 |
| FR-EPCS-004 | The system shall include the patient's DEA registration information on the prescription and ask which DEA registration to use when the patient has more than one, as stated in S-PRES-30. | The system includes the patient's DEA registration information on the prescription, asks which DEA registration to use when the patient has more than one, and this information is verified to be correct. | S-PRES-03; S-PRES-14; S-PRES-30 |
| FR-EPCS-005 | The system shall allow printing of a prescription after transmission only if it is clearly labeled as a copy not for dispensing. | The system allows printing of a prescription after transmission only if it is clearly labeled as a copy not for dispensing. | S-PRES-01; S-PRES-02 |
| NFR-EPCS-008 | The system shall maintain records related to controlled substance prescriptions for two years. | The system maintains records related to controlled substance prescriptions for two years. | S-PRES-01; S-PRES-02 |
| NFR-EPCS-013 | The system shall digitally sign and archive the signed record of controlled substances prescriptions. | The system generates a digital signature for each signed prescription and stores it in an archived record. | S-CRED-06 |
| FR-EPCS-008 | The system shall generate monthly prescription logs for controlled substances. | The system generates and stores a log of all controlled substances prescriptions issued within the last month. | S-CRED-06; S-CRED-17 |
| NFR-EPCS-020 | The system shall keep records as the DEA requires. | The system retains controlled-substance records electronically for at least two years and makes them readily retrievable. | S-COMP-07 |
| NFR-EPCS-026 | The system shall generate monthly prescription logs. | The system generates and maintains monthly prescription logs. | S-COMP-01 |
| FR-EPCS-014 | The system shall ensure that each prescription is never received as a fax converted from the electronic original. | Each prescription received by the system must not be a fax converted from an electronic original. | S-PHARM-01; S-PHARM-06; S-PHARM-11; S-PHARM-17 |
| NFR-EPCS-033 | NFR-EPCS-033: The system shall maintain a log of all prescriptions processed on a monthly basis. | The system generates and maintains a log of all prescriptions processed on a monthly basis. | S-PHARM-01; S-PHARM-06; S-PHARM-13 |
| NFR-EPCS-041 | The system shall retain all archived records electronically for at least two years from the date of their receipt or creation. | All archived records are retained electronically for at least two years from the date of their receipt or creation. | S-AUD-01; S-AUD-05 |
| NFR-EPCS-045 | The system shall archive signed records of prescriptions. | Signed records are archived. | DOC-KICKOFF#p2 |
| NFR-EPCS-047 | The system shall generate monthly prescription logs. | Monthly prescription logs are generated. | DOC-KICKOFF#p2 |
| FR-EPCS-025 | The system shall generate monthly prescription logs. | Monthly prescription logs are generated. | DOC-IDP#p1 |
