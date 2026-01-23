#!/usr/bin/env python3
"""Convert *_plain lists into Keenetic route add .bat files."""
from __future__ import annotations

import argparse
import ipaddress
import os
import sys
from pathlib import Path
from typing import Iterable, List


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(__file__).resolve().parent
DEFAULT_MAX_LINES = 1024


def _available_providers(repo_root: Path) -> List[str]:
    providers: List[str] = []
    for entry in sorted(repo_root.iterdir()):
        if not entry.is_dir():
            continue
        plain_ipv4 = entry / f"{entry.name}_plain_ipv4.txt"
        plain = entry / f"{entry.name}_plain.txt"
        if plain_ipv4.exists() or plain.exists():
            providers.append(entry.name)
    return providers


def _prompt_for_providers(available: List[str]) -> List[str]:
    print("Available providers:")
    print(", ".join(sorted(available)))
    print("Enter provider names separated by commas.")
    while True:
        raw = input("> ").strip()
        if not raw:
            print("Please enter at least one provider name.")
            continue
        selected = [item.strip() for item in raw.split(",") if item.strip()]
        if not selected:
            print("Please enter at least one provider name.")
            continue
        return selected


def _parse_provider_args(args: argparse.Namespace, available: List[str]) -> List[str]:
    if args.all and args.providers:
        raise SystemExit("Use either --all or --providers, not both.")
    if args.all:
        return list(available)
    if args.providers:
        selected: List[str] = []
        for item in args.providers:
            for part in item.split(","):
                part = part.strip()
                if part:
                    selected.append(part)
        return selected
    return _prompt_for_providers(available)


def _read_ipv4_prefixes(path: Path) -> List[ipaddress.IPv4Network]:
    prefixes: List[ipaddress.IPv4Network] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            network = ipaddress.ip_network(line, strict=False)
        except ValueError:
            continue
        if network.version == 4:
            prefixes.append(network)
    return prefixes


def _build_routes(prefixes: Iterable[ipaddress.IPv4Network]) -> List[str]:
    lines: List[str] = []
    for network in prefixes:
        lines.append(
            f"route add {network.network_address} mask {network.netmask} 0.0.0.0"
        )
    return lines


def _chunk_lines(lines: List[str], max_lines: int) -> List[List[str]]:
    return [lines[i : i + max_lines] for i in range(0, len(lines), max_lines)]


def _write_chunks(provider: str, chunks: List[List[str]]) -> None:
    if not chunks:
        return
    multiple = len(chunks) > 1
    for idx, chunk in enumerate(chunks, start=1):
        if multiple:
            filename = f"{provider}_keenetic_{idx}.bat"
        else:
            filename = f"{provider}_keenetic.bat"
        path = OUTPUT_DIR / filename
        path.write_text("\n".join(chunk) + "\n", encoding="utf-8")


def main() -> int:
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        print("This script is intended for manual use only, not for GitHub Actions.")
        return 1

    parser = argparse.ArgumentParser(
        description="Convert *_plain lists into Keenetic route add .bat files."
    )
    parser.add_argument(
        "--providers",
        nargs="*",
        help="Provider names (comma or space separated).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all available providers.",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=DEFAULT_MAX_LINES,
        help="Maximum lines per .bat file (default: 1024).",
    )
    args = parser.parse_args()

    if args.max_lines <= 0:
        print("--max-lines must be a positive integer.", file=sys.stderr)
        return 2

    available = _available_providers(REPO_ROOT)
    if not available:
        print("No providers with *_plain lists found.", file=sys.stderr)
        return 1

    selected = _parse_provider_args(args, available)
    unknown = [name for name in selected if name not in available]
    if unknown:
        print(f"Unknown providers: {', '.join(unknown)}", file=sys.stderr)
        return 1

    for provider in selected:
        provider_dir = REPO_ROOT / provider
        plain_ipv4 = provider_dir / f"{provider}_plain_ipv4.txt"
        plain = provider_dir / f"{provider}_plain.txt"
        source_path = plain_ipv4 if plain_ipv4.exists() else plain
        if not source_path.exists():
            print(f"{provider}: no *_plain list found, skipping.")
            continue

        prefixes = _read_ipv4_prefixes(source_path)
        if not prefixes:
            print(f"{provider}: no IPv4 prefixes found, skipping.")
            continue

        lines = _build_routes(prefixes)
        chunks = _chunk_lines(lines, args.max_lines)
        _write_chunks(provider, chunks)
        if len(chunks) == 1:
            print(f"{provider}: wrote {len(lines)} routes to {provider}_keenetic.bat")
        else:
            print(
                f"{provider}: wrote {len(lines)} routes to {len(chunks)} files "
                f"(max {args.max_lines} per file)"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
