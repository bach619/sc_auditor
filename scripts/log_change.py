#!/usr/bin/env python3
"""
System Log Helper — mencatat perubahan ke SYSTEM_LOG.md

Usage:
    python scripts/log_change.py --type CREATE --file "path/file.py" --desc "Menambahkan fitur X"
    python scripts/log_change.py --type MODIFY --file "path/file.py" --desc "Refactor fungsi Y"
    python scripts/log_change.py --type DELETE --file "path/old.md" --desc "Hapus file usang"

Options:
    --type      : CREATE | MODIFY | DELETE | REFACTOR | FIX | DOCS | CONFIG | TEST | META
    --file       : Path file yang diubah (relative ke root repo)
    --desc       : Deskripsi perubahan
    --agent      : Nama agent (default: lore-master)
    --tag        : Tag tambahan (opsional, misal: "agenda-14", "hotfix").
                  Ditampilkan sebelum deskripsi.
    --no-commit  : Jangan auto-commit ke git (default: auto-commit)
    --dry-run    : Hanya tampilkan entri, tanpa menulis file
    --stdout     : Cetak entri ke stdout saja, tanpa menulis file

Format entri:
    `YYYY-MM-DD HH:MM | [TYPE] | File: path | Agent: agent | Deskripsi`

Entri baru selalu ditambahkan di bagian TERATAS dari section tanggal hari ini.
Jika section hari ini belum ada, dibuat otomatis.
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path


# --- Constants ---
REPO_ROOT = Path(__file__).resolve().parent.parent
SYSTEM_LOG_PATH = REPO_ROOT / "SYSTEM_LOG.md"
VALID_TYPES = {"CREATE", "MODIFY", "DELETE", "REFACTOR", "FIX", "DOCS", "CONFIG", "TEST", "META"}
VALID_TYPES_HELP = ", ".join(f"`{t}`" for t in sorted(VALID_TYPES))
SECTION_HEADER_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="System Log — catat perubahan ke SYSTEM_LOG.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--type", "-t",
        required=True,
        choices=sorted(VALID_TYPES),
        help=f"Tipe perubahan: {VALID_TYPES_HELP}",
    )
    parser.add_argument(
        "--file", "-f",
        required=True,
        help="Path file yang diubah (relative ke root repo)",
    )
    parser.add_argument(
        "--desc", "-d",
        required=True,
        help="Deskripsi perubahan",
    )
    parser.add_argument(
        "--agent", "-a",
        default="lore-master",
        help="Nama agent (default: lore-master)",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Tag tambahan (opsional, misal: 'agenda-14', 'hotfix')",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Jangan auto-commit (default: auto-commit jika di git repo)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Hanya tampilkan entri tanpa menulis ke file",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Cetak entri ke stdout saja, tanpa menulis file",
    )
    return parser.parse_args()


def build_entry(args: argparse.Namespace) -> str:
    """Buat satu baris entri system log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    file_path = args.file.replace("\\", "/")

    if args.tag:
        desc = f"[{args.tag}] {args.desc}"
    else:
        desc = args.desc

    return (
        f"### `{timestamp} | [{args.type}] | File: {file_path} "
        f"| Agent: {args.agent} | {desc}`"
    )


def _get_today_header() -> str:
    return datetime.now().strftime("## %Y-%m-%d")


def _create_fresh_log(entry: str) -> str:
    """Create a brand new SYSTEM_LOG.md content with header and entry."""
    today = _get_today_header()
    return (
        f"# System Log — sc_auditor (Vyper)\n"
        f"\n"
        f"> **System Log** — Mencatat **setiap perubahan** (write/modify/delete) "
        f"yang dilakukan oleh opencode agents.\n"
        f">\n"
        f"> Format: `YYYY-MM-DD HH:MM | [TYPE] | File: path | Agent: agent | Deskripsi`\n"
        f">\n"
        f"> **TYPE**: {VALID_TYPES_HELP}\n"
        f">\n"
        f"> ---\n"
        f">\n"
        f"> Gunakan `python scripts/log_change.py --type TYPE --file \"path\" "
        f"--desc \"deskripsi\"` untuk menambah entri.\n"
        f"> Atau edit langsung file ini (append di bagian atas).\n"
        f"\n"
        f"---\n"
        f"\n"
        f"{today}\n"
        f"\n"
        f"{entry}\n"
    )


def _insert_entry_in_content(content: str, entry: str) -> str:
    """
    Insert an entry into the content.
    - If today's section exists, insert as the first entry under it.
    - If not, create today's section at the top.
    - Returns updated content.
    """
    today_header = _get_today_header()
    today_short = datetime.now().strftime("%Y-%m-%d")
    lines = content.split("\n")

    # --- Find today's section ---
    today_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == today_header:
            today_idx = i
            break

    if today_idx is not None:
        # Today's section exists.
        # We want to insert the entry as the first entry after the section header.
        # Skip the section header line and any blank lines after it.
        insert_idx = today_idx + 1
        while insert_idx < len(lines) and lines[insert_idx].strip() == "":
            insert_idx += 1
        # Insert entry before the current first entry (or at end if section is empty)
        lines.insert(insert_idx, entry)
        # Ensure a blank line between section header and first entry
        if insert_idx > today_idx + 1:
            # Already has blank lines, no need to add
            pass
        else:
            # Need to add a blank line after section header
            lines.insert(today_idx + 1, "")
    else:
        # Today's section doesn't exist.
        # Find the first existing section header (most recent date)
        first_section_idx = None
        for i, line in enumerate(lines):
            if SECTION_HEADER_RE.match(line.strip()):
                first_section_idx = i
                break

        if first_section_idx is not None:
            # Insert before the first section
            lines.insert(first_section_idx, "")
            lines.insert(first_section_idx, entry)
            lines.insert(first_section_idx, "")
            lines.insert(first_section_idx, today_header)
        else:
            # No sections at all - append to end
            lines.append("")
            lines.append(today_header)
            lines.append("")
            lines.append(entry)

    return "\n".join(lines)


def append_to_system_log(entry: str, dry_run: bool = False, stdout: bool = False) -> None:
    """Append entri ke SYSTEM_LOG.md."""

    if dry_run:
        print(f"[DRY-RUN] Akan menambahkan:\n{entry}")
        return

    if stdout:
        print(entry)
        return

    if not SYSTEM_LOG_PATH.exists():
        content = _create_fresh_log(entry)
        SYSTEM_LOG_PATH.write_text(content, encoding="utf-8")
        print(f"[LOG] SYSTEM_LOG.md dibuat: {SYSTEM_LOG_PATH}")
    else:
        content = SYSTEM_LOG_PATH.read_text(encoding="utf-8")
        content = _insert_entry_in_content(content, entry)
        SYSTEM_LOG_PATH.write_text(content, encoding="utf-8")
        print(f"[LOG] Entri ditambahkan ke SYSTEM_LOG.md")

    print(f"[ENTRY] {entry}")


def git_auto_commit(entry: str) -> None:
    """Auto-commit perubahan SYSTEM_LOG.md ke git."""
    try:
        import subprocess
        # Cek apakah di git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            print("[GIT] Bukan git repo — skip auto-commit")
            return

        # Stage SYSTEM_LOG.md
        subprocess.run(
            ["git", "add", str(SYSTEM_LOG_PATH)],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=5,
        )

        # Commit
        commit_msg = f"system-log: {entry[:120]}"
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg, "--no-verify"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print(f"[GIT] Auto-commit: {commit_msg}")
        else:
            if "nothing to commit" in result.stderr or "nothing to commit" in result.stdout:
                print("[GIT] Tidak ada perubahan baru untuk di-commit")
            else:
                print(f"[GIT] Commit skipped: {result.stderr.strip() or result.stdout.strip()}")
    except ImportError:
        print("[GIT] subprocess tidak tersedia — skip auto-commit")
    except Exception as e:
        print(f"[GIT] Error auto-commit: {e}")


def main():
    args = parse_args()

    # Build entry
    entry = build_entry(args)

    # Append to system log
    append_to_system_log(entry, dry_run=args.dry_run, stdout=args.stdout)

    # Auto-commit
    if not args.no_commit and not args.dry_run and not args.stdout:
        git_auto_commit(entry)

    sys.exit(0)


if __name__ == "__main__":
    main()
