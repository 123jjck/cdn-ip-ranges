#!/usr/bin/env python3
"""Generate CDN IP range lists in plain text formats."""
from __future__ import annotations

import csv
import ipaddress
import json
import os
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Sequence, Tuple, Union
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "cdn-ip-range-updater/1.0 (+https://github.com/123jjck/cdn-ip-ranges)"
AWS_IP_RANGES_URL = "https://ip-ranges.amazonaws.com/ip-ranges.json"
ORACLE_IP_RANGES_URL = "https://docs.oracle.com/iaas/tools/public_ip_ranges.json"
RIPE_DATA_URL = "https://stat.ripe.net/data/announced-prefixes/data.json?resource={resource}"
NETWORKSDB_ORG_NETWORKS_URL = "https://networksdb.io/api/org-networks"
DIGITALOCEAN_GEO_CSV_URL = "https://digitalocean.com/geo/google.csv"
TELEGRAM_STATIC_PREFIXES = ("5.28.192.0/18", "109.239.140.0/24", "2a0a:f280::/32")

@dataclass(frozen=True)
class PrefixEntry:
    cidr: str
    region: str = ""


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    fetcher: Callable[[], Sequence[PrefixEntry]]
    include_in_all: bool = True
    include_in_csv: bool | None = None
    allow_empty: bool = False


def _urlopen_with_retries(
    request: Request, timeout: int = 60, attempts: int = 4, delay: float = 2.0, max_delay: float = 20.0
):
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return urlopen(request, timeout=timeout)  # nosec: B310 - trusted endpoints
        except HTTPError as exc:
            last_exc = exc
            # Retry only for throttling and transient upstream failures.
            if exc.code not in {408, 425, 429} and not (500 <= exc.code <= 599):
                raise
            if attempt == attempts:
                raise
        except (URLError, TimeoutError, socket.timeout, ConnectionError) as exc:
            last_exc = exc
            if attempt == attempts:
                raise

        sleep_seconds = min(delay * (2 ** (attempt - 1)), max_delay)
        print(
            f"request retry {attempt}/{attempts - 1} after error: {last_exc}; waiting {sleep_seconds:.1f}s",
            file=sys.stderr,
        )
        time.sleep(sleep_seconds)

    raise RuntimeError("Unreachable: retries exhausted without exception") from last_exc


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with _urlopen_with_retries(request) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset)
    except HTTPError as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"HTTP error {exc.code} while fetching {url}") from exc
    except URLError as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"Network error while fetching {url}: {exc.reason}") from exc
    except (TimeoutError, socket.timeout) as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"Network timeout while fetching {url}: {exc}") from exc


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
        with _urlopen_with_retries(request) as response:
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
    except (TimeoutError, socket.timeout) as exc:  # pragma: no cover - defensive
        raise RuntimeError(
            f"vercel: network timeout while fetching {NETWORKSDB_ORG_NETWORKS_URL}: {exc}"
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


def fetch_discord_voice_ranges() -> Sequence[PrefixEntry]:
    from collect_discord_voice_ips import DEFAULT_REGION_SLUGS, collect_voice_domain_ips

    regions = list(DEFAULT_REGION_SLUGS)
    all_domains, _, resolved_by_domain, _ = collect_voice_domain_ips(
        regions=regions,
        db_host="crt.sh",
        db_port=5432,
        db_name="certwatch",
        db_user="guest",
        db_connect_timeout=20,
        resolver="system",
        workers=24,
        timeout=2.0,
        retries=3,
        max_domains=0,
        progress_every=500,
    )

    if not resolved_by_domain:
        print(
            "discord-voice: system resolver returned 0 resolved domains, retrying with udp",
            file=sys.stderr,
        )
        all_domains, _, resolved_by_domain, _ = collect_voice_domain_ips(
            regions=regions,
            db_host="crt.sh",
            db_port=5432,
            db_name="certwatch",
            db_user="guest",
            db_connect_timeout=20,
            resolver="udp",
            workers=24,
            timeout=2.0,
            retries=3,
            max_domains=0,
            progress_every=500,
        )

    prefixes: List[PrefixEntry] = []
    seen: set[tuple[str, str]] = set()
    resolved_domains = sorted(resolved_by_domain)

    for domain in resolved_domains:
        host_label = domain[: -len(".discord.gg")] if domain.endswith(".discord.gg") else domain
        for ip in resolved_by_domain[domain]:
            try:
                ip_obj = ipaddress.ip_address(ip)
            except ValueError:
                continue
            if not ip_obj.is_global:
                continue
            cidr = f"{ip_obj}/32" if ip_obj.version == 4 else f"{ip_obj}/128"
            key = (cidr, host_label)
            if key in seen:
                continue
            seen.add(key)
            prefixes.append(PrefixEntry(cidr=cidr, region=host_label))

    matched_domains = len(all_domains)
    print(
        (
            f"discord-voice: matched {matched_domains} domains, "
            f"resolved {len(resolved_domains)} domains, "
            f"global IPs {len(prefixes)}"
        ),
        file=sys.stderr,
    )
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


def write_amnezia_ipv4_json(path: Path, prefixes: Sequence[PrefixEntry]) -> None:
    payload = [{"hostname": entry.cidr, "ip": ""} for entry in prefixes]
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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
    amnezia_ipv4_path = provider_dir / f"{provider}_amnezia_ipv4.json"

    write_plain(plain_path, prefixes)
    write_plain(plain_ipv4_path, ipv4_prefixes)
    write_amnezia_ipv4_json(amnezia_ipv4_path, ipv4_prefixes)


def aggregate_csv_entries(
    entries: Sequence[tuple[str, PrefixEntry]],
) -> List[tuple[str, PrefixEntry]]:
    """Aggregate IP prefixes within each provider+region group.

    For providers that have no region data at all, all prefixes are collapsed
    together.  For providers with regions, prefixes are collapsed within each
    region separately.
    """
    from collections import defaultdict

    # Group entries by provider
    provider_entries: dict[str, List[PrefixEntry]] = defaultdict(list)
    for provider, entry in entries:
        provider_entries[provider].append(entry)

    result: List[tuple[str, PrefixEntry]] = []

    for provider in sorted(provider_entries):
        pref_list = provider_entries[provider]

        if provider == "discord-voice":
            unique: dict[tuple[str, str], PrefixEntry] = {}
            for entry in pref_list:
                unique[(entry.cidr, entry.region)] = entry
            ordered = sorted(
                unique.values(),
                key=lambda e: (
                    e.region,
                    ipaddress.ip_network(e.cidr, strict=False).version,
                    int(ipaddress.ip_network(e.cidr, strict=False).network_address),
                    ipaddress.ip_network(e.cidr, strict=False).prefixlen,
                ),
            )
            for entry in ordered:
                result.append((provider, entry))
            continue

        has_regions = any(entry.region for entry in pref_list)

        if not has_regions:
            # Provider has no regions at all — aggregate everything
            collapsed = _collapse_networks(
                [ipaddress.ip_network(e.cidr, strict=False) for e in pref_list]
            )
            before = len(pref_list)
            after = len(collapsed)
            if before != after:
                print(
                    f"{provider} (all.csv): aggregated {before} → {after} prefixes",
                    file=sys.stderr,
                )
            for net in collapsed:
                result.append((provider, PrefixEntry(str(net), "")))
        else:
            # Aggregate within each region
            region_groups: dict[str, List[PrefixEntry]] = defaultdict(list)
            for entry in pref_list:
                region_groups[entry.region].append(entry)

            for region in sorted(region_groups):
                region_entries = region_groups[region]
                collapsed = _collapse_networks(
                    [ipaddress.ip_network(e.cidr, strict=False) for e in region_entries]
                )
                before = len(region_entries)
                after = len(collapsed)
                if before != after:
                    print(
                        f"{provider}/{region or '(no region)'} (all.csv): aggregated {before} → {after} prefixes",
                        file=sys.stderr,
                    )
                for net in collapsed:
                    result.append((provider, PrefixEntry(str(net), region)))

    return result


def _collapse_networks(
    networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]],
) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
    """Collapse a list of networks, handling IPv4 and IPv6 separately."""
    collapsed: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = []
    for version in (4, 6):
        version_nets = [n for n in networks if n.version == version]
        if version_nets:
            collapsed.extend(ipaddress.collapse_addresses(version_nets))
    collapsed.sort(key=lambda n: (n.version, int(n.network_address), n.prefixlen))
    return collapsed


def write_all_csv(entries: Sequence[tuple[str, PrefixEntry]]) -> None:
    all_dir = REPO_ROOT / "all"
    all_dir.mkdir(parents=True, exist_ok=True)
    csv_path = all_dir / "all.csv"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["provider", "cidr", "region"])
        for provider, entry in entries:
            writer.writerow([provider, entry.cidr, entry.region])


def write_all_no_akamai_plain_ipv4(entries: Sequence[tuple[str, PrefixEntry]]) -> None:
    all_dir = REPO_ROOT / "all"
    all_dir.mkdir(parents=True, exist_ok=True)
    output_path = all_dir / "all_no_akamai_plain_ipv4.txt"

    non_akamai_entries = [entry for provider, entry in entries if provider != "akamai"]
    ipv4_entries = [
        entry
        for entry in non_akamai_entries
        if ipaddress.ip_network(entry.cidr, strict=False).version == 4
    ]

    normalized = normalize_prefixes("all_no_akamai_ipv4", ipv4_entries)
    aggregated = aggregate_prefixes("all_no_akamai_ipv4", normalized)
    write_plain(output_path, aggregated)


def main() -> int:
    providers: Sequence[ProviderSpec] = (
        ProviderSpec("akamai", lambda: list(fetch_ripe_prefixes("20940")) + list(fetch_ripe_prefixes("63949"))),
        ProviderSpec("aws", fetch_aws_ranges),
        ProviderSpec("buyvm", lambda: fetch_ripe_prefixes("53667")),
        ProviderSpec("cdn77", lambda: fetch_ripe_prefixes("60068")),
        ProviderSpec("cloudflare", lambda: fetch_ripe_prefixes("13335")),
        ProviderSpec("cogent", lambda: fetch_ripe_prefixes("174")),
        ProviderSpec("constant", lambda: fetch_ripe_prefixes("20473")),
        ProviderSpec("contabo", lambda: list(fetch_ripe_prefixes("51167")) + list(fetch_ripe_prefixes("141995"))),
        ProviderSpec("datacamp", lambda: fetch_ripe_prefixes("212238")),
        ProviderSpec("digitalocean", lambda: list(fetch_digitalocean_ranges()) + list(fetch_ripe_prefixes("14061"))),
        ProviderSpec("fastly", lambda: fetch_ripe_prefixes("54113")),
        ProviderSpec("hetzner", lambda: list(fetch_ripe_prefixes("24940")) + list(fetch_ripe_prefixes("213230")) + list(fetch_ripe_prefixes("212317"))),
        ProviderSpec("melbicom", lambda: list(fetch_ripe_prefixes("8849")) + list(fetch_ripe_prefixes("56630"))),
        ProviderSpec("oracle", lambda: list(fetch_oracle_ranges()) + list(fetch_ripe_prefixes("31898")) + list(fetch_ripe_prefixes("6142")) + list(fetch_ripe_prefixes("20054")) + list(fetch_ripe_prefixes("54253"))),
        ProviderSpec("ovh", lambda: fetch_ripe_prefixes("16276")),
        ProviderSpec("gcore", lambda: list(fetch_ripe_prefixes("199524")) + list(fetch_ripe_prefixes("202422"))),
        ProviderSpec("glesys", lambda: fetch_ripe_prefixes("42708")),
        ProviderSpec("gthost", lambda: fetch_ripe_prefixes("63023")),
        ProviderSpec("meta", lambda: fetch_ripe_prefixes("32934"), include_in_all=False),
        ProviderSpec("roblox", lambda: fetch_ripe_prefixes("22697"), include_in_all=False),
        ProviderSpec("scaleway", lambda: list(fetch_ripe_prefixes("12876")) + list(fetch_ripe_prefixes("29447"))),
        ProviderSpec("scalaxy", lambda: fetch_ripe_prefixes("58061")),
        ProviderSpec(
            "telegram",
            lambda: (
                list(fetch_ripe_prefixes("62041"))
                + list(fetch_ripe_prefixes("62014"))
                + list(fetch_ripe_prefixes("211157"))
                + list(fetch_ripe_prefixes("44907"))
                + list(fetch_ripe_prefixes("59930"))
                + [PrefixEntry(prefix) for prefix in TELEGRAM_STATIC_PREFIXES]
            ),
            include_in_all=False,
        ),
        ProviderSpec(
            "discord-voice",
            fetch_discord_voice_ranges,
            include_in_all=False,
            include_in_csv=False,
            allow_empty=True,
        ),
        ProviderSpec("vercel", fetch_vercel_ranges),
    )

    all_prefixes: List[PrefixEntry] = []
    all_csv_entries: List[tuple[str, PrefixEntry]] = []
    failed_providers: List[str] = []

    for spec in providers:
        try:
            raw_prefixes = list(spec.fetcher())
            if not raw_prefixes and spec.allow_empty:
                write_provider_outputs(spec.name, [])
                print(f"Generated {0:>5} aggregated prefixes for {spec.name}")
                continue

            prefixes = normalize_prefixes(spec.name, raw_prefixes)
            aggregated = aggregate_prefixes(spec.name, prefixes)
            write_provider_outputs(spec.name, aggregated)
            print(f"Generated {len(aggregated):>5} aggregated prefixes for {spec.name}")
            if spec.include_in_all:
                all_prefixes.extend(aggregated)
            include_in_csv = spec.include_in_all if spec.include_in_csv is None else spec.include_in_csv
            if include_in_csv:
                all_csv_entries.extend((spec.name, entry) for entry in prefixes)
        except Exception as exc:
            print(f"FAILED  {spec.name}: {exc}", file=sys.stderr)
            failed_providers.append(spec.name)

    if all_prefixes:
        normalized_all = normalize_prefixes("all", all_prefixes)
        aggregated_all = aggregate_prefixes("all", normalized_all)
        write_provider_outputs("all", aggregated_all)
        aggregated_csv = aggregate_csv_entries(all_csv_entries)
        write_all_csv(aggregated_csv)
        write_all_no_akamai_plain_ipv4(aggregated_csv)
        print(f"Generated {len(aggregated_all):>5} aggregated prefixes for all providers")

    if failed_providers:
        print(
            f"\nFailed providers ({len(failed_providers)}): {', '.join(failed_providers)}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
