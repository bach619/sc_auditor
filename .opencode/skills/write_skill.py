import pathlib, sys, json

content = sys.argv[1] if len(sys.argv) > 1 else ''
p = pathlib.Path('E:/website/.opencode/skills/security-crypto/SKILL.md')
p.write_text(content, encoding='utf-8')
print(f'Wrote {len(content)} chars')
