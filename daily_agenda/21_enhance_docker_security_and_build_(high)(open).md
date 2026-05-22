# Enhance Docker security and build efficiency [high][open]

**Labels:** `high` + `open`

## Deskripsi

Dua masalah pada Docker layer yang perlu diperbaiki:

### 1. Insecure `chmod 777` di entrypoint

File `scripts/entrypoint.sh` (baris 28) menggunakan `chmod 777` pada semua direktori data:

```bash
chmod 777 "$dir" 2>/dev/null || true
```

Ini memberikan akses read/write/execute ke **semua user** di container — melanggar prinsip least privilege.

### 2. Double pip install di Dockerfile.base

File `Dockerfile.base` menginstal dependencies dua kali:
- Baris 9-17: `pip install fastapi==0.111.0 uvicorn ...` (hardcoded versions)
- Baris 20-21: `COPY requirements.txt .` lalu `RUN pip install ... -r requirements.txt`

Ini menyebabkan:
- Build lebih lambat (instalasi ganda)
- Inkon sistensi versi jika requirements.txt tidak sinkron dengan hardcoded list
- Image size lebih besar dari yang diperlukan

**Lokasi:** `scripts/entrypoint.sh`, `Dockerfile.base`

## Langkah Implementasi

- [ ] **Untuk entrypoint.sh:** Ganti `chmod 777` dengan pendekatan yang lebih aman:
  - Gunakan `chown appuser:appuser` untuk kepemilikan direktori
  - Gunakan `chmod 755` untuk direktori dan `chmod 644` untuk file
  - Pertimbangkan volume mount dengan user ID yang tepat
- [ ] **Untuk Dockerfile.base:** Pilih salah satu strategi:
  - **Opsi A:** Hanya gunakan `requirements.txt` (single source of truth), hapus hardcoded pip install
  - **Opsi B:** Jika pinning versi eksplisit diperlukan, pindahkan semua ke `requirements.txt` dan hapus blok hardcoded
- [ ] Update `.dockerignore` untuk mempercepat build (exclude `__pycache__`, `.git`, `tests`, `node_modules`)
- [ ] Test build ulang semua image dan verifikasi masih berfungsi

## Kriteria Selesai

- [ ] Tidak ada `chmod 777` di `scripts/entrypoint.sh`
- [ ] Direktori data menggunakan permission minimal yang diperlukan
- [ ] `Dockerfile.base` tidak menginstal dependencies dua kali
- [ ] Build Docker sukses dan semua service berjalan normal
- [ ] Tidak ada regresi keamanan

## Catatan Tambahan

Untuk entrypoint.sh, pendekatan yang lebih aman:

```bash
# Create directories with proper ownership
for dir in /data/config /data/scanner /data/source ...; do
    mkdir -p "$dir"
    chown appuser:appuser "$dir"
    chmod 755 "$dir"
done
```

Untuk Dockerfile.base, rekomendasi:

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
```
