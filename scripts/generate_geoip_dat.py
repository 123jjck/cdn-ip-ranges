#!/usr/bin/env python3
"""Generate V2Ray GeoIP dat files from existing CDN IPv4 lists."""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = [
    "akamai",
    "aws",
    "cdn77",
    "cloudflare",
    "cogent",
    "constant",
    "contabo",
    "datacamp",
    "digitalocean",
    "fastly",
    "hetzner",
    "oracle",
    "ovh",
    "roblox",
    "scaleway",
    "vercel",
    "all",
]


def build_geoip_config() -> dict[str, Any]:
    inputs = []
    outputs = []

    for provider in PROVIDERS:
        provider_dir = REPO_ROOT / provider
        source_path = provider_dir / f"{provider}_plain.txt"
        if not source_path.exists():
            raise FileNotFoundError(f"Missing source file: {source_path}")

        inputs.append(
            {
                "type": "text",
                "action": "add",
                "args": {
                    "name": provider,
                    "uri": str(source_path),
                },
            }
        )
        outputs.extend(
            [
                {
                    "type": "v2rayGeoIPDat",
                    "action": "output",
                    "args": {
                        "outputDir": str(provider_dir),
                        "outputName": f"{provider}_geoip.dat",
                        "wantedList": [provider],
                    },
                },
                {
                    "type": "v2rayGeoIPDat",
                    "action": "output",
                    "args": {
                        "outputDir": str(provider_dir),
                        "outputName": f"{provider}_geoip_ipv4.dat",
                        "wantedList": [provider],
                        "onlyIPType": "ipv4",
                    },
                },
            ]
        )

    return {"input": inputs, "output": outputs}


def run_geoip_generator(config_path: Path) -> None:
    subprocess.run(
        [
            "go",
            "run",
            "github.com/v2fly/geoip@latest",
            "-c",
            str(config_path),
        ],
        check=True,
        cwd=REPO_ROOT,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate V2Ray GeoIP dat files for CDN IPv4 lists."
    )
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="Only validate inputs and write the GeoIP config without running go.",
    )
    parser.add_argument(
        "--config-path",
        type=Path,
        help="Optional path to write the generated GeoIP config.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = build_geoip_config()

    if args.config_path:
        config_path = args.config_path
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        if args.config_only:
            return 0
    else:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "geoip-config.json"
            config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            if args.config_only:
                return 0
            run_geoip_generator(config_path)
            return 0

    run_geoip_generator(config_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
