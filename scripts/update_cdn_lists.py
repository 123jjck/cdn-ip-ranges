#!/usr/bin/env python3
"""Generate CDN IP range lists in plain and Clash formats."""
from __future__ import annotations

import ipaddress
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "cdn-ip-range-updater/1.0 (+https://github.com/tajjck/cdnip)"
AWS_IP_RANGES_URL = "https://ip-ranges.amazonaws.com/ip-ranges.json"
CLOUDFLARE_IPV4_URL = "https://www.cloudflare.com/ips-v4"
CLOUDFLARE_IPV6_URL = "https://www.cloudflare.com/ips-v6"
RIPE_DATA_URL = "https://stat.ripe.net/data/announced-prefixes/data.json?resource={resource}"


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    fetcher: Callable[[], Sequence[str]]


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=60) as response:  # nosec: B310 - trusted endpoints
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset)
    except HTTPError as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"HTTP error {exc.code} while fetching {url}") from exc
    except URLError as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"Network error while fetching {url}: {exc.reason}") from exc


def fetch_json(url: str) -> dict:
    body = fetch_text(url)
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"Invalid JSON payload from {url}") from exc


def fetch_aws_ranges() -> Sequence[str]:
    raw = fetch_json(AWS_IP_RANGES_URL)
    prefixes: List[str] = []

    for entry in raw.get("prefixes", []):
        prefix = entry.get("ip_prefix")
        if prefix:
            prefixes.append(prefix)

    for entry in raw.get("ipv6_prefixes", []):
        prefix = entry.get("ipv6_prefix")
        if prefix:
            prefixes.append(prefix)

    return prefixes


def fetch_cloudflare_ranges() -> Sequence[str]:
    prefixes: List[str] = []

    for url in (CLOUDFLARE_IPV4_URL, CLOUDFLARE_IPV6_URL):
        body = fetch_text(url)
        for line in body.splitlines():
            prefix = line.strip()
            if not prefix:
                continue
            prefixes.append(prefix)

    return prefixes


def fetch_ripe_prefixes(asn: str) -> Sequence[str]:
    normalized = asn.upper()
    if not normalized.startswith("AS"):
        normalized = f"AS{normalized}"

    url = RIPE_DATA_URL.format(resource=normalized)
    payload = fetch_json(url)
    prefixes: List[str] = []

    for entry in payload.get("data", {}).get("prefixes", []):
        prefix = entry.get("prefix")
        if prefix:
            prefixes.append(prefix)

    return prefixes


def normalize_prefixes(provider: str, prefixes: Iterable[str]) -> List[str]:
    pref_list = list(prefixes)
    if not pref_list:
        raise RuntimeError(f"{provider}: empty prefix list fetched")

    normalized: List[Tuple[int, int, int, str]] = []
    seen: set[str] = set()
    duplicates: set[str] = set()

    for prefix in pref_list:
        if not prefix:
            continue
        try:
            network = ipaddress.ip_network(prefix, strict=False)
        except ValueError as exc:
            raise RuntimeError(f"{provider}: invalid prefix '{prefix}'") from exc
        canonical = str(network)
        if canonical in seen:
            duplicates.add(canonical)
            continue
        seen.add(canonical)
        normalized.append((network.version, int(network.network_address), network.prefixlen, canonical))

    if duplicates:
        sample = ", ".join(sorted(duplicates)[:10])
        print(
            f"{provider}: removed {len(duplicates)} duplicate prefixes (e.g., {sample})",
            file=sys.stderr,
        )

    if not normalized:
        raise RuntimeError(f"{provider}: no valid prefixes after validation")

    normalized.sort()
    return [entry[-1] for entry in normalized]


def write_plain(path: Path, prefixes: Sequence[str]) -> None:
    path.write_text("\n".join(prefixes) + ("\n" if prefixes else ""), encoding="utf-8")


def write_clash(path: Path, prefixes: Sequence[str]) -> None:
    lines = []
    for prefix in prefixes:
        network = ipaddress.ip_network(prefix, strict=False)
        is_ipv6 = network.version == 6 or ":" in prefix
        tag = "IP-CIDR6" if is_ipv6 else "IP-CIDR"
        normalized = f"{network.network_address}/{network.prefixlen}"
        lines.append(f"{tag},{normalized}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_provider_outputs(provider: str, prefixes: Sequence[str]) -> None:
    provider_dir = REPO_ROOT / provider
    provider_dir.mkdir(parents=True, exist_ok=True)

    ipv4_prefixes = [
        prefix for prefix in prefixes if ipaddress.ip_network(prefix, strict=False).version == 4
    ]

    plain_path = provider_dir / f"{provider}_plain.txt"
    plain_ipv4_path = provider_dir / f"{provider}_plain_ipv4.txt"
    clash_path = provider_dir / f"{provider}_clash.txt"
    clash_ipv4_path = provider_dir / f"{provider}_clash_ipv4.txt"

    write_plain(plain_path, prefixes)
    write_plain(plain_ipv4_path, ipv4_prefixes)
    write_clash(clash_path, prefixes)
    write_clash(clash_ipv4_path, ipv4_prefixes)


def main() -> int:
    providers: Sequence[ProviderSpec] = (
        ProviderSpec("hetzner", lambda: fetch_ripe_prefixes("24940")),
        ProviderSpec("aws", fetch_aws_ranges),
        ProviderSpec("cdn77", lambda: fetch_ripe_prefixes("60068")),
        ProviderSpec("ovh", lambda: fetch_ripe_prefixes("16276")),
        ProviderSpec("cloudflare", fetch_cloudflare_ranges),
    )

    for spec in providers:
        raw_prefixes = list(spec.fetcher())
        prefixes = normalize_prefixes(spec.name, raw_prefixes)
        write_provider_outputs(spec.name, prefixes)
        print(f"Generated {len(prefixes):>5} prefixes for {spec.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
