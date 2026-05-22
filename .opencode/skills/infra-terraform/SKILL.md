---
name: infra-terraform
description: Terraform + Terragrunt: module design, state management, provider patterns, HCL best practices, remote state, workspaces, and CI/CD integration
license: MIT
compatibility: opencode
metadata:
  audience: devops-engineers
  domain: infrastructure
  paradigm: declarative
  integrates_with: [infra-kubernetes, devops-platform-engineering, security-audit, security-crypto, backend-go]
---

## Infrastructure Terraform Skill

### Module Design
- **Single responsibility**: One resource type or tightly-coupled group per module
- **Interface contracts**: variables.tf (inputs), outputs.tf (exports), versions.tf (constraints)
- **Version pinning**: source = "git::https://...?ref=v1.2.0"; never use branch refs
- **Composition over inheritance**: Compose small modules; avoid deep nesting
- **Default values**: Sensible defaults for all variables; use nullable when optional

### State Management
- **Remote state always**: S3 + DynamoDB lock (AWS), GCS (GCP), Azure Storage + lease (Azure)
- **State isolation**: Separate state per environment (dev/staging/prod)
- **Workspaces**: Use for temporary environments (PR previews); NOT for permanent environments
- **State migration**: terraform state mv for refactoring; terraform import for existing resources
- **State locking**: Prevent concurrent modifications; DynamoDB for AWS, built-in for Terraform Cloud

### HCL Best Practices
- **Dynamic blocks**: Use for repeatable nested blocks; cleaner than count on resources
- **for_each over count**: for_each with map/set preserves identity; count is order-dependent
- **locals**: Compute complex expressions once; use for naming conventions
- **Data sources**: Prefer lookup by tags over hardcoded IDs
- **lifecycle blocks**: create_before_destroy for zero-downtime; prevent_destroy for critical resources; ignore_changes for externally managed attributes

### Terragrunt
- **DRY configurations**: Include blocks for shared config; dependency blocks for ordering
- **Remote state auto-config**: generate remote_state block per module
- **Hooks**: before_hook/after_hook for pre/post actions; error_hook for cleanup
- **Run-all**: terragrunt run-all apply for multi-module orchestration

### Provider Patterns
- **Multiple providers**: aliases for multi-region, multi-account
- **Assume role**: AWS cross-account via provider assume_role block
- **Provider version**: Pin to MINOR version (~> 5.0, not ~> 5)

### CI/CD Integration
- **Plan**: terraform plan -out=tfplan on PR; post as comment
- **Apply**: terraform apply tfplan on merge (reuse plan file)
- **Lint**: terraform fmt -check -recursive; tflint for rule-based checks
- **Security**: tfsec or checkov for policy-as-code
- **Cost**: infracost for cost estimation on plan

### Anti-Patterns
- Monolithic root module (decompose)
- Manual state manipulation (use import/mv CLI)
- Hardcoded values (use variables with defaults)
- .terraform.lock.hcl not committed

### Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---|---|---|---|
| `Failed to lock state` | Another process holds the lock; crashed process left stale lock | Check DynamoDB/lease table for lock entry; verify no concurrent plans | Wait for lock release; use `terraform force-unlock <lock_id>` |
| `Error: error configuring provider` | Provider credentials expired; wrong region; missing env vars | Verify `AWS_PROFILE`, `GOOGLE_CREDENTIALS`, AZURE env vars | Re-authenticate; check provider block config |
| State file corruption | Interrupted apply; manual S3 modification; parallel writes | `terraform state list` returns error; JSON parsing fails | Restore from S3 versioning; use `terraform state pull > backup.tfstate` |
| `for_each` sensitive value error | Using value derived from sensitive output as `for_each` key | Plan shows `(sensitive value)` in for_each | Use non-sensitive derived values; mark less outputs as sensitive |
| `Cycle` dependency error | Circular reference between resources | Plan output shows dependency cycle | Break cycle with explicit `depends_on` or restructure resources |
| Slow `terraform plan` | Large state file (>100K resources); many provider API calls | `TF_LOG=DEBUG terraform plan` shows slow API calls | Use `-target` for focused plans; increase `-parallelism`; use `refresh=false` |
| Provider rate limiting | Too many API calls to cloud provider | Provider errors show HTTP 429 or `ThrottlingException` | Reduce parallelism; add `max_retries` in provider config |
| `Invalid index` when using `count` | Resource removed from middle of list shifts all subsequent indices | Resource recreated because `count.index` changed | Use `for_each` with map instead of `count` wherever possible |
| `Error: Provider produced inconsistent result` | Resource not fully created when state was written; eventual consistency | Resource exists in cloud but not in state | `terraform import` the resource; add `time_sleep` in between dependencies |
| Workspace drift between environments | `terraform workspace` states diverged; manual changes applied | `terraform plan` shows unexpected differences | Run `terraform apply` regularly; use `drift detection` tools; adopt GitOps |

### Implementation Checklist

- [ ] Remote state configured (S3 + DynamoDB, GCS, or Terraform Cloud)
- [ ] State locking enabled and tested
- [ ] Provider versions pinned to MINOR (`~> 5.0`, NOT `~> 5`)
- [ ] `.terraform.lock.hcl` committed to version control
- [ ] Variables use sensible defaults with descriptions
- [ ] Sensitive variables marked `sensitive = true` (never in plain text)
- [ ] `for_each` used over `count` for resource repetition
- [ ] Modules follow single-responsibility principle with clear contracts
- [ ] `terraform fmt -check` enforced in CI
- [ ] `tflint` or `terraform validate` run on every PR
- [ ] `tfsec` / `checkov` / `trivy` security scanning in CI
- [ ] `infracost` cost estimation run on plan (with cost thresholds)
- [ ] `terraform plan` output posted as PR comment
- [ ] `terraform apply` only on merge to main (plan file reuse)
- [ ] Secrets managed via Vault/AWS Secrets Manager/SOPS (never plain env vars in CI)
- [ ] `.gitignore` includes `.terraform/`, `*.tfstate*`, `*.tfvars` (except `.example`)
- [ ] Separate state per environment (dev/staging/prod) — never shared state
- [ ] Break-glass IAM roles documented for emergency access
- [ ] Tagging strategy enforced via `terraform` policy or module defaults
- [ ] Resource lifecycle blocks (`prevent_destroy`, `create_before_destroy`) on critical resources
