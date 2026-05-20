---
name: infra-terraform
description: >
  God-Tier Terraform + Terragrunt mastery: architecture, HCL deep dive, provider patterns,
  state management, module design, Terragrunt DRY, CI/CD integration, testing, security,
  performance optimization, DR, migration patterns, decision trees, and troubleshooting.
license: MIT
compatibility: opencode
metadata:
  audience: devops-engineers
  domain: infrastructure
  paradigm: declarative
  integrates_with:
    - infra-kubernetes
    - devops-platform-engineering
    - security-audit
    - security-crypto
    - backend-go
    - infra-observability
  terraform_version: ">= 1.8"
  terragrunt_version: ">= 0.60"
---

# Terraform + Terragrunt Mastery — God-Tier Skill

> *"Infrastructure as Code is not about automating clicks. It's about declaring intent — then letting the machine converge."*

---

## 1. Terraform Architecture & Core Concepts

### 1.1 IaC Philosophy
Declarative: you declare *desired state*, Terraform computes diff against *actual state* and produces a plan.

```
┌───────────────────────────────────────────────────────┐
│              TERRAFORM EXECUTION FLOW                   │
├───────────────────────────────────────────────────────┤
│  ┌─────────┐ ┌──────────┐ ┌───────────┐              │
│  │  *.tf   │ │  State   │ │ Provider  │              │
│  │ (HCL)   │ │ .tfstate │ │  Plugin   │              │
│  └────┬────┘ └────┬─────┘ └─────┬─────┘              │
│       ▼           ▼              ▼                     │
│  ┌───────────────────────────────────────┐            │
│  │         Terraform Core                │            │
│  │  ┌──────────┐ ┌──────────┐           │            │
│  │  │  Graph   │→│  Plan    │           │            │
│  │  │ Builder  │ │  Engine  │           │            │
│  │  └──────────┘ └──────────┘           │            │
│  └───────────────────────────────────────┘            │
│  init → validate → plan → apply → destroy              │
└───────────────────────────────────────────────────────┘
```

### 1.2 Core Concepts & Phases

| Concept | Description | Phase | Action |
|---------|-------------|-------|--------|
| **Resource** | `resource "aws_vpc" "main" {}` | `init` | Downloads provider plugins & modules |
| **Data Source** | `data "aws_ami" "ubuntu" {}` | `validate` | Checks syntax & references |
| **Provider** | Plugin managing resource lifecycle | `plan` | Refreshes state, computes diff → plan file |
| **State** | `terraform.tfstate` (mapping config→real) | `apply` | Executes plan in dependency order |
| **Module** | Reusable resource container | `destroy` | Tears down in reverse dependency order |
| **Plan** | Execution diff (create/update/destroy) | | |

---

## 2. HCL Language Deep Dive

### 2.1 Resource Blocks & Loops

```hcl
resource "aws_s3_bucket" "data" {
  bucket = "company-data-${var.environment}"
  tags   = var.default_tags
}

# count — numeric index (fragile: removing shifts indices)
resource "aws_iam_user" "devs" {
  count = length(var.developer_names)
  name  = var.developer_names[count.index]
}

# for_each — map/set key (stable: removing doesn't affect others)
resource "aws_iam_user" "devs_map" {
  for_each = toset(var.developer_names)
  name     = each.key
}
```

### 2.2 Data Sources

```hcl
data "aws_vpc" "selected" {
  tags = { Environment = var.environment, ManagedBy = "terraform" }
}
data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.selected.id]
  }
}
```

### 2.3 Variables, Outputs, Locals

```hcl
# variables.tf
variable "environment" {
  description = "Deploy environment"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Must be dev/staging/prod."
  }
}
variable "tags" { type = map(string), default = {} }

# outputs.tf
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}
output "db_password" {
  value     = random_password.db.result
  sensitive = true   # Never shown in CLI
}

# locals.tf — computed once
locals {
  name_prefix = "${var.project}-${var.environment}"
  common_tags = merge(var.tags, {
    Environment = var.environment
    ManagedBy   = "terraform"
  })
}
```

### 2.4 Expressions & Functions

```hcl
# for expression — transforms lists/maps
locals {
  key_ids  = [for k in aws_kms_key.main : k.key_id]                    # list→list
  prod_only = { for k, v in var.resources : k => v if var.environment == "prod" }  # filtered map
}

# Conditionals
locals {
  instance_type = var.environment == "prod" ? "t3.large" : "t3.micro"
  enable_nat    = var.environment != "dev"
}

# String / encoding functions
locals {
  bucket_name   = format("%s-%s-logs", var.project, var.environment)
  template      = templatefile("${path.module}/user_data.sh", { env = var.environment })
  policy_json   = jsonencode(var.iam_policy)
  user_data_b64 = base64encode(file("${path.module}/bootstrap.sh"))
  config_hash   = sha256(jsonencode(var.config))
}
```

### 2.5 Dynamic Blocks

```hcl
resource "aws_security_group" "main" {
  name   = "${local.name_prefix}-sg"
  vpc_id = aws_vpc.main.id

  dynamic "ingress" {
    for_each = var.ingress_rules
    content {
      description = ingress.value.description
      from_port   = ingress.value.from_port
      to_port     = ingress.value.to_port
      protocol    = ingress.value.protocol
      cidr_blocks = ingress.value.cidr_blocks
    }
  }
}
```

### 2.6 Lifecycle Blocks

```hcl
resource "aws_instance" "web" {
  lifecycle { create_before_destroy = true }    # Zero-downtime replacement
}
resource "aws_db_instance" "critical" {
  lifecycle { prevent_destroy = true }          # Safety net
}
resource "aws_autoscaling_group" "app" {
  lifecycle { ignore_changes = [desired_capacity] }  # Externally managed
}
```

---

## 3. Provider Patterns

### 3.1 Basic & Multi-Region

```hcl
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.80" }
  }
  required_version = ">= 1.8"
}

# Multi-region with aliases
provider "aws" { region = "us-east-1", alias = "virginia" }
provider "aws" { region = "eu-west-1", alias = "ireland" }

resource "aws_s3_bucket" "replicated" {
  provider = aws.virginia
  bucket   = "my-global-bucket"
}
```

### 3.2 Cross-Account Assume Role

```hcl
provider "aws" {
  alias  = "production"
  region = var.region
  assume_role {
    role_arn     = "arn:aws:iam::${var.prod_account_id}:role/TerraformExecRole"
    session_name = "terraform-cross-account"
    external_id  = var.external_id
    duration     = "2h"
  }
}
resource "aws_vpc" "prod" {
  provider    = aws.production
  cidr_block  = "10.1.0.0/16"
}
```

### 3.3 Provider Version Pinning

| Constraint | Meaning | Risk |
|-----------|---------|------|
| `~> 5.80` | `>= 5.80, < 5.90` | ✅ Recommended — safe minor upgrades |
| `~> 5.0` | `>= 5.0, < 6.0` | ⚠️ Any minor — risky |
| `>= 5.80` | Any version ≥ 5.80 | 🔴 Very risky — may break |
| `= 5.80.0` | Exact version | ✅ Safest, blocks patch updates |

---

## 4. State Management

### 4.1 Remote Backend Decision Tree

```
Which cloud provider?
├── AWS ──────► S3 + DynamoDB ──► Most mature, battle-tested
│   └─ Bucket: versioning+encryption; Table: consistency+TTL
├── GCP ──────► GCS ──► Built-in object versioning + lock
├── Azure ────► AzureRM ──► Blob + lease locking
├── Multi ────► Terraform Cloud ──► Native locked state + RBAC
└── Air-gap ──► PostgreSQL ──► Self-hosted via pgclient
```

### 4.2 S3 + DynamoDB Backend

```hcl
terraform {
  backend "s3" {
    bucket         = "company-terraform-state"
    key            = "infra/vpc/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-locks"
  }
}
# Partial config per env: terraform init -backend-config=backend-prod.hcl
```

### 4.3 State Operations

```bash
terraform state list                                    # List all resources
terraform state show aws_instance.web[0]                # Show single resource
terraform state mv 'module.v1.aws_s3_bucket.data' 'module.v2.aws_s3_bucket.data'
terraform state rm aws_instance.legacy                  # Remove from state (not destroy)
terraform import aws_s3_bucket.data my-existing-bucket   # Import existing resource
terraform state pull > backup.tfstate                   # Download remote state
terraform force-unlock <LOCK_ID>                        # Only if process is truly dead
```

### 4.4 Workspace Strategy

```bash
# Workspaces: USE only for temporary/PR environments
# DO NOT use for permanent environments (dev/staging/prod)
terraform workspace new pr-123
terraform workspace select pr-123

# Why NOT for permanent envs:
# 1. Human error: apply dev changes to prod
# 2. CI complexity: workspace switching is error-prone
# 3. State isolation is weaker — same backend

# BETTER: directory-per-environment with separate state keys
# envs/dev/ → key = "env/dev/vpc/terraform.tfstate"
# envs/prod/ → key = "env/prod/vpc/terraform.tfstate"
```

---

## 5. Module Design (Deep)

### 5.1 Standard Structure

```
modules/vpc/
├── main.tf        # Resources
├── variables.tf   # Inputs with descriptions + types
├── outputs.tf     # Exports with descriptions
├── versions.tf    # Provider + TF version constraints
├── locals.tf      # Computed values
├── data.tf        # Data sources
└── README.md      # Auto-generated via terraform-docs
```

### 5.2 Complete Module Example

```hcl
# ─── versions.tf ───
terraform {
  required_version = ">= 1.8"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.80" }
  }
}

# ─── variables.tf ─── (key inputs)
variable "name"         { type = string }
variable "cidr_block"   { type = string }
variable "public_subnets"  { type = list(string), default = [] }
variable "private_subnets" { type = list(string), default = [] }
variable "tags" { type = map(string), default = {} }

# ─── main.tf ───
resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_hostnames = true
  tags = merge(var.tags, { Name = "${var.name}-vpc" })
}
resource "aws_subnet" "public" {
  count = length(var.public_subnets)
  vpc_id     = aws_vpc.this.id
  cidr_block = var.public_subnets[count.index]
  tags = merge(var.tags, { Name = "${var.name}-public-${count.index + 1}" })
}
resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
}

# ─── outputs.tf ───
output "vpc_id"            { value = aws_vpc.this.id }
output "public_subnet_ids" { value = aws_subnet.public[*].id }
```

### 5.3 Module Sources & Composition

```hcl
# Local
module "vpc" { source = "../../modules/vpc", name = var.name, ... }
# Git with tag (NEVER branch refs)
module "vpc" { source = "git::https://github.com/company/modules.git//vpc?ref=v1.2.0" }
# Registry
module "vpc" { source = "terraform-aws-modules/vpc/aws", version = "~> 5.0" }

# Composition
module "network"  { source = "../../modules/vpc", ... }
module "database" {
  source     = "../../modules/rds"
  vpc_id     = module.network.vpc_id
  subnet_ids = module.network.private_subnet_ids
}
```

### 5.4 Module Testing (Terratest)

```go
package test
import (
  "testing"
  "github.com/gruntwork-io/terratest/modules/terraform"
  "github.com/stretchr/testify/assert"
)
func TestVPCModule(t *testing.T) {
  opts := &terraform.Options{
    TerraformDir: "../examples/simple",
    Vars: map[string]interface{}{
      "name": "test-vpc", "cidr_block": "10.0.0.0/16",
      "public_subnets": []string{"10.0.1.0/24", "10.0.2.0/24"},
    },
  }
  defer terraform.Destroy(t, opts)
  terraform.InitAndApply(t, opts)
  vpcId := terraform.Output(t, opts, "vpc_id")
  assert.NotEmpty(t, vpcId)
}
```

---

## 6. Terragrunt Deep Dive

### 6.1 Why Terragrunt?
1. **DRY**: No repeated backend/provider config across modules
2. **Dependencies**: Explicit module ordering (`dependency` blocks)
3. **Orchestration**: `run-all` for multi-module apply

### 6.2 Directory Structure

```
infrastructure/
├── terragrunt.hcl           # Root: inherit by all modules
├── account.hcl              # Account-level shared config
├── env/prod/terragrunt.hcl  # Env-level config
│   ├── vpc/terragrunt.hcl   # Module instance
│   ├── rds/terragrunt.hcl
│   └── ecs/terragrunt.hcl
```

### 6.3 Complete terragrunt.hcl

```hcl
# ─── Root terragrunt.hcl (inherited by all) ───
locals {
  env       = reverse(split("/", get_terragrunt_dir()))[2]
  region    = reverse(split("/", get_terragrunt_dir()))[1]
  module    = reverse(split("/", get_terragrunt_dir()))[0]
}

# Auto-generate provider — no more provider blocks in modules!
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region = "${local.region}"
  assume_role {
    role_arn = "arn:aws:iam::${local.account_id}:role/TerraformExecRole"
  }
  default_tags { tags = { Environment = "${local.env}", ManagedBy = "terragrunt" } }
}
EOF
}

# Auto-generate remote state — S3+DynamoDB
generate "backend" {
  path      = "backend.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
terraform {
  backend "s3" {
    bucket = "company-terraform-state"
    key    = "${local.env}/${local.region}/${local.module}/terraform.tfstate"
    region = "us-east-1"; encrypt = true
    dynamodb_table = "terraform-state-locks"
  }
}
EOF
}

# ─── Module instance (env/prod/vpc/terragrunt.hcl) ───
terraform {
  source = "git::https://github.com/company/modules.git//vpc?ref=v2.1.0"
}
include "root" { path = find_in_parent_folders() }
dependency "network" {
  config_path = "../network-base"
  mock_outputs = { vpc_id = "vpc-mock" }
}
inputs = {
  vpc_cidr = "10.0.0.0/16"
  enable_nat = true
}
```

### 6.4 Terragrunt CLI & Hooks

```bash
terragrunt plan                         # Plan single module (auto-init)
terragrunt run-all plan                 # Plan all modules
terragrunt run-all apply                # Apply in dependency order
terragrunt run-all destroy              # Destroy in reverse order
terragrunt hclfmt                       # Format terragrunt.hcl files
terragrunt graph-dependencies           # Show dependency graph
```

```hcl
terraform {
  before_hook "tflint" {
    commands = ["apply", "plan"]
    execute  = ["tflint", "--format", "compact"]
  }
  error_hook "cleanup" {
    commands  = ["apply"]
    execute   = ["echo", "Apply failed"]
    on_errors = [".*"]
  }
}
```

---

## 7. Environment Strategy

```
How many permanent environments?
├── 2-3 (dev/staging/prod) ──► Directory per env
│   Clear state separation, no human error
├── 20+ PR previews ─────────► Workspaces
│   Dynamic creation/destruction
├── Mixed ──────────────────► Directory for perms + Workspaces for temp
└── 50+ multitenant ────────► Terraform Cloud Workspaces
    UI management + RBAC + API
```

### Recommended Structure

```
infrastructure/
├── global/                   # IAM, DNS, cross-env
├── envs/
│   ├── dev/   → backend key: "env/dev/"
│   ├── staging/ → backend key: "env/staging/"
│   └── prod/  → backend key: "env/prod/"
└── modules/{vpc, rds, ecs}/
```

---

## 8. CI/CD Integration

### 8.1 GitHub Actions Workflow

```yaml
name: Terraform CI/CD
on:
  pull_request: { branches: [main], paths: ['infra/**'] }
  push: { branches: [main], paths: ['infra/**'] }
env:
  TF_VERSION: "1.9.5"; AWS_REGION: "us-east-1"
permissions: { id-token: write, contents: read, pull-requests: write }

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with: { terraform_version: "${{ env.TF_VERSION }}" }
      - run: terraform fmt -check -recursive
      - run: terraform init -backend=false && terraform validate

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: terraform-linters/setup-tflint@v4
      - run: tflint --format=compact
      - uses: bridgecrewio/checkov-action@v12
        with: { directory: infra/, framework: terraform, quiet: true }
      - uses: infracost/actions/setup@v3
      - run: infracost breakdown --path=infra/envs/dev --format=diff

  plan:
    needs: [validate, security]
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest; environment: dev
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with: { terraform_version: "${{ env.TF_VERSION }}" }
      - uses: aws-actions/configure-aws-credentials@v4
        with: { role-to-assume: "arn:aws:iam::${{ secrets.AWS_ACCOUNT }}:role/GHActionsTerraform", aws-region: "${{ env.AWS_REGION }}" }
      - run: terraform init -backend-config=backend-dev.hcl
      - run: terraform plan -no-color -out=tfplan-dev
      - uses: actions/upload-artifact@v4
        with: { name: "tfplan-dev-${{ github.sha }}", path: "tfplan-dev" }

  apply:
    needs: [plan]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest; environment: dev
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - uses: actions/download-artifact@v4
        with: { name: "tfplan-dev-${{ github.sha }}" }
      - run: terraform apply tfplan-dev

  apply-prod:
    needs: [plan]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: prod  # Requires manual approval
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - run: |
          terraform init -backend-config=backend-prod.hcl
          terraform plan -no-color -out=tfplan-prod
          terraform apply tfplan-prod
```

### 8.2 Atlantis Integration

```yaml
# atlantis.yaml
version: 3
projects:
  - name: dev-network
    dir: envs/dev
    terraform_version: v1.9.5
    autoplan: { when_modified: ["*.tf", "../../modules/**/*.tf"], enabled: true }
  - name: prod-network
    dir: envs/prod
    apply_requirements: [approved, mergeable]
```

---

## 9. Testing & Validation Pipeline

```bash
# 1. Format:           terraform fmt -check -recursive
# 2. Validate:         terraform validate
# 3. Lint:             tflint --format=compact
# 4. Security:         checkov -d . --framework terraform --quiet
# 5. Cost:             infracost breakdown --path . --format=json
# 6. Policy:           opa eval -d policy/ -i plan.json "data.terraform.deny"
```

### tflint Custom Rules (.tflint.hcl)

```hcl
plugin "aws" { enabled = true, version = "0.30.0", source = "github.com/terraform-linters/tflint-ruleset-aws" }
rule "aws_instance_invalid_type"           { enabled = true }
rule "terraform_required_providers"        { enabled = true }
rule "terraform_required_version"           { enabled = true }
rule "terraform_module_pinned_source"      { enabled = true, style = "flexible" }
rule "terraform_deprecated_interpolation"  { enabled = true }
```

---

## 10. Security & Compliance

### 10.1 Secrets Management Decision Tree

```
Where do you deploy?
├── AWS ──────► AWS Secrets Manager ──► data.aws_secretsmanager_secret
├── Multi-cloud ─► HashiCorp Vault ──► vault provider (dynamic secrets)
├── Git-based ───► SOPS ──► encrypt .tfvars, decrypt in CI
├── K8s ─────────► External Secrets Operator ──► syncs from Vault/AWS SM
└── Small team ──► 1Password CLI ──► eval $(op signin) before apply
```

### 10.2 Secure Secrets Pattern

```hcl
# ❌ NEVER: variable "password" { default = "P@ssw0rd!" }
# ✅ Correct: use secret manager
data "aws_secretsmanager_secret_version" "db" {
  secret_id = "/${var.environment}/database/master"
}
locals {
  db_creds = jsondecode(data.aws_secretsmanager_secret_version.db.secret_string)
}
resource "aws_db_instance" "main" {
  username = local.db_creds["username"]
  password = local.db_creds["password"]  # Auto-marked sensitive
}

# SOPS encryption
# $ sops --encrypt prod.tfvars > prod.enc.tfvars
# $ sops exec-env 'terraform apply -var-file=prod.enc.tfvars'
```

### 10.3 Security Best Practices

```hcl
# ❌ Bad: 0.0.0.0/0 SSH
resource "aws_security_group" "bad" {
  ingress { from_port = 22, to_port = 22, protocol = "tcp", cidr_blocks = ["0.0.0.0/0"] }
}
# ✅ Good: limited bastion SG
resource "aws_security_group" "good" {
  ingress { from_port = 22, to_port = 22, protocol = "tcp", security_groups = [aws_security_group.bastion.id] }
}

# Mandatory: S3 bucket encryption + block public access
resource "aws_s3_bucket_server_side_encryption_configuration" "s" {
  bucket = aws_s3_bucket.data.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "aws:kms" } }
}
resource "aws_s3_bucket_public_access_block" "s" {
  bucket = aws_s3_bucket.data.id
  block_public_acls = true; block_public_policy = true
  ignore_public_acls = true; restrict_public_buckets = true
}
```

---

## 11. Performance Optimization

```bash
# Parallelism — increase from default 10
terraform plan -parallelism=30
terraform apply -parallelism=30

# Skip refresh (if state is trusted accurate)
terraform plan -refresh=false         # Much faster, no API calls

# Targeted plans
terraform plan -target=module.vpc
terraform apply -target=aws_security_group.x

# Provider caching (reuse across projects)
export TF_PLUGIN_CACHE_DIR="$HOME/.terraform.d/plugin-cache"

# State file size management
# >100MB state files slow operations — split into modules
# Each module has its own state file
```

```bash
# Benchmark plan time
Measure-Command { terraform plan -no-color }

# Parallelism scaling test
for ($i=10; $i -le 50; $i+=10) {
  $s = Get-Date; terraform plan -parallelism=$i -no-color -out /dev/null
  Write-Host "parallelism=$i : $(((Get-Date)-$s).TotalSeconds)s"
}
```

---

## 12. Disaster Recovery

### 12.1 State Backup & Restore

```bash
# S3 versioning = first line of defense
aws s3api list-object-versions --bucket company-terraform-state --prefix env/prod/network/tfstate

# Restore from version
aws s3api get-object --bucket company-tf-state --key env/prod/vpc/terraform.tfstate \
  --version-id "GOOD_VERSION" restored.tfstate
terraform state push restored.tfstate

# Full recovery procedure:
# 1. Identify disaster (corrupted state / accidental delete)
# 2. List S3 versions → find last GOOD version
# 3. Download good version
# 4. Verify: terraform state list -state=restored.tfstate
# 5. Force unlock if stuck: terraform force-unlock <LOCK_ID>
# 6. Push: terraform state push restored.tfstate
# 7. Verify: terraform plan → should show "No changes"
```

### 12.2 Emergency Procedures

```bash
# Force unlock — ONLY if process is truly dead
terraform force-unlock <LOCK_ID>

# Remove corrupted resource from state
terraform state rm aws_instance.dead

# Import orphaned resource
terraform import aws_instance.orphaned i-1234567890abcdef0

# Refresh-only (sync state with cloud)
terraform plan -refresh-only && terraform apply -refresh-only

# Save plan files for audit
terraform plan -out=tfplan-$(date +%Y%m%d-%H%M%S)
aws s3 cp tfplan-*.tfplan s3://company-terraform-plans/$(date +%Y/%m/%d)/
```

---

## 13. Migration Patterns

### 13.1 Terraform Version Migration

```hcl
# v0.12 style:   provider "aws" { version = "2.70" }
# v1.x style:    required_providers block
terraform {
  required_version = ">= 1.8"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.80" }
  }
}
```

### 13.2 State Refactoring with `moved` (v1.8+)

```hcl
# Before: inline resource
resource "aws_s3_bucket" "data" { bucket = "company-data-${var.environment}" }
# After: moved to module
module "bucket" { source = "../../modules/s3-bucket", name = "company-data-${var.environment}" }
moved { from = aws_s3_bucket.data, to = module.bucket.aws_s3_bucket.this }

# Rename resource
moved { from = aws_instance.web, to = aws_instance.app_server }
```

### 13.3 Importing & Backend Migration

```bash
# Import existing resources
# 1. Write resource block  2. terraform import <type.name> <id>  3. terraform plan

# terraform add (v1.5+): auto-generates resource block
terraform add aws_s3_bucket existing --bucket=company-existing-bucket

# Move between backends (e.g., S3 → Terraform Cloud)
terraform init -migrate-state       # Detects change, prompts to copy
terraform init -migrate-state -force-copy  # Non-interactive for CI

# ALWAYS backup before migration
terraform state pull > pre-migration-backup.tfstate
```

### 13.4 Monolithic → Modular Migration

```bash
# 1. Create module structure: mkdir -p modules/{vpc,rds}
# 2. Move resource groups into respective modules
# 3. Define module interfaces (variables.tf, outputs.tf)
# 4. Update root to use modules: module "vpc" { source = "../../modules/vpc" }
# 5. Use moved blocks: moved { from = aws_vpc.main, to = module.vpc.aws_vpc.this }
# 6. terraform plan → should show "No changes"
# 7. terraform apply → updates state references, zero resource changes
```

---

## 14. Decision Trees

### 14.1 Module Strategy

```
"When to create a module vs inline?"
├── Used in 2+ places?  ──► MODULE
├── >50 lines with complex logic? ──► MODULE (readability)
├── Logical domain boundary? ──► MODULE per domain
└── Single simple resource? ──► INLINE (KISS)
```

### 14.2 State Strategy

```
"Terragrunt vs TFC vs directory?"
├── Solo/small, 2-3 envs ──► Directory structure (simplest)
├── Small team, >5 modules ──► Terragrunt (DRY + orchestration)
├── Enterprise, >5 engineers ──► Terraform Cloud (RBAC + Sentinel)
└── Hybrid ──► Terragrunt for DRY + TFC for remote ops
```

### 14.3 Loop Strategy

```
"count vs for_each vs for expression?"
├── Creating resources? ──► Need stable IDs?
│   ├── YES ──► for_each (set/map key — removing doesn't shift)
│   └── NO ───► count (sequential — fragile, list changes shift indices)
├── Transforming data? ──► for expression (comprehension)
│   └─ [for v in list : upper(v)] | {for k, v in map : k => v if v != null}
└── Neither? ──► No loop needed
```

### 14.4 Provider Strategy

```
"Single vs multiple aliases vs multiple providers?"
├── Single region/account ──► Single provider block
├── Multiple regions ──► Provider aliases (one per region)
├── Multiple accounts ──► Assume_role aliases (one per account)
└── Multi-cloud (AWS+GCP) ──► Multiple provider types
```

---

## 15. Anti-Patterns

| # | Anti-Pattern | Why | Fix |
|---|-------------|-----|-----|
| 1 | **Monolith root module** (2000+ line main.tf) | Hard to read/test; slow plan | Split into `modules/{vpc,rds,compute}/` |
| 2 | **Manual apply on production** | No audit trail; no peer review | CI/CD: plan on PR, apply on merge |
| 3 | **State in git** | Secrets exposed in history | `*.tfstate*` in `.gitignore`; remote state |
| 4 | **Hardcoded secrets** | Leaked in git/logs | Use secret manager (Vault/AWS SM/SOPS) |
| 5 | **No state locking** | Concurrent applies corrupt state | S3+DynamoDB / GCS / AzureRM locking |
| 6 | **One state for all envs** | Dev breaks prod; state too large | Separate state key per environment |
| 7 | **Workspaces for permanent envs** | Easy to apply dev→prod by mistake | Directory-per-environment instead |
| 8 | **Too many outputs** | Slows plan; increases blast radius | Output only what consumers need |
| 9 | **Complex variable validation** | Unhelpful errors; too long | `condition` + clear `error_message` |
| 10 | **`terraform fmt` not enforced** | Inconsistent formatting | `terraform fmt -check -recursive` in CI |
| 11 | **Using `latest` provider** | Unplanned upgrades break infra | Pin `~> 5.80`; upgrade intentionally |
| 12 | **Not committing `.terraform.lock.hcl`** | Different provider versions per dev | **Always commit** lock file |
| 13 | **No drift detection** | Manual changes go unnoticed | Scheduled `terraform plan -refresh-only` |
| 14 | **Manual state editing** | Corrupt state | `terraform import` / `moved` blocks |
| 15 | **`count` for mutable lists** | Remove shifts indices, recreates resources | Use `for_each` with unique keys |
| 16 | **No `prevent_destroy` on critical** | Accidental destroy of RDS/S3 data | `lifecycle { prevent_destroy = true }` |
| 17 | **Large parallelism untested** | Rate limiting, API throttling | Start default 10, tune upward gradually |
| 18 | **No `terraform validate` in CI** | Syntax errors caught late | `init -backend=false && validate` |
| 19 | **Sharing state between projects** | Unintended deps; lock conflicts | One state per module/project |
| 20 | **Overusing `depends_on`** | Masks real dep graph issues | Let TF infer from references |

---

## 16. Troubleshooting

| # | Symptom | Cause | Diagnose | Fix |
|---|---------|-------|----------|-----|
| 1 | `Failed to lock state` | Stale lock; crashed process | `aws dynamodb get-item --table-name locks --key '...'` | `terraform force-unlock <LOCK_ID>` |
| 2 | Provider config error | Credentials expired; wrong region | `aws sts get-caller-identity` | Re-authenticate; check region/roles |
| 3 | `for_each` sensitive error | Sensitive value as key | Plan shows `(sensitive)` | Derive keys from non-sensitive values |
| 4 | `Cycle` dependency error | Circular resource reference | `TF_LOG=DEBUG plan 2>&1 \| grep cycle` | Break with `depends_on` or restructure |
| 5 | Slow plan (>30s) | Large state; slow data sources | `TF_LOG=INFO plan \| grep -E "refresh"` | `-parallelism=30`; `-refresh=false` |
| 6 | Provider rate limiting (429) | Too many API calls | Provider errors: `ThrottlingException` | `max_retries=5` in provider; lower parallelism |
| 7 | `Invalid index` with count | List shifted, resources recreated | Plan shows unexpected recreation | Migrate to `for_each` |
| 8 | `Inconsistent result` | Eventually consistent API | Resource in cloud but not state | `terraform import`; add `time_sleep` |
| 9 | Workspace drift | Manual changes via console | `terraform plan -refresh-only` shows diffs | `terraform apply -refresh-only`; adopt GitOps |
| 10 | Init required | `.terraform/` deleted/corrupted | Plan fails with init error | `terraform init -reconfigure` |
| 11 | Missing changes but resources gone | Deleted outside TF | `state list` shows; cloud has nothing | `state rm` → `import` |
| 12 | State lock in CI | Parallel CI jobs same state | Check CI concurrency settings | Add concurrency groups; separate branch states |
| 13 | `Invalid legacy provider address` | Migrated from old TF | Provider format changed in 0.13 | `state replace-provider hashicorp/aws registry.terraform.io/hashicorp/aws` |
| 14 | `Missing required provider` | No `required_providers` block | `terraform providers` shows missing | Add `required_providers` with source+version |
| 15 | `Resource not applied` | Apply failed mid-way | Resources in "planned" state | `terraform apply -refresh-only` |
| 16 | `Unsupported attribute` | Wrong attribute for provider version | Check provider docs | Update attribute name for schema |
| 17 | Tainted resource | Created but post-check failed | `terraform show` shows `tainted` | `terraform apply -replace=<resource>` |
| 18 | `templatefile` not found | Path issue | `templatefile("./script.sh", {})` | Use `path.module`: `templatefile("${path.module}/x", {})` |
| 19 | DynamoDB AccessDenied | Missing IAM permissions | `aws dynamodb describe-table` | Add `dynamodb:GetItem/PutItem/DeleteItem` |
| 20 | `Error acquiring state lock` in CI | Concurrent runs | Check CI pipeline triggers | Add concurrency: `concurrency: group: ${{ matrix.env }}${{ github.ref }}` |

---

## 17. Implementation Checklist

- [ ] **State**: Remote backend (S3+DynamoDB/GCS/AzureRM/TFC) with locking
- [ ] **State**: Encryption at rest (SSE-KMS/CMEK/CMK) + S3 versioning
- [ ] **State**: `.gitignore` includes `*.tfstate*`, `.terraform/`, `*.tfvars` (keep `.example`)
- [ ] **State**: `.terraform.lock.hcl` committed to version control
- [ ] **Provider**: Versions pinned `~> 5.80` (minor), `required_providers` with `source`
- [ ] **Provider**: Aliases for multi-region, assume_role for multi-account
- [ ] **Provider**: Caching enabled (`TF_PLUGIN_CACHE_DIR`)
- [ ] **Quality**: `terraform fmt -check -recursive` in CI
- [ ] **Quality**: `terraform validate` on every PR
- [ ] **Quality**: `tflint` custom rules in CI
- [ ] **Quality**: Checkov/Trivy/tfsec security scanning
- [ ] **Quality**: `infracost` cost estimation on every plan
- [ ] **Quality**: All variables have `description` + `type`, all outputs have `description`
- [ ] **Quality**: `sensitive = true` on secrets; `validation` blocks on critical inputs
- [ ] **Modules**: Single-responsibility; standard structure; version-pinned sources
- [ ] **Modules**: Terratest or kitchen-terraform for integration tests
- [ ] **CI/CD**: Plan posted as PR comment; apply only on merge (plan reuse)
- [ ] **CI/CD**: Multi-env pipeline (dev→staging→prod with manual gates)
- [ ] **Security**: Secrets via Vault/AWS SM/GCP SM/SOPS (never plain text)
- [ ] **Security**: State bucket publicly blocked; no `0.0.0.0/0` SSH/RDP/DB ports
- [ ] **Security**: SGs resource-specific; S3 buckets encrypted + public access blocked
- [ ] **Security**: IAM least-privilege for Terraform execution role
- [ ] **Security**: Tagging strategy enforced via policy or defaults
- [ ] **Operations**: `prevent_destroy` on critical (RDS/S3/KMS); `create_before_destroy` on services
- [ ] **Operations**: `ignore_changes` for externally managed attributes
- [ ] **Operations**: Break-glass IAM roles documented
- [ ] **Operations**: DR runbook (state restore from S3 versioning)
- [ ] **Operations**: Drift detection (scheduled `plan -refresh-only` or GitOps tool)
- [ ] **Operations**: Plan files archived for audit; force-unlock procedure documented
- [ ] **Terragrunt** (if used): `generate` blocks for provider+backend; `dependency` blocks; `run-all` orchestration
- [ ] **Testing**: tflint + checkov + infracost (minimum); Terratest (ideal)

---

## 18. Quick Reference

### 18.1 Terraform Commands

| Command | Use | Key Flags |
|---------|-----|-----------|
| `init` | Init working dir | `-backend-config=`, `-reconfigure`, `-migrate-state` |
| `plan` | Show changes | `-out=tfplan`, `-var-file=`, `-target=`, `-refresh=false`, `-parallelism=N` |
| `apply` | Apply changes | `tfplan`, `-auto-approve`, `-replace=`, `-parallelism=N` |
| `destroy` | Tear down | `-target=`, `-auto-approve` |
| `validate` | Check config | (none) |
| `fmt` | Format HCL | `-check`, `-recursive`, `-diff` |
| `state list` | List resources | (none) |
| `state mv` | Move in state | `<from> <to>` |
| `state rm` | Remove from state | `<address>` |
| `import` | Import existing | `<type.name> <id>` |
| `output` | Read outputs | `-json`, `-raw` |
| `force-unlock` | Release lock | `<LOCK_ID>` (⚠️) |

### 18.2 HCL Syntax Reference

| Construct | Example | Use |
|-----------|---------|-----|
| `resource` | `resource "aws_vpc" "m" {}` | Create/manage infra |
| `data` | `data "aws_ami" "u" {}` | Query existing infra |
| `variable` | `variable "n" { type = string }` | Input parameter |
| `output` | `output "id" { value = aws_vpc.m.id }` | Export value |
| `locals` | `locals { n = "${var.e}-vpc" }` | Computed value |
| `module` | `module "v" { source = "./v" }` | Reusable group |
| `terraform` | `terraform { backend "s3" {} }` | Settings block |
| `provider` | `provider "aws" { region = "x" }` | Provider config |
| `moved` | `moved { from = ..., to = ... }` | State refactor |
| `lifecycle` | `lifecycle { create_before_destroy = true }` | Resource rules |
| `dynamic` | `dynamic "ingress" { for_each = ... }` | Nested blocks |
| `for_each` | `for_each = toset(var.names)` | Per-item (stable) |
| `count` | `count = length(var.x)` | N-times (fragile) |

### 18.3 Terragrunt Commands

| Command | Use |
|---------|-----|
| `terragrunt plan` | Plan (auto-init) |
| `terragrunt apply` | Apply (auto-init) |
| `terragrunt destroy` | Destroy |
| `terragrunt run-all plan/apply/destroy` | All modules in order |
| `terragrunt hclfmt` | Format .hcl files |
| `terragrunt graph-dependencies` | Show dependency graph |
| `terragrunt output` | Show outputs |

### 18.4 Environment Variables

| Variable | Purpose |
|----------|---------|
| `TF_VAR_<name>` | Set variable from env |
| `TF_LOG` | TRACE/DEBUG/INFO/WARN/ERROR |
| `TF_IN_AUTOMATION` | Suppress prompts |
| `TF_PLUGIN_CACHE_DIR` | Provider cache path |
| `TF_WORKSPACE` | Select workspace |
| `TF_CLI_ARGS` | Default CLI args |

---

> **Final Word**: Terraform is declarative — declare *what*, not *how*. The graph engine handles ordering. State is your source of truth — protect it. Modules are abstraction boundaries — keep them focused. Never apply to production without a plan review.

> *"Terraform doesn't manage servers. It manages declarations of intent — and converges reality to match."*
