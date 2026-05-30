# VYPER TUI v2 — Perencanaan Pembangunan Layer Panels 1–3

> **Dokumen ini adalah blueprint implementasi** untuk tiga panel pertama dari 6 Layer Panel
> di VYPER TUI v2. Setiap panel dibangun di atas fondasi EventBus (SSE), StateStore reaktif,
> dan framework **Textual** (Python TUI).

---

## Daftar Isi

1. [Fondasi Bersama (Shared Foundation)](#1-fondasi-bersama)
2. [Panel 1 — Data & Config Panel](#2-panel-1--data--config-panel)
3. [Panel 2 — Processing Panel](#3-panel-2--processing-panel)
4. [Panel 3 — Intelligence Panel](#4-panel-3--intelligence-panel)
5. [Urutan Implementasi & Milestone](#5-urutan-implementasi--milestone)
6. [Testing Strategy](#6-testing-strategy)

---

## 1. Fondasi Bersama

Ketiga panel ini mewarisi satu base class `LayerPanel` dan bergantung pada komponen
infrastruktur yang harus dibangun lebih dahulu.

### 1.1 Prasyarat (Harus Ada Sebelum Panel Dibangun)

| Komponen | File | Status |
|----------|------|--------|
| `EventBus` | `src/core/event_bus.py` | Prasyarat utama |
| `ActivityMonitorV2` | `src/monitors/activity_monitor.py` | Prasyarat utama |
| `VyperState` / `AppState` | `src/core/state_store.py` | Prasyarat utama |
| `PollingFallback` | `src/core/polling_fallback.py` | Backup jika SSE belum live |
| `ServiceActivity` dataclass | `src/models/activity.py` | Model data |

### 1.2 Base Class `LayerPanel`

```python
# src/panels/base_layer_panel.py

from textual.widget import Widget
from textual.reactive import reactive
from src.core.state_store import AppState, VyperState
from src.core.event_bus import EventBus, VyperEvent
from src.models.activity import ServiceActivity

class LayerPanel(Widget):
    """
    Base class untuk semua 6 Layer Panel.
    Menyediakan:
    - Koneksi ke EventBus (subscribe service.activity & service.health)
    - Akses ke AppState
    - Helper render status icon + warna
    - Drill-down shortcut (Enter → Service Detail Overlay)
    - Sparkline render helper
    """

    # Daftar service yang dikelola panel ini — override di subclass
    SERVICES: list[tuple[str, int]] = []  # [(name, port), ...]
    PANEL_TITLE: str = "Layer Panel"

    def on_mount(self):
        self.event_bus: EventBus = self.app.event_bus
        self._register_handlers()

    def _register_handlers(self):
        @self.event_bus.on("service.activity")
        async def _on_activity(event: VyperEvent):
            if event.service in [s[0] for s in self.SERVICES]:
                AppState.update(
                    service_activities={
                        **AppState.get().service_activities,
                        event.service: ServiceActivity(**event.payload)
                    }
                )
                self.refresh()

        @self.event_bus.on("service.health")
        async def _on_health(event: VyperEvent):
            if event.service in [s[0] for s in self.SERVICES]:
                AppState.update(
                    service_health={
                        **AppState.get().service_health,
                        event.service: event.payload.get("healthy", False)
                    }
                )
                self.refresh()

    def _status_icon(self, status: str) -> str:
        """Konversi status → visual icon sesuai Motion System v2."""
        icons = {
            "idle":    "💤",
            "busy":    "⣾",   # akan dirotasi oleh spinner tick
            "pending": "⏳",
            "error":   "⚠️",
            "unknown": "?",
        }
        return icons.get(status, "?")

    def _status_color(self, status: str) -> str:
        """Konversi status → CSS color class."""
        colors = {
            "idle":    "dim",
            "busy":    "success",
            "pending": "warning",
            "error":   "error",
            "unknown": "muted",
        }
        return colors.get(status, "muted")

    def _health_icon(self, healthy: bool | None) -> str:
        if healthy is True:  return "✅"
        if healthy is False: return "❌"
        return "❓"

    def _render_sparkline(self, samples: list[int], width: int = 20) -> str:
        """Render list[0-100] → ASCII sparkline bar."""
        bars = " ▁▂▃▄▅▆▇█"
        if not samples:
            return " " * width
        step = max(1, len(samples) // width)
        return "".join(bars[min(8, s * 8 // 100)] for s in samples[-width::step])

    def on_key(self, event):
        """Panel-level keyboard shortcuts."""
        if event.key == "enter":
            self._open_service_detail()
        elif event.key == "r":
            self._restart_focused_service()
        elif event.key == "l":
            self._open_logs_panel()

    def _open_service_detail(self):
        """Buka Service Detail Overlay (drill-down)."""
        self.app.push_screen("service_detail", service=self._focused_service)

    def _restart_focused_service(self):
        """Trigger /restart <service> via CommandRouter."""
        self.app.command_router.execute(f"/restart {self._focused_service}")

    def _open_logs_panel(self):
        """Trigger /logs <service> via CommandRouter."""
        self.app.command_router.execute(f"/logs {self._focused_service}")
```

### 1.3 Konvensi Visual (dari Motion System v2)

```
STATUS    ICON        WARNA           BLINK
─────────────────────────────────────────────
idle      💤          DIM GREY        —
busy      ⣾⣽⣻⢿⡿⣟⣯⣷  BRIGHT GREEN    spinner 100ms
pending   ⏳          YELLOW          2Hz
error     ⚠️          RED             1Hz
unknown   ?           DARK GREY       —
```

---

## 2. Panel 1 — Data & Config Panel

### 2.1 Identitas Panel

| Atribut | Nilai |
|---------|-------|
| **Nama** | Data & Config Panel |
| **Layer** | Layer 1 |
| **Services** | 01-Config (8011), 02-Immunefi (8001), 03-Source (8002) |
| **File** | `src/panels/layer1_data_config.py` |
| **Posisi di Layout** | Kolom kiri, baris 1 (di atas Processing Panel) |
| **Tinggi** | ~8 baris terminal |

### 2.2 Tanggung Jawab Panel

Panel ini memvisualisasikan tiga service yang bertanggung jawab atas **input data** ke
pipeline audit:

- `01-Config` — Menyediakan konfigurasi global VYPER (scanner timeout, model LLM, dll.)
- `02-Immunefi` — Fetching program info dari Immunefi API (bounty amount, scope, dll.)
- `03-Source` — Fetching source code kontrak (via Etherscan/Sourcify/on-chain)

### 2.3 Tampilan Target

```
╭─ DATA & CONFIG ───────────────────────────────╮
│ 01 ✅ 💤  Config    :8011  config ready        │
│           ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁               │
│                                               │
│ 02 ✅ ⣾  Immunefi  :8001  fetching 0x4c9e... │
│           ▁▁▁▂▃▅▇████▇▅▃▂▁▁▁▁▁▁▂▃            │
│           [████████░░░░░░] 62%  ETA: 8s       │
│                                               │
│ 03 ✅ 💤  Source    :8002  last: 12 files     │
│           ▁▁▁▁▁▁▁▁▁▁▂▃▅▇████▇▅▃▁▁           │
╰───────────────────────────────────────────────╯
```

### 2.4 Implementasi

```python
# src/panels/layer1_data_config.py

from textual.app import ComposeResult
from textual.widgets import Static
from textual.reactive import reactive
from .base_layer_panel import LayerPanel
from src.core.state_store import AppState

class DataConfigPanel(LayerPanel):
    """
    Layer 1 — Data & Config Panel.
    Memonitor: 01-Config, 02-Immunefi, 03-Source.
    """

    PANEL_TITLE = "DATA & CONFIG"
    SERVICES = [
        ("01-config",   8011),
        ("02-immunefi", 8001),
        ("03-source",   8002),
    ]

    # Service yang saat ini di-fokus (untuk keyboard nav)
    _focused_idx: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        yield Static(id="data-config-content")

    def on_state_updated(self, message):
        """Dipanggil setiap kali AppState berubah untuk service kami."""
        if any(s in message.fields for s in
               ["service_activities", "service_health", "service_sparklines"]):
            self.refresh()

    def render(self) -> str:
        state = AppState.get()
        lines = [f"╭─ {self.PANEL_TITLE} {'─' * 32}╮"]

        for idx, (svc_name, port) in enumerate(self.SERVICES):
            activity = state.service_activities.get(svc_name)
            healthy  = state.service_health.get(svc_name)
            sparkline = state.service_sparklines.get(svc_name, [])

            status = activity.status if activity else "unknown"
            task   = activity.task[:28] if activity and activity.task else ""
            progress = activity.progress if activity else None

            # Baris utama service
            icon   = self._status_icon(status)
            health = self._health_icon(healthy)
            focused = "▶" if idx == self._focused_idx else " "

            svc_short = svc_name.split("-")[1][:7].capitalize()
            line = (f"│ {focused}{health} {icon}  {svc_short:<10}"
                    f":{ port}  {task:<28}│")
            lines.append(line)

            # Baris sparkline
            spark = self._render_sparkline(sparkline, width=30)
            lines.append(f"│   {spark}              │")

            # Baris progress (jika ada)
            if progress is not None:
                bar_filled = int(progress / 100 * 14)
                bar = "█" * bar_filled + "░" * (14 - bar_filled)
                lines.append(f"│   [{bar}] {progress:3d}%"
                              + " " * 14 + "│")

            # Separator antar service (kecuali yang terakhir)
            if idx < len(self.SERVICES) - 1:
                lines.append(f"│{'─' * 47}│")

        lines.append(f"╰{'─' * 47}╯")
        return "\n".join(lines)
```

### 2.5 Event yang Di-consume

| Event Type | Handler | Aksi |
|------------|---------|------|
| `service.activity` | `_on_activity` (dari base) | Update status, task, progress |
| `service.health` | `_on_health` (dari base) | Update ✅/❌ indicator |
| `audit.state_change` | `_on_audit_state` | Highlight service yang aktif di audit |

### 2.6 Event Khusus Panel Ini

```python
# Tambahan event handler spesifik untuk Data & Config layer

@self.event_bus.on("audit.state_change")
async def _on_audit_state(event: VyperEvent):
    """
    Saat audit pindah ke FETCHING_PROGRAM → highlight 02-immunefi.
    Saat audit pindah ke FETCHING_SOURCE  → highlight 03-source.
    """
    stage = event.payload.get("state", "")
    stage_to_service = {
        "fetching_program": "02-immunefi",
        "fetching_source":  "03-source",
    }
    if stage in stage_to_service:
        self._active_for_audit = stage_to_service[stage]
        self.refresh()
```

### 2.7 Keyboard Navigation (Panel-Specific)

| Key | Aksi |
|-----|------|
| `↑ / ↓` | Navigasi fokus antar service |
| `Enter` | Buka Service Detail Overlay (logs + metrics) |
| `r` | Restart service terfokus |
| `l` | Buka logs panel |
| `c` | Buka Config Panel overlay (khusus 01-Config) |

### 2.8 Sub-fitur: Config Quick Viewer

Saat service `01-Config` difokus dan `c` ditekan, tampilkan overlay ringkas:

```
╭─ CONFIG VIEWER — 01-Config ──────────────────╮
│  scanner_timeout   : 900s                    │
│  ai_model          : claude-sonnet-4-6       │
│  max_concurrent_scan: 2                      │
│  exploit_enabled   : true                    │
│  notifier_webhook  : configured ✅           │
│                                              │
│  [e] Edit  [r] Reload  [Esc] Close           │
╰──────────────────────────────────────────────╯
```

### 2.9 Checklist Implementasi

```
[ ] DataConfigPanel extends LayerPanel
[ ] SERVICES = 3 service terdaftar benar
[ ] Render baris utama per service (health + status + task)
[ ] Render sparkline per service
[ ] Render progress bar (conditional jika progress != None)
[ ] Keyboard nav ↑/↓ mengubah _focused_idx
[ ] Enter → buka ServiceDetailOverlay
[ ] r → trigger /restart via CommandRouter
[ ] l → trigger /logs via CommandRouter
[ ] c → buka ConfigViewerOverlay (khusus 01-config)
[ ] _on_audit_state handler (highlight saat audit aktif di layer ini)
[ ] CSS: border, warna per status, fokus indicator
[ ] Unit test: render dengan berbagai state kombinasi
[ ] Integration test: SSE event → refresh panel
```

---

## 3. Panel 2 — Processing Panel

### 3.1 Identitas Panel

| Atribut | Nilai |
|---------|-------|
| **Nama** | Processing Panel |
| **Layer** | Layer 2 |
| **Services** | 04-Scanner (8003), 04a-Slither (8014), 04b-Echidna (8015), 04c-Forge (8016), 04d-Halmos (8017), 05-Mythril (8013) |
| **File** | `src/panels/layer2_processing.py` |
| **Posisi di Layout** | Kolom kiri, baris 2 (tengah, di antara Data & Intelligence) |
| **Tinggi** | ~14 baris terminal (panel terbesar di kolom kiri) |

### 3.2 Tanggung Jawab Panel

Panel ini paling **padat informasi** karena memonitor 6 service sekaligus yang merupakan
inti kerja berat pipeline: scanning statis, fuzzing, formal verification, dan symbolic execution.

- `04-Scanner` — Orchestrator scanning (delegasi ke sub-scanner)
- `04a-Slither` — Static analysis (Python, cepat, ~2 menit)
- `04b-Echidna` — Fuzzing/property testing (Haskell, ~30 menit)
- `04c-Forge` — Build & test runner (Rust/Foundry)
- `04d-Halmos` — Formal verification (SMT solver)
- `05-Mythril` — Symbolic execution (Python, terlambat, P95: 211s)

### 3.3 Tampilan Target

```
╭─ PROCESSING ──────────────────────────────────╮
│ SCANNER LAYER                                  │
│ 04  ✅ ⣽  Scanner  :8003  orchestrating...    │
│            ▁▂▄▆█████▆▄▂▁▁▁▂▄▆████▇▅▃          │
│                                               │
│ 04a ✅ ⣾  Slither  :8014  0x4c9e... 45%      │
│            ▁▂▃▅▇████████▇▆▅▄▃▂▁▁▁▁▂▃          │
│            [██████░░░░░░░░] 45%  ETA: ~15m    │
│            compile ✓  reentrancy ✓  overflow ⣾│
│                                               │
│ 04b ✅ ⏳  Echidna  :8015  queued             │
│            ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁               │
│                                               │
│ 04c ✅ 💤  Forge    :8016  build OK           │
│            ▁▁▁▂▃▅▇████▇▅▃▂▁▁▁▁▁▁              │
│                                               │
│ 04d ✅ ⣾  Halmos   :8017  verifying...       │
│            ▁▁▁▁▁▂▃▅▇████▇▅▃▂▁▁▁▁              │
│                                               │
│ 05  ✅ ⣾  Mythril  :8013  0x4c9e... (P95:211s)│
│            ▂▃▅▇████████████████▇▆▅▄▃▂▁▁       │
│            [███████████░░░░░] 68%             │
╰───────────────────────────────────────────────╯
```

### 3.4 Implementasi

```python
# src/panels/layer2_processing.py

from dataclasses import dataclass
from .base_layer_panel import LayerPanel

@dataclass
class SubTaskStatus:
    name: str
    done: bool

class ProcessingPanel(LayerPanel):
    """
    Layer 2 — Processing Panel.
    Memonitor: 04-Scanner dan semua sub-scanner + 05-Mythril.
    Panel terbesar di kolom kiri.
    """

    PANEL_TITLE = "PROCESSING"
    SERVICES = [
        ("04-scanner",  8003),
        ("04a-slither", 8014),
        ("04b-echidna", 8015),
        ("04c-forge",   8016),
        ("04d-halmos",  8017),
        ("05-mythril",  8013),
    ]

    # Cache sub-tasks per service (dari activity.sub_tasks)
    _sub_tasks: dict[str, list[SubTaskStatus]] = {}

    # Indikator bottleneck — service paling lambat saat ini
    _bottleneck_service: str | None = None

    def on_mount(self):
        super().on_mount()
        self._register_scan_handlers()

    def _register_scan_handlers(self):
        """Handler tambahan untuk sub-task progress."""

        @self.event_bus.on("service.activity")
        async def _on_scan_detail(event):
            if event.service in [s[0] for s in self.SERVICES]:
                sub_tasks = event.payload.get("sub_tasks", [])
                if sub_tasks:
                    self._sub_tasks[event.service] = [
                        SubTaskStatus(t["name"], t["done"])
                        for t in sub_tasks
                    ]
                # Deteksi bottleneck: Mythril yang paling sering busy terlama
                self._update_bottleneck()

        @self.event_bus.on("audit.state_change")
        async def _on_scan_stage(event):
            """Saat audit masuk SCANNING, highlight panel ini."""
            if event.payload.get("state") == "scanning":
                self._active_audit_id = event.payload.get("audit_id")
                self.refresh()

    def _update_bottleneck(self):
        """Tandai service yang paling lama busy sebagai bottleneck."""
        state = AppState.get()
        longest = None
        longest_duration = 0
        for svc, _ in self.SERVICES:
            activity = state.service_activities.get(svc)
            if activity and activity.status == "busy" and activity.started_at:
                duration = (datetime.now() - parse(activity.started_at)).seconds
                if duration > longest_duration:
                    longest_duration = duration
                    longest = svc
        self._bottleneck_service = longest

    def _render_sub_tasks(self, service: str) -> str:
        """
        Render sub-task checklist seperti:
        compile ✓  reentrancy ✓  overflow ⣾  report ○
        """
        tasks = self._sub_tasks.get(service, [])
        if not tasks:
            return ""
        parts = []
        for t in tasks:
            icon = "✓" if t.done else "⣾"
            parts.append(f"{t.name} {icon}")
        return "  ".join(parts)

    def render(self) -> str:
        state = AppState.get()
        lines = [f"╭─ {self.PANEL_TITLE} {'─' * 32}╮",
                 f"│ SCANNER LAYER {'─' * 32}│"]

        for idx, (svc_name, port) in enumerate(self.SERVICES):
            activity  = state.service_activities.get(svc_name)
            healthy   = state.service_health.get(svc_name)
            sparkline = state.service_sparklines.get(svc_name, [])

            status   = activity.status   if activity else "unknown"
            task     = activity.task[:26] if activity and activity.task else ""
            progress = activity.progress  if activity else None
            icon     = self._status_icon(status)
            health   = self._health_icon(healthy)
            focused  = "▶" if idx == self._focused_idx else " "
            bottleneck = " ⚡SLOW" if svc_name == self._bottleneck_service else ""

            svc_label = svc_name[:8].capitalize()
            line = (f"│ {focused}{health} {icon}  {svc_label:<10}"
                    f":{port}  {task:<22}{bottleneck}│")
            lines.append(line)

            # Sparkline
            spark = self._render_sparkline(sparkline, width=28)
            lines.append(f"│   {spark}                │")

            # Progress bar
            if progress is not None:
                bar_filled = int(progress / 100 * 14)
                bar = "█" * bar_filled + "░" * (14 - bar_filled)
                lines.append(f"│   [{bar}] {progress:3d}%"
                              + " " * 12 + "│")

            # Sub-task checklist
            sub = self._render_sub_tasks(svc_name)
            if sub:
                lines.append(f"│   {sub[:44]:<44}│")

            # Separator
            if idx < len(self.SERVICES) - 1:
                lines.append(f"│{'─' * 47}│")

        lines.append(f"╰{'─' * 47}╯")
        return "\n".join(lines)
```

### 3.5 Event yang Di-consume

| Event Type | Handler | Aksi |
|------------|---------|------|
| `service.activity` | Base + `_on_scan_detail` | Update status, progress, sub_tasks |
| `service.health` | Base `_on_health` | Update health indicator |
| `audit.state_change` | `_on_scan_stage` | Highlight panel saat stage = SCANNING |
| `audit.finding` | `_on_finding` | Counter findings real-time di task description |

### 3.6 Fitur Khusus Processing Panel

#### 3.6.1 Bottleneck Detection

```python
# Tampilkan ⚡SLOW di samping service yang paling lama running.
# Berguna untuk operator mengetahui bottleneck tanpa perlu /latency command.
# Mythril secara historis P95 = 211s → akan sering mendapat label ini.
```

#### 3.6.2 Sub-Task Drill-Down

Saat user tekan `Enter` di service `04a-Slither`, tampilkan Service Detail Overlay
dengan sub-task breakdown lengkap:

```
╭─ SLITHER DETAIL ─────────────────────────────────────────────╮
│  Status: ⣾ busy  │  Started: 10:20:15  │  ETA: ~15 menit   │
│  Contract: 0x4c9edd... (ethereum)                            │
│                                                              │
│  Sub-tasks:                                                  │
│  ✓ Compile (2.1s)                                            │
│  ✓ Detect reentrancy (8.3s)                                  │
│  ⣾ Detect integer overflow (running, 45s elapsed)            │
│  ○ Detect access control                                     │
│  ○ Generate report                                           │
│                                                              │
│  Findings so far: 7 (2 HIGH, 3 MEDIUM, 2 LOW)               │
│  Trace ID: 1a2b3c4d... [/trace 1a2b3c4d]                    │
╰──────────────────────────────────────────────────────────────╯
```

#### 3.6.3 Concurrent Slot Awareness

Processing Panel harus menampilkan indikasi ketika scanner slot governor
membatasi eksekusi (sinkron dengan ResourcePanel):

```python
# Jika activity.status == "pending" DAN resource_slots.scanner_used >= scanner_max
# → tampilkan label "queued (slot full)" bukan hanya "⏳"
```

### 3.7 Keyboard Navigation

| Key | Aksi |
|-----|------|
| `↑ / ↓` | Navigasi antar 6 service |
| `Enter` | Buka Service Detail (sub-tasks + findings) |
| `r` | Restart service terfokus |
| `l` | Buka logs (tail -n 100) |
| `t` | Buka Trace Viewer untuk trace_id aktif |

### 3.8 Checklist Implementasi

```
[ ] ProcessingPanel extends LayerPanel
[ ] SERVICES = 6 service (04, 04a, 04b, 04c, 04d, 05)
[ ] Render per service: health + icon + task + sparkline
[ ] Render progress bar jika activity.progress != None
[ ] Render sub-task checklist (_render_sub_tasks)
[ ] Bottleneck detection (_update_bottleneck) → label ⚡SLOW
[ ] Slot awareness: "queued (slot full)" saat scanner penuh
[ ] Enter → ServiceDetailOverlay dengan sub-task breakdown
[ ] t → TraceViewerOverlay untuk trace_id aktif
[ ] Event handler audit.state_change → highlight SCANNING stage
[ ] Event handler audit.finding → update findings counter
[ ] CSS: compact spacing (panel besar, space terbatas)
[ ] Unit test: render 6 service dalam berbagai state
[ ] Unit test: bottleneck detection logic
[ ] Integration test: sub-task update via SSE
```

---

## 4. Panel 3 — Intelligence Panel

### 4.1 Identitas Panel

| Atribut | Nilai |
|---------|-------|
| **Nama** | Intelligence Panel |
| **Layer** | Layer 3 |
| **Services** | 06-AI (8004), 07-Classifier (8005) |
| **File** | `src/panels/layer3_intelligence.py` |
| **Posisi di Layout** | Kolom kiri, baris 3 (bawah, sebelum Exploit & Output) |
| **Tinggi** | ~8 baris terminal |

### 4.2 Tanggung Jawab Panel

Panel ini memonitor dua service dengan tanggung jawab paling tinggi di pipeline:

- `06-AI` — LLM analysis (claude-sonnet-4-6): menganalisis findings, menentukan severity,
  membuat reasoning chain. Ini adalah service yang paling "mahal" (latency + cost).
- `07-Classifier` — ML classifier: TP/FP classification berdasarkan model yang telah dilatih.
  Menjadi garda terakhir sebelum exploit stage.

### 4.3 Tampilan Target

```
╭─ INTELLIGENCE ────────────────────────────────╮
│ 06 ✅ ⣾  AI         :8004  analyzing 0x4c9e... │
│           ▁▁▂▄▇████████████▇▅▃▂▁▁▁▁▁▁          │
│           Model: claude-sonnet-4-6              │
│           [████████████░░░] 78%  ETA: ~28s     │
│           Findings analyzed: 18/25              │
│─────────────────────────────────────────────── │
│ 07 ✅ 💤  Classifier :8005  last: 14 classified │
│           ▁▁▁▁▁▁▁▁▁▁▁▂▃▅▇████▇▅▃▁▁            │
│           TP:61 FP:8  Precision:88.4%           │
╰───────────────────────────────────────────────╯
```

### 4.4 Implementasi

```python
# src/panels/layer3_intelligence.py

from .base_layer_panel import LayerPanel
from src.core.state_store import AppState

class IntelligencePanel(LayerPanel):
    """
    Layer 3 — Intelligence Panel.
    Memonitor: 06-AI (LLM analysis) + 07-Classifier (ML TP/FP).
    Panel terpenting untuk quality gate pipeline.
    """

    PANEL_TITLE = "INTELLIGENCE"
    SERVICES = [
        ("06-ai",         8004),
        ("07-classifier", 8005),
    ]

    # Cache metrics untuk 07-classifier (diupdate oleh metric.update event)
    _classifier_metrics: dict = {}

    # Cache model LLM yang sedang aktif (dari 06-ai activity payload)
    _active_model: str = "—"

    # Cache jumlah findings yang sedang dianalisis (dari 06-ai)
    _findings_analyzed: str = ""

    def on_mount(self):
        super().on_mount()
        self._register_intelligence_handlers()

    def _register_intelligence_handlers(self):

        @self.event_bus.on("service.activity")
        async def _on_ai_activity(event: VyperEvent):
            if event.service == "06-ai":
                # Extract model name dan findings count dari payload
                self._active_model = event.payload.get("model", "—")
                findings_done  = event.payload.get("findings_analyzed", 0)
                findings_total = event.payload.get("findings_total", 0)
                if findings_total:
                    self._findings_analyzed = f"{findings_done}/{findings_total}"
                self.refresh()

        @self.event_bus.on("metric.update")
        async def _on_metric(event: VyperEvent):
            """
            Update classifier metrics saat TP/FP berubah.
            Event payload: { tool, tp, fp, fn, precision, recall }
            """
            tool = event.payload.get("tool", "")
            if tool in ("classifier", "07-classifier"):
                self._classifier_metrics = event.payload
                AppState.update(
                    classifier_metrics={
                        **AppState.get().classifier_metrics,
                        tool: event.payload
                    }
                )
                self.refresh()

        @self.event_bus.on("audit.state_change")
        async def _on_intel_stage(event: VyperEvent):
            """Highlight panel saat audit masuk AI_ANALYSIS atau CLASSIFYING."""
            stage = event.payload.get("state", "")
            if stage in ("ai_analysis", "classifying"):
                self._active_stage = stage
                self.refresh()

    def _render_classifier_metrics(self) -> str:
        m = self._classifier_metrics
        if not m:
            return "No metrics yet"
        tp = m.get("tp", 0)
        fp = m.get("fp", 0)
        precision = m.get("precision", 0)
        return f"TP:{tp} FP:{fp}  Precision:{precision:.1f}%"

    def render(self) -> str:
        state = AppState.get()
        lines = [f"╭─ {self.PANEL_TITLE} {'─' * 32}╮"]

        for idx, (svc_name, port) in enumerate(self.SERVICES):
            activity  = state.service_activities.get(svc_name)
            healthy   = state.service_health.get(svc_name)
            sparkline = state.service_sparklines.get(svc_name, [])

            status   = activity.status   if activity else "unknown"
            task     = activity.task[:26] if activity and activity.task else ""
            progress = activity.progress  if activity else None
            icon     = self._status_icon(status)
            health   = self._health_icon(healthy)
            focused  = "▶" if idx == self._focused_idx else " "

            svc_label = svc_name.split("-")[1][:10].capitalize()
            line = (f"│ {focused}{health} {icon}  {svc_label:<12}"
                    f":{port}  {task:<20}│")
            lines.append(line)

            # Sparkline
            spark = self._render_sparkline(sparkline, width=28)
            lines.append(f"│   {spark}                │")

            # Fitur khusus per service
            if svc_name == "06-ai":
                lines.append(f"│   Model: {self._active_model:<36}│")
                if progress is not None:
                    bar_filled = int(progress / 100 * 14)
                    bar = "█" * bar_filled + "░" * (14 - bar_filled)
                    lines.append(f"│   [{bar}] {progress:3d}%"
                                 + " " * 12 + "│")
                if self._findings_analyzed:
                    lines.append(f"│   Findings analyzed: "
                                 f"{self._findings_analyzed:<25}│")

            elif svc_name == "07-classifier":
                metrics_str = self._render_classifier_metrics()
                lines.append(f"│   {metrics_str:<44}│")

            # Separator
            if idx < len(self.SERVICES) - 1:
                lines.append(f"│{'─' * 47}│")

        lines.append(f"╰{'─' * 47}╯")
        return "\n".join(lines)
```

### 4.5 Event yang Di-consume

| Event Type | Handler | Aksi |
|------------|---------|------|
| `service.activity` | Base + `_on_ai_activity` | Update model name, findings progress |
| `service.health` | Base `_on_health` | Update health indicator |
| `metric.update` | `_on_metric` | Update TP/FP/Precision classifier |
| `audit.state_change` | `_on_intel_stage` | Highlight saat AI_ANALYSIS / CLASSIFYING |

### 4.6 Fitur Khusus Intelligence Panel

#### 4.6.1 LLM Cost Awareness (06-AI)

Panel ini menampilkan indikasi biaya LLM secara real-time. Informasi ini di-push
dari 06-AI service setiap kali API call selesai:

```python
# Payload tambahan dari 06-AI service.activity:
{
    "status": "busy",
    "task": "analyzing 0x4c9edd...",
    "progress": 78,
    "model": "claude-sonnet-4-6",
    "findings_analyzed": 18,
    "findings_total": 25,
    "tokens_used": 4821,        # optional
    "estimated_cost_usd": 0.14  # optional
}
```

Jika tersedia, tampilkan `~$0.14` di samping nama model.

#### 4.6.2 Classifier Quality Gate Indicator

Saat precision classifier turun di bawah threshold (misal < 80%),
panel menampilkan warning:

```
│ 07 ✅ ⣾  Classifier :8005  classifying...    │
│   ⚠️  PRECISION DROP: 73.2% (threshold: 80%) │
│   TP:45 FP:17  Recall:88.0%                  │
```

```python
PRECISION_THRESHOLD = 80.0  # dapat dikonfigurasi dari config.yaml

def _render_classifier_metrics(self) -> str:
    m = self._classifier_metrics
    precision = m.get("precision", 100.0)
    warning = ""
    if precision < PRECISION_THRESHOLD:
        warning = f"\n│   ⚠️  PRECISION DROP: {precision:.1f}% (threshold: {PRECISION_THRESHOLD:.0f}%)"
    ...
```

#### 4.6.3 Real-Time Findings Counter (06-AI)

Saat AI sedang menganalisis findings, tampilkan counter yang update setiap
finding selesai dianalisis — memberikan feedback yang sangat responsif
dibanding hanya progress bar generic.

### 4.7 Drill-Down: AI Analysis Detail

Saat `Enter` ditekan di service `06-AI`, buka overlay yang menampilkan
reasoning chain aktif (sinkron dengan AntonioPanel jika agent mode aktif):

```
╭─ AI ANALYSIS DETAIL ─────────────────────────────────────────────╮
│  Model: claude-sonnet-4-6  │  Session: aud_001  │  Cost: ~$0.14  │
│                                                                   │
│  ANALYZING FINDING 18/25:                                        │
│  vuln_018 — "Unchecked return value in transfer()"              │
│  Severity estimate: MEDIUM → needs confirmation                   │
│                                                                   │
│  Reasoning:                                                       │
│  "Transfer to ERC20 token without checking return value.         │
│   In non-standard tokens this may silently fail.                 │
│   Risk: fund loss if token reverts silently."                    │
│                                                                   │
│  COMPLETED:                                                       │
│  ✅ vuln_001 → CRITICAL (flash loan reentrancy)                   │
│  ✅ vuln_002 → HIGH (access control bypass)                       │
│  ✅ vuln_003 → FALSE_POSITIVE (intended behavior)                 │
│  ... (17 more)                                                    │
╰───────────────────────────────────────────────────────────────────╯
```

### 4.8 Keyboard Navigation

| Key | Aksi |
|-----|------|
| `↑ / ↓` | Navigasi antara 06-AI dan 07-Classifier |
| `Enter` | Buka AI Analysis Detail / Classifier Detail |
| `m` | Tampilkan MetricsPanel overlay penuh |
| `r` | Restart service terfokus |
| `l` | Buka logs |

### 4.9 Checklist Implementasi

```
[ ] IntelligencePanel extends LayerPanel
[ ] SERVICES = 2 service (06-ai, 07-classifier)
[ ] Render per service: health + icon + task + sparkline
[ ] 06-AI: render model name
[ ] 06-AI: render progress bar dengan findings counter (x/total)
[ ] 06-AI: render token usage + estimated cost (jika tersedia)
[ ] 07-Classifier: render TP/FP/Precision dari _classifier_metrics
[ ] 07-Classifier: precision warning < threshold
[ ] metric.update handler → update _classifier_metrics
[ ] audit.state_change handler → highlight AI_ANALYSIS / CLASSIFYING
[ ] Enter di 06-AI → buka AI Analysis Detail overlay
[ ] Enter di 07-Classifier → buka Classifier Detail overlay
[ ] m → buka MetricsPanel overlay
[ ] PRECISION_THRESHOLD configurable dari config.yaml
[ ] Unit test: precision warning logic
[ ] Unit test: render saat metric.update dengan berbagai nilai
[ ] Integration test: SSE metric.update → panel refresh
```

---

## 5. Urutan Implementasi & Milestone

### Phase 0 — Infrastruktur (Prasyarat)

```
Minggu 1-2

[ ] EventBus (SSE client + reconnect backoff)
[ ] ActivityMonitorV2 (state cache, bukan polling)
[ ] VyperState + AppState (singleton reactive state)
[ ] PollingFallback (backup 5s untuk service tanpa SSE)
[ ] ServiceActivity dataclass
[ ] LayerPanel base class
[ ] Motion system: _status_icon, _status_color, _render_sparkline
[ ] CSS foundation: warna, border, fokus indicator
```

### Phase 1 — Panel 1: Data & Config

```
Minggu 3

[ ] DataConfigPanel (3 service, sederhana)
[ ] Render dasar: status + sparkline + progress
[ ] Keyboard nav ↑/↓ + Enter + r + l
[ ] ConfigViewerOverlay (bonus: untuk 01-Config)
[ ] Unit + integration test
[ ] Demo: panel hidup dengan mock SSE events
```

### Phase 2 — Panel 2: Processing

```
Minggu 4

[ ] ProcessingPanel (6 service, paling kompleks)
[ ] Sub-task checklist render
[ ] Bottleneck detection (⚡SLOW label)
[ ] Slot awareness ("queued (slot full)")
[ ] ServiceDetailOverlay dengan sub-task breakdown
[ ] TraceViewerOverlay (drill-down via trace_id)
[ ] Unit + integration test
```

### Phase 3 — Panel 3: Intelligence

```
Minggu 5

[ ] IntelligencePanel (2 service, high-value display)
[ ] 06-AI: model name + findings counter + cost indicator
[ ] 07-Classifier: TP/FP/Precision + warning threshold
[ ] AIAnalysisDetailOverlay
[ ] metric.update handler
[ ] Unit + integration test
```

### Phase 4 — Integrasi & Polish

```
Minggu 6

[ ] Integrasi ketiga panel ke Mode FULL layout
[ ] Keyboard nav antar panel (Tab/Shift+Tab)
[ ] CSS polish: konsistensi warna, spacing, border
[ ] Stress test: 20 SSE events/detik → render performance
[ ] SSH/tmux compatibility test
[ ] Dokumentasi panel API
```

---

## 6. Testing Strategy

### 6.1 Unit Tests (Per Panel)

```python
# tests/panels/test_layer1_data_config.py

def test_render_idle_services():
    """Semua service idle → tampilkan 💤 dan DIM."""

def test_render_busy_with_progress():
    """02-Immunefi busy 62% → tampilkan progress bar."""

def test_render_error_state():
    """03-Source error → tampilkan ⚠️ merah."""

def test_keyboard_nav_up_down():
    """↑↓ mengubah _focused_idx dengan wrap-around."""

def test_drill_down_enter():
    """Enter → ServiceDetailOverlay dipush ke screen stack."""
```

### 6.2 Integration Tests

```python
# tests/integration/test_sse_to_panel.py

async def test_sse_event_updates_panel():
    """SSE 'service.activity' event → panel refresh dengan data baru."""

async def test_metric_update_classifier():
    """metric.update event → IntelligencePanel menampilkan precision baru."""

async def test_bottleneck_detection():
    """Mythril busy 200+ detik → ProcessingPanel menampilkan ⚡SLOW."""
```

### 6.3 Visual Regression Tests

```python
# Gunakan Textual's built-in snapshot testing
# tests/snapshots/

async def test_data_config_full_state(snap_compare):
    """Screenshot panel dalam state tertentu === expected snapshot."""
    assert snap_compare("data_config_busy_state.svg")
```

### 6.4 Performance Tests

```
Target: render time < 16ms per frame (60fps equivalent)
        EventBus dispatch < 5ms per event
        Panel refresh < 10ms (termasuk re-render)
```

---

> **VYPER TUI v2 — Layer Panels Build Plan**
> Dibuat berdasarkan: `arsitektur.md` (VYPER TUI v2 Enhanced Architecture Document)
> Covers: Panel 1 (Data & Config), Panel 2 (Processing), Panel 3 (Intelligence)
> Last updated: 2026-05-26