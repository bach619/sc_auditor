---
name: infra-kubernetes
description: Kubernetes advanced: Operator pattern (Custom Resources, controllers, reconcilers), eBPF (Cilium, Hubble), WASM runtime, scheduling, security (OPA, Kyverno), and GitOps (ArgoCD, Flux)
license: MIT
compatibility: opencode
metadata:
  audience: devops-engineers
  domain: infrastructure
  paradigm: orchestration
  integrates_with: [infra-observability, infra-terraform, systems-ebpf, security-audit, devops-platform-engineering, backend-go]
---

## Infrastructure Kubernetes Skill

### Operator Pattern
- **CRD + Controller**: Custom Resource Definition defines schema; Controller reconciles desired vs actual
- **Reconciler loop**: Observe → Analyze → Act; always idempotent; handle finalizers for cleanup
- **Status subresource**: Separate spec (desired) from status (actual); update status independently
- **Operator SDK**: kubebuilder (Go), Kopf (Python), Java Operator SDK
- **Idempotency**: Every reconciliation must produce same result regardless of starting state

### eBPF in Kubernetes
- **Cilium**: eBPF-based CNI; identity-aware networking, L7 policies, Hubble for observability
- **Hubble**: Service map, flow logs, metrics (HTTP/gRPC/Kafka/DNS latency, drops)
- **Network policies**: DNS-aware, HTTP method/path filtering, FQDN-based policies
- **Bandwidth manager**: eBPF-based bandwidth management without sidecars

### Security
- **Pod Security Standards**: Enforce via Pod Security Admission (built-in v1.25+)
- **OPA/Gatekeeper**: Rego-based policy-as-code; mutation + validation + audit
- **Kyverno**: Kubernetes-native policies; generate, mutate, validate, verify images
- **Network policies**: Zero-trust: deny-all ingress, allow specific; CiliumNetworkPolicy for L7
- **Image security**: Cosign signature verification; SBOM attestation; private registry only
- **RBAC**: Least privilege; Role/RoleBinding (namespaced), ClusterRole/ClusterRoleBinding (cluster)

### Scheduling
- **Taints/Tolerations**: Repel pods from nodes; toleration allows scheduling
- **Node affinity**: requiredDuringScheduling (hard), preferredDuringScheduling (soft)
- **Pod affinity/anti-affinity**: Co-locate or spread pods; topologyKey for zone/host
- **Topology spread constraints**: maxSkew across zones; whenUnsatisfiable: DoNotSchedule
- **Priority classes**: Preempt lower priority pods; system-node-critical > system-cluster-critical

### GitOps (ArgoCD / Flux)
- **ArgoCD**: Application CRD; auto-sync or manual; health assessment; diff view
- **Flux**: Source controller (GitRepository, HelmRepository, Bucket); Kustomize controller
- **Progressive delivery**: Argo Rollouts (canary, blue-green with metric analysis)
- **Sealed Secrets / SOPS**: Encrypt secrets for Git storage

### WASM on Kubernetes
- **Krustlet**: Node that runs WASM modules instead of containers
- **containerd-wasm-shim**: Run WASM via containerd; no container overhead
- **WASI**: WebAssembly System Interface for sandboxed execution
- **Use cases**: Edge computing, plugin systems, FaaS

### Observability
- **Metrics**: Prometheus + kube-state-metrics + node-exporter
- **Logs**: Loki or Elasticsearch; structured JSON logging
- **Traces**: Jaeger or Tempo; OpenTelemetry auto-instrumentation
- **Dashboards**: Grafana with pre-built Kubernetes dashboards

### Common Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| No resource limits/requests | Best-effort pods starved or evicted unpredictably | Set requests=limits for predictable workloads; use LimitRange and ResourceQuota |
| Using `:latest` tags | Unknown which image version runs; no rollback capability | Always pin to digest or semantic version tag |
| Over-permissioned RBAC | Compromised pod gets cluster-admin access | Least privilege: per-namespace Roles, avoid wildcard verbs/resources |
| No Pod Disruption Budget | Node drains cause full outage | Define PDB with minAvailable or maxUnavailable |
| Ignoring PodSecurity standards | Privileged containers increase attack surface | Enforce baseline/restricted via PodSecurity Admission |
| `default` namespace for production | Mixed workloads, no isolation | Always use dedicated namespaces; never deploy in default |
| No liveliness/readiness probes | Unhealthy pods keep receiving traffic | Configure both probes with appropriate thresholds and periods |
| Single-node persistence without PV | Data lost on pod restart | Use StatefulSets with PersistentVolumeClaims |
| Manually editing resources via kubectl | Git drift, untracked changes, broken audit | GitOps only; ArgoCD auto-sync with prune |

### Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---|---|---|---|
| `CrashLoopBackOff` | Application panics on startup; missing configmap/secret | `kubectl describe pod` + `kubectl logs --previous` | Fix app startup; ensure configs mounted |
| `ImagePullBackOff` | Wrong image name/tag; registry auth failure; rate limited | `kubectl describe pod` for events; `kubectl get secrets` | Correct image ref; add imagePullSecrets |
| `Pending` pod | Insufficient resources; PVC not bound; nodeSelector mismatch | `kubectl describe pod` for scheduler events | Add nodes; create PV; fix nodeSelector/affinity |
| `OOMKilled` | Container exceeded memory limit | `kubectl describe pod` for exit code 137 | Increase memory limit or fix memory leak |
| `Readiness probe failed` | App not ready in time; probe endpoint broken | Check `initialDelaySeconds` and probe path | Increase delay; fix probe handler |
| RBAC `403 Forbidden` | ServiceAccount missing permissions | `kubectl auth can-i --as=system:serviceaccount:ns:sa <verb> <resource>` | Add appropriate Role/RoleBinding |
| Service not routing | Selector labels mismatch; wrong port | `kubectl get endpoints` — should list pod IPs | Fix selector in Service to match pod labels |
| CNI not working | Network plugin not installed or misconfigured | `kubectl get pods -n kube-system` for CNI pods | Install/reconfigure Cilium/Calico/Flannel |
| `Terminating` stuck | Finalizer not completing; kubelet unreachable | `kubectl get pod -o json` for finalizers | Remove finalizer; force delete `--grace-period=0 --force` |

### Implementation Checklist

- [ ] All namespaces defined with resource quotas and limit ranges
- [ ] All pods have resource requests and limits set
- [ ] All images pinned to digests or specific tags (no `:latest`)
- [ ] RBAC configured with least-privilege principle
- [ ] NetworkPolicies in place (deny-all + specific allows)
- [ ] PodSecurity standards enforced (baseline minimum, restricted where possible)
- [ ] Liveliness and readiness probes configured on all deployments
- [ ] PodDisruptionBudgets defined for all workloads requiring HA
- [ ] PersistentVolumes and StatefulSets used for stateful workloads
- [ ] GitOps configured (ArgoCD/Flux) — no manual kubectl applies
- [ ] OPA/Kyverno policies for compliance enforcement
- [ ] Secrets managed via External Secrets Operator / Vault (not plain ConfigMap)
- [ ] Cluster autoscaling configured (Karpenter / Cluster Autoscaler)
- [ ] Log aggregation and monitoring dashboards operational
- [ ] Backup strategy documented and tested (Velero for PV + etcd)
- [ ] Upgrade strategy tested on staging cluster first
