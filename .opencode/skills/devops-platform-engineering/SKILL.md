---
name: devops-platform-engineering
description: DevOps & Platform Engineering: CI/CD (GitHub Actions, ArgoCD, Flux), platform engineering patterns, SRE practices, chaos engineering, progressive delivery, developer experience, and Internal Developer Platforms (IDP)
license: MIT
compatibility: opencode
metadata:
  audience: devops-engineers
  domain: devops
  paradigm: delivery-engineering
  integrates_with: [infra-kubernetes, infra-terraform, infra-observability, security-audit, workflow-general, database-postgres]
---

## DevOps Platform Engineering Skill

### CI/CD Architecture
- **GitHub Actions**: Composite actions for reusability; matrix builds; concurrency groups; OIDC for cloud auth; environments for approval gates
- **ArgoCD**: ApplicationSets for multi-cluster; sync waves for ordering; progressive sync; health checks (custom)
- **Flux**: Kustomize + Helm controllers; image automation (ImagePolicy, ImageRepository); notifications (Slack, Teams)

### Pipeline Design
```
Code → Build → Test → Security Scan → Artifact → Deploy Staging → Integration Test → Deploy Prod → Monitor
  │       │       │          │            │            │                  │               │            │
  └───────┴───────┴──────────┴────────────┴────────────┴──────────────────┴───────────────┴────────────┘
                                   Fast Feedback (< 5 min)                     Progressive Delivery
```

### Platform Engineering Patterns
- **Internal Developer Platform (IDP)**: Golden paths; self-service; Backstage for service catalog
- **Paved roads**: Pre-configured templates (cookiecutter, degit, Backstage templates); CI/CD pre-wired
- **Platform as Product**: Treat platform like a product; SLAs, roadmap, user research with dev teams
- **Golden signals**: Latency, traffic, errors, saturation — measure platform health

### Progressive Delivery
- **Canary**: Shift N% traffic to new version; validate metrics; increase or rollback
- **Blue-Green**: Two identical environments; switch all traffic at once; instant rollback
- **Feature Flags**: Decouple deploy from release; OpenFeature standard; targeting rules
- **Argo Rollouts**: Canary with metric analysis (Prometheus, Datadog, NewRelic); automatic promotion/abort

### SRE Practices
- **Error budgets**: SLO-based decision making; freeze features when budget exhausted
- **Toil reduction**: Automate repetitive operational work; target <50% toil
- **Blameless postmortems**: What happened, impact, timeline, root causes, action items
- **Runbook automation**: Script responses to known incidents; reduce MTTR

### Chaos Engineering
- **Steady state**: Define normal behavior via metrics before experiment
- **Hypothesis**: "Service X should handle Y failure without Z degradation"
- **Experiments**: CPU stress, memory fill, network latency/loss, pod kill, AZ failure
- **Tools**: Chaos Mesh (K8s native), LitmusChaos, Gremlin (managed), AWS Fault Injection Simulator
- **Blast radius**: Minimal initially; expand if system proves resilient

### Developer Experience (DevEx)
- **Pre-commit hooks**: lint-staged + husky; run lint + format + typecheck before commit
- **Local dev**: docker-compose or Tilt for local dependencies; telepresence for K8s development
- **Preview environments**: Per-PR ephemeral environments; Terraform/Pulumi + GitHub Actions
- **On-call**: Clear escalation paths; runbooks; shadow rotations for new on-call engineers

### Observability for Platform
- **DORA metrics**: Deployment frequency, lead time, MTTR, change failure rate
- **SPACE framework**: Satisfaction, Performance, Activity, Communication, Efficiency
- **Developer survey**: Quarterly; NPS, pain points, tool satisfaction

### Common Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| TicketOps (ticket-driven platform) | Platform team becomes gatekeeper; developers wait days for infrastructure | Build self-service catalog; golden path templates; Backstage developer portal |
| Over-engineering the IDP | Platform becomes more complex than the problems it solves | Start with paved roads (templates + CI pre-wired); add features based on developer feedback |
| Ignoring developer experience (DevEx) | Platform is powerful but painful to use; developers work around it | Quarterly DevEx survey; SPACE framework metrics; shadowing sessions |
| No platform SLOs | Platform reliability is unknown; developers lose trust | Define SLOs: time-to-create-service < 5min, CI pipeline duration < 10min, platform availability 99.9% |
| One-size-fits-all pipelines | Forces all teams into same workflow; some teams rebel and bypass CI | Golden paths as defaults, not mandates; teams can customize within guardrails |
| Manual environment provisioning | "Can you spin up a staging env for me?" — platform team bottleneck | Preview environments per PR; self-service via Terraform/Pulumi modules |
| No cost visibility | Teams provision resources without understanding cost; AWS bill shock | Tag all resources; show cost per team/service in Backstage; set budgets |
| CI/CD as afterthought | Pipeline added after code is written; flaky tests ignored | Pre-wired CI in template; test framework ready; flaky test quarantine policy |

### Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---|---|---|---|
| ArgoCD `OutOfSync` loop | Manual kubectl change; auto-sync disabled; resource conflict | Check `argocd app diff`; review sync policy | Enable auto-sync with prune; never manually edit synced resources |
| GitHub Actions `runner not found` | Self-hosted runner offline; GitHub-hosted runner pool exhausted | Check runner status in repo settings; check GitHub status page | Add more runners; use larger runner class; check runner scaling policy |
| Pipeline flaky tests | Unstable test environment; race conditions; time-dependent tests | Identify flaky tests by rerun history; quarantine suspect tests | Add retry with backoff; use deterministic test data; fix race conditions |
| ArgoCD sync stuck `Progressing` | Pod in CrashLoopBackOff; health check undefined | `kubectl describe` the stuck resource; check health assessment | Fix root cause of pod failure; add custom health check if using CRD |
| Image pull failures in CI | Registry auth expired; image tag doesn't exist; pull rate limit | Check registry credentials; verify image tag exists | Use ECR/Artifact Registry login action; pin to digests |
| Preview environment not cleaned up | Lifecycle hook not triggered; TTL not set | List stale preview environments; check cleanup cron | Add TTL annotation; auto-destroy on PR close/merge |
| Platform API rate limiting | Too many requests to cloud provider from CI/CD | Check provider API rate limits; batch resource operations | Use Terraform plan caching; reduce CI frequency for non-code changes |

### Implementation Checklist

- [ ] Internal Developer Platform strategy documented (paved roads vs golden paths vs self-service)
- [ ] Service catalog implemented (Backstage or equivalent)
- [ ] Golden path templates available (cookiecutter, degit, Backstage templates)
- [ ] CI/CD pipeline pre-configured in all templates (lint → test → build → scan → deploy)
- [ ] GitOps configured (ArgoCD or Flux) for all deployments
- [ ] Preview environments per PR with auto-cleanup on merge/close
- [ ] Platform SLOs defined and monitored
- [ ] Developer survey conducted quarterly (NPS, pain points, tool satisfaction)
- [ ] DORA metrics tracked: deployment frequency, lead time, MTTR, change failure rate
- [ ] Secret management integrated (Vault, SOPS, External Secrets) — no plain secrets in Git
- [ ] Progressive delivery configured: canary or blue-green for production deployments
- [ ] Chaos engineering experiments planned (start small, expand)
- [ ] Cost dashboards per team/service with budget alerts
- [ ] On-call rotation and escalation paths defined for platform team
- [ ] Runbooks for common platform operations (adding new service, debugging CI failure, etc.)
- [ ] Platform change log and communication channel for developer teams
