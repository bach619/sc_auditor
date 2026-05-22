# Harden CI pipeline by removing `|| true` masking [high][open]

**Labels:** `high` + `open`

## Deskripsi

File `.github/workflows/ci.yml` menggunakan `|| true` di beberapa step kritis, yang **menyembunyikan kegagalan** dan membuat CI selalu hijau meskipun ada error:

| Baris | Step | Masalah |
|-------|------|---------|
| 21 | `ruff check ... \|\| true` | Linter error tidak memicu kegagalan CI |
| 38 | `npx eslint src/ ... \|\| true` | ESLint error tidak terdeteksi |
| 55 | `npx tsc --noEmit \|\| true` | TypeScript error tidak terdeteksi |
| 70 | `python -m pytest ... \|\| true` | Test failure tidak memicu kegagalan CI |

**Dampak:**
- Kode dengan bug atau pelanggaran standar bisa di-merge ke `main` tanpa terdeteksi
- Memberikan false sense of security — "CI hijau" padahal banyak yang gagal
- Menghilangkan value dari pipeline CI sebagai quality gate

## Langkah Implementasi

- [ ] Hapus `|| true` dari step `ruff check` (baris 21)
- [ ] Hapus `|| true` dari step ESLint (baris 38)
- [ ] Hapus `|| true` dari step TypeScript check (baris 55)
- [ ] Hapus `|| true` dari step pytest (baris 70)
- [ ] Untuk step yang benar-benar non-critical, gunakan `continue-on-error: true` sebagai alternatif eksplisit
- [ ] Jalankan CI di branch terpisah untuk memverifikasi error sekarang memicu kegagalan
- [ ] Perbaiki semua error yang muncul setelah masking dihapus

## Kriteria Selesai

- [ ] Tidak ada `|| true` di step lint, type-check, atau test di `ci.yml`
- [ ] CI gagal (red) jika ruff menemukan pelanggaran
- [ ] CI gagal (red) jika ESLint menemukan error
- [ ] CI gagal (red) jika TypeScript type-check gagal
- [ ] CI gagal (red) jika ada test yang fail
- [ ] Semua error yang sebelumnya termasking sudah diperbaiki

## Catatan Tambahan

Jika ada step yang memang non-critical, gunakan `continue-on-error: true` yang lebih eksplisit:

```yaml
- name: Run ruff linter
  continue-on-error: true  # advisory only
  run: ruff check services/*/src/ --no-fix
```

Setelah masking dihapus, prioritaskan perbaikan error test terlebih dahulu, baru lint/format issues.
