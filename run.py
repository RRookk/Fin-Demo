#!/usr/bin/env python
"""Fin Demo — One-click launcher.

Usage:
    python run.py              # Combined mode (single port 8000)
    python run.py --separate   # Separate mode (Fin-train:8001, Finogrid:8002)
    python run.py --port 8080  # Custom port for combined mode
"""

import sys
import os
import argparse

# Ensure fin-demo is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description="Fin Demo Launcher")
    parser.add_argument("--separate", action="store_true",
                        help="Run Fin-train (8001) and Finogrid (8002) separately")
    parser.add_argument("--port", type=int, default=8000,
                        help="Port for combined mode (default: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1",
                        help="Host to bind to (default: 127.0.0.1)")
    args = parser.parse_args()

    if args.separate:
        _run_separate(args.host)
    else:
        _run_combined(args.host, args.port)


def _run_combined(host: str, port: int):
    """Run both Fin-train and Finogrid on a single port."""
    import uvicorn
    print(f"""
╔══════════════════════════════════════════════════════════╗
║                    Fin Demo Launcher                      ║
║                                                          ║
║  Combined mode: http://{host}:{port}                         ║
║  API docs:      http://{host}:{port}/docs                      ║
║                                                          ║
║  Fin-train endpoints:                                    ║
║    POST /api/fin-train/sentiment                         ║
║    POST /api/fin-train/forecast                          ║
║    POST /api/fin-train/rag                                ║
║                                                          ║
║  Finogrid endpoints:                                     ║
║    POST /api/finogrid/agents                             ║
║    POST /api/finogrid/micropay                            ║
║    POST /api/finogrid/batches                             ║
║    GET  /api/finogrid/corridors                           ║
║                                                          ║
║  Database: SQLite (auto-created)                         ║
║  AI: Simulated (no GPU needed)                            ║
╚══════════════════════════════════════════════════════════╝
""")
    uvicorn.run("demo.main:create_combined_app", host=host, port=port,
                factory=True, reload=True, log_level="info")


def _run_separate(host: str):
    """Run Fin-train and Finogrid on separate ports in separate processes."""
    import multiprocessing
    import time

    def run_fin_train():
        import uvicorn
        uvicorn.run("demo.main:create_fin_train_app", host=host, port=8001,
                    factory=True, log_level="info")

    def run_finogrid():
        import uvicorn
        uvicorn.run("demo.main:create_finogrid_app", host=host, port=8002,
                    factory=True, log_level="info")

    print(f"""
╔══════════════════════════════════════════════════════════╗
║                    Fin Demo Launcher                      ║
║                                                          ║
║  Separate mode:                                          ║
║    Fin-train API: http://{host}:8001/docs                    ║
║    Finogrid API:  http://{host}:8002/docs                    ║
║                                                          ║
║  Database: SQLite (auto-created)                         ║
║  AI: Simulated (no GPU needed)                            ║
╚══════════════════════════════════════════════════════════╝
""")

    p1 = multiprocessing.Process(target=run_fin_train, daemon=True)
    p2 = multiprocessing.Process(target=run_finogrid, daemon=True)

    p1.start()
    time.sleep(1)
    p2.start()

    try:
        p1.join()
        p2.join()
    except KeyboardInterrupt:
        print("\n[Fin Demo] Shutting down...")
        p1.terminate()
        p2.terminate()


if __name__ == "__main__":
    main()
