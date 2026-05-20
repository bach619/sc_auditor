---
name: infra-kubernetes
description: Kubernetes mastery: architecture, workloads, networking, security, GitOps, operators, observability, scaling, storage, multi-tenancy, edge, troubleshooting, and Day-2 operations. Covers Operator pattern (CRD + controllers), eBPF (Cilium, Hubble), WASM runtime, scheduling, security (OPA, Kyverno, PSS), GitOps (ArgoCD, Flux, Crossplane), and production-hardened patterns.
license: MIT
compatibility: opencode
metadata:
  audience: devops-engineers
  domain: infrastructure
  paradigm: orchestration
  integrates_with: [infra-observability, infra-terraform, systems-ebpf, security-audit, devops-platform-engineering, backend-go]
  maturity: god-tier
---

# Kubernetes Mastery (God-Tier)

Production-hardened Kubernetes patterns with real YAML/Go/PromQL examples, decision trees, and actionable guidance.

---

## 1. Architecture & Core Concepts

```
Control Plane: apiserver → etcd ← scheduler/controller-manager
                    │
Worker Nodes:  kubelet + kube-proxy + containerd
```

**API Request Flow**: Client → Authn (TLS/OIDC) → Authz (RBAC) → Admission (Mutating+Validating webhooks) → etcd

| Component | Function | Key Detail |
|-----------|----------|------------|
| `kube-apiserver` | All API gateway; authn/authz/admission | Only component talking to etcd |
| `etcd` | Distributed KV + RAFT consensus | 3-5 nodes for HA; daily backup |
| `kube-scheduler` | Pod→node assignment | Pluggable; custom schedulers possible |
| `kube-controller-manager` | Self-healing controller loop | Deployments, ReplicaSets, etc. |
| `kubelet` | Node agent; manages pods | Primary node component |
| `kube-proxy` | Traffic routing (iptables/IPVS) | Node-level network rules |
| `container-runtime` | containerd / CRI-O | Docker deprecated since v1.24 |

**Operator Pattern**: CRD (spec) ←watch→ Controller (Go/Python) ←reconcile→ Actual State → status update

---

## 2. Workload Resources

### Decision Tree
```
Persistent storage/identity? → batch? → Job/CronJob
                               └── NO → StatefulSet
No persistence? → Runs on ALL nodes? → DaemonSet
                  └── HA rolling? → Deployment (95% cases)
```

### Deployment (stateless, zero-downtime)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
spec:
  replicas: 3
  revisionHistoryLimit: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0     # zero-downtime guarantee
  minReadySeconds: 10
  selector:
    matchLabels:
      app: api-server
  template:
    metadata:
      labels:
        app: api-server
    spec:
      terminationGracePeriodSeconds: 30
      containers:
      - name: api
        image: myregistry.io/api-server:v1.5.2
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: 250m
            memory: 512Mi
          limits:
            cpu: 500m
            memory: 1Gi
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 3
          periodSeconds: 5
        env:
        - name: DB_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
```

### StatefulSet (stable identity, persistent storage)
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
spec:
  serviceName: postgres     # headless service for DNS
  replicas: 3
  podManagementPolicy: OrderedReady
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:16-alpine
        ports: [{containerPort: 5432, name: db}]
        volumeMounts: [{name: data, mountPath: /var/lib/postgresql/data}]
        env:
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-pass
              key: password
  volumeClaimTemplates:
  - metadata: {name: data}
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: ssd
      resources:
        requests:
          storage: 100Gi
```

### DaemonSet & CronJob
```yaml
# Runs on every node (logging, monitoring, CNI)
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluentbit
  namespace: logging
spec:
  selector:
    matchLabels:
      name: fluentbit
  template:
    spec:
      tolerations: [{operator: Exists}]
      hostNetwork: true
      containers:
      - name: fluentbit
        image: fluent/fluent-bit:3.0
        volumeMounts: [{name: varlog, mountPath: /var/log}]
      volumes:
      - name: varlog
        hostPath: {path: /var/log}
---
# Scheduled batch job
apiVersion: batch/v1
kind: CronJob
metadata:
  name: db-backup
spec:
  schedule: "0 2 * * *"
  timeZone: "Asia/Jakarta"
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: backup
            image: myrepo/db-backup:2.1.0
```

---

## 3. Pod Design Patterns

```yaml
# Sidecar (shared volume)
spec:
  containers:
  - name: app
    image: myapp:1.0
    volumeMounts: [{name: shared-logs, mountPath: /var/log/app}]
  - name: log-shipper
    image: fluent/fluent-bit:3.0
    volumeMounts: [{name: shared-logs, mountPath: /var/log/app, readOnly: true}]
  volumes:
  - name: shared-logs
    emptyDir: {}

# Init Container (blocking setup)
  initContainers:
  - name: init-db
    image: alpine:3.20
    command: ['sh', '-c', 'until nc -z -w5 db-host 5432; do sleep 2; done']

# Lifecycle + Security Context
  containers:
  - name: app
    image: myapp:1.0
    lifecycle:
      preStop:
        httpGet: {path: /drain, port: 8080}
    securityContext:
      runAsNonRoot: true
      runAsUser: 1001
      capabilities: {drop: ["ALL"]}
      allowPrivilegeEscalation: false
      seccompProfile: {type: RuntimeDefault}
```

**QoS Classes**: Requests==Limits → Guaranteed | Requests<Limits → Burstable | None → BestEffort

**Topology Spread**:
```yaml
spec:
  topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: DoNotSchedule
```

---

## 4. Service Networking

### Decision Tree
```
External access? → NO → ClusterIP
                   └── YES → HTTP/gRPC → Ingress or Gateway API
                             └── TCP/UDP → LoadBalancer
                             └── Fixed port → NodePort
                             └── External DNS → ExternalName
```

### Service Types
```yaml
# ClusterIP (default internal)
apiVersion: v1
kind: Service
metadata:
  name: api-svc
spec:
  ports: [{port: 80, targetPort: 8080, protocol: TCP}]
  selector:
    app: api-server

# LoadBalancer (AWS NLB)
apiVersion: v1
kind: Service
metadata:
  name: web-lb
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: nlb-ip
spec:
  type: LoadBalancer
  ports: [{port: 443, targetPort: 8443}]
  selector:
    app: web
```

### Ingress
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
  - hosts: [api.myapp.com]
    secretName: api-tls
  rules:
  - host: api.myapp.com
    http:
      paths:
      - path: /v1
        pathType: Prefix
        backend:
          service: {name: api-svc, port: {number: 80}}
```

### NetworkPolicy (zero-trust)
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-api
spec:
  podSelector:
    matchLabels:
      app: api-server
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: ingress-nginx
    ports: [{port: 8080}]
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: database
    ports: [{port: 5432}]
```

### Cilium L7 Policy
```yaml
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: http-methods
spec:
  endpointSelector:
    matchLabels:
      app: api-server
  ingress:
  - toPorts:
    - ports: [{port: "8080", protocol: TCP}]
      rules:
        http:
        - method: "GET"
          path: "/api/v1/users"
```

---

## 5. Configuration & Secrets

```yaml
# ConfigMap (immutable)
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
immutable: true
data:
  LOG_LEVEL: info
  config.yaml: |
    server:
      port: 8080
      timeout: 30s

# Secret
apiVersion: v1
kind: Secret
metadata:
  name: app-secret
type: Opaque
stringData:
  DB_URL: postgres://user:pass@host:5432/db

# External Secrets Operator
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: aws-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secretsmanager
    kind: ClusterSecretStore
  target:
    name: db-credentials
  data:
  - secretKey: username
    remoteRef:
      key: /production/postgres/credentials
      property: username

# Downward API (pod metadata injection)
spec:
  containers:
  - name: app
    env:
    - name: POD_NAME
      valueFrom:
        fieldRef: {fieldPath: metadata.name}
    - name: NODE_NAME
      valueFrom:
        fieldRef: {fieldPath: spec.nodeName}
    - name: POD_IP
      valueFrom:
        fieldRef: {fieldPath: status.podIP}
```

---

## 6. Storage

### Decision Tree
```
Pod-level temp? → emptyDir (disk or tmpfs)
Persistent? → PV/PVC with StorageClass
  RWO → Block (EBS, PersistentDisk)
  RWX → Shared (EFS, NFS, Azure Files)
  ROX → Read-only shared
  RWOP → Read-write once pod (CSI v1.22+)
```

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ssd
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-pvc
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: ssd
  resources:
    requests:
      storage: 50Gi
---
# VolumeSnapshot (CSI)
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: db-snapshot
spec:
  volumeSnapshotClassName: csi-ebs-snapshot
  source:
    persistentVolumeClaimName: data-pvc
```

---

## 7. Security (Deep)

### RBAC (least privilege)
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-sa
  namespace: production
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: api-role
  namespace: production
rules:
- apiGroups: [""]
  resources: ["pods", "services", "configmaps"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["pods/log"]
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: api-binding
  namespace: production
subjects:
- kind: ServiceAccount
  name: api-sa
  namespace: production
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: api-role
```

### Pod Security Standards
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted
```

### Kyverno (policy-as-code)
```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: restrict-image-registry
spec:
  validationFailureAction: Enforce
  rules:
  - name: allowed-registries
    match:
      any:
      - resources:
          kinds: [Pod]
    validate:
      message: "Images must be from myregistry.io"
      pattern:
        spec:
          containers:
          - image: "myregistry.io/*"
```

### OPA/Gatekeeper (Rego)
```rego
# ConstraintTemplate enforces required labels on Deployments
violation[{"msg": msg}] {
  input.request.kind.kind == "Deployment"
  provided := {label | input.request.object.metadata.labels[label]}
  required := {label | label := input.parameters.labels[_]}
  missing := required - provided
  count(missing) > 0
  msg := sprintf("Missing labels: %v", [missing])
}
```

### Pod Identity (IRSA on EKS)
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: s3-sa
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/s3-access
# Usage: spec.serviceAccountName: s3-sa
```

---

## 8. GitOps (Deep)

### Decision Tree: ArgoCD vs Flux
```
GUI/multi-cluster/SSO? → ArgoCD (Web UI, Projects, SSO)
CLI-first/K8s-native? → Flux (GitOpsToolkit, simpler model)
Progressive delivery? → ArgoCD + Argo Rollouts (canary/metrics)
Multi-team tenants? → ArgoCD Projects with RBAC
```

### ArgoCD Application
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: production-api
  namespace: argocd
spec:
  destination:
    namespace: production
    server: https://kubernetes.default.svc
  project: default
  source:
    repoURL: https://github.com/myorg/k8s-manifests.git
    targetRevision: main
    path: apps/api/overlays/production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
    - ServerSideApply=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

### Argo Rollouts (canary with metrics)
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: api-rollout
spec:
  replicas: 5
  selector:
    matchLabels:
      app: api
  template:
    metadata: {labels: {app: api}}
    spec:
      containers:
      - name: api
        image: myregistry.io/api:v2.0.0
        ports: [{containerPort: 8080}]
  strategy:
    canary:
      maxSurge: 2
      maxUnavailable: 0
      steps:
      - setWeight: 20
      - pause: {duration: 5m}
      - setWeight: 60
      - pause: {duration: 5m}
      - analysis:
          templates: [{templateName: success-rate}]
      - setWeight: 100
---
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate
spec:
  metrics:
  - name: success-rate
    interval: 60s
    successCondition: "result[0] >= 0.95"
    failureLimit: 3
    provider:
      prometheus:
        address: http://prometheus:9090
        query: |
          sum(rate(http_requests_total{status=~"2.."}[5m]))
          / sum(rate(http_requests_total[5m])) * 100
```

### Flux Kustomization
```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-system
  namespace: flux-system
spec:
  interval: 1m
  url: https://github.com/myorg/k8s-manifests.git
  ref: {branch: main}
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: production-api
  namespace: flux-system
spec:
  interval: 5m
  path: ./apps/api/overlays/production
  prune: true
  sourceRef:
    kind: GitRepository
    name: flux-system
  healthChecks:
  - apiVersion: apps/v1
    kind: Deployment
    name: api-server
    namespace: production
```

---

## 9. Observability

### PrometheusRule (alerting)
```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: k8s-alerts
  namespace: monitoring
spec:
  groups:
  - name: kubernetes-apps
    interval: 30s
    rules:
    - alert: HighCPUUsage
      expr: |
        sum(rate(container_cpu_usage_seconds_total[5m])) by(pod)
        / sum(kube_pod_container_resource_limits{resource="cpu"}) by(pod) > 0.8
      for: 5m
      labels: {severity: warning}
    - alert: PodCrashLooping
      expr: kube_pod_status_phase{phase="CrashLoopBackOff"} > 0
      for: 1m
      labels: {severity: critical}
    - alert: PVUsageHigh
      expr: (kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes) > 0.85
      for: 5m
```

| Layer | Stack |
|-------|-------|
| Metrics | Prometheus + kube-state-metrics + node-exporter → Alertmanager + Grafana |
| Logs | Vector/FluentBit (DaemonSet) → Loki/Elasticsearch |
| Traces | OpenTelemetry Collector → Tempo/Jaeger |
| Cost | Kubecost — namespace allocation & right-sizing |

---

## 10. Scaling & Scheduling

### HPA (Horizontal)
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  minReplicas: 3
  maxReplicas: 20
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies: [{type: Percent, value: 10, periodSeconds: 60}]
    scaleUp:
      stabilizationWindowSeconds: 60
      policies: [{type: Percent, value: 100, periodSeconds: 60}]
  metrics:
  - type: Resource
    resource:
      name: cpu
      target: {type: Utilization, averageUtilization: 70}
  - type: Pods
    pods:
      metric: {name: requests_per_second}
      target: {type: AverageValue, averageValue: 1000}
```

### VPA (Vertical)
```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: api-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  updatePolicy:
    updateMode: Auto   # Off, Initial, Auto, Recreate
  resourcePolicy:
    containerPolicies:
    - containerName: '*'
      minAllowed: {cpu: 100m, memory: 256Mi}
      maxAllowed: {cpu: 4, memory: 8Gi}
      controlledResources: ["cpu", "memory"]
```

### PDB & PriorityClass
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: api-server
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: high-priority
value: 1000000
preemptionPolicy: PreemptLowerPriority
```

---

## 11. Operator Pattern

### CRD with Validation
```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: databases.myorg.io
spec:
  group: myorg.io
  names: {plural: databases, singular: database, kind: Database, shortNames: [db]}
  scope: Namespaced
  versions:
  - name: v1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
        required: ["spec"]
        properties:
          spec:
            type: object
            required: ["engine", "version", "storage"]
            properties:
              engine: {type: string, enum: ["postgres", "mysql", "redis"]}
              version: {type: string, pattern: "^\\d+\\.\\d+$"}
              storage: {type: integer, minimum: 10, maximum: 10000, default: 100}
              replicas: {type: integer, minimum: 1, maximum: 10, default: 3}
          status:
            type: object
            properties:
              phase: {type: string, enum: ["Creating","Ready","Upgrading","Failed"]}
              conditions:
                type: array
                items:
                  type: object
                  properties:
                    type: {type: string}
                    status: {type: string, enum: ["True","False","Unknown"]}
    subresources: {status: {}}
    additionalPrinterColumns:
    - {name: Engine, type: string, jsonPath: .spec.engine}
    - {name: Status, type: string, jsonPath: .status.phase}
```

### Go Reconciler (kubebuilder)
```go
type DatabaseReconciler struct { client.Client }

func (r *DatabaseReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	var db myorgv1.Database
	r.Get(ctx, req.NamespacedName, &db)

	// Finalizer: add on create, cleanup on delete
	if db.DeletionTimestamp.IsZero() {
		addFinalizer(&db, "db.myorg.io/finalizer")
		r.Update(ctx, &db)
	} else {
		removeFinalizer(&db, "db.myorg.io/finalizer")
		r.Update(ctx, &db)
		return ctrl.Result{}, nil
	}
	// Reconcile: ensure child StatefulSet matches spec
	sts := buildStatefulSet(&db)
	apply(ctx, r.Client, sts)

	db.Status.Phase = "Ready"
	r.Status().Update(ctx, &db)
	return ctrl.Result{RequeueAfter: 30 * time.Second}, nil
}
// +kubebuilder:rbac:groups=myorg.io,resources=databases,verbs=get;list;watch;create;update;patch;delete
```

---

## 12. Day 2 Operations

### Cluster Upgrade
```
1. Check release notes & deprecated APIs  2. Update clients
3. Test backup restore on staging        4. Upgrade staging → test
5. Drain nodes (respect PDBs)            6. Upgrade control plane
7. Replace node groups                   8. Verify DNS/CNI/ingress/monitoring
9. e2e conformance tests                10. Verify all ArgoCD apps sync
```

### Velero Backup
```yaml
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: daily-backup
  namespace: velero
spec:
  schedule: "0 1 * * *"
  template:
    includedNamespaces: [production, staging]
    excludedResources: [pods, events]
    ttl: 720h  # 30 days
    defaultVolumesToFsBackup: true
```

### cert-manager & Audit Policy
```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    email: devops@myorg.com
    server: https://acme-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt-key
    solvers:
    - dns01:
        route53: {region: ap-southeast-1}
---
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
- level: Metadata
  resources: [{group: "", resources: ["secrets", "configmaps"]}]
- level: RequestResponse
  verbs: ["create", "update", "patch", "delete"]
  resources: [{group: "", resources: ["pods", "deployments", "statefulsets"]}]
```

---

## 13. Namespaces & Multi-tenancy

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-quota
  namespace: team-a
spec:
  hard:
    requests.cpu: "8"
    requests.memory: 32Gi
    limits.cpu: "16"
    limits.memory: 64Gi
    persistentvolumeclaims: 10
    pods: "40"
    count/deployments.apps: 20
---
apiVersion: v1
kind: LimitRange
metadata:
  name: container-limits
  namespace: team-a
spec:
  limits:
  - max: {cpu: "4", memory: 8Gi}
    min: {cpu: 50m, memory: 64Mi}
    default: {cpu: 500m, memory: 512Mi}
    defaultRequest: {cpu: 100m, memory: 256Mi}
    type: Container
```

---

## 14. Edge/IoT & Specialized

### Decision Tree
```
Full upstream? → Managed (EKS/GKE/AKS)
  ├── AWS → EKS (IRSA, Karpenter)
  ├── GCP → GKE (Autopilot)
  └── Azure → AKS
Resource-constrained?
  ├── <1GB RAM / ARM → K3s (single binary)
  ├── On-prem HA → K0s
  └── Dev/laptop → MicroK8s (snap)
WASM workloads? → Krustlet / containerd-wasm-shim
Edge computing? → KubeEdge (CloudCore ↔ EdgeCore)
```

```yaml
# K3s/WASM — same YAML as standard K8s
apiVersion: apps/v1
kind: Deployment
metadata:
  name: edge-app
spec:
  replicas: 2
  selector: {matchLabels: {app: edge}}
  template:
    metadata: {labels: {app: edge}}
    spec:
      containers:
      - name: app
        image: myregistry.io/edge:1.0
        resources:
          requests: {cpu: 50m, memory: 64Mi}
```

---

## 15. Anti-Patterns

| Anti-Pattern | Why | Fix |
|---|---|---|
| `:latest` image tag | No rollback; unknown version | Pin to `v1.5.2` or digest |
| No requests/limits | BestEffort QoS, evicted | Set requests=limits; LimitRange |
| Over-permissioned RBAC | Compromised SA = cluster admin | `verbs: ["get","list"]` not `["*"]` |
| Prod in `default` ns | No isolation/quota | Dedicated namespace |
| No probes | Unhealthy pods serve traffic | liveness + readiness probes |
| No PDB | Node drain kills all | `minAvailable: 2` |
| Single replica stateful | No HA, manual recovery | `replicas: 3` + PDB + anti-affinity |
| Manual `kubectl edit` | Git drift, no audit | GitOps (ArgoCD/Flux) |
| Config in image | Rebuild per env | ConfigMap + External Secrets |
| No NetworkPolicy | Any pod can reach any pod | Deny-all default + allow rules |
| Privileged containers | Container escape | `runAsNonRoot: true` |
| No pod anti-affinity | All pods on one node = SPOF | TopologySpreadConstraints |
| Secrets in env vars | Leaked in logs/debug | Mount as volumes |
| Ignoring PSS | Privileged escalation | Enforce `restricted` in prod |
| Mixing workloads in one pool | Critical vs batch compete | Node pools per class + taints |
| No backup strategy | Cluster failure = data loss | Velero daily + DR test quarterly |
| Too many etcd members | Write perf degrades | 3 or 5 members |
| Unauthenticated API | Anyone can modify resources | `--anonymous-auth=false` |
| No audit logging | Can't detect breaches | Audit policy + SIEM |
| Ignoring HPA/VPA | Over/under-provisioned | HPA stateless; VPA stateful |

---

## 16. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `CrashLoopBackOff` | App crash | `k logs --previous`; fix app code |
| `ImagePullBackOff` | Bad tag/auth | `k describe pod` events; fix tag, add imagePullSecrets |
| Pod `Pending` | No resources/PVC/taint | `k describe pod` scheduler events; scale nodes, fix PVC |
| `OOMKilled` (137) | Memory exceeded | Increase limit; VPA recommend |
| Readiness probe fail | Wrong path/app not ready | `k exec <p> -- curl :8080/healthz`; fix probe config |
| 403 Forbidden | Missing RBAC | `k auth can-i`; create Role+RoleBinding |
| Service no traffic | Label mismatch | `k get endpoints <svc>`; fix selector labels |
| `Terminating` stuck | Finalizer blocking | `k get pod -o json \| jq .finalizers`; remove finalizer |
| Node `NotReady` | kubelet offline/disk pressure | SSH; restart kubelet; `crictl rmi` clean images |
| HPA not scaling | No metrics-server | Install metrics-server |
| PVC `Pending` | SC missing/CSI not installed | Install CSI driver; check SC name |
| DNS fail | CoreDNS misconfig | `k rollout restart deploy/coredns -n kube-system` |
| Ingress down | Wrong class/TLS missing | `k describe ingress` events; fix class, create TLS secret |
| etcd leader election | Network partition/slow disk | Check disk latency <10ms; fix network |
| ConfigMap stale | Pods don't auto-reload | `k rollout restart deploy/<d>` |
| Disk pressure | Disk >85% | `crictl rmi` prune old images; increase node disk |
| CNI broken | Cilium/Calico not running | `k get pods -n kube-system \| grep -E "cilium\|calico"`; reinstall |
| `Init:Error` | Init container failed | `k logs <p> -c <init-container>` and fix |

---

## 17. Implementation Checklist

- [ ] Cluster provisioned | [ ] Namespace Quota+LimitRange | [ ] RBAC least privilege | [ ] PSS restricted | [ ] NetworkPolicies deny-all | [ ] resources requests+limits | [ ] pinned image tags | [ ] liveness+readiness probes | [ ] PDB HA workloads | [ ] TopologySpreadConstraints | [ ] StatefulSet for stateful | [ ] StorageClass Delete+Wait | [ ] GitOps (ArgoCD/Flux) | [ ] External Secrets | [ ] CSI driver | [ ] HPA stateless | [ ] VPA recs | [ ] Cluster Autoscaler/Karpenter | [ ] Prometheus+grafana | [ ] PrometheusRules alerts | [ ] centralized logging | [ ] OTel+traces | [ ] cert-manager | [ ] Velero backup 30d | [ ] etcd backup | [ ] audit policy+SIEM | [ ] Kyverno/OPA policies | [ ] Falco/Tetragon runtime | [ ] Kubecost | [ ] upgrade procedure tested | [ ] DR runbook quarterly | [ ] PriorityClasses | [ ] containerd runtime | [ ] node-problem-detector

---

## 18. Quick Reference

### kubectl Commands
`k get all -n <ns>` — list resources | `k describe pod <p>` — pod detail + events | `k logs -f <p>` — stream logs | `k exec -it <p> -- sh` — shell | `k port-forward pod/<p> 8080:80` — forward port | `k rollout status deploy/<d>` — watch rollout | `k rollout undo deploy/<d>` — rollback | `k top pod -n <ns>` — CPU/memory | `k top node` — node usage | `k drain <n> --ignore-daemonsets` — drain | `k debug pod/<p> -it --image=busybox` — debug container | `k auth can-i --as=system:sa:ns:sa get pods` — check perms

### Resource Short Names
`po`=pods, `deploy`=deployments, `svc`=services, `sts`=statefulsets, `ds`=daemonsets, `cm`=configmaps, `pv`=persistentvolumes, `pvc`=persistentvolumeclaims, `sa`=serviceaccounts, `ing`=ingresses, `np`=networkpolicies, `hpa`=horizontalpodautoscalers, `pdb`=poddisruptionbudgets, `crd`=customresourcedefinitions, `secret`=secrets, `ev`=events

---

> **Integration**: This skill works with `infra-observability` (Grafana/Prometheus), `infra-terraform` (cluster provisioning), `systems-ebpf` (Cilium/eBPF), `security-audit` (K8s audit), `devops-platform-engineering` (CI/CD pipelines), and `backend-go` (Go operators).
