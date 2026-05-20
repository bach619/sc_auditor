---
name: security-audit
description: Security audit methodology: OWASP Top 10, threat modeling (STRIDE, PASTA), vulnerability assessment (CVSS scoring), penetration testing, SAST/DAST, and remediation planning
license: MIT
compatibility: opencode
metadata:
  audience: security-engineers
  domain: security
  paradigm: defensive
  integrates_with: [security-crypto, backend-python, backend-go, backend-elixir, database-postgres, frontend-react, frontend-svelte, infra-kubernetes, devops-platform-engineering]
---

## Security Audit & Pentesting Skill

### Audit Methodology
```
Reconnaissance → Threat Modeling → Vulnerability Assessment → Exploitation → Remediation → Re-verification
```

### OWASP Top 10 (Current)
1. **Broken Access Control**: IDOR, path traversal, CORS misconfig, forced browsing — verify every endpoint
2. **Cryptographic Failures**: Hardcoded keys, weak algorithms (MD5/SHA1), missing TLS, exposed secrets
3. **Injection**: SQL, NoSQL, OS command, LDAP, XPath — parameterize ALL queries
4. **Insecure Design**: Missing rate limiting, no input validation, over-trust of client-side data
5. **Security Misconfig**: Default credentials, verbose errors, unnecessary features enabled
6. **Vulnerable Components**: Outdated dependencies, unpatched CVEs, unsupported software
7. **Auth Failures**: Weak password policy, credential stuffing vulnerable, session fixation
8. **Software & Data Integrity**: Unsigned updates, insecure deserialization, CI/CD pipeline poisoning
9. **Logging & Monitoring**: No audit trail, insufficient alerting, logs without integrity protection
10. **SSRF**: Server-Side Request Forgery — validate and sanitize ALL user-supplied URLs

### Threat Modeling
- **STRIDE**: Spoofing, Tampering, Repudiation, Info disclosure, DoS, Elevation of privilege
- **PASTA**: Process for Attack Simulation and Threat Analysis — 7-stage risk-centric
- **Attack Trees**: Root = goal, nodes = attack steps, leaves = attack vectors
- **Outputs**: Data flow diagram (trust boundaries), threat list (prioritized), mitigation plan

### Vulnerability Scoring (CVSS v4)
- **Base**: Exploitability (AV, AC, PR, UI) + Impact (C, I, A) = 0-10
- **Temporal**: Exploit maturity, remediation level, report confidence
- **Environmental**: Modified base metrics + security requirements
- **Severity**: None (0), Low (0.1-3.9), Medium (4.0-6.9), High (7.0-8.9), Critical (9.0-10.0)

### SAST / DAST
- **SAST (Static)**: Semgrep, CodeQL, SonarQube — analyze source code without execution
- **DAST (Dynamic)**: OWASP ZAP, Burp Suite — test running application
- **SCA (Composition)**: Dependabot, Snyk, OWASP Dependency-Check — check dependencies
- **Secret Scanning**: TruffleHog, Gitleaks, GitGuardian — find exposed credentials

### Remediation Priorities
1. **Critical (24h)**: RCE, authentication bypass, data exfiltration possible
2. **High (1 week)**: SQLi, XSS (stored), privilege escalation, SSRF
3. **Medium (1 sprint)**: XSS (reflected), CSRF, information disclosure
4. **Low (backlog)**: Security headers missing, verbose errors in non-prod

### Common Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| Checkbox compliance | Running SAST scanner without reviewing results gives false confidence | Triage every finding; maintain a vulnerability register with owners |
| Relying solely on automated scanners | Scanners miss business logic flaws, auth bypass, race conditions | Combine SAST + DAST + manual penetration testing |
| No threat modeling | Security bolted on after design; fundamental flaws missed | Run STRIDE/PASTA during architecture phase; update on scope changes |
| Shift-right testing | Testing only after deployment to production | Integrate security gates in CI: pre-commit → PR → staging → pre-prod |
| Ignoring dependency vulnerabilities | Known CVEs in transitive dependencies accumulate unpatched | Dependabot/Renovate with auto-merge for patch; weekly review for major |
| False sense of security from pentest | One pentest per year doesn't catch daily code changes | Continuous security testing; automated DAST on every deployment |
| Over-reliance on WAF | WAF bypass techniques bypass signature-based rules | Defense in depth: WAF + input validation + parameterized queries + CSP |
| No responsible disclosure program | Security researchers can't report vulnerabilities safely | Publish `security.txt`; set up bug bounty or vulnerability disclosure program |
| Secret sprawl | API keys, tokens, passwords in code, configs, logs, chat history | Secret scanning in CI (truffleHog/gitleaks); pre-commit hooks; vault for secrets |

### Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---|---|---|---|
| SAST false positives overwhelming | Scanner rules too broad; no tuning | Review false positive rate per rule (>30% is high) | Disable noisy rules; use suppression comments with justification |
| DAST scan too slow | Crawling entire app; too many pages | Check scan duration; review crawl scope | Limit to critical paths; use authenticated scan for protected pages |
| SCA dependency conflicts | Transitive dependency version mismatch; breaking changes | Run `npm ls`, `pipdeptree`, `go mod graph` | Pin with lockfile; test upgrades on staging |
| Secret in git history | Secret committed before scanning was configured | `git log -p` shows secret in old commits | Rotate secret immediately; use `git filter-repo` to purge history |
| OWASP ZAP false positives on CSRF | ZAP sends requests without proper tokens | Review ZAP alerts for CSRF tokens in session | Configure ZAP context with auth; use script-based auth |
| Container image scan rejecting builds | High-severity CVEs in base image | Check scan output for CVE IDs and fix versions | Update base image; use distroless; pin to digest |
| SSL/TLS scan shows weak ciphers | Old TLS config on server | ssllabs.com or testssl.sh scan | Restrict to TLS 1.2+ with strong cipher suites |

### Implementation Checklist

- [ ] Threat model created (STRIDE/PASTA) for the system
- [ ] SAST tool configured in CI (Semgrep/CodeQL/SonarQube)
- [ ] DAST scanning scheduled (OWASP ZAP/Burp Suite) on staging
- [ ] SCA/dependency scanning active (Dependabot/Snyk/OWASP Dependency-Check)
- [ ] Secret scanning in CI and pre-commit hooks (truffleHog/gitleaks)
- [ ] Container image scanning in CI pipeline (Trivy/Grype)
- [ ] OWASP Top 10 covered by automated tests for the specific tech stack
- [ ] Rate limiting on all auth and API endpoints
- [ ] CSP headers configured and tested
- [ ] CORS configured with explicit origins (no `*` in production)
- [ ] Responsible disclosure / bug bounty program published
- [ ] `security.txt` deployed at `/.well-known/security.txt`
- [ ] Penetration test conducted before major releases
- [ ] Vulnerability remediation SLAs defined (Critical: 24h, High: 1w, Medium: 1 sprint)
- [ ] Incident response plan documented and tested (tabletop exercise)
- [ ] Security regression tests added for previously fixed vulnerabilities
