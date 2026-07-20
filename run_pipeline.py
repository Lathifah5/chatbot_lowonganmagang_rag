#!/usr/bin/env python3
"""
One-command pipeline runner:
scrape -> preprocess -> build vector db -> (optional) run streamlit app
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run_step(cmd: list[str], step_name: str) -> None:
    print(f"\n=== {step_name} ===")
    print("Command:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"Step gagal: {step_name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Jalankan pipeline lengkap dari scraping sampai app Streamlit."
    )
    parser.add_argument("--skip-scrape", action="store_true", help="Lewati proses scraping")
    parser.add_argument("--skip-preprocess", action="store_true", help="Lewati preprocess data")
    parser.add_argument("--skip-build-db", action="store_true", help="Lewati build Chroma DB")
    parser.add_argument(
        "--run-app",
        action="store_true",
        help="Jalankan Streamlit setelah pipeline selesai",
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Install dependency dari requirements.txt dulu",
    )
    parser.add_argument(
        "--collection",
        default="lowongan_magang",
        help="Nama collection untuk build_vector_db.py",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8501,
        help="Port Streamlit saat app dijalankan",
    )
    args = parser.parse_args()

    py = sys.executable

    try:
        if args.install_deps:
            run_step([py, "-m", "pip", "install", "--user", "-r", "requirements.txt"], "Install dependencies")

        if not args.skip_scrape:
            run_step([py, "scrape_jobs.py"], "Scraping data")

        if not args.skip_preprocess:
            run_step([py, "preprocess_data.py"], "Preprocessing data")

        if not args.skip_build_db:
            run_step(
                [py, "build_vector_db.py", "--collection", args.collection],
                "Build vector database",
            )

        print("\nPipeline selesai.")
        print("Dataset bersih: data/lowongan_clean.csv")
        print("Vector DB: chroma_db/")

        if args.run_app:
            run_step(
                [py, "-m", "streamlit", "run", "app.py", "--server.port", str(args.port)],
                "Run Streamlit app",
            )
        else:
            print("Jalankan app manual: streamlit run app.py")

    except RuntimeError as err:
        print(f"\nERROR: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
