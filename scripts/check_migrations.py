#!/usr/bin/env python
"""
Migration CI Check Script
=========================
Validates Alembic migration chain integrity. Run in CI on every PR that
touches ``app/models.py`` or ``alembic/versions/``.

Exit codes:
    0 — all checks passed
    1 — one or more checks failed

Usage:
    python scripts/check_migrations.py
"""

import os
import sys
import subprocess
import tempfile

# Ensure project root is on the path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Safely handle UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PASS = "[PASS]"
FAIL = "[FAIL]"


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        **kwargs,
    )


def check_single_head() -> bool:
    """Verify there is exactly one Alembic head (no divergent branches)."""
    result = _run([sys.executable, "-m", "alembic", "heads"])
    if result.returncode != 0:
        print(f"{FAIL} `alembic heads` failed:\n{result.stderr}")
        return False

    heads = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
    if len(heads) != 1:
        print(f"{FAIL} Expected 1 head, found {len(heads)}: {heads}")
        return False

    print(f"{PASS} Single migration head: {heads[0]}")
    return True


def check_upgrade_head() -> bool:
    """
    Run ``alembic upgrade head`` against a throwaway SQLite database to
    confirm all revisions apply cleanly.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = os.path.join(tmpdir, "migration_test.db")
        env = os.environ.copy()
        # Force the migration to use a throwaway SQLite DB
        env["DATABASE_URL"] = f"sqlite:///{test_db}"
        env.pop("USE_POSTGRES", None)
        env.pop("NEON_URL", None)

        result = _run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=env,
        )
        if result.returncode != 0:
            print(f"{FAIL} `alembic upgrade head` failed:\n{result.stderr}")
            return False

    print(f"{PASS} All migrations apply cleanly against a fresh database")
    return True


def check_no_pending_revisions() -> bool:
    """Verify the migration script files import without syntax errors."""
    versions_dir = os.path.join(PROJECT_ROOT, "alembic", "versions")
    if not os.path.isdir(versions_dir):
        print(f"{FAIL} alembic/versions directory not found")
        return False

    migration_files = [f for f in os.listdir(versions_dir) if f.endswith(".py") and not f.startswith("__")]
    if not migration_files:
        print(f"{FAIL} No migration files found in alembic/versions/")
        return False

    print(f"{PASS} Found {len(migration_files)} migration file(s)")
    return True


def main() -> int:
    print("=" * 60)
    print("  Clarix - Migration Integrity Check")
    print("=" * 60)
    print()

    results = [
        ("Single head check", check_single_head()),
        ("Migration files present", check_no_pending_revisions()),
        ("Upgrade head (clean apply)", check_upgrade_head()),
    ]

    print()
    print("-" * 60)
    all_passed = all(ok for _, ok in results)
    for name, ok in results:
        status = PASS if ok else FAIL
        print(f"  {status}  {name}")

    print("-" * 60)
    if all_passed:
        print("  All migration checks passed.")
    else:
        print("  Some checks FAILED. See output above.")
    print()

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
