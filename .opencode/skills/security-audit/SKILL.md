---
name: security-audit
description: Security audit methodology — OWASP, threat modeling, SAST/DAST, pentesting, supply chain, and remediation planning.
license: MIT
maturity: god-tier
audience: security-engineers, devs
---

# Security-Audit — Panduan Lengkap (Bahasa Indonesia)

Dokumen ini adalah panduan praktis untuk melakukan security audit aplikasi web dan microservices. Menggabungkan metodologi threat modeling, SAST/DAST, manual pentest, dan audit rantai pasokan.

## 1. Phases of an Audit

1. Scope & Rules of Engagement (ROE): boundaries, timebox, sensitive data handling
2. Reconnaissance: asset inventory, open ports, dependency tree
3. Threat Modeling: STRIDE per component
4. Automated Scans: SAST (static), DAST (dynamic), dependency scanning
5. Manual Testing: auth bypass, business logic, chained exploits
6. Reporting & Remediation: triage by severity (CVSS) + reproduction steps

## 2. Threat Modeling (STRIDE)

- Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege
- For each component: identify assets, entry points, trust boundaries, and mitigations.

## 3. SAST & Dependency Scanning

- Tools: Semgrep, Bandit (Python), npm audit / snyk, OWASP Dependency-Check
- CI integration: fail build on high-severity vulnerabilities, create ticket with remediation steps

CI example (GitHub Actions) snippet:

```yaml
name: security-scan
on: [push, pull_request]
jobs:
  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Semgrep
        uses: returntocorp/semgrep-action@v1
      - name: Run dependency-check
        uses: owasp/dependency-check-action@v2
```

## 4. DAST & Runtime Analysis

- Use OWASP ZAP or Burp Suite for dynamic scans. Instrument runtime logs and traces to correlate findings.
- Fuzz critical endpoints with corpora derived from real traffic.

## 5. Manual Pentest Priority Areas

- Authentication & session management (login brute force, session fixation)
- Authorization (object-level access control, IDOR)
- Business logic abuse (refund flows, race conditions)
- Input validation (SQLi, XSS, command injection)
- File upload & deserialization vulnerabilities

## 6. Supply Chain Security

- Use Sigstore/Cosign for artifact signing
- Enforce SLSA levels for CI/CD pipelines
- Lock dependency versions, use reproducible builds

## 7. Reporting & Remediation

- Triage by CVSS + exploitability + business impact
- Provide PoC (if safe) + remediation steps + test case
- Post-fix: re-run targeted tests and confirm fix

---

## Appendix: Quick Checklist (Bahasa Indonesia)

- [ ] Scope & ROE defined
- [ ] Asset inventory complete
- [ ] Semgrep/SAST in CI
- [ ] Dependency scanning configured
- [ ] DAST scan executed
- [ ] Manual pentest critical flows covered
- [ ] Remediation tickets created + verified
