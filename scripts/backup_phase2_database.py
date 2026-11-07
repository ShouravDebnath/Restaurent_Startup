"""Create and inspect a private backup before applying Phase 2 migrations."""

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main():
    result = subprocess.run(
        ["docker", "compose", "ps", "--quiet", "db"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    container = result.stdout.strip()
    if not container or "\n" in container:
        raise RuntimeError("Expected exactly one existing project database container")
    folder = ROOT / ".secrets" / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (
        datetime.now(UTC).strftime("phase2-before-%Y%m%dT%H%M%SZ-")
        + uuid4().hex[:8]
        + ".dump"
    )
    with path.open("xb") as output:
        dumped = subprocess.run(
            [
                "docker",
                "exec",
                container,
                "sh",
                "-c",
                'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc',
            ],
            stdout=output,
            stderr=subprocess.PIPE,
            check=False,
        )
    if dumped.returncode or path.stat().st_size < 5:
        raise RuntimeError(
            "Backup failed; do not migrate. No private error details printed."
        )
    with path.open("rb") as backup:
        inspected = subprocess.run(
            ["docker", "exec", "--interactive", container, "pg_restore", "--list"],
            stdin=backup,
            capture_output=True,
            check=False,
        )
    if inspected.returncode:
        raise RuntimeError("Backup archive inspection failed; do not migrate")
    print(
        "Private database backup created and archive inspected: "
        + str(path.relative_to(ROOT))
    )


if __name__ == "__main__":
    main()
