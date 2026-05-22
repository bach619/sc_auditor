---
name: security-crypto
description: Modern cryptography: Post-quantum (NIST PQC), ZK-SNARKs/STARKs, MPC (Multi-Party Computation), homomorphic encryption, key management, TLS configuration, and zero-trust encryption strategy
license: MIT
compatibility: opencode
metadata:
  audience: security-engineers
  domain: security
  paradigm: cryptographic
  integrates_with: [security-audit, backend-python, backend-go, backend-elixir, systems-embedded, infra-terraform]
---

## Security Cryptography Skill

### Cryptographic Primitives (Current Best Choices)
| Purpose | Algorithm | Notes |
|---------|-----------|-------|
| Symmetric Encryption | AES-256-GCM | AEAD; 12-byte nonce, 16-byte tag |
| Asymmetric Encryption | X25519 + AES-GCM | Hybrid; ECDH for key exchange |
| Digital Signatures | Ed25519 | Fast, compact, no bias |
| Key Exchange | X25519 | Montgomery curve; constant-time |
| Hashing | SHA-256 / BLAKE3 | BLAKE3 is faster |
| Password Hashing | Argon2id | Memory-hard; 2+ iterations |
| MAC | HMAC-SHA256 | Encrypt-then-MAC (modern best practice; MAC-then-encrypt led to padding oracle attacks like Lucky13) |

### Post-Quantum Cryptography (NIST PQC Standards)
- **CRYSTALS-Kyber (ML-KEM)**: Key encapsulation; lattice-based; small ciphertexts
- **CRYSTALS-Dilithium (ML-DSA)**: Digital signatures; lattice-based
- **SPHINCS+ (SLH-DSA)**: Stateless hash-based signatures; backup for lattice
- **FALCON**: Compact signatures; lattice-based with Gaussian sampling
- **Hybrid approach**: Classical + PQC key exchange (X25519 + Kyber) during transition

### Zero-Knowledge Proofs
- **ZK-SNARKs**: Groth16 (smallest proofs, circuit-specific setup), PLONK (universal setup), Halo2 (recursive, no trusted setup)
- **ZK-STARKs**: Transparent (no trusted setup), post-quantum secure, larger proofs
- **Use cases**: Private transactions, identity verification, verifiable compute, rollup validity proofs
- **Tooling**: Circom + snarkjs, Noir (domain-specific language), RISC Zero (zkVM)

### MPC (Multi-Party Computation)
- **Secret sharing**: Shamir's (t-of-n); add, multiply, compare without revealing shares
- **Garbled circuits**: Boolean circuits with encrypted gates; constant rounds
- **Threshold ECDSA**: Distributed key generation + signing; never reconstruct full key
- **PSI (Private Set Intersection)**: Find common elements without revealing other elements
- **Use cases**: Distributed key management, private auctions, privacy-preserving ML

### Homomorphic Encryption
- **CKKS**: Approximate arithmetic; best for ML inference
- **BFV/BGV**: Exact integer arithmetic; leveled (bounded depth)
- **TFHE**: Gate-by-gate; slow but unbounded depth
- **Fully Homomorphic (FHE)**: Any computation on encrypted data
- **Tooling**: Microsoft SEAL, OpenFHE, TFHE-rs

### Key Management
- **Envelope encryption**: Data key (DEK) encrypts data; Key encryption key (KEK) encrypts DEK
- **HSM**: Hardware Security Module for key generation, storage, operations
- **KMS**: Key rotation (automatic), access control (IAM), audit logging
- **TEE**: Trusted Execution Environment (AWS Nitro, Intel SGX/TDX, AMD SEV-SNP)

### TLS Configuration
- **Minimum**: TLS 1.3 only (if possible); TLS 1.2 minimum
- **Ciphers**: TLS_AES_256_GCM_SHA384, TLS_CHACHA20_POLY1305_SHA256
- **Key exchange**: X25519 (ECDHE); no static RSA
- **Certificates**: ECDSA P-256 minimum; 90-day rotation with ACME/Let's Encrypt
- **HSTS**: Strict-Transport-Security: max-age=31536000; includeSubDomains; preload

### Common Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| Rolling your own crypto | Custom algorithms or protocol implementations invariably have subtle flaws | Always use battle-tested libraries (libsodium, Go crypto, Python cryptography) |
| ECB mode for encryption | Identical plaintext blocks produce identical ciphertext blocks (penguin problem) | Use AEAD modes: AES-GCM, ChaCha20-Poly1305 |
| Hardcoded keys in source | Keys leak to version control, logs, and all environments | Use KMS/HSM/Vault; inject keys via env vars loaded from secrets manager |
| Weak random number generation | `Math.random()`, `rand()` are not cryptographically secure | Use CSPRNG: `crypto/rand` (Go), `secrets` module (Python), `:crypto.strong_rand_bytes` (Elixir) |
| Static IVs/nonces | Nonce reuse with same key in GCM/CTR mode completely breaks confidentiality | Generate random nonce for each encryption; use counter-based for deterministic |
| Using SHA1/MD5 for security | Both are cryptographically broken (collision attacks practical) | SHA-256 minimum; SHA-384 or BLAKE3 for new designs |
| Storing passwords with fast hashes | SHA-256/BCRYPT without tuning allows brute force at billions/second | Argon2id with m=19MB, t=2, p=1 minimum (OWASP recommendation) |
| Key reuse across purposes | Using same key for encryption + MAC opens replay/tag manipulation attacks | Separate keys for separate purposes; use HKDF to derive from master key |
| No key rotation plan | Keys never rotated; compromise is permanent | Automatic rotation via KMS; envelope encryption for data key rotation |
| Ignoring side-channel safety | Constant-time violations leak key material via timing | Use constant-time comparison functions; avoid secret-dependent branches |

### Troubleshooting

| Symptom | Likely Cause | Diagnosis | Fix |
|---|---|---|---|
| Certificate chain errors | Missing intermediate cert; expired root; self-signed not trusted | `openssl s_client -connect host:443 -showcerts` | Include full chain in cert file; use Let's Encrypt with auto-renewal |
| TLS handshake failure | Cipher suite mismatch between client and server | Check supported ciphers: `nmap --script ssl-enum-ciphers` | Allow TLS 1.2 minimum with modern cipher suites |
| Signature verification failure | Key type mismatch (RSA vs ECDSA); payload encoding difference | Base64/hex encode consistently; verify key algorithm matches | Normalize encoding; use standard signature formats |
| Argon2 too slow (>2s) | Parameters too aggressive for the hardware | Benchmark: `p, m, t` parameters; measure on target hardware | Tune to 0.5-1s on production hardware |
| HSM connectivity issues | Network partition; PKCS#11 driver mismatch; slot occupied | Check HSM client logs; `pkcs11-tool --list-slots` | Verify driver version; check network; increase retry/timeout |
| Key format mismatch (PEM vs DER) | Library expects one format, receives the other | Check file headers: `-----BEGIN` = PEM; binary = DER | Convert: `openssl rsa -in key.der -inform DER -out key.pem -outform PEM` |

### Implementation Checklist

- [ ] Cryptographic inventory documented (what algorithms used, where, for what purpose)
- [ ] All symmetric encryption uses AEAD (AES-256-GCM or ChaCha20-Poly1305)
- [ ] All asymmetric operations use X25519/Ed25519 (or RSA-4096/ECDSA-P256 minimum)
- [ ] Password hashing uses Argon2id with OWASP-recommended parameters
- [ ] All keys generated via CSPRNG, never hardcoded
- [ ] Key management via KMS/HSM with automatic rotation
- [ ] TLS 1.2 minimum enforced; TLS 1.3 preferred
- [ ] Certificate lifecycle automated (ACME / cert-manager) with 90-day rotation
- [ ] Certificate transparency monitoring enabled
- [ ] PQC migration plan evaluated (Kyber + X25519 hybrid for TLS; Dilithium for signatures)
- [ ] Constant-time functions used for all cryptographic comparisons
- [ ] Crypto library versions pinned and regularly updated
- [ ] Side-channel mitigations reviewed (timing, power, cache)
- [ ] Audit logging enabled for all key access and usage
- [ ] Cryptographic bill of materials (CBOM) generated and reviewed
