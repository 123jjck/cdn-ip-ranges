#!/usr/bin/env python3
"""Collect Discord voice domains from crt.sh PostgreSQL and resolve to IPs."""
from __future__ import annotations

import argparse
import concurrent.futures
import ipaddress
import json
import socket
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Sequence

try:
    import psycopg
except ModuleNotFoundError:  # pragma: no cover - runtime dependency check
    psycopg = None  # type: ignore[assignment]

try:
    import dns.exception as dns_exception
    import dns.resolver as dns_resolver
except ModuleNotFoundError:  # pragma: no cover - runtime dependency check
    dns_exception = None  # type: ignore[assignment]
    dns_resolver = None  # type: ignore[assignment]

UDP_NAMESERVERS: tuple[str, ...] = (
    "8.8.8.8", "8.8.4.4",          # Google
    "1.1.1.1", "1.0.0.1",          # Cloudflare
    "9.9.9.9", "149.112.112.112",  # Quad9
)
CRTSH_SQL_QUERY = """
SELECT name_value
FROM certificate_and_identities
WHERE plainto_tsquery('certwatch', '.discord.gg') @@ identities(CERTIFICATE)
    AND NAME_VALUE ILIKE '%.discord.gg'
    AND NAME_TYPE = '2.5.4.3' -- commonName
    AND x509_notAfter(CERTIFICATE) >= now() AT TIME ZONE 'UTC'
"""
DEFAULT_REGION_SLUGS: tuple[str, ...] = (
    "brazil",
    "bucharest",
    "dubai",
    "finland",
    "frankfurt",
    "hongkong",
    "india",
    "japan",
    "madrid",
    "milan",
    "rotterdam",
    "santiago",
    "seattle",
    "singapore",
    "south-korea",
    "south-korea-streams",
    "southafrica",
    "stage-scale",
    "sydney",
    "tel-aviv",
    "us-east",
    "us-south",
    "us-west",
    "warsaw",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Parse Discord voice-like *.discord.gg domains by region slug and "
            "resolve them to IP addresses."
        )
    )
    parser.add_argument(
        "--regions",
        default=",".join(DEFAULT_REGION_SLUGS),
        help="Comma-separated region slugs to match.",
    )
    parser.add_argument("--crtsh-db-host", default="crt.sh", help="crt.sh PostgreSQL host.")
    parser.add_argument("--crtsh-db-port", type=int, default=5432, help="crt.sh PostgreSQL port.")
    parser.add_argument("--crtsh-db-name", default="certwatch", help="crt.sh PostgreSQL database name.")
    parser.add_argument("--crtsh-db-user", default="guest", help="crt.sh PostgreSQL user.")
    parser.add_argument(
        "--crtsh-db-connect-timeout",
        type=int,
        default=20,
        help="PostgreSQL connection timeout in seconds.",
    )
    parser.add_argument(
        "--resolver",
        choices=("udp", "system"),
        default="udp",
        help="Resolver backend (default: udp = public DNS over UDP).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=24,
        help="Number of concurrent resolver workers (default: 24).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=25.0,
        help="Per-request timeout in seconds (default: 25).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=5,
        help="Number of retries for network requests (default: 5).",
    )
    parser.add_argument(
        "--max-domains",
        type=int,
        default=0,
        help="Optional hard cap for domains to resolve (0 = no cap).",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=200,
        help="Print resolver progress every N domains (default: 200).",
    )
    parser.add_argument(
        "--domains-out",
        type=Path,
        help="Optional file path for discovered domains list.",
    )
    parser.add_argument(
        "--ips-out",
        type=Path,
        help="Optional file path for unique resolved IP list.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="Optional file path for full JSON report.",
    )
    parser.add_argument(
        "--resolved-domains-only",
        action="store_true",
        help="Write only domains that resolved to at least one IP.",
    )
    return parser.parse_args()


def normalize_regions(raw: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in raw.split(","):
        slug = item.strip().lower()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        result.append(slug)
    return result


def fetch_ct_domains_from_postgres(
    host: str,
    port: int,
    dbname: str,
    user: str,
    connect_timeout: int,
    retries: int,
) -> list[str]:
    if psycopg is None:
        raise RuntimeError("Python module 'psycopg' is required. Install with: pip install 'psycopg[binary]'")

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with psycopg.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                connect_timeout=connect_timeout,
                sslmode="prefer",
            ) as conn:
                conn.autocommit = True
                with conn.cursor() as cursor:
                    cursor.execute(CRTSH_SQL_QUERY)
                    rows = cursor.fetchall()
        except Exception as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(min(2 ** (attempt - 1), 8))
            continue

        domains: set[str] = set()
        for row in rows:
            value = str(row[0] if row else "").strip().lower()
            if not value:
                continue
            if value.startswith("*."):
                value = value[2:]
            if value.endswith(".discord.gg"):
                domains.add(value)

        return sorted(domains)

    raise RuntimeError(f"Failed to fetch crt.sh domains via PostgreSQL: {last_error}") from last_error


def _match_region_label(label: str, ordered_regions: Sequence[str]) -> str | None:
    for region in ordered_regions:
        if not label.startswith(region):
            continue
        suffix = label[len(region) :]
        if not suffix:
            return region
        if suffix.startswith("-"):
            suffix = suffix[1:]
        if suffix.isdigit():
            return region
    return None


def extract_voice_domains(domains: Iterable[str], regions: Sequence[str]) -> dict[str, set[str]]:
    regions_sorted = sorted(set(regions), key=len, reverse=True)
    result: dict[str, set[str]] = defaultdict(set)

    for host in domains:
        host = host.strip().lower()
        if not host:
            continue
        if host.startswith("*."):
            host = host[2:]
        if not host.endswith(".discord.gg"):
            continue

        label = host[: -len(".discord.gg")]
        if not label:
            continue

        matched_region = _match_region_label(label, regions_sorted)
        if matched_region is None:
            continue
        result[matched_region].add(host)

    return result


def resolve_domain_system(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return []
    ips = {
        ip
        for ip in {info[4][0] for info in infos}
        if ipaddress.ip_address(ip).is_global
    }
    return sorted(ips, key=lambda ip: (ipaddress.ip_address(ip).version, ipaddress.ip_address(ip)))


_udp_resolver = None


def _get_udp_resolver(timeout: float):
    global _udp_resolver
    if _udp_resolver is None:
        if dns_resolver is None:
            raise RuntimeError("Python module 'dnspython' is required. Install with: pip install dnspython")
        _udp_resolver = dns_resolver.Resolver(configure=False)
        _udp_resolver.nameservers = list(UDP_NAMESERVERS)
        _udp_resolver.rotate = True
        _udp_resolver.timeout = timeout
        _udp_resolver.lifetime = timeout
    return _udp_resolver


def _resolve_udp_type(host: str, qtype: str, timeout: float, retries: int) -> list[str]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resolver = _get_udp_resolver(timeout)
            answers = resolver.resolve(
                host,
                rdtype=qtype,
                tcp=False,
                search=False,
                raise_on_no_answer=False,
            )
            if answers is None:
                return []
            values: list[str] = []
            for rdata in answers:
                address = getattr(rdata, "address", None)
                if isinstance(address, str) and address:
                    values.append(address)
            return values
        except Exception as exc:
            # Empty DNS answer should not be considered a hard resolver error.
            if dns_resolver is not None and dns_exception is not None and isinstance(
                exc,
                (dns_resolver.NoAnswer, dns_resolver.NXDOMAIN, dns_resolver.NoNameservers, dns_exception.Timeout),
            ):
                return []
            last_error = exc
            if attempt == retries:
                break
            time.sleep(min(2 ** (attempt - 1), 8))

    raise RuntimeError(f"UDP DNS query failed for {host}: {last_error}") from last_error


def resolve_domain_udp(host: str, timeout: float, retries: int) -> list[str]:
    ips = set(_resolve_udp_type(host, "A", timeout=timeout, retries=retries))
    ips.update(_resolve_udp_type(host, "AAAA", timeout=timeout, retries=retries))
    ips = {ip for ip in ips if ipaddress.ip_address(ip).is_global}
    return sorted(ips, key=lambda ip: (ipaddress.ip_address(ip).version, ipaddress.ip_address(ip)))


def resolve_all_domains(
    domains: Sequence[str],
    resolver: str,
    workers: int,
    timeout: float,
    retries: int,
    progress_every: int,
) -> tuple[dict[str, list[str]], dict[str, str]]:
    resolved: dict[str, list[str]] = {}
    errors: dict[str, str] = {}

    def _resolve_one(host: str) -> list[str]:
        if resolver == "system":
            return resolve_domain_system(host)
        return resolve_domain_udp(host, timeout=timeout, retries=retries)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(workers, 1)) as executor:
        futures = {executor.submit(_resolve_one, host): host for host in domains}
        completed = 0
        total = len(futures)
        for future in concurrent.futures.as_completed(futures):
            host = futures[future]
            try:
                ips = future.result()
            except Exception as exc:  # pragma: no cover - defensive
                errors[host] = str(exc)
                ips = []
            if ips:
                resolved[host] = ips
            completed += 1
            if progress_every > 0 and (completed % progress_every == 0 or completed == total):
                print(
                    f"Resolve progress: {completed}/{total} domains",
                    file=sys.stderr,
                )

    return resolved, errors


def collect_voice_domain_ips(
    regions: Sequence[str],
    db_host: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_connect_timeout: int,
    resolver: str,
    workers: int,
    timeout: float,
    retries: int,
    max_domains: int,
    progress_every: int,
) -> tuple[list[str], dict[str, set[str]], dict[str, list[str]], dict[str, str]]:
    all_ct_domains = fetch_ct_domains_from_postgres(
        host=db_host,
        port=db_port,
        dbname=db_name,
        user=db_user,
        connect_timeout=db_connect_timeout,
        retries=retries,
    )
    domains_by_region = extract_voice_domains(all_ct_domains, regions)
    all_domains = sorted({host for hosts in domains_by_region.values() for host in hosts})
    if max_domains > 0 and len(all_domains) > max_domains:
        all_domains = all_domains[:max_domains]

    if not all_domains:
        raise RuntimeError("No matching domains were found in crt.sh response.")

    print(
        (
            f"Source: crt.sh PostgreSQL | Will resolve {len(all_domains)} domains across "
            f"{len(regions)} configured regions."
        ),
        file=sys.stderr,
    )

    resolved_by_domain, errors_by_domain = resolve_all_domains(
        domains=all_domains,
        resolver=resolver,
        workers=workers,
        timeout=timeout,
        retries=retries,
        progress_every=progress_every,
    )
    return all_domains, domains_by_region, resolved_by_domain, errors_by_domain


def _write_lines(path: Path, lines: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(lines).strip()
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


def main() -> int:
    args = parse_args()
    regions = normalize_regions(args.regions)
    if not regions:
        print("No regions provided.", file=sys.stderr)
        return 2

    all_domains, domains_by_region, resolved_by_domain, errors_by_domain = collect_voice_domain_ips(
        regions=regions,
        db_host=args.crtsh_db_host,
        db_port=args.crtsh_db_port,
        db_name=args.crtsh_db_name,
        db_user=args.crtsh_db_user,
        db_connect_timeout=args.crtsh_db_connect_timeout,
        resolver=args.resolver,
        workers=args.workers,
        timeout=args.timeout,
        retries=args.retries,
        max_domains=args.max_domains,
        progress_every=args.progress_every,
    )

    unique_ips = sorted(
        {ip for values in resolved_by_domain.values() for ip in values},
        key=lambda ip: (ipaddress.ip_address(ip).version, ipaddress.ip_address(ip)),
    )
    domains_for_output = sorted(resolved_by_domain) if args.resolved_domains_only else all_domains

    if args.domains_out:
        _write_lines(args.domains_out, domains_for_output)
    if args.ips_out:
        _write_lines(args.ips_out, unique_ips)
    if args.json_out:
        payload = {
            "source": "crt.sh-postgresql",
            "source_query": CRTSH_SQL_QUERY.strip(),
            "regions": regions,
            "domains_by_region": {
                region: sorted(domains_by_region.get(region, set()))
                for region in sorted(regions)
            },
            "resolved_domains": {domain: resolved_by_domain[domain] for domain in sorted(resolved_by_domain)},
            "unique_ips": unique_ips,
            "resolve_errors": {domain: errors_by_domain[domain] for domain in sorted(errors_by_domain)},
        }
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    for ip in unique_ips:
        print(ip)

    unresolved = len(all_domains) - len(resolved_by_domain)
    print(
        (
            f"Matched domains: {len(all_domains)} | Resolved domains: {len(resolved_by_domain)} | "
            f"Unique IPs: {len(unique_ips)} | Unresolved: {unresolved}"
        ),
        file=sys.stderr,
    )
    if errors_by_domain:
        print(f"Resolver errors: {len(errors_by_domain)} (see --json-out for details)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
