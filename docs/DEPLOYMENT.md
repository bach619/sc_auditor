# VYPER — Production Deployment Guide

## Prasyarat
- Docker 24+ & Docker Compose v3.9+
- Minimum: 8 CPU, 32GB RAM, 100GB SSD
- Recommended: 16 CPU, 64GB RAM, 500GB NVMe
- Ubuntu 22.04 LTS (tested) | macOS 14+ (tested)

## Quick Deploy
1. Clone repo: `git clone ...`
2. Copy config: `cp .env.example .env`
3. Edit `.env`: tambahkan API keys (Anthropic, OpenAI, Infura, Alchemy)
4. Build: `docker compose build`
5. Start: `docker compose up -d`
6. Verify: `docker compose ps` → 28/28 Up
7. Dashboard: `http://localhost:8000`

## Production Checklist
- [ ] Non-root user untuk semua container
- [ ] Firewall: hanya expose port 8000 (dashboard), 8011 (config)
- [ ] VPN/tailscale untuk akses remote
- [ ] Disk: mount /data di SSD terpisah
- [ ] Backup: cron job setiap 6 jam (built-in via 13-upkeep)
- [ ] Monitoring: Grafana + Prometheus (opsional)
- [ ] Secrets: API keys via environment variables, bukan hardcoded
- [ ] Resource limits: atur di docker-compose.yml per service

## Troubleshooting
| Symptom | Cause | Fix |
|---------|-------|-----|
| Service restarting | Missing env var | Cek `docker compose logs {service}` |
| Pipeline stuck | Tool timeout | Perbesar `step_timeout_seconds` di config |
| Out of disk | Backup menumpuk | Cek `/data/backups/`, cleanup otomatis 30 hari |
| Slow scan | Kontrak besar | Upgrade resource limits di docker-compose |
