# VYPER — Disaster Recovery Plan

## Recovery Time Objective (RTO): 30 menit
## Recovery Point Objective (RPO): 6 jam (interval backup)

## Scenario 1: Single Service Crash
1. `docker compose restart {service}`
2. Jika masih crash → `docker compose logs {service} --tail=50`
3. Jika perlu rebuild → `docker compose build {service} && docker compose up -d {service}`

## Scenario 2: Docker Daemon Crash
1. `sudo systemctl restart docker`
2. `docker compose up -d`
3. Verify: `docker compose ps`

## Scenario 3: Server Total Failure
1. Provision server baru (Ubuntu 22.04)
2. Install Docker + Docker Compose
3. Clone repo → copy `.env` dari backup
4. Restore `/data/` dari backup terakhir:
   ```bash
   tar -xzf /backup/full_backup_20260604_120000.tar.gz -C /data/
   ```
5. `docker compose up -d`
6. Verify dashboard: `http://SERVER_IP:8000`
7. Test pipeline: submit 1 audit → verify report generated

## Scenario 4: Data Corruption
1. Stop services: `docker compose down`
2. Restore dari backup terbersih:
   ```bash
   # Cek backup integrity
   for f in /backup/full_backup_*.tar.gz; do
       tar -tzf "$f" > /dev/null && echo "$f: OK" || echo "$f: CORRUPT"
   done
   # Restore yang OK
   tar -xzf /backup/full_backup_LATEST_OK.tar.gz -C /data/
   ```
3. Start: `docker compose up -d`
4. Verify: cek audit history di dashboard

## Backup Locations
- Primary: `/data/backups/` (local)
- Secondary: rsync ke external storage (S3, NAS, etc.) — cron setiap 24 jam
