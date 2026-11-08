"""Explicit local setup commands; never activate a camera or preview on import."""

import argparse
import getpass
from pathlib import Path

from restaurant_edge.source_config import SourceRegistry


def main():
    parser = argparse.ArgumentParser(description="Local authorized video and calibration setup")
    commands = parser.add_subparsers(dest="command", required=True)
    synthetic = commands.add_parser("synthetic", help="Generate new geometric DEMO MP4 footage")
    synthetic.add_argument("--output", type=Path, required=True)
    synthetic.add_argument("--seconds", type=int, default=90, choices=range(1, 301), metavar="1..300")
    serve = commands.add_parser("serve", help="Serve local authenticated calibration on loopback only")
    serve.add_argument("--config", type=Path, required=True)
    serve.add_argument("--api", default="http://127.0.0.1:8000")
    serve.add_argument("--api-origin", default="http://localhost:3000")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--ai-debug", action="store_true", help="Enable the protected local shadow AI lab")
    serve.add_argument("--analysis-root", type=Path, default=Path('.secrets/phase5/profiles'))
    serve.add_argument("--models", type=Path, help="Private operator-reviewed model approval manifest; no download")
    credential = commands.add_parser("credential", help="Privately set a new Windows camera credential")
    credential.add_argument("--config", type=Path, required=True)
    credential.add_argument("--camera", required=True)
    args = parser.parse_args()
    try:
        if args.command == "synthetic":
            from restaurant_edge.video_sources import synthetic_mp4
            synthetic_mp4(args.output, args.seconds)
            print("Generated new synthetic MP4 locally. No camera or microphone was opened.")
        elif args.command == "serve":
            import uvicorn

            from restaurant_edge.companion import create_companion
            if not 1024 <= args.port <= 65535:
                raise ValueError("Invalid loopback port")
            registry = SourceRegistry.load(args.config)
            from restaurant_edge.detectors.onnx_detector import ModelCatalog
            catalog = ModelCatalog.load(args.models) if args.models else ModelCatalog()
            app = create_companion(registry, api_url=args.api, api_origin=args.api_origin, port=args.port,
                                   ai_debug=args.ai_debug, analysis_root=args.analysis_root, model_catalog=catalog)
            uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning")
        elif args.command == "credential":
            from restaurant_edge.secret_store import account, backend, save
            registry = SourceRegistry.load(args.config)
            sources = [s for s in registry.entries.values() if str(s.camera_id)==args.camera and s.kind=="rtsp"]
            if len(sources) != 1:
                raise ValueError("Select exactly one configured authorized RTSP camera")
            source = sources[0]
            if backend().get_password("RestaurantEdgePhase4", account(source)) is not None:
                raise ValueError("An existing credential is preserved; review rotation separately")
            username = getpass.getpass("Camera username (hidden): ")
            password = getpass.getpass("Camera password (hidden): ")
            save(source, username, password)
            print("Stored a new camera credential in this Windows user's protected store.")
    except (ValueError, OSError, RuntimeError):
        parser.exit(1, "Local setup failed; check configuration and permissions. Private values omitted.\n")


if __name__ == "__main__":
    main()
