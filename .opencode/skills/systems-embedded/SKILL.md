---
name: systems-embedded
description: Embedded systems & IoT: Zephyr RTOS, FreeRTOS, bare-metal programming, FPGA/Verilog/VHDL, bootloaders, linker scripts, memory-mapped I/O, sensor protocols (I2C, SPI, UART), and low-power design
license: MIT
compatibility: opencode
metadata:
  audience: systems-engineers
  domain: systems
  paradigm: resource-constrained
  integrates_with: [systems-ebpf, security-crypto, backend-go, math-hpc]
---

## Systems Embedded & IoT Skill

### RTOS Platforms
- **Zephyr RTOS**: Device tree (DTS) for hardware description; Kconfig for build config; west meta-tool; threading (cooperative + preemptive); IPC (mailbox, message queue, pipe, stack); BLE mesh, Thread, Matter
- **FreeRTOS**: Tasks (priority preemptive); queues (FIFO, overwrite); semaphores (binary, counting, mutex with priority inheritance); software timers; stream buffers; event groups; idle hook for low-power

### Bare-Metal Fundamentals
- **Startup sequence**: Reset vector → stack pointer init → .data copy from flash → .bss zero → main()
- **Linker script**: MEMORY regions (FLASH, RAM); SECTIONS (.text, .rodata, .data, .bss, .stack)
- **Vector table**: Exception vectors at fixed addresses; default handler for unhandled interrupts
- **System tick**: SysTick (ARM) or timer peripheral; typically 1ms for RTOS
- **Critical sections**: Disable interrupts (short); BASEPRI (ARM, masks lower priority only)

### Memory-Mapped I/O
- **volatile**: Every hardware register read/write MUST be volatile
- **Bit manipulation**: SET (|=), CLEAR (&= ~), TOGGLE (^=), CHECK (&)
- **Memory barriers**: DSB/DMB/ISB (ARM); after register writes before relying on effects
- **DMA**: Direct Memory Access for bulk transfers; double buffering for continuous; interrupt on completion

### Communication Protocols
- **I2C**: 2-wire (SDA/SCL); 7/10-bit addressing; 100kHz/400kHz/1MHz/3.4MHz; start/stop/ack/nack
- **SPI**: 4-wire (MOSI/MISO/SCLK/CS); full duplex; no addressing; multi-slave via CS lines
- **UART**: Asynchronous serial; baud rate, start/stop bits, parity; RS232/RS485 levels
- **CAN**: Multi-master bus; 11/29-bit IDs; arbitration; error detection; CAN FD for higher bandwidth
- **BLE**: GAP (advertising/scanning), GATT (service/characteristic), pairing/bonding

### FPGA & HDL
- **Verilog/SystemVerilog**: always_comb, always_ff, assign; blocking (=) vs non-blocking (<=); FSM patterns
- **VHDL**: Entity/Architecture, process, signal/variable, component instantiation
- **High-Level Synthesis (HLS)**: C/C++ → Verilog; #pragma HLS for directives
- **Timing closure**: Setup/hold analysis; clock domain crossing (CDC); metastability handling (2-FF synchronizer)
- **IP cores**: PCIe, DDR controller, Ethernet MAC, AXI interconnect

### Low-Power Design
- **Sleep modes**: Deep sleep (RAM retention), stop, standby; wake-up sources (GPIO, RTC, LPUART)
- **Clock gating**: Disable unused peripheral clocks; dynamic frequency scaling
- **Duty cycling**: Wake → measure → transmit → sleep; minimize active time
- **Energy profiling**: Measure μA in sleep, mA active; target years on battery

### Firmware Update (OTA)
- **Dual-bank flash**: Swap active/inactive bank after verified update
- **Bootloader**: Verify signature (Ed25519), check version, rollback on failure
- **Delta updates**: Send only changed bytes; bsdiff or custom
- **MCUboot**: Zephyr/Mynewt bootloader; image validation; secure boot chain

### Common Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| Disabling all interrupts for long periods | System unresponsive; timer ticks lost; communication timeouts | Keep critical sections under ~100 cycles; use lock-free data structures |
| Busy-waiting instead of interrupts/DMA | Burns power; blocks other tasks; misses real-time deadlines | Configure peripheral interrupts; use DMA for bulk transfers |
| Global variables for ISR communication without `volatile` | Compiler optimizes away or caches reads; ISR updates invisible to main loop | Mark shared variables `volatile`; use atomic operations; use lock-free ring buffers |
| No watchdog timer | Hardware lockup never recovered; device requires manual reset | Enable independent watchdog (IWDG); reset in ~1-5 seconds |
| `printf` in ISR | Blocks interrupt context; extremely slow; causes nested interrupt issues | Buffer data and log from main loop; use ITM/SWO trace for real-time debugging |
| Unbounded stack usage | Stack overflow corrupts heap/globals; hard-to-debug crashes | Measure stack high-water mark; use static analysis; avoid recursion |
| Hardcoded memory addresses | Non-portable; breaks with firmware update; linker script changes | Use linker-defined symbols; generated headers from device tree |
| No firmware update mechanism | Bugs cannot be fixed in field; devices become permanently vulnerable | Implement OTA with dual-bank flash, signature verification, and rollback |
| Floating point in ISR | FPU context saving expensive; not all MCUs support it | Avoid float in ISRs; delegate to main thread; use fixed-point math |

### Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---|---|---|---|
| HardFault / BusFault | Invalid memory access; unaligned access; null pointer dereference | Read stacked PC from `HardFault_Handler`; check exception frame | Add MPU protection; validate pointers before dereference |
| Watchdog reset loop | Firmware crash → WDT reset → crash again → infinite loop | Check reset cause register; log last state before reset | Fix root cause; add persistent crash counter; fallback to safe mode |
| Stack overflow | ISR nesting too deep; local arrays too large | Fill stack with known pattern (0xDEADBEEF); check high-water mark | Increase stack size; move large buffers to heap; reduce ISR nesting |
| Race condition with ISR | Non-atomic read-modify-write on shared variable | `volatile` present but still corrupted; interrupt preempts read-then-write | Use atomic operations; disable interrupt briefly; use lock-free queue |
| UART/I2C/SPI data corruption | Wrong baud rate; clock stretching; noise; buffer overflow | Logic analyzer on bus; check timing; verify termination | Match baud rates; add pull-ups; use error detection (parity/CRC) |
| Flash write failure | Page not erased; write to protected area; flash wear | Check flash status register; verify erase before write | Erase page before write; check write protection bits; use wear leveling |
| Bootloader not launching | Vector table at wrong offset; invalid firmware signature | Check linker script for bootloader entry point; verify signature | Set correct VTOR offset; sign firmware with Ed25519 |

### Implementation Checklist

- [ ] Linker script defines correct memory regions and section placement
- [ ] Startup code initializes .data, .bss, and stack pointer correctly
- [ ] Watchdog timer enabled with appropriate timeout
- [ ] Fault handlers implemented (HardFault, MemManage, BusFault, UsageFault)
- [ ] `volatile` on all hardware register accesses and ISR-shared variables
- [ ] Critical sections bounded (< 100 cycles) — use lock-free where possible
- [ ] Stack high-water mark measured for all tasks/ISRs
- [ ] RTOS selected (or bare-metal justified) with scheduling policy defined
- [ ] All peripherals configured via device tree (Zephyr) or vendor HAL
- [ ] Communication protocols validated with logic analyzer
- [ ] Power budget calculated: active current × duty cycle + sleep current
- [ ] Secure boot chain verified (ROM → bootloader → application)
- [ ] OTA firmware update implemented with signature verification and rollback
- [ ] Hardware-in-the-loop testing pipeline operational
- [ ] Production programming and factory provisioning documented
- [ ] FCC/CE/regulatory compliance tested (if applicable)
