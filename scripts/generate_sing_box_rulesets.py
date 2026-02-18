#!/usr/bin/env python3

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def discover_providers(repo_root: Path) -> list[str]:
    providers = sorted(
        d.name for d in repo_root.iterdir()
        if d.is_dir() and (d / f"{d.name}_plain.txt").exists() and d.name != "all"
    )
    providers.append("all")
    return providers


def convert_ruleset(singbox_path: Path, source_path: Path, binary_path: Path):
    subprocess.run(
        [
            str(singbox_path),
            "rule-set",
            "compile",
            str(source_path),
            "-o",
            str(binary_path),
        ],
        check=True,
        cwd=REPO_ROOT,
    )


def generate_ruleset(singbox_path: Path, input_path: Path, output_path: Path):
    cidrs = list(
        filter(
            lambda line: len(line) > 0,
            map(
                lambda line: line.strip(),
                input_path.read_text(encoding="utf-8").splitlines(),
            ),
        )
    )

    ruleset = {
        "version": 3,
        "rules": [{"ip_cidr": cidrs}],
    }

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".json", delete=False
    ) as temp_file:
        temp_path = Path(temp_file.name)
        json.dump(ruleset, temp_file)

    try:
        convert_ruleset(singbox_path, temp_path, output_path)
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate sing-box ruleset files")
    parser.add_argument(
        "--sing-box", type=Path, default="sing-box", help="Path to sing-box executable"
    )
    args = parser.parse_args()

    for provider in discover_providers(REPO_ROOT):
        print(f"Processing {provider}")

        provider_dir = REPO_ROOT / provider
        generate_ruleset(
            args.sing_box,
            provider_dir / f"{provider}_plain.txt",
            provider_dir / f"{provider}_singbox.srs",
        )
        generate_ruleset(
            args.sing_box,
            provider_dir / f"{provider}_plain_ipv4.txt",
            provider_dir / f"{provider}_singbox_ipv4.srs",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
