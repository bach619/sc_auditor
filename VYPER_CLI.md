# Vyper CLI (Go)

CLI untuk Smart Contract Bug Hunter — microservice-based.

## Install

### Ubuntu / Linux

```bash
# 1. Install Go (sekali aja)
sudo snap install go --classic

# 2. Clone repo & build
git clone https://github.com/antangpatahumahagalewu-stack/sc_auditor.git
cd sc_auditor
go build -o vyper ./cmd/vyper/

# 3. Pakai
./vyper --help
```

### WSL / Windows

```bash
# Sama seperti Ubuntu via WSL
# Atau download Go installer dari https://go.dev/dl/
go build -o vyper.exe ./cmd/vyper/
```

### Install ke PATH (semua OS)

```bash
# Tinggal ketik "vyper" dari mana aja
go install ./cmd/vyper/
vyper --help
```

> **Catatan:** Binary Vyper static — tidak perlu Python, pip, atau dependencies apapun. Cukup satu file `vyper` (~5MB).

## Usage

```
vyper [command] [flags]
```

## Commands

| Command | Deskripsi |
|---------|-----------|
| `audit <address>` | Mulai audit pipeline |
| `scan <file>` | Scan file Solidity |
| `exploit <finding-id>` | Generate PoC exploit |
| `status <audit-id>` | Cek status audit |
| `list` | Lihat semua audit |
| `stats` | Statistik pipeline |
| `queue` | Antrian audit |
| `health` | Cek semua service |
| `up` | Start Docker services |
| `down` | Stop Docker services |
| `logs [service]` | Lihat log service |
| `ps` | Lihat service yang running |
| `restart [service]` | Restart service |
| `config` | Lihat/edit konfigurasi |
| `version` | Versi CLI |

## Contoh

```bash
# Cek semua service
vyper health

# Audit contract
vyper audit 0x1234dead... --chain ethereum

# Scan file lokal
vyper scan contract.sol --tools slither,mythril

# Generate exploit
vyper exploit finding-001 --attack reentrancy

# Docker management
vyper up -d
vyper logs scanner -f
vyper down

# Lihat config
vyper config --show
```

## Global Flags

| Flag | Deskripsi |
|------|-----------|
| `--config` | Path config file |
| `-f, --format` | Output format (auto, json, text) |
| `-d, --debug` | Debug logging |
| `-h, --help` | Help |

## Config File

Lokasi: `~/.vyper/config.yml`

```yaml
orchestrator_url: http://localhost:8009
scanner_url: http://localhost:8003
exploit_url: http://localhost:8006
output_format: auto
```
