"""Start an isolated synthetic PostgreSQL test server; never mount project data."""

import json
import os
import secrets
import socket
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import psycopg

ROOT = Path(__file__).resolve().parents[1]


def wait_ready(config):
    for _ in range(60):
        try:
            with psycopg.connect(
                host="127.0.0.1",
                port=config["port"],
                dbname=config["database"],
                user=config["username"],
                password=config["password"],
                connect_timeout=1,
            ):
                return
        except psycopg.OperationalError:
            time.sleep(0.25)
    raise RuntimeError(
        "Isolated test database did not become ready; no credentials printed"
    )


def main():
    folder = ROOT / ".secrets"
    folder.mkdir(exist_ok=True)
    manifest = folder / "phase2-test.json"
    if manifest.exists():
        previous = json.loads(manifest.read_text(encoding="utf-8"))
        result = subprocess.run(
            ["docker", "inspect", previous["container"]],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            container = json.loads(result.stdout)[0]
            if container["Config"]["Labels"].get("restaurant.phase2-test") != "true":
                raise RuntimeError("Refusing to use an unmarked test container")
            if not container["State"]["Running"]:
                raise RuntimeError("Test container is stopped; review it before reuse")
            wait_ready(previous)
            print("Existing isolated test server is ready; no data reset.")
            return
        # Preserve the old private manifest when replacing an already-removed test server.
        (folder / f"phase2-test-history-{uuid4().hex}.json").write_text(
            manifest.read_text(encoding="utf-8"), encoding="utf-8"
        )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    config = {
        "container": "restaurant-phase2-test-" + uuid4().hex[:10],
        "port": port,
        "database": "phase2_security_test",
        "username": "phase2_test_admin",
        "password": secrets.token_urlsafe(36),
    }
    result = subprocess.run(
        [
            "docker",
            "run",
            "--detach",
            "--pull=never",
            "--name",
            config["container"],
            "--label",
            "restaurant.phase2-test=true",
            "--tmpfs",
            "/var/lib/postgresql/data",
            "--publish",
            f"127.0.0.1:{port}:5432",
            "--env",
            "POSTGRES_PASSWORD",
            "--env",
            "POSTGRES_USER=" + config["username"],
            "--env",
            "POSTGRES_DB=" + config["database"],
            "postgres:16-alpine",
        ],
        env=dict(os.environ, POSTGRES_PASSWORD=config["password"]),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Test container could not start; no private details printed")
    manifest.write_text(json.dumps(config), encoding="utf-8")
    wait_ready(config)
    print(
        f"Isolated test server created on localhost:{port}; existing data volume untouched."
    )


if __name__ == "__main__":
    main()
