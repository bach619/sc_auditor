

---
name: security-crypto
description: Modern cryptography: post-quantum, ZK, MPC, key management, TLS hardening, KMS integration, and developer patterns.
license: MIT
maturity: god-tier
audience: security-engineers, backend-engineers
---

# Security-Crypto — Panduan Praktis (Bahasa Indonesia)

Dokumen ini menjelaskan pilihan kriptografi modern untuk aplikasi web dan layanan microservice. Fokus: praktik aman yang dapat diadopsi oleh tim engineering tanpa riset akademik mendalam.

Ringkasan cepat:
- Gunakan KMS (AWS KMS / GCP KMS / Azure Key Vault) untuk key management — jangan simpan private keys di repo.
- Prefer: AEAD (AES-GCM atau ChaCha20-Poly1305) untuk enkripsi data-at-rest dan data-in-transit beyond TLS endpoints.
- Hashing password: Argon2id (memory-hard) dengan parameter yang disesuaikan dengan resource server.
- TLS: gunakan TLS 1.3 only, disable RSA key-exchange, prefer ECDHE and PFS curves (X25519, secp256r1).

## 1. Key Management

Praktik:
- Rotate keys periodically (90 days) and support immediate revocation.
- Use envelope encryption: data encrypted with DEK (data encryption key) stored encrypted by KMS-managed KEK (key-encryption key).
- Audit logs: enable KMS audit trail, log key usage with event context.

Example (AWS KMS envelope encryption pseudo-code):

```python
from aws_encryption_sdk import encrypt, decrypt

def encrypt_blob(plaintext: bytes, key_arn: str) -> bytes:
    ciphertext, header = encrypt(source=plaintext, key_arn=key_arn)
    return ciphertext

def decrypt_blob(ciphertext: bytes) -> bytes:
    plaintext, header = decrypt(source=ciphertext)
    return plaintext
```

## 2. Password Storage

- Use Argon2id: tune time_cost (2), memory_cost (64 MB), parallelism (1) as baseline — increase until acceptable.
- Always use a per-user random salt (>=16 bytes) and store parameters with hash.

Example (argon2-cffi):

```python
from argon2 import PasswordHasher
ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=1)
hash = ph.hash('correct horse battery staple')
ph.verify(hash, 'correct horse battery staple')
```

## 3. TLS & Network

- TLS 1.3 only, disable TLS 1.0/1.1/1.2 if possible (beware legacy clients).
- Use HSTS, Certificate Transparency, and OCSP stapling.
- Configure cipher suites: prefer X25519/ECDHE and AES-GCM/ChaCha20-Poly1305.

OpenSSL minimal server config snippet:

```
openssl s_server -accept 443 -cert server.crt -key server.key -www -tls1_3
```

## 4. Post-Quantum Considerations (Practical)

- Track NIST PQC standardization; avoid early rollouts of PQC unless required.
- Hybrid key-exchange: combine classical ECDHE with PQ KEM (e.g., Kyber) to hedge.

## 5. ZK & MPC (High-Level)

- ZK-SNARKs: use circuits for proof-of-knowledge scenarios (identity attestations), verify proofs server-side.
- MPC: use off-the-shelf frameworks (MP-SPDZ, SCALE-MAMBA) for high-sensitivity multi-party computation; heavy ops, not first-line for typical web apps.

## 6. Code Patterns & Safe Defaults

- Use libs: cryptography (Python), libsodium for high-level primitives, avoid writing your own crypto primitives.
- Validate inputs to crypto APIs: lengths, encodings, non-null, exception handling.

## 7. Checklist (Operational)

- [ ] KMS configured + audit logs
- [ ] Password hashing Argon2id implemented
- [ ] TLS 1.3 enforced + HSTS
- [ ] Key rotation plan documented
- [ ] Secrets scanning in CI (git-secrets, truffleHog)

---

## References

- NIST PQC project
- libsodium documentation
- AWS KMS best practices
