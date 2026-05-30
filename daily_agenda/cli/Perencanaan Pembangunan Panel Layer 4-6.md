# Perencanaan Pembangunan Panel Layer 4-6
## Exploit & Output Panel · Orchestration & Agent Panel · Infra & Delivery Panel

> **Dokumen ini** adalah blueprint implementasi untuk tiga Layer Panel terakhir di VYPER TUI v2.
> Mengacu pada arsitektur event-driven SSE, reactive state management, dan prinsip desain
> yang telah ditetapkan di arsitektur dokumen utama.
>
> Dibuat: 2026-05-26

---

## Daftar Isi

1. [Ringkasan Eksekutif](#1-ringkasan-eksekutif)
2. [Layer 4 — Exploit & Output Panel](#2-layer-4--exploit--output-panel)
3. [Layer 5 — Orchestration & Agent Panel](#3-layer-5--orchestration--agent-panel)
4. [Layer 6 — Infra & Delivery Panel](#4-layer-6--infra--delivery-panel)
5. [Integrasi Lintas Panel](#5-integrasi-lintas-panel)
6. [Roadmap Implementasi](#6-roadmap-implementasi)
7. [Checklist QA](#7-checklist-qa)

---

## 1. Ringkasan Eksekutif

### 1.1 Konteks: Posisi Ketiga Panel dalam Arsitektur VYPER

Tiga panel ini mencakup **Layer 4–6** dari topology service VYPER — bagian hilir pipeline yang
paling "high-stakes": eksekusi exploit PoC, orkestrasi multi-agent, dan pengiriman hasil ke
dunia luar.

```
PIPELINE AUDIT (10 stage)
──────────────────────────────────────────────────────────────────────────────
 PEND → PROG → SRC → SCAN → HALMOS → AI → CLASS → [EXPLOIT] → [REPORT] → DONE
                                                        ↑            ↑
                                               Layer 4 mengambil alih di sini
──────────────────────────────────────────────────────────────────────────────

SERVICE LAYER MAP
┌─────────────────────────────────────────────────────────────────────────────┐
│ Layer 4 — EXPLOIT & OUTPUT   : 08-Exploit(8006)  09-Reporter(8007)         │
│                                10-Notifier(8008)                           │
│ Layer 5 — ORCHESTRATION      : 11-Orchestrator(8009)  14-Agent(8021)       │
│ Layer 6 — INFRA & DELIVERY   : 12-Webhook(8010)  13-Upkeep(8012)          │
│                                15-Dashboard(8000)  16-Submission(8018)     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Prinsip yang Diwarisi dari Arsitektur Utama

Ketiga panel ini **wajib** mengikuti prinsip v2:

| Prinsip | Implementasi |
|---------|--------------|
| Event-Driven | Subscribe ke SSE via EventBus, tidak ada polling mandiri |
| Depth-on-Demand | Default: ringkas 3–5 baris; `Enter` → overlay detail |
| Setiap Pixel Membawa Makna | Warna = status real, animasi = aktivitas nyata |
| No State Isolation | Semua state via `AppState` / `StateStore`, tidak ada state lokal panel |
| Terminal-First | Operasi penuh via keyboard, tidak ada ketergantungan mouse |

### 1.3 Dependensi Antar Panel

```
ExploitOutputPanel ←────── terima sinyal dari ────── PipelineTracker
       │                                                    │
       │ exploit.result event                               │ classifying → exploiting
       ▼                                                    ▼
OrchestrationAgentPanel ←── koordinasi ──────── AntonioPanel (Layer 5)
       │
       │ delegation, task dispatch
       ▼
InfraDeliveryPanel ←────── webhook/submit/upkeep ───── ExploitOutputPanel
```

---

## 2. Layer 4 — Exploit & Output Panel

### 2.1 Deskripsi & Tanggung Jawab

Panel ini menampilkan **tiga service paling dramatis** dalam pipeline VYPER:
- **08-Exploit** — Menjalankan Anvil fork chain dan PoC exploit script
- **09-Reporter** — Menghasilkan laporan Immunefi-ready dan full audit report
- **10-Notifier** — Mengirim notifikasi ke Discord, Telegram, Email

**Mengapa panel ini kritis:** Exploit engine adalah titik validasi akhir kerentanan.
Seorang operator harus bisa melihat secara real-time apakah PoC berhasil dieksekusi,
berapa estimasi profit, dan apakah laporan sudah siap untuk submission.

### 2.2 Services yang Dimonitor

```
Service         Port    Tanggung Jawab
──────────────────────────────────────────────────────────────────────────────
08-exploit      8006    Fork chain (Anvil), deploy attacker contract,
                        execute PoC, verify profit, generate tx proof
09-reporter     8007    Generate immunefi.md, full.md, executive summary,
                        format laporan sesuai severity
10-notifier     8008    Discord webhook, Telegram bot, Email SMTP,
                        alert throttling, delivery confirmation
```

### 2.3 UI Layout & Mockup

#### Tampilan Default (Mode FULL — posisi di Layer Panel kiri bawah)

```
╭─ L4: EXPLOIT & OUTPUT ─────────────────────────────────────────────── [4] ─╮
│  08-Exploit   🔥 ⣾ RUNNING    poc_reentrancy_0x4c9edd.sol  [████░░░] 67%   │
│  09-Reporter  ✅ 💤 idle       Last: immunefi.md aud_001  (3m ago)          │
│  10-Notifier  ✅ 💤 idle       Last: Discord #vyper-alerts (3m ago)         │
╰─────────────────────────────────────────────────────────────────────────────╯
```

#### Tampilan saat Exploit Aktif (auto-expand)

```
╭─ L4: EXPLOIT & OUTPUT ─────────────────────── 🔥 PoC RUNNING ──────── [4] ─╮
│  ┌─ 08-EXPLOIT ENGINE ── aud_001 / vuln_001 ─────────────────────────────┐  │
│  │  🔥 Anvil fork: ethereum @ block 21,500,000                           │  │
│  │  Finding  : reentrancy — price manipulation via flash loan            │  │
│  │  Expected : ~$2.4M profit if exploited                                │  │
│  │                                                                        │  │
│  │  [PHASE 1] Fork chain       ✅  2.1s                                  │  │
│  │  [PHASE 2] Deploy attacker  ✅  8.3s                                  │  │
│  │  [PHASE 3] Execute attack   ⣾  running (42s elapsed...)              │  │
│  │  [PHASE 4] Verify profit    ○   waiting                               │  │
│  │  [PHASE 5] Generate proof   ○   waiting                               │  │
│  │                                                                        │  │
│  │  Attacker: 0x0000... (ephemeral)   Gas: --   Block: 21,500,042       │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│  09-Reporter  💤 idle   10-Notifier  💤 idle                                 │
╰─────────────────────────────────────────────────────────────────────────────╯
```

#### Tampilan setelah Exploit Berhasil

```
╭─ L4: EXPLOIT & OUTPUT ──────────────── ✅ EXPLOIT CONFIRMED ───────── [4] ─╮
│  08-Exploit   ✅ 💤 idle  Last: tx 0xdeadbeef... profit: $2,418,392  (1m)   │
│  09-Reporter  ✅ ⣾ BUSY   Generating immunefi.md...  [████████░░░] 78%      │
│  10-Notifier  ✅ ⏳ PEND  Waiting for reporter...                           │
│                                                                              │
│  ▶ [Enter] Lihat exploit detail  [r] Lihat laporan  [n] Preview notif      │
╰─────────────────────────────────────────────────────────────────────────────╯
```

#### Tampilan setelah Seluruh Layer Selesai

```
╭─ L4: EXPLOIT & OUTPUT ─────────────────────────────── ALL DONE ──────── [4]─╮
│  08-Exploit   ✅ 💤 idle  aud_001: $2.4M confirmed. aud_003: no exploit.     │
│  09-Reporter  ✅ 💤 idle  aud_001: immunefi.md + full.md ready              │
│  10-Notifier  ✅ 💤 idle  Discord ✓  Telegram ✓  Email ✓                    │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### 2.4 Event Subscriptions

Panel ini subscribe ke event-event berikut dari EventBus:

```python
# Sumber event: 15-Dashboard SSE hub

EVENT YANG DIDENGARKAN          TINDAKAN DI PANEL
──────────────────────────────────────────────────────────────────────────────
exploit.phase_update            Update progress bar exploit (phase 1–5)
exploit.confirmed               Tampilkan profit, set status 08-Exploit idle
exploit.failed                  Tampilkan error merah, fase yang gagal
service.activity (08-exploit)   Update status baris exploit service
service.activity (09-reporter)  Update status baris reporter service
service.activity (10-notifier)  Update status baris notifier service
report.generated                Tampilkan nama file laporan di baris reporter
notification.sent               Tampilkan channel + status di baris notifier
audit.state_change              Jika state = "exploiting" → auto-expand panel
```

### 2.5 State yang Dikelola di AppState

```python
# Tambahkan ke VyperState di state_store.py

@dataclass
class ExploitState:
    audit_id: str
    finding_id: str
    finding_type: str           # "reentrancy", "overflow", dll
    status: str                 # "running" | "confirmed" | "failed" | "no_exploit"
    current_phase: int          # 1–5
    phase_results: dict         # {1: {"done": True, "duration": 2.1}, ...}
    expected_profit_usd: float | None
    confirmed_profit_usd: float | None
    tx_hash: str | None
    attacker_contract: str | None
    fork_block: int | None
    started_at: datetime | None
    duration_s: float | None

@dataclass
class ReportState:
    audit_id: str
    status: str                 # "generating" | "ready" | "failed"
    files: list[str]            # ["immunefi.md", "full.md"]
    progress: int               # 0–100
    generated_at: datetime | None

@dataclass
class NotificationState:
    audit_id: str
    status: str                 # "pending" | "sent" | "failed"
    channels: dict              # {"discord": "✓", "telegram": "✓", "email": "✗"}
    sent_at: datetime | None

# Di VyperState:
active_exploits: dict[str, ExploitState]    # keyed by audit_id
report_states: dict[str, ReportState]       # keyed by audit_id
notification_states: dict[str, NotificationState]
```

### 2.6 Implementasi Python (Textual Widget)

```python
# src/panels/exploit_output_panel.py

from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from rich.progress import ProgressBar

class ExploitOutputPanel(Widget):
    """
    Layer 4 Panel: 08-Exploit, 09-Reporter, 10-Notifier.
    Auto-expands saat exploit aktif. Kembali ke compact saat idle.
    """

    DEFAULT_CSS = """
    ExploitOutputPanel {
        height: auto;
        min-height: 3;
        max-height: 12;
        border: solid $panel-border;
        border-title-color: $warning;
    }
    ExploitOutputPanel.exploit-running {
        border: solid $error;
        border-title-color: $error;
        animation: pulse 1s infinite;
    }
    ExploitOutputPanel.exploit-confirmed {
        border: solid $success;
        border-title-color: $success;
    }
    """

    exploit_running = reactive(False)
    exploit_confirmed = reactive(False)

    EXPLOIT_PHASES = [
        "Fork chain",
        "Deploy attacker",
        "Execute attack",
        "Verify profit",
        "Generate proof",
    ]

    def on_mount(self):
        bus = self.app.event_bus

        @bus.on("exploit.phase_update")
        async def _on_phase(event):
            audit_id = event.payload["audit_id"]
            phase = event.payload["phase"]          # 1–5
            done = event.payload["done"]
            duration = event.payload.get("duration_s")
            state = self.app.state.active_exploits.get(audit_id)
            if state:
                state.current_phase = phase
                state.phase_results[phase] = {"done": done, "duration": duration}
            self.exploit_running = True
            self.refresh()

        @bus.on("exploit.confirmed")
        async def _on_confirmed(event):
            audit_id = event.payload["audit_id"]
            profit = event.payload["profit_usd"]
            tx = event.payload["tx_hash"]
            state = self.app.state.active_exploits.get(audit_id)
            if state:
                state.status = "confirmed"
                state.confirmed_profit_usd = profit
                state.tx_hash = tx
            self.exploit_running = False
            self.exploit_confirmed = True
            self._set_class("exploit-confirmed", True)
            self.refresh()

        @bus.on("exploit.failed")
        async def _on_failed(event):
            audit_id = event.payload["audit_id"]
            state = self.app.state.active_exploits.get(audit_id)
            if state:
                state.status = "failed"
            self.exploit_running = False
            self._set_class("exploit-confirmed", False)
            self.refresh()

        @bus.on("service.activity")
        async def _on_activity(event):
            if event.service in ("08-exploit", "09-reporter", "10-notifier"):
                self.app.state.service_activities[event.service] = event.payload
                self.refresh()

        @bus.on("audit.state_change")
        async def _on_state_change(event):
            if event.payload["state"] == "exploiting":
                self.exploit_running = True
                self._set_class("exploit-running", True)

        @bus.on("report.generated")
        async def _on_report(event):
            audit_id = event.payload["audit_id"]
            files = event.payload["files"]
            # Update report state
            self.app.state.report_states[audit_id] = ReportState(
                audit_id=audit_id,
                status="ready",
                files=files,
                progress=100,
                generated_at=datetime.now(),
            )
            self.refresh()

        @bus.on("notification.sent")
        async def _on_notif(event):
            audit_id = event.payload["audit_id"]
            channels = event.payload["channels"]
            self.app.state.notification_states[audit_id] = NotificationState(
                audit_id=audit_id,
                status="sent",
                channels=channels,
                sent_at=datetime.now(),
            )
            self.refresh()

    def render(self) -> Panel:
        lines = []

        # Baris 08-Exploit
        exploit_activities = self.app.state.service_activities.get("08-exploit")
        active_exploit = self._get_latest_active_exploit()

        if active_exploit and active_exploit.status == "running":
            # Mode expanded
            lines.extend(self._render_exploit_engine(active_exploit))
        else:
            lines.append(self._render_service_row("08-exploit", exploit_activities))

        # Baris 09-Reporter
        lines.append(self._render_reporter_row())

        # Baris 10-Notifier
        lines.append(self._render_notifier_row())

        title = "L4: EXPLOIT & OUTPUT"
        border_style = "red" if self.exploit_running else (
                        "green" if self.exploit_confirmed else "dim")

        return Panel(
            "\n".join(str(l) for l in lines),
            title=title,
            border_style=border_style,
        )

    def _render_exploit_engine(self, state: ExploitState) -> list[str]:
        """Render expanded exploit engine view."""
        rows = [
            f"  🔥 Anvil fork: {state.chain} @ block {state.fork_block:,}",
            f"  Finding  : {state.finding_type}",
            f"  Expected : ~${state.expected_profit_usd:,.0f} profit if exploited",
            "",
        ]
        for i, phase_name in enumerate(self.EXPLOIT_PHASES, 1):
            result = state.phase_results.get(i)
            if result and result["done"]:
                dur = f"  {result['duration']:.1f}s"
                rows.append(f"  [PHASE {i}] {phase_name:<20} ✅{dur}")
            elif state.current_phase == i:
                elapsed = (datetime.now() - state.started_at).seconds
                rows.append(f"  [PHASE {i}] {phase_name:<20} ⣾  running ({elapsed}s)")
            else:
                rows.append(f"  [PHASE {i}] {phase_name:<20} ○   waiting")
        return rows

    def _render_reporter_row(self) -> str:
        """Baris ringkas untuk 09-reporter."""
        activity = self.app.state.service_activities.get("09-reporter")
        # Cari laporan terbaru
        latest_report = max(
            self.app.state.report_states.values(),
            key=lambda r: r.generated_at or datetime.min,
            default=None,
        )
        if activity and activity.get("status") == "busy":
            prog = activity.get("progress", 0)
            bar = self._mini_bar(prog)
            return f"  09-Reporter  ✅ ⣾ BUSY   Generating...  [{bar}] {prog}%"
        elif latest_report and latest_report.status == "ready":
            files = ", ".join(latest_report.files)
            return f"  09-Reporter  ✅ 💤 idle   Last: {files} ({latest_report.audit_id})"
        return "  09-Reporter  ✅ 💤 idle"

    def _render_notifier_row(self) -> str:
        """Baris ringkas untuk 10-notifier."""
        latest_notif = max(
            self.app.state.notification_states.values(),
            key=lambda n: n.sent_at or datetime.min,
            default=None,
        )
        if latest_notif and latest_notif.status == "sent":
            ch = "  ".join(f"{k} {v}" for k, v in latest_notif.channels.items())
            return f"  10-Notifier  ✅ 💤 idle   Last: {ch}"
        return "  10-Notifier  ✅ 💤 idle"

    def _mini_bar(self, pct: int, width: int = 10) -> str:
        filled = int(pct / 100 * width)
        return "█" * filled + "░" * (width - filled)

    def action_drill_down(self):
        """Enter key → buka ExploitEnginePanel overlay."""
        exploit = self._get_latest_active_exploit()
        if exploit:
            self.app.push_screen(ExploitDetailOverlay(exploit_id=exploit.audit_id))

    def on_key(self, event):
        if event.key == "enter":
            self.action_drill_down()
        elif event.key == "r":
            self._open_report_preview()
        elif event.key == "n":
            self._preview_notification()
```

### 2.7 Drill-Down Overlays

Dua overlay on-demand yang dipicu dari panel ini:

#### A. Exploit Engine Detail Overlay (sudah ada di arsitektur sebagai `Exploit Engine Panel`)

```
╭─ EXPLOIT ENGINE — aud_001 / vuln_001 ──────────────────────────────────── X ─╮
│  🔥 Anvil fork: ethereum @ block 21,500,000                                   │
│  Finding: reentrancy — price manipulation via flash loan                      │
│  PoC Script: poc_reentrancy_0x4c9edd_001.sol                                  │
│  Attacker: 0x0000...dead (ephemeral)                                          │
│                                                                                │
│  PHASE DETAIL                                                                  │
│  [1] Fork chain       ✅  2.1s    Fork established at block 21,500,000        │
│  [2] Deploy attacker  ✅  8.3s    0x0000dead @ 21,500,001, gas: 2,847,291    │
│  [3] Execute attack   ✅  34.7s   tx 0xdeadbeef... 3 txs confirmed            │
│  [4] Verify profit    ✅  0.4s    Balance Δ: +$2,418,392 (2,418 USDC)        │
│  [5] Generate proof   ✅  1.2s    proof.json saved                            │
│                                                                                │
│  TX PROOF                                                                      │
│  0xdeadbeef1234567890...   Block: 21,500,043   Gas: 1,203,444                │
│  Profit: 2,418,392 USDC   ≈ $2.4M at current price                           │
│                                                                                │
│  [Esc] Tutup   [c] Copy tx hash   [e] Export proof.json                       │
╰────────────────────────────────────────────────────────────────────────────────╯
```

#### B. Report Preview Overlay

```
╭─ LAPORAN — aud_001 (immunefi.md) ──────────────────────────────────────── X ─╮
│  # Critical: Reentrancy in USDe.mint()                                        │
│  **Severity:** Critical | **Program:** Ethena | **Bounty:** Up to $1,000,000  │
│  **Contract:** 0x4c9edd5852cd905f086c759e8383e09bff1e68b3                     │
│                                                                                │
│  ## Vulnerability Description                                                  │
│  The `mint()` function calls an external contract before updating...           │
│  [scroll untuk selengkapnya]                                                   │
│                                                                                │
│  [Esc] Tutup  [e] Export  [s] /submit aud_001  [c] Copy path                 │
╰────────────────────────────────────────────────────────────────────────────────╯
```

### 2.8 Keyboard Shortcuts

| Key | Aksi |
|-----|------|
| `Enter` | Buka Exploit Engine Detail overlay |
| `r` | Preview laporan terbaru |
| `n` | Preview status notifikasi |
| `e` | Export laporan ke file |
| `s` | Jalankan `/submit <audit_id>` untuk audit terbaru |
| `Esc` | Tutup overlay |

### 2.9 Slash Commands yang Relevan

```
/exploit <audit_id>          — Trigger manual exploit untuk audit (jika classifier sudah selesai)
/exploit-status <audit_id>   — Status exploit engine untuk audit
/report <audit_id>           — Preview laporan di overlay
/report export <audit_id>    — Export laporan ke ~/.vyper/reporter/<audit_id>/
/submit <audit_id>           — Assist submission ke Immunefi
/notify test                 — Kirim test notification ke semua channel
```

### 2.10 Interaksi dengan Service Backend

```
TUI Action                    HTTP Endpoint (via CommandRouter)
──────────────────────────────────────────────────────────────────────────────
/exploit <id>          →     POST http://localhost:8006/run
                              {"audit_id": "<id>", "finding_ids": [...]}

/exploit-status <id>   →     GET  http://localhost:8006/status/<id>

/report <id>           →     GET  http://localhost:8007/report/<id>

/report export <id>    →     POST http://localhost:8007/export/<id>
                              {"format": ["immunefi", "full"]}

/notify test           →     POST http://localhost:8008/test
                              {"channels": ["discord", "telegram", "email"]}
```

### 2.11 Fase Implementasi

| Fase | Deliverable | Estimasi |
|------|-------------|----------|
| **Fase 1** | Baris ringkas 3 service (status + last activity) | 2 hari |
| **Fase 2** | Auto-expand saat `exploit.phase_update` event masuk | 1 hari |
| **Fase 3** | Render 5-phase progress bar saat exploit berjalan | 2 hari |
| **Fase 4** | Exploit Engine Detail overlay (drill-down `Enter`) | 2 hari |
| **Fase 5** | Report preview overlay + export action | 2 hari |
| **Fase 6** | Notifier status rendering + test notif command | 1 hari |
| **Testing** | Unit test event handler + integration test SSE | 2 hari |
| **Total** | | **~12 hari** |

---

## 3. Layer 5 — Orchestration & Agent Panel

### 3.1 Deskripsi & Tanggung Jawab

Panel ini mengawasi **jantung kendali** ekosistem VYPER:
- **11-Orchestrator** — Mesin state machine pipeline; menerima request audit, mengelola
  queue, mendispatch task ke service yang tepat, dan mengendalikan retry/timeout
- **14-Agent (Antonio)** — ReAct agent utama; menjalankan audit end-to-end secara otonom,
  berinteraksi dengan semua service, mengelola memori, dan beroperasi dalam team mode

**Mengapa ini berbeda dari AntonioPanel:** `AntonioPanel` (yang sudah ada) fokus pada
*reasoning detail* — THOUGHT/ACTION/OBSERVE langkah per langkah. `OrchestrationAgentPanel`
fokus pada *operational health* — queue, session aktif, resource governor, daemon cycle,
dan health orchestrator itu sendiri.

### 3.2 Services yang Dimonitor

```
Service             Port    Tanggung Jawab
──────────────────────────────────────────────────────────────────────────────
11-orchestrator     8009    State machine pipeline, priority queue,
                            retry logic, audit lifecycle management
14-agent (Antonio)  8021    ReAct agent, team mode coordination,
                            daemon task scheduler, memory management
```

### 3.3 UI Layout & Mockup

#### Tampilan Default (Mode FULL)

```
╭─ L5: ORCHESTRATION & AGENT ──────────────────────────────────────── [5] ──╮
│  11-Orchestr  ✅ ⣾ BUSY   coordinating aud_001–003  queue:5  slots:1/2    │
│  14-Agent     ✅ ⣾ BUSY   session agent-abc123  step:7/25  skill:scan ⣾   │
╰─────────────────────────────────────────────────────────────────────────────╯
```

#### Tampilan dengan Detail Queue (setelah fokus / expand)

```
╭─ L5: ORCHESTRATION & AGENT ─────────────────────────────────── EXPANDED ──╮
│  ┌─ 11-ORCHESTRATOR ─────────────────────────────────── ⣾ COORDINATING ──┐ │
│  │  Active: 3 audits  │  Queue: 5  │  Scanner: 1/2  │  AI: 0/3           │ │
│  │                                                                         │ │
│  │  ACTIVE PIPELINE                                                        │ │
│  │  aud_001  [AI_ANALYSIS    ] ████████░░ 67%  0x4c9edd / Ethena          │ │
│  │  aud_002  [SCANNING       ] ███░░░░░░ 20%  0xdAC17F / Tether          │ │
│  │  aud_003  [PENDING        ] ░░░░░░░░  0%  0xA0b86  / Circle           │ │
│  │                                                                         │ │
│  │  RETRY QUEUE                                                            │ │
│  │  aud_005  scan_failed → retry #1 (scheduled 10:27:00)                 │ │
│  └─────────────────────────────────────────────────────────────────────── ┘ │
│  ┌─ 14-AGENT (ANTONIO) ─────────────── session: agent-abc123  step:7/25 ──┐ │
│  │  Mode: FULL_AUDIT   LLM: claude-sonnet-4-6   Skills: 4/10 used        │ │
│  │  Current: ACTION → scan_contract ⣾  (mythril, elapsed: 28s)           │ │
│  │  Daemon : RUNNING   Cycle #847   Next task: auto_hunt @ 10:30:00      │ │
│  └─────────────────────────────────────────────────────────────────────── ┘ │
╰─────────────────────────────────────────────────────────────────────────────╯
```

#### Tampilan saat Daemon Mode Aktif (tanpa sesi agent aktif)

```
╭─ L5: ORCHESTRATION & AGENT ──────────────────────────────────────────── [5]─╮
│  11-Orchestr  ✅ 💤 idle   No active audits  queue:0                         │
│  14-Agent     ✅ 🔄 DAEMON  Cycle #847  auto_hunt ⣾ scanning Immunefi...    │
╰──────────────────────────────────────────────────────────────────────────────╯
```

#### Tampilan Team Mode Aktif

```
╭─ L5: ORCHESTRATION & AGENT ──────────────────── TEAM MODE ──────────── [5] ─╮
│  11-Orchestr  ✅ ⣾ BUSY   coordinating team audit  aud_010                   │
│  14-Agent     ✅ ⣾ LEAD   Delegating to Code Analyst → scan 0x4c9edd        │
│               ├ Code Analyst  ⣾ scanning (slither 45%)                       │
│               ├ Exploit Spec  💤 idle                                         │
│               └ Report Writer 💤 idle                                         │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### 3.4 Event Subscriptions

```python
EVENT YANG DIDENGARKAN              TINDAKAN DI PANEL
──────────────────────────────────────────────────────────────────────────────
service.activity (11-orch)          Update baris orchestrator (status, task)
service.activity (14-agent)         Update baris agent (status, session info)
audit.state_change                  Refresh daftar audit aktif di orchestrator
audit.completed                     Hapus dari daftar aktif
resource.slot_change                Update counter scanner/AI/exploit slots
agent.step                          Update "step X/Y" di baris agent
agent.skill_call                    Update "skill: <name> ⣾" di baris agent
agent.delegation                    Jika team mode → update sub-agent rows
daemon.cycle                        Update nomor cycle + task daemon saat ini
agent.team_started                  Switch ke tampilan team mode
agent.team_completed                Kembali ke tampilan normal
audit.retry_scheduled               Tampilkan di retry queue
```

### 3.5 State yang Dikelola di AppState

```python
# Tambahkan ke VyperState

@dataclass
class OrchestratorState:
    status: str                     # "idle" | "busy" | "error"
    active_audit_ids: list[str]     # max 3 concurrent
    queue_size: int
    scanner_slots: tuple[int, int]  # (used, max)
    ai_slots: tuple[int, int]
    exploit_slots: tuple[int, int]
    retry_queue: list[RetryItem]
    uptime_s: float

@dataclass
class RetryItem:
    audit_id: str
    failed_stage: str
    retry_number: int
    scheduled_at: datetime

@dataclass
class AgentOperationalState:
    # Berbeda dari AgentSession yang ada — ini focus operational
    session_id: str | None
    mode: str                       # "idle" | "full_audit" | "team" | "daemon"
    current_step: int | None
    total_steps: int | None
    current_skill: str | None
    skill_elapsed_s: int | None
    llm_model: str
    skills_used: list[str]
    daemon_status: DaemonStatus | None
    team_members: list[TeamMember] | None

@dataclass
class TeamMember:
    name: str                       # "Code Analyst", "Exploit Spec", dll
    status: str                     # "idle" | "running" | "done"
    current_task: str | None
    progress: int | None

# Di VyperState:
orchestrator_state: OrchestratorState | None = None
agent_operational: AgentOperationalState | None = None
```

### 3.6 Implementasi Python (Textual Widget)

```python
# src/panels/orchestration_agent_panel.py

class OrchestrationAgentPanel(Widget):
    """
    Layer 5 Panel: 11-Orchestrator + 14-Agent.
    Dual-section: orchestrator di atas, agent di bawah.
    Auto-expand pada team mode atau saat ada audit aktif.
    """

    is_team_mode = reactive(False)
    is_expanded = reactive(False)

    TEAM_MODE_COLORS = {
        "idle": "dim",
        "running": "green",
        "done": "bright_green",
        "failed": "red",
    }

    def on_mount(self):
        bus = self.app.event_bus

        @bus.on("service.activity")
        async def _on_activity(event):
            if event.service in ("11-orchestrator", "14-agent"):
                # Update state dan refresh
                self._update_service_state(event)
                self.refresh()

        @bus.on("audit.state_change")
        async def _on_audit_state(event):
            orch = self.app.state.orchestrator_state
            if orch:
                self.refresh()

        @bus.on("resource.slot_change")
        async def _on_slots(event):
            orch = self.app.state.orchestrator_state
            if orch:
                slot_type = event.payload["slot_type"]
                used = event.payload["used"]
                max_val = event.payload["max"]
                if slot_type == "scanner":
                    orch.scanner_slots = (used, max_val)
                elif slot_type == "ai":
                    orch.ai_slots = (used, max_val)
                elif slot_type == "exploit":
                    orch.exploit_slots = (used, max_val)
                self.refresh()

        @bus.on("agent.step")
        async def _on_step(event):
            ops = self.app.state.agent_operational
            if ops:
                ops.current_step = event.payload["step_number"]
                ops.total_steps = event.payload.get("total_steps")
            self.refresh()

        @bus.on("agent.skill_call")
        async def _on_skill(event):
            ops = self.app.state.agent_operational
            if ops:
                ops.current_skill = event.payload["skill_name"]
                ops.skill_elapsed_s = 0
            self.refresh()

        @bus.on("agent.observation")
        async def _on_observe(event):
            ops = self.app.state.agent_operational
            if ops:
                ops.current_skill = None
                ops.skill_elapsed_s = None
            self.refresh()

        @bus.on("agent.delegation")
        async def _on_delegation(event):
            ops = self.app.state.agent_operational
            if ops and ops.team_members:
                target = event.payload["target_agent"]
                task = event.payload["task_summary"]
                for member in ops.team_members:
                    if member.name.lower() in target.lower():
                        member.status = "running"
                        member.current_task = task
                self.is_team_mode = True
            self.refresh()

        @bus.on("agent.team_started")
        async def _on_team_start(event):
            self.is_team_mode = True
            self.is_expanded = True
            self.refresh()

        @bus.on("daemon.cycle")
        async def _on_daemon(event):
            ops = self.app.state.agent_operational
            if ops and ops.daemon_status:
                ops.daemon_status.cycle_number = event.payload["cycle"]
                ops.daemon_status.current_task = event.payload.get("current_task")
            self.refresh()

    def render(self):
        sections = []

        # Section 1: Orchestrator
        sections.append(self._render_orchestrator())

        # Section 2: Agent
        sections.append(self._render_agent())

        return "\n".join(sections)

    def _render_orchestrator(self) -> str:
        orch = self.app.state.orchestrator_state
        if not orch:
            return "  11-Orchestr  ✅ ? unknown"

        status_icon = {"idle": "💤", "busy": "⣾", "error": "⚠️"}.get(orch.status, "?")
        slots_str = (
            f"scanner:{orch.scanner_slots[0]}/{orch.scanner_slots[1]}  "
            f"ai:{orch.ai_slots[0]}/{orch.ai_slots[1]}"
        )

        if not self.is_expanded:
            n_active = len(orch.active_audit_ids)
            return (
                f"  11-Orchestr  ✅ {status_icon} {orch.status.upper():<8}"
                f"  {n_active} audit aktif  queue:{orch.queue_size}  {slots_str}"
            )
        else:
            # Expanded: tampilkan audit aktif
            lines = [
                f"  ┌─ 11-ORCHESTRATOR ─────────── {status_icon} "
                f"active:{len(orch.active_audit_ids)}  queue:{orch.queue_size}  {slots_str} ─┐",
            ]
            for aid in orch.active_audit_ids[:3]:
                record = self.app.state.active_audits.get(aid)
                if record:
                    bar = self._mini_bar(record.progress)
                    lines.append(
                        f"  │  {aid}  [{record.state:<15}] {bar} {record.progress}%  "
                        f"{record.contract_address[:8]}..."
                    )
            if orch.retry_queue:
                lines.append("  │  RETRY:")
                for item in orch.retry_queue[:2]:
                    lines.append(
                        f"  │  {item.audit_id}  {item.failed_stage} → retry #{item.retry_number}"
                    )
            lines.append("  └" + "─" * 70 + "┘")
            return "\n".join(lines)

    def _render_agent(self) -> str:
        ops = self.app.state.agent_operational
        if not ops:
            return "  14-Agent     ✅ ? unknown"

        if ops.mode == "daemon" and ops.daemon_status:
            ds = ops.daemon_status
            task = ds.current_task or "monitoring"
            return (
                f"  14-Agent     ✅ 🔄 DAEMON  Cycle #{ds.cycle_number}  "
                f"{task} ⣾"
            )

        if ops.mode == "team" and self.is_team_mode:
            lines = [
                f"  14-Agent     ✅ ⣾ LEAD   Coordinating team"
            ]
            if ops.team_members:
                for m in ops.team_members:
                    icon = {"idle": "💤", "running": "⣾", "done": "✅"}.get(m.status, "?")
                    task_str = f"  {m.current_task[:40]}" if m.current_task else ""
                    lines.append(f"               ├ {m.name:<15} {icon}{task_str}")
            return "\n".join(lines)

        if ops.mode in ("full_audit", "idle") and ops.session_id:
            step_str = (
                f"step:{ops.current_step}/{ops.total_steps}"
                if ops.current_step else "idle"
            )
            skill_str = ""
            if ops.current_skill:
                elapsed = ops.skill_elapsed_s or 0
                skill_str = f"  skill:{ops.current_skill} ⣾ ({elapsed}s)"
            return (
                f"  14-Agent     ✅ ⣾ BUSY   {ops.session_id}  "
                f"{step_str}{skill_str}"
            )

        return f"  14-Agent     ✅ 💤 idle   LLM: {ops.llm_model}"

    def _mini_bar(self, pct: int, width: int = 8) -> str:
        filled = int(pct / 100 * width)
        return "█" * filled + "░" * (width - filled)

    def on_key(self, event):
        if event.key == "enter":
            self.is_expanded = not self.is_expanded
            self.refresh()
        elif event.key == "q":
            self._show_queue_overlay()
        elif event.key == "d":
            self._show_delegation_chain()
        elif event.key == "m":
            self._show_memory_panel()
```

### 3.7 Drill-Down Overlays

Overlay yang dipicu dari panel ini (selain yang sudah ada di arsitektur):

#### A. Orchestrator Queue Detail

```
╭─ ORCHESTRATOR — Priority Queue ────────────────────────────────────── X ─╮
│  5 audits pending                                                          │
│                                                                            │
│  Rank  Audit ID   Contract         Score   Wait   Program                 │
│  ─────────────────────────────────────────────────────────────────────    │
│   1    aud_004    0x1f97...        9.2     04:00  Aave V3 (critical)      │
│   2    aud_005    0x7fc...         8.7     02:00  Compound V3             │
│   3    aud_006    0xBeef...        6.1     08:00  Uniswap V4              │
│   4    aud_007    0x3fC...         4.3     15:00  Curve Finance           │
│   5    aud_008    0x5e28...        3.1     22:00  Lido                    │
│                                                                            │
│  RETRY: aud_005  scan_failed → retry #1  sched: 10:27:00                 │
│                                                                            │
│  [b] Boost  [p] Pause  [r] Resume  [x] Clear  [Esc] Tutup               │
╰────────────────────────────────────────────────────────────────────────────╯
```

#### B. Agent Delegation Chain

```
╭─ AGENT DELEGATION CHAIN ───────────────────────────── session: abc123 X ─╮
│  ANTONIO (Lead)                                                            │
│  └→ [10:23:41] 08-exploit   "run PoC for vuln_001"          ⣾ pending    │
│  └→ [10:22:17] 11-orch      "check queue for 0x4c9edd"       ✅ done      │
│                └→ [10:21:55] 04-scanner  "slither+mythril"   ✅ done      │
│                                                                            │
│  PENDING DELEGATION: antonio → 09-reporter  "generate report"             │
│  Expected next: notifying, then completed                                  │
│                                                                            │
│  [Esc] Tutup   [t] Buka TraceViewer                                       │
╰────────────────────────────────────────────────────────────────────────────╯
```

### 3.8 Keyboard Shortcuts

| Key | Aksi |
|-----|------|
| `Enter` | Toggle expand/collapse detail |
| `q` | Buka Queue Detail overlay |
| `d` | Buka Delegation Chain overlay |
| `m` | Buka Memory Panel overlay |
| `t` | Buka Trace Viewer untuk session aktif |
| `b` | Boost prioritas audit pertama di queue |
| `p` | Pause queue |

### 3.9 Slash Commands yang Relevan

```
/queue                     — Tampilkan queue detail (sama dengan key q)
/boost <audit_id> [+N]     — Boost prioritas
/pause                     — Pause queue
/resume                    — Resume queue
/agent-status              — Status lengkap Antonio
/daemon status             — Status daemon cycle
/daemon start              — Start daemon
/daemon stop               — Stop daemon
/team run <address>        — Mulai team audit
/agent-stop <session_id>   — Stop sesi agent
/memory                    — Tampilkan memory stats
/memory-search <query>     — Cari di vector memory
```

### 3.10 Fase Implementasi

| Fase | Deliverable | Estimasi |
|------|-------------|----------|
| **Fase 1** | Baris ringkas 2 service (status + ringkasan) | 2 hari |
| **Fase 2** | Orchestrator: daftar audit aktif + slot info | 2 hari |
| **Fase 3** | Agent: step/skill display + daemon mode | 2 hari |
| **Fase 4** | Team mode tree view (sub-agent rows) | 3 hari |
| **Fase 5** | Queue Detail overlay | 2 hari |
| **Fase 6** | Delegation Chain overlay | 2 hari |
| **Testing** | Event handler + state update tests | 2 hari |
| **Total** | | **~15 hari** |

---

## 4. Layer 6 — Infra & Delivery Panel

### 4.1 Deskripsi & Tanggung Jawab

Panel ini mengawasi **fondasi infrastruktur** yang memungkinkan hasil audit sampai ke dunia luar:
- **12-Webhook** — Menerima dan mendispatch external webhook (misalnya dari Immunefi, Alchemy Notify)
- **13-Upkeep** — Scheduled maintenance: cleanup file lama, health check periodik, backup data
- **15-Dashboard** — SSE hub utama; juga menyediakan API aggregasi dan metric endpoint
- **16-Submission** — Otomasi submission bounty ke Immunefi; form filling, API calls

**Mengapa panel ini penting:** Tanpa monitoring infra layer, operator bisa kehilangan
webhook inbound (misalnya notifikasi batas bounty baru dari Immunefi), upkeep failure
yang menyebabkan disk penuh, atau submission yang gagal diam-diam.

### 4.2 Services yang Dimonitor

```
Service             Port    Tanggung Jawab
──────────────────────────────────────────────────────────────────────────────
12-webhook          8010    Inbound webhook handler (dari Immunefi, Alchemy,
                            custom sources); rate limiting, signature verify
13-upkeep           8012    Cron job: cleanup ~/.vyper/*, health check,
                            metrics rotation, DB vacuum, log rotation
15-dashboard        8000    SSE event hub, /metrics aggregator, proxy layer
                            ke semua backend service
16-submission       8018    Immunefi submission automation: draft, review,
                            submit, track status response
```

### 4.3 UI Layout & Mockup

#### Tampilan Default (Mode FULL — 4 baris compact)

```
╭─ L6: INFRA & DELIVERY ─────────────────────────────────────────── [6] ──╮
│  12-Webhook    ✅ 💤 idle    Last: immunefi-alert 3 bounties (2m ago)    │
│  13-Upkeep     ✅ 💤 idle    Next: log_rotate @ 11:00  disk: 67%         │
│  15-Dashboard  ✅ ⣾ BUSY    SSE: 2 clients  pub: 847 events/hr           │
│  16-Submission ✅ 💤 idle    Last: aud_001 → Immunefi submitted (1h ago) │
╰─────────────────────────────────────────────────────────────────────────╯
```

#### Tampilan saat Webhook Inbound

```
╭─ L6: INFRA & DELIVERY ─────────────────── 📨 WEBHOOK RECEIVED ────── [6]─╮
│  12-Webhook    ✅ ⣾ BUSY    ← immunefi: new program "Aave V4" bounty $2M │
│  13-Upkeep     ✅ 💤 idle   Next: health_check @ 10:30  disk: 67%         │
│  15-Dashboard  ✅ ⣾ BUSY   SSE: 2 clients  pub: 847 events/hr             │
│  16-Submission ✅ 💤 idle   queue: 0  last: aud_001 submitted 1h ago       │
│                                                                             │
│  📨 WEBHOOK QUEUE: 1 pending                                               │
│  [10:26:41] immunefi.program_update  "Aave V4"  $2M max  → processing    │
╰─────────────────────────────────────────────────────────────────────────────╯
```

#### Tampilan saat Submission Berjalan

```
╭─ L6: INFRA & DELIVERY ──────────────────── 📤 SUBMITTING ───────── [6] ─╮
│  12-Webhook    ✅ 💤 idle   Last: immunefi-alert (5m ago)                 │
│  13-Upkeep     ✅ 💤 idle   disk: 67%  next: log_rotate @ 11:00           │
│  15-Dashboard  ✅ ⣾ BUSY   SSE: 2 clients  pub: 891 events/hr             │
│  16-Submission ✅ ⣾ BUSY   Submitting aud_001 → Immunefi...               │
│  ├ [1/4] Auth check           ✅ 0.4s                                      │
│  ├ [2/4] Format report        ✅ 1.2s                                      │
│  ├ [3/4] Upload attachments   ⣾ running (poc.sol, proof.json)             │
│  └ [4/4] Submit form          ○ waiting                                    │
╰─────────────────────────────────────────────────────────────────────────────╯
```

#### Tampilan saat Upkeep Berjalan

```
╭─ L6: INFRA & DELIVERY ─────────────────── 🔧 UPKEEP RUNNING ──── [6] ─╮
│  12-Webhook    ✅ 💤 idle   Last: immunefi-alert (12m ago)               │
│  13-Upkeep     ✅ ⣾ BUSY   log_rotate ⣾ [████░░░░] 45%  freed: 1.2 GB  │
│  15-Dashboard  ✅ ⣾ BUSY   SSE: 1 client  pub: 612 events/hr            │
│  16-Submission ✅ 💤 idle   queue: 0                                     │
╰──────────────────────────────────────────────────────────────────────────╯
```

#### Tampilan saat Dashboard Bermasalah (SSE disconnected)

```
╭─ L6: INFRA & DELIVERY ────────────────── ⚠️ SSE DISCONNECTED ─── [6] ─╮
│  12-Webhook    ✅ 💤 idle                                                │
│  13-Upkeep     ✅ 💤 idle                                                │
│  15-Dashboard  ⚠️ ⚠️ ERROR   SSE hub unreachable — reconnecting... (3s) │
│  16-Submission ✅ 💤 idle                                                │
│                                                                          │
│  ⚠️ EventBus disconnected. Polling fallback aktif (interval: 5s)        │
╰──────────────────────────────────────────────────────────────────────────╯
```

### 4.4 Event Subscriptions

```python
EVENT YANG DIDENGARKAN              TINDAKAN DI PANEL
──────────────────────────────────────────────────────────────────────────────
service.activity (12-webhook)       Update baris webhook (status, last event)
service.activity (13-upkeep)        Update baris upkeep (task, disk usage)
service.activity (15-dashboard)     Update baris dashboard (clients, events/hr)
service.activity (16-submission)    Update baris submission (progress)
service.health (15-dashboard)       Jika health berubah → tampilkan warning SSE
webhook.received                    Append ke webhook queue, expand panel
webhook.processed                   Update last processed, compact panel
upkeep.task_started                 Expand baris upkeep dengan progress bar
upkeep.task_completed               Kembali ke ringkasan + disk usage
upkeep.disk_warning                 Highlight baris 13-upkeep merah (> 85%)
submission.step_update              Update progress submission step 1–4
submission.completed                Tampilkan status + link submission ID
submission.failed                   Tampilkan error + saran tindakan
sse.client_connected                Increment client counter di dashboard row
sse.client_disconnected             Decrement counter
```

### 4.5 State yang Dikelola di AppState

```python
# Tambahkan ke VyperState

@dataclass
class WebhookState:
    status: str                     # "idle" | "busy" | "error"
    pending_queue: list[WebhookItem]
    last_received: WebhookItem | None
    events_processed_today: int

@dataclass
class WebhookItem:
    source: str                     # "immunefi" | "alchemy" | "custom"
    event_type: str                 # "program_update" | "bounty_claimed" | dll
    summary: str
    received_at: datetime
    status: str                     # "pending" | "processed" | "failed"

@dataclass
class UpkeepState:
    status: str                     # "idle" | "busy"
    current_task: str | None        # "log_rotate" | "health_check" | dll
    task_progress: int | None       # 0–100
    disk_usage_pct: float           # 0.0–100.0
    disk_freed_gb: float | None
    next_scheduled: dict            # {"log_rotate": datetime, "health_check": datetime}

@dataclass
class DashboardInfraState:
    # Berbeda dari dashboard connection state di EventBus
    sse_client_count: int
    events_published_hr: int        # rolling 1-hour count
    last_event_at: datetime | None
    health: bool

@dataclass
class SubmissionState:
    audit_id: str | None
    status: str                     # "idle" | "running" | "completed" | "failed"
    current_step: int               # 1–4
    step_results: dict              # {1: {"done": True, "duration": 0.4}, ...}
    submission_id: str | None       # Immunefi submission ID
    submitted_at: datetime | None
    error_msg: str | None
    queue: list[str]                # audit_id menunggu giliran

# Di VyperState:
webhook_state: WebhookState | None = None
upkeep_state: UpkeepState | None = None
dashboard_infra: DashboardInfraState | None = None
submission_state: SubmissionState | None = None
```

### 4.6 Implementasi Python (Textual Widget)

```python
# src/panels/infra_delivery_panel.py

class InfraDeliveryPanel(Widget):
    """
    Layer 6 Panel: 12-Webhook, 13-Upkeep, 15-Dashboard, 16-Submission.
    Default: 4 baris ringkas.
    Auto-expand saat webhook masuk, upkeep berjalan, atau submission aktif.
    Tampilkan warning jika disk > 85% atau SSE disconnected.
    """

    DISK_WARNING_THRESHOLD = 85.0
    SUBMISSION_STEPS = [
        "Auth check",
        "Format report",
        "Upload attachments",
        "Submit form",
    ]

    webhook_pending = reactive(False)
    submission_running = reactive(False)
    upkeep_running = reactive(False)
    sse_disconnected = reactive(False)

    def on_mount(self):
        bus = self.app.event_bus

        @bus.on("service.activity")
        async def _on_activity(event):
            if event.service in ("12-webhook", "13-upkeep", "15-dashboard", "16-submission"):
                self.app.state.service_activities[event.service] = event.payload
                self.refresh()

        @bus.on("service.health")
        async def _on_health(event):
            if event.service == "15-dashboard":
                healthy = event.payload.get("healthy", True)
                self.sse_disconnected = not healthy
                infra = self.app.state.dashboard_infra
                if infra:
                    infra.health = healthy
                self.refresh()

        @bus.on("webhook.received")
        async def _on_webhook_recv(event):
            wh = self.app.state.webhook_state
            if wh:
                item = WebhookItem(
                    source=event.payload["source"],
                    event_type=event.payload["event_type"],
                    summary=event.payload["summary"],
                    received_at=datetime.fromisoformat(event.timestamp),
                    status="pending",
                )
                wh.pending_queue.append(item)
                wh.last_received = item
            self.webhook_pending = True
            self.refresh()

        @bus.on("webhook.processed")
        async def _on_webhook_proc(event):
            wh = self.app.state.webhook_state
            if wh and wh.pending_queue:
                wh.pending_queue.pop(0)
                wh.events_processed_today += 1
            if not wh or not wh.pending_queue:
                self.webhook_pending = False
            self.refresh()

        @bus.on("upkeep.task_started")
        async def _on_upkeep_start(event):
            state = self.app.state.upkeep_state
            if state:
                state.current_task = event.payload["task"]
                state.task_progress = 0
            self.upkeep_running = True
            self.refresh()

        @bus.on("upkeep.task_completed")
        async def _on_upkeep_done(event):
            state = self.app.state.upkeep_state
            if state:
                state.current_task = None
                state.disk_freed_gb = event.payload.get("freed_gb")
                state.disk_usage_pct = event.payload.get("disk_pct", state.disk_usage_pct)
            self.upkeep_running = False
            self.refresh()

        @bus.on("upkeep.disk_warning")
        async def _on_disk_warn(event):
            state = self.app.state.upkeep_state
            if state:
                state.disk_usage_pct = event.payload["disk_pct"]
            self.refresh()

        @bus.on("submission.step_update")
        async def _on_submit_step(event):
            state = self.app.state.submission_state
            if state:
                step = event.payload["step"]
                done = event.payload["done"]
                dur = event.payload.get("duration_s")
                state.current_step = step
                state.step_results[step] = {"done": done, "duration": dur}
            self.submission_running = True
            self.refresh()

        @bus.on("submission.completed")
        async def _on_submit_done(event):
            state = self.app.state.submission_state
            if state:
                state.status = "completed"
                state.submission_id = event.payload.get("submission_id")
                state.submitted_at = datetime.now()
            self.submission_running = False
            self.refresh()

        @bus.on("submission.failed")
        async def _on_submit_fail(event):
            state = self.app.state.submission_state
            if state:
                state.status = "failed"
                state.error_msg = event.payload.get("error")
            self.submission_running = False
            self.refresh()

        @bus.on("sse.client_connected")
        async def _on_sse_connect(event):
            infra = self.app.state.dashboard_infra
            if infra:
                infra.sse_client_count += 1
            self.refresh()

        @bus.on("sse.client_disconnected")
        async def _on_sse_disconnect(event):
            infra = self.app.state.dashboard_infra
            if infra:
                infra.sse_client_count = max(0, infra.sse_client_count - 1)
            self.refresh()

    def render(self):
        lines = [
            self._render_webhook_row(),
            self._render_upkeep_row(),
            self._render_dashboard_row(),
            self._render_submission_row(),
        ]

        # Optional expanded sections
        wh = self.app.state.webhook_state
        if self.webhook_pending and wh and wh.pending_queue:
            lines.append("")
            lines.append(f"  📨 WEBHOOK QUEUE: {len(wh.pending_queue)} pending")
            for item in wh.pending_queue[:3]:
                t = item.received_at.strftime("%H:%M:%S")
                lines.append(f"  [{t}] {item.source}.{item.event_type}  {item.summary[:50]}")

        if self.submission_running:
            sub = self.app.state.submission_state
            if sub:
                lines.append("")
                for i, step_name in enumerate(self.SUBMISSION_STEPS, 1):
                    result = sub.step_results.get(i)
                    if result and result["done"]:
                        dur = f"  {result['duration']:.1f}s" if result["duration"] else ""
                        lines.append(f"  ├ [{i}/4] {step_name:<22} ✅{dur}")
                    elif sub.current_step == i:
                        lines.append(f"  ├ [{i}/4] {step_name:<22} ⣾ running")
                    else:
                        lines.append(f"  └ [{i}/4] {step_name:<22} ○ waiting")

        if self.sse_disconnected:
            lines.append("")
            lines.append("  ⚠️  EventBus disconnected. Polling fallback aktif (5s)")

        border_style = "red" if self.sse_disconnected else "dim"
        title = "L6: INFRA & DELIVERY"
        if self.sse_disconnected:
            title += " ⚠️ SSE DISCONNECTED"

        return "\n".join(lines)

    def _render_webhook_row(self) -> str:
        state = self.app.state.webhook_state
        if not state:
            return "  12-Webhook    ✅ ? unknown"

        if state.status == "busy" and state.pending_queue:
            item = state.pending_queue[0]
            return f"  12-Webhook    ✅ ⣾ BUSY    ← {item.source}: {item.summary[:45]}"

        if state.last_received:
            ago = self._time_ago(state.last_received.received_at)
            return (
                f"  12-Webhook    ✅ 💤 idle    "
                f"Last: {state.last_received.source}-{state.last_received.event_type} ({ago})"
            )

        return "  12-Webhook    ✅ 💤 idle"

    def _render_upkeep_row(self) -> str:
        state = self.app.state.upkeep_state
        if not state:
            return "  13-Upkeep     ✅ ? unknown"

        disk_pct = state.disk_usage_pct
        disk_color = "🔴" if disk_pct > self.DISK_WARNING_THRESHOLD else ""
        disk_str = f"  disk:{disk_pct:.0f}%{disk_color}"

        if state.current_task and self.upkeep_running:
            prog = state.task_progress or 0
            bar = self._mini_bar(prog)
            freed = f"  freed:{state.disk_freed_gb:.1f}GB" if state.disk_freed_gb else ""
            return f"  13-Upkeep     ✅ ⣾ BUSY    {state.current_task} [{bar}]{freed}"

        # Next scheduled task
        next_tasks = []
        if state.next_scheduled:
            for task, dt in list(state.next_scheduled.items())[:2]:
                next_tasks.append(f"{task} @ {dt.strftime('%H:%M')}")
        next_str = "  Next: " + ", ".join(next_tasks) if next_tasks else ""

        return f"  13-Upkeep     ✅ 💤 idle   {next_str}{disk_str}"

    def _render_dashboard_row(self) -> str:
        infra = self.app.state.dashboard_infra

        if self.sse_disconnected:
            return "  15-Dashboard  ⚠️ ⚠️ ERROR   SSE hub unreachable — reconnecting..."

        if not infra:
            return "  15-Dashboard  ✅ ? unknown"

        clients = infra.sse_client_count
        rate = infra.events_published_hr
        return f"  15-Dashboard  ✅ ⣾ BUSY    SSE: {clients} client(s)  pub: {rate} events/hr"

    def _render_submission_row(self) -> str:
        state = self.app.state.submission_state
        if not state:
            return "  16-Submission ✅ ? unknown"

        if state.status == "running" and state.audit_id:
            return f"  16-Submission ✅ ⣾ BUSY    Submitting {state.audit_id} → Immunefi..."

        if state.status == "completed" and state.submitted_at:
            ago = self._time_ago(state.submitted_at)
            sub_id = f"  ID: {state.submission_id}" if state.submission_id else ""
            return f"  16-Submission ✅ 💤 idle    Last: {state.audit_id} submitted ({ago}){sub_id}"

        if state.status == "failed":
            return f"  16-Submission ✅ ⚠️ ERROR   {state.audit_id} failed: {state.error_msg[:40]}"

        queue_str = f"  queue: {len(state.queue)}" if state.queue else ""
        return f"  16-Submission ✅ 💤 idle   {queue_str}"

    def _mini_bar(self, pct: int, width: int = 6) -> str:
        filled = int(pct / 100 * width)
        return "█" * filled + "░" * (width - filled)

    def _time_ago(self, dt: datetime) -> str:
        diff = (datetime.now() - dt).seconds
        if diff < 60:
            return f"{diff}s ago"
        elif diff < 3600:
            return f"{diff // 60}m ago"
        return f"{diff // 3600}h ago"

    def on_key(self, event):
        if event.key == "enter":
            self._open_service_detail()
        elif event.key == "w":
            self._open_webhook_log()
        elif event.key == "u":
            self._open_upkeep_schedule()
        elif event.key == "s":
            self._open_submission_status()
```

### 4.7 Drill-Down Overlays

#### A. Webhook Log Overlay

```
╭─ WEBHOOK LOG — 12-webhook ──────────────────────────────────────────── X ─╮
│  Source           Event Type           Status    Received         Summary   │
│  ──────────────────────────────────────────────────────────────────────── │
│  immunefi         program_update       ✅ done   10:26:41  "Aave V4 $2M"  │
│  immunefi         bounty_claimed       ✅ done   09:14:22  "Curve $300K"  │
│  alchemy          block.mined          ✅ done   09:00:01  "Block 21.5M"  │
│  immunefi         program_update       ✅ done   08:30:15  "Uniswap V4"  │
│                                                                              │
│  PENDING: 0   PROCESSED TODAY: 47   FAILED: 0                              │
│                                                                              │
│  [r] Replay webhook  [f] Filter by source  [Esc] Tutup                     │
╰────────────────────────────────────────────────────────────────────────────╯
```

#### B. Upkeep Schedule Overlay

```
╭─ UPKEEP SCHEDULE — 13-upkeep ───────────────────────────────────────── X ─╮
│  Disk Usage: 67% (threshold: 85%)                                           │
│  Data dir: ~/.vyper  Used: 134 GB / 200 GB                                  │
│                                                                              │
│  SCHEDULED TASKS                                                             │
│  Task                Interval    Next Run      Last Run     Duration        │
│  ─────────────────────────────────────────────────────────────────────────  │
│  health_check        5m          10:30:00      10:25:03     0.8s           │
│  log_rotate          1h          11:00:00      10:00:12     45.3s          │
│  metrics_rotation    6h          14:00:00      08:00:41     12.1s          │
│  stale_cleanup       24h         00:00:00      (yesterday)  2m 13s         │
│  memory_consolidate  24h         14:00:00      (yesterday)  8m 44s         │
│  db_vacuum           weekly      Mon 00:00     (last Mon)   1h 23m         │
│                                                                              │
│  [r] Run task now  [Esc] Tutup                                              │
╰────────────────────────────────────────────────────────────────────────────╯
```

#### C. Submission Status Overlay

```
╭─ SUBMISSION STATUS — 16-submission ────────────────────────────────── X ─╮
│  COMPLETED SUBMISSIONS                                                      │
│  ─────────────────────────────────────────────────────────────────────     │
│  aud_001  Immunefi #89234  Critical  Ethena/USDe  Submitted 10:05:32       │
│           Status: Under Review  Estimated bounty: $750K–$1M               │
│                                                                              │
│  aud_002  Immunefi #87901  High      Tether/USDT  Submitted 09:32:14       │
│           Status: Triaged  Response: "Valid, under review"                  │
│                                                                              │
│  PENDING QUEUE: 0                                                           │
│                                                                              │
│  [s] Submit next  [v] View on Immunefi  [Esc] Tutup                       │
╰────────────────────────────────────────────────────────────────────────────╯
```

### 4.8 Keyboard Shortcuts

| Key | Aksi |
|-----|------|
| `Enter` | Buka Service Detail overlay (logs + metrics) |
| `w` | Buka Webhook Log overlay |
| `u` | Buka Upkeep Schedule overlay |
| `s` | Buka Submission Status overlay |
| `d` | Buka Dashboard metrics detail |

### 4.9 Slash Commands yang Relevan

```
/webhook list                  — Tampilkan webhook queue dan log
/webhook replay <id>           — Replay webhook yang gagal
/upkeep status                 — Status lengkap upkeep tasks
/upkeep run <task>             — Run upkeep task manual
/upkeep disk                   — Tampilkan disk usage detail
/submit <audit_id>             — Queue audit untuk submission ke Immunefi
/submit status <audit_id>      — Status submission audit
/submit queue                  — Tampilkan submission queue
/dashboard clients             — Jumlah SSE client yang aktif
/dashboard events              — Event rate stats
```

### 4.10 Fase Implementasi

| Fase | Deliverable | Estimasi |
|------|-------------|----------|
| **Fase 1** | Baris ringkas 4 service (status + last activity) | 2 hari |
| **Fase 2** | Webhook: inbound event display + pending queue | 2 hari |
| **Fase 3** | Upkeep: task progress + disk usage warning | 2 hari |
| **Fase 4** | Dashboard infra: SSE client count + event rate | 1 hari |
| **Fase 5** | Submission: 4-step progress display | 2 hari |
| **Fase 6** | Webhook Log overlay | 1 hari |
| **Fase 7** | Upkeep Schedule overlay + manual trigger | 2 hari |
| **Fase 8** | Submission Status overlay | 2 hari |
| **Fase 9** | SSE disconnect detection + warning display | 1 hari |
| **Testing** | Event handler + disk warning + submission test | 2 hari |
| **Total** | | **~17 hari** |

---

## 5. Integrasi Lintas Panel

### 5.1 Event Flow Diagram

```
PIPELINE EVENT FLOW YANG MEMPENGARUHI KETIGA PANEL
══════════════════════════════════════════════════════════════════════════════

[11-Orchestrator] ─ audit.state_change: "classifying" ──────────────────────┐
                                                                             │
[07-Classifier] ── finding.classified: "CRITICAL" ──────────────────────────┤
                                                                             │
[EventBus / 15-Dashboard]                                                   │
         │                                                                  │
         ├──→ ExploitOutputPanel ◄─── exploit.phase_update ── [08-Exploit]  │
         │         │                                                        │
         │         │ report.generated                                       │
         │         ├──→ [09-Reporter]                                       │
         │         │                                                        │
         │         │ notification.sent                                      │
         │         └──→ [10-Notifier] ───────────────────────────────────── │
         │                                                                  │
         ├──→ OrchestrationAgentPanel ◄── agent.step ──── [14-Agent]       │
         │         │                                                        │
         │         │ resource.slot_change                                   │
         │         └──→ update slot counters                                │
         │                                                                  │
         └──→ InfraDeliveryPanel ◄───── webhook.received ─ [12-Webhook]    │
                   │                                                        │
                   │ submission.completed                                   │
                   └──→ [16-Submission] ─────────────────────────────────── ┘
```

### 5.2 State Sharing

| State | Owner | Consumers |
|-------|-------|-----------|
| `active_audits` | PipelineTracker | ExploitOutput, OrchestrationAgent |
| `active_exploits` | ExploitOutputPanel | StatusBar (profit summary) |
| `orchestrator_state` | OrchestrationAgent | ResourcePanel, StatusBar |
| `agent_operational` | OrchestrationAgent | AntonioPanel (cross-reference) |
| `webhook_state` | InfraDelivery | ChatPanel (co-pilot suggestions) |
| `submission_state` | InfraDelivery | ChatPanel (/submit assistance) |
| `upkeep_state` | InfraDelivery | StatusBar (disk warning) |

### 5.3 Co-Pilot Triggers

Antonio dapat mengirim saran ke `ChatPanel v2` berdasarkan event dari ketiga panel:

```python
# Contoh co-pilot trigger yang berasal dari ketiga panel

TRIGGER                            CO-PILOT MESSAGE
──────────────────────────────────────────────────────────────────────────────
exploit.confirmed (profit > $100K) "🎯 Exploit dikonfirmasi! Laporan Immunefi
                                    siap. Gunakan /submit aud_001 sekarang."

webhook.received (new program)     "📨 Program baru dari Immunefi: Aave V4
                                    dengan bounty $2M. Mulai audit? /audit ..."

upkeep.disk_warning (>85%)        "⚠️ Disk 87% penuh. Jalankan /upkeep run
                                    stale_cleanup untuk membebaskan ruang."

submission.completed               "✅ Submission aud_001 berhasil! ID: #89234.
                                    Pantau respons di /submit status aud_001."

agent.delegation (team started)    "🤖 Team mode aktif. Code Analyst sedang
                                    scanning. Eksplor sub-agent di panel L5."
```

### 5.4 StatusBar Integration

StatusBar (baris bawah permanen) mendapat kontribusi dari ketiga panel:

```
 Scanner:1/2  AI:0/3  Exploit:0/1  │  Queue:5  │  Disk:67%  │  SSE:2  │  LLM:claude-sonnet-4-6
      ↑ dari L5            ↑ dari L5    ↑ dari L6    ↑ dari L6   ↑ dari L5
```

---

## 6. Roadmap Implementasi

### 6.1 Urutan yang Direkomendasikan

```
MINGGU 1–2: Foundation
  ├ Setup struktur file src/panels/exploit_output_panel.py
  ├ Setup src/panels/orchestration_agent_panel.py
  ├ Setup src/panels/infra_delivery_panel.py
  └ Tambah state definitions ke state_store.py

MINGGU 3–4: Exploit & Output Panel (Fase 1–4)
  ├ Baris ringkas 3 service
  ├ Auto-expand logic (exploit.phase_update)
  ├ 5-phase progress bar rendering
  └ Exploit Engine Detail overlay

MINGGU 5: Exploit & Output Panel (Fase 5–6) + Testing
  ├ Report preview overlay
  ├ Notifier status rendering
  └ Unit tests ExploitOutputPanel

MINGGU 6–7: Orchestration & Agent Panel (Fase 1–4)
  ├ Baris ringkas 2 service
  ├ Orchestrator: daftar audit aktif
  ├ Agent: step/skill/daemon display
  └ Team mode tree view

MINGGU 8: Orchestration & Agent Panel (Fase 5–6) + Testing
  ├ Queue Detail overlay
  ├ Delegation Chain overlay
  └ Unit tests OrchestrationAgentPanel

MINGGU 9–10: Infra & Delivery Panel (Fase 1–6)
  ├ Baris ringkas 4 service
  ├ Webhook inbound display
  ├ Upkeep task + disk warning
  ├ Dashboard SSE metrics
  └ Submission 4-step progress

MINGGU 11: Infra & Delivery Panel (Fase 7–9) + Testing
  ├ Tiga overlay (Webhook, Upkeep, Submission)
  ├ SSE disconnect detection
  └ Unit tests InfraDeliveryPanel

MINGGU 12: Integration Testing & Polish
  ├ End-to-end test: full audit flow semua panel
  ├ Test co-pilot triggers lintas panel
  ├ StatusBar integration
  ├ Performance profiling (pastikan render < 16ms)
  └ SSH/tmux compatibility test
```

### 6.2 Total Estimasi

| Panel | Estimasi |
|-------|----------|
| Exploit & Output Panel | ~12 hari kerja |
| Orchestration & Agent Panel | ~15 hari kerja |
| Infra & Delivery Panel | ~17 hari kerja |
| Integration & Testing | ~8 hari kerja |
| **TOTAL** | **~52 hari kerja (~10.5 minggu)** |

### 6.3 Dependencies yang Harus Ada Sebelum Mulai

Sebelum ketiga panel dapat diimplementasi secara penuh, pastikan komponen berikut sudah ada:

- [ ] `EventBus` sudah berjalan dan subscribe ke SSE hub di `15-Dashboard`
- [ ] `AppState / VyperState` sudah memiliki slot untuk state baru ketiga panel
- [ ] `15-Dashboard` sudah publish event-event: `exploit.*`, `webhook.*`, `submission.*`, `upkeep.*`
- [ ] Service `08-exploit`, `12-webhook`, `13-upkeep`, `16-submission` sudah publish `EventPublisher`
- [ ] Overlay framework sudah ada (`app.push_screen()` pattern dari panel lain)
- [ ] `PollingFallback` tersedia untuk service yang belum publish SSE

---

## 7. Checklist QA

### 7.1 Exploit & Output Panel

- [ ] Saat `exploit.phase_update` diterima, panel auto-expand dan tampilkan progress bar
- [ ] Saat `exploit.confirmed`, border berubah hijau dan profit ditampilkan
- [ ] Saat `exploit.failed`, border berubah merah dan fase gagal di-highlight
- [ ] Saat tidak ada exploit aktif, panel kembali ke 3 baris ringkas
- [ ] Overlay Exploit Engine Detail bisa dibuka dengan `Enter` dan ditutup dengan `Esc`
- [ ] `/report aud_001` membuka report preview overlay
- [ ] `/submit aud_001` dapat dipanggil dari keyboard shortcut `s`
- [ ] Panel berfungsi di mode FULL, AUDIT, dan COMPACT

### 7.2 Orchestration & Agent Panel

- [ ] Saat audit baru masuk ke pipeline, daftar audit aktif di orchestrator update
- [ ] Slot counter (scanner/ai/exploit) update saat `resource.slot_change`
- [ ] Saat agent step berjalan, baris agent menampilkan step X/Y dan skill yang aktif
- [ ] Team mode tree view muncul saat `agent.team_started`
- [ ] Sub-agent rows update saat `agent.delegation`
- [ ] Daemon status (cycle, next task) update saat `daemon.cycle`
- [ ] Queue Detail overlay menampilkan 5 audit teratas dengan wait time
- [ ] `/boost aud_007 +3.0` berjalan dari keyboard shortcut `b`

### 7.3 Infra & Delivery Panel

- [ ] Saat webhook masuk, baris 12-webhook update dan webhook queue ditampilkan
- [ ] Saat upkeep task berjalan, baris 13-upkeep expand dengan progress bar
- [ ] Disk usage > 85% → baris upkeep di-highlight merah/orange
- [ ] SSE client count di baris 15-dashboard update real-time
- [ ] Saat `15-dashboard` down, panel tampilkan warning dan info polling fallback
- [ ] Submission 4-step progress muncul saat `submission.step_update`
- [ ] Submission berhasil → ditampilkan dengan submission ID
- [ ] Submission gagal → ditampilkan error message + saran tindakan
- [ ] Tiga overlay (Webhook Log, Upkeep Schedule, Submission Status) dapat dibuka/ditutup

### 7.4 Checklist Umum (Ketiga Panel)

- [ ] Semua rendering menggunakan event-driven update (tidak ada polling mandiri)
- [ ] State tidak disimpan lokal di panel — selalu via `AppState`
- [ ] Render function tidak memiliki side-effects (pure render)
- [ ] Animasi spinner (`⣾⣽⣻⢿⡿⣟⣯⣷`) berjalan smooth di 100ms interval
- [ ] Panel berfungsi via SSH tanpa mouse
- [ ] `Tab` dapat memindah fokus dari/ke ketiga panel
- [ ] `l` key dapat membuka log panel untuk setiap service yang difokus
- [ ] Panel tidak crash saat state `None` (graceful default rendering)
- [ ] Performance: render selesai dalam < 16ms (60fps target)

---

> **VYPER TUI v2** — *Layer 4–6: Dari Exploit ke Pengiriman, Semua Terpantau.*
>
> Dokumen ini adalah blueprint implementasi untuk tiga layer panel terakhir
> yang melengkapi ekosistem monitoring VYPER TUI v2. Setelah ketiga panel ini
> selesai, seluruh 20 microservice akan terpantau secara real-time dari satu terminal.
>
> Last updated: 2026-05-26