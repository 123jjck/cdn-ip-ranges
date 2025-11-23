#!/usr/bin/env python3
"""Generate CDN IP range lists in plain text formats."""
from __future__ import annotations

import csv
import ipaddress
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Sequence, Tuple, Union
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "cdn-ip-range-updater/1.0 (+https://github.com/tajjck/cdnip)"
AWS_IP_RANGES_URL = "https://ip-ranges.amazonaws.com/ip-ranges.json"
ORACLE_IP_RANGES_URL = "https://docs.oracle.com/iaas/tools/public_ip_ranges.json"
RIPE_DATA_URL = "https://stat.ripe.net/data/announced-prefixes/data.json?resource={resource}"
NETWORKSDB_ORG_NETWORKS_URL = "https://networksdb.io/api/org-networks"
DIGITALOCEAN_GEO_CSV_URL = "https://digitalocean.com/geo/google.csv"

@dataclass(frozen=True)
class PrefixEntry:
    cidr: str
    region: str = ""


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    fetcher: Callable[[], Sequence[PrefixEntry]]


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


def fetch_aws_ranges() -> Sequence[PrefixEntry]:
    raw = fetch_json(AWS_IP_RANGES_URL)
    prefixes: List[PrefixEntry] = []

    for entry in raw.get("prefixes", []):
        prefix = entry.get("ip_prefix")
        if prefix:
            prefixes.append(PrefixEntry(prefix, entry.get("region", "")))

    for entry in raw.get("ipv6_prefixes", []):
        prefix = entry.get("ipv6_prefix")
        if prefix:
            prefixes.append(PrefixEntry(prefix, entry.get("region", "")))

    return prefixes


def fetch_oracle_ranges() -> Sequence[PrefixEntry]:
    payload = fetch_json(ORACLE_IP_RANGES_URL)
    prefixes: List[PrefixEntry] = []

    for region in payload.get("regions", []):
        region_name = region.get("region", "")
        for entry in region.get("cidrs", []):
            prefix = entry.get("cidr")
            if prefix:
                prefixes.append(PrefixEntry(prefix, region_name))

    return prefixes


def fetch_digitalocean_ranges() -> Sequence[PrefixEntry]:
    body = fetch_text(DIGITALOCEAN_GEO_CSV_URL)
    prefixes: List[PrefixEntry] = []

    for row in csv.reader(body.splitlines()):
        if not row:
            continue
        prefix = row[0].strip()
        if prefix:
            region = row[2].strip() if len(row) > 2 else ""
            prefixes.append(PrefixEntry(prefix, region))

    return prefixes


def fetch_vercel_ranges() -> Sequence[PrefixEntry]:
    api_key = os.environ.get("NETWORKSDB_API_KEY")
    if not api_key:
        raise RuntimeError("vercel: NETWORKSDB_API_KEY environment variable is not set")

    payload = urlencode({"id": "vercel-inc"}).encode("utf-8")
    request = Request(
        NETWORKSDB_ORG_NETWORKS_URL,
        data=payload,
        headers={
            "User-Agent": USER_AGENT,
            "X-Api-Key": api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    try:
        with urlopen(request, timeout=60) as response:  # nosec: B310 - trusted endpoint
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read().decode(charset)
    except HTTPError as exc:  # pragma: no cover - defensive
        raise RuntimeError(
            f"vercel: HTTP error {exc.code} while fetching {NETWORKSDB_ORG_NETWORKS_URL}"
        ) from exc
    except URLError as exc:  # pragma: no cover - defensive
        raise RuntimeError(
            f"vercel: network error while fetching {NETWORKSDB_ORG_NETWORKS_URL}: {exc.reason}"
        ) from exc

    try:
        payload_json = json.loads(body)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise RuntimeError("vercel: invalid JSON payload from networksdb API") from exc

    prefixes: List[PrefixEntry] = []
    for entry in payload_json.get("results", []):
        prefix = entry.get("cidr")
        if prefix:
            prefixes.append(PrefixEntry(prefix))

    return prefixes


def fetch_ripe_prefixes(asn: str) -> Sequence[PrefixEntry]:
    normalized = asn.upper()
    if not normalized.startswith("AS"):
        normalized = f"AS{normalized}"

    url = RIPE_DATA_URL.format(resource=normalized)
    payload = fetch_json(url)
    prefixes: List[PrefixEntry] = []

    for entry in payload.get("data", {}).get("prefixes", []):
        prefix = entry.get("prefix")
        if prefix:
            prefixes.append(PrefixEntry(prefix))

    return prefixes


def normalize_prefixes(provider: str, prefixes: Iterable[PrefixEntry]) -> List[PrefixEntry]:
    pref_list = list(prefixes)
    if not pref_list:
        raise RuntimeError(f"{provider}: empty prefix list fetched")

    normalized: List[Tuple[int, int, int, str, str]] = []
    seen: set[str] = set()
    duplicates: set[str] = set()

    for entry in pref_list:
        prefix = entry.cidr
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
        normalized.append(
            (network.version, int(network.network_address), network.prefixlen, canonical, entry.region)
        )

    if duplicates:
        sample = ", ".join(sorted(duplicates)[:10])
        print(
            f"{provider}: removed {len(duplicates)} duplicate prefixes (e.g., {sample})",
            file=sys.stderr,
        )

    if not normalized:
        raise RuntimeError(f"{provider}: no valid prefixes after validation")

    normalized.sort()
    return [PrefixEntry(entry[3], entry[4]) for entry in normalized]


def aggregate_prefixes(provider: str, prefixes: Sequence[PrefixEntry]) -> List[PrefixEntry]:
    if not prefixes:
        raise RuntimeError(f"{provider}: empty prefix list before aggregation")

    networks = [ipaddress.ip_network(entry.cidr, strict=False) for entry in prefixes]
    collapsed: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = []

    for version in (4, 6):
        version_networks = [net for net in networks if net.version == version]
        if not version_networks:
            continue
        collapsed.extend(ipaddress.collapse_addresses(version_networks))

    collapsed.sort(key=lambda net: (net.version, int(net.network_address), net.prefixlen))
    aggregated = [PrefixEntry(str(network)) for network in collapsed]

    if len(aggregated) != len(prefixes):
        print(
            f"{provider}: aggregated {len(prefixes)} prefixes down to {len(aggregated)}",
            file=sys.stderr,
        )

    return aggregated


def write_plain(path: Path, prefixes: Sequence[PrefixEntry]) -> None:
    lines = [entry.cidr for entry in prefixes]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_provider_outputs(provider: str, prefixes: Sequence[PrefixEntry]) -> None:
    provider_dir = REPO_ROOT / provider
    provider_dir.mkdir(parents=True, exist_ok=True)

    ipv4_prefixes = [
        prefix
        for prefix in prefixes
        if ipaddress.ip_network(prefix.cidr, strict=False).version == 4
    ]

    plain_path = provider_dir / f"{provider}_plain.txt"
    plain_ipv4_path = provider_dir / f"{provider}_plain_ipv4.txt"

    write_plain(plain_path, prefixes)
    write_plain(plain_ipv4_path, ipv4_prefixes)


def write_all_csv(entries: Sequence[tuple[str, PrefixEntry]]) -> None:
    all_dir = REPO_ROOT / "all"
    all_dir.mkdir(parents=True, exist_ok=True)
    csv_path = all_dir / "all.csv"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["provider", "cidr", "region"])
        for provider, entry in entries:
            writer.writerow([provider, entry.cidr, entry.region])


def main() -> int:
    providers: Sequence[ProviderSpec] = (
        ProviderSpec("hetzner", lambda: fetch_ripe_prefixes("24940")),
        ProviderSpec("aws", fetch_aws_ranges),
        ProviderSpec("cdn77", lambda: fetch_ripe_prefixes("60068")),
        ProviderSpec("ovh", lambda: fetch_ripe_prefixes("16276")),
        ProviderSpec("cloudflare", lambda: fetch_ripe_prefixes("13335")),
        ProviderSpec("contabo", lambda: fetch_ripe_prefixes("51167")),
        ProviderSpec("constant", lambda: fetch_ripe_prefixes("20473")),
        ProviderSpec("scaleway", lambda: fetch_ripe_prefixes("12876")),
        ProviderSpec("akamai", lambda: fetch_ripe_prefixes("20940")),
        ProviderSpec("oracle", fetch_oracle_ranges),
        ProviderSpec("digitalocean", fetch_digitalocean_ranges),
        ProviderSpec("cogent", lambda: fetch_ripe_prefixes("174")),
        ProviderSpec("vercel", fetch_vercel_ranges),
    )

    all_prefixes: List[PrefixEntry] = []
    all_csv_entries: List[tuple[str, PrefixEntry]] = []
    for spec in providers:
        raw_prefixes = list(spec.fetcher())
        prefixes = normalize_prefixes(spec.name, raw_prefixes)
        aggregated = aggregate_prefixes(spec.name, prefixes)
        write_provider_outputs(spec.name, aggregated)
        print(f"Generated {len(aggregated):>5} aggregated prefixes for {spec.name}")
        all_prefixes.extend(aggregated)
        all_csv_entries.extend((spec.name, entry) for entry in prefixes)

    if all_prefixes:
        normalized_all = normalize_prefixes("all", all_prefixes)
        aggregated_all = aggregate_prefixes("all", normalized_all)
        write_provider_outputs("all", aggregated_all)
        write_all_csv(all_csv_entries)
        print(f"Generated {len(aggregated_all):>5} aggregated prefixes for all providers")

    return 0


if __name__ == "__main__":
    sys.exit(main())
