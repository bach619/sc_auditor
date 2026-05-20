import pathlib, re

p = pathlib.Path("E:/website/.opencode/skills/security-crypto/SKILL.md")
raw = p.read_text(encoding="utf-8")

# Remove all YAML frontmatter blocks (--- ... --- at start)
raw = re.sub(r"^---\n.*?^---\n", "", raw, flags=re.DOTALL | re.MULTILINE, count=10)

# Fix the header
raw = re.sub(r"^# Security Cryptography --- God-Tier Engineering Skill", "# Security Cryptography \u2014 God-Tier Engineering Skill", raw, flags=re.MULTILINE)

# Build proper frontmatter
fm = []
fm.append("---")
fm.append("name: security-crypto")
fm.append("description: Comprehensive modern cryptography engineering skill covering symmetric/asymmetric encryption, AEAD, digital signatures, password hashing, post-quantum (NIST PQC), TLS 1.3, PKI, Zero-Knowledge Proofs, MPC, homomorphic encryption, key management (HSM/KMS), side-channel resistance, applied patterns, anti-patterns, and implementation checklist")
fm.append("license: MIT")
fm.append("compatibility: opencode")
fm.append("metadata:")
fm.append("  audience: security-engineers")
fm.append("  domain: security")
fm.append("  paradigm: cryptographic")
fm.append("  integrates_with: [security-audit, backend-python, backend-go, backend-elixir, systems-embedded, infra-terraform]")
fm.append("---")

result = "\n".join(fm) + "\n\n" + raw.strip() + "\n"
p.write_text(result, encoding="utf-8")
print("Rewritten: " + str(len(result)) + " chars")
