---
name: infra-observability
description: Observability (OpenTelemetry, Grafana Stack, Honeycomb): distributed tracing, metrics, structured logging, SLO/SLI definitions, error budgets, alerting, and dashboards
license: MIT
compatibility: opencode
metadata:
  audience: devops-engineers
  domain: infrastructure
  paradigm: observability-driven
  integrates_with: [infra-kubernetes, devops-platform-engineering, backend-python, backend-go, backend-elixir, database-postgres, frontend-react, frontend-svelte]
---

## Infrastructure Observability Skill

### The Three Pillars (Unified via OpenTelemetry)
- **Traces**: End-to-end request flow across services; spans with parent/child relationships
- **Metrics**: Numeric time-series: counters, gauges, histograms, summaries
- **Logs**: Structured events with trace_id linking; JSON format always

### OpenTelemetry
- **Auto-instrumentation**: Zero-code for most languages (Java, Python, Node, .NET)
- **Manual instrumentation**: Spans for business logic; attributes for debugging context
- **Context propagation**: W3C TraceContext (traceparent/tracestate); B3 fallback
- **Collector**: Receivers → Processors → Exporters pipeline; tail sampling, batching, filtering
- **Exporters**: OTLP (standard), Jaeger, Zipkin, Prometheus

### SLO-Based Approach
- **SLI (Service Level Indicator)**: Measurable metric (e.g., p99 latency, error rate, uptime)
- **SLO (Service Level Objective)**: Target for SLI (e.g., 99.9% availability, p99 < 200ms)
- **SLA (Service Level Agreement)**: Contract with consequences (e.g., 99.5% or credit)
- **Error budget**: 1 - SLO (e.g., 0.1% = 43m/month allowed downtime)
- **Burn rate**: How fast error budget is consumed; alert when >1% consumed in 1 hour
- **Multi-window alerting**: Short window (high burn rate → page) + Long window (slow burn → ticket)

### Alerting Strategy
- **Symptom-based**: Alert on user-visible symptoms, not causes
- **Alert severity**: Critical (page), Warning (ticket), Info (dashboard)
- **Runbook linked**: Every alert has a documented response procedure
- **Silence/Inhibit**: Prevent alert storms; one root cause → one notification
- **Deduplication**: Group related alerts; don't wake up the whole team

### Dashboard Design
- **Service dashboard**: RED metrics (Rate, Errors, Duration) + saturation
- **Resource dashboard**: USE method (Utilization, Saturation, Errors) per resource
- **Business dashboard**: High-level KPIs for non-technical stakeholders
- **Design rules**: Top-left = most important; minimize scrolling; use red/green sparingly

### Grafana Stack
- **Loki**: Log aggregation with label-based indexing; LogQL query language
- **Mimir**: Horizontal scalable Prometheus; long-term storage
- **Tempo**: Distributed tracing; TraceQL for search
- **Grafana**: Unified visualization; alerting; SLO dashboard

### Honeycomb (High-Cardinality)
- **BubbleUp**: Automatic anomaly detection across thousands of dimensions
- **SLO-based alerting**: Burn rate alerts on high-cardinality data
- **Honeycomb query**: GROUP BY any dimension; explore without pre-aggregation
- **Best for**: Debugging production issues faster than logs

### Common Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| Alert fatigue (too many alerts) | On-call team ignores all alerts; real incidents missed | Alert only on SLO burn rate; silence low-priority alerts |
| Wrong metric type | Using gauge where counter belongs (e.g., request count as gauge resets on restart) | counter for cumulative values; gauge for instantaneous |
| Cardinality explosion | Label values like user_id or session_id create millions of time series | Keep cardinality < 100K unique per metric; aggregate before ingestion |
| No structured logging | Freeform text logs unparseable; no correlation with traces | Always emit JSON logs with `trace_id` and `span_id` fields |
| All dashboards, no alerts | Beautiful dashboards but nobody paged for outages | Define SLOs; configure burn-rate alerts BEFORE dashboards |
| Over-instrumentation | Every line of code traced creates massive telemetry volume | Instrument only: entry/exit of services, DB queries, external calls, errors |
| Missing context propagation | Trace breaks at async boundaries (message queues, background jobs) | Inject trace context into message headers; always create parent span |
| Logging PII/secrets | Passwords, tokens, emails in logs reach log aggregation | Redact sensitive fields; use structured logging with field-level redaction |
| Manual sampling decisions | Inconsistent trace sampling across services | Use consistent probabilistic or tail-based sampling via OTel Collector |

### Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---|---|---|---|
| Missing spans/traces | Sampling rate too aggressive; context not propagated | Check sampler config; verify `traceparent` header in requests | Increase sample rate; fix context propagation |
| OTel Collector backpressure | Export queue full; backend slow or unreachable | Check collector metrics: `otelcol_exporter_queue_size` | Increase queue size; add batching; check backend |
| Prometheus not scraping targets | Network policy blocking; ServiceMonitor selector wrong; TLS mismatch | `kubectl port-forward prometheus-0 9090` → check Targets page | Fix NetworkPolicy; correct ServiceMonitor labels |
| High query latency in Grafana | Dashboard queries too broad; no recording rules | Check Prometheus query time; look at `prometheus_rule_evaluation_duration_seconds` | Use recording rules; lower dashboard time range |
| Disk full on Prometheus | Retention period too long; no compaction | Check `prometheus_tsdb_size_bytes` metric | Reduce retention; enable compaction; add Thanos/Mimir |
| No data in Tempo/Jaeger | Ingestor not receiving spans; wrong tenant ID | Check distributor logs; verify OTLP endpoint | Fix exporter config; ensure tenant header passed |
| Loki logs not found | Label mismatch; stream not coming through | Query `{job="myapp"} |= ""` to see if any logs arrive | Fix promtail/agent config; check label selectors |
| Alerts not firing | Rule evaluation interval too long; `for:` duration not met | Check rule group interval; manually execute PromQL | Reduce `for:`; fix PromQL expression |

### Implementation Checklist

- [ ] OpenTelemetry auto-instrumentation enabled for all services
- [ ] Manual spans added for critical business logic paths
- [ ] OTel Collector deployed (sidecar or daemonset) for centralized processing
- [ ] W3C TraceContext propagation configured across all services
- [ ] Structured JSON logging with `trace_id` and `span_id` on all apps
- [ ] Prometheus metrics exported for RED (Rate/Errors/Duration) per service
- [ ] USE metrics (Utilization/Saturation/Errors) for infrastructure
- [ ] SLOs defined for all critical user journeys (at minimum: availability + latency)
- [ ] Multi-window burn rate alerts configured (short: 14.4x/1h, long: 6x/6h)
- [ ] Runbooks linked from every alert (document the response procedure)
- [ ] Grafana dashboards: service dashboard (RED) + resource dashboard (USE) + business KPIs
- [ ] Tail sampling configured for high-throughput services (keep errors + slow + small % of normal)
- [ ] PII/secret redaction configured in OTel Collector processors
- [ ] Log retention and metric retention policies defined and enforced
- [ ] On-call rotation and escalation paths documented and tested
