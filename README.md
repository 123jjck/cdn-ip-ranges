# cdn_ip_ranges

## English

`cdn_ip_ranges` collects IPv4/IPv6 subnet lists for popular CDN providers (Hetzner, AWS, CDN77, OVH, Cloudflare, Oracle) and stores them inside per-provider folders. Each folder (e.g., `aws/`, `hetzner/`) contains:

- `<provider>_plain.txt` – one subnet per line.
- `<provider>_plain_ipv4.txt` – the same, but IPv4-only.
- `<provider>_clash.txt` – `IP-CIDR` / `IP-CIDR6` entries for Clash/Meta.
- `<provider>_clash_ipv4.txt` – Clash rules limited to IPv4.

### Refreshing the data

Run `python3 scripts/update_cdn_lists.py` locally to pull the latest ranges and rewrite the text files.

### Where the data comes from

The script reads official public endpoints provided by the vendors (RIPE Stat for Hetzner/CDN77/OVH, AWS JSON feed, Cloudflare IPv4/IPv6 lists, Oracle public IP range JSON) so you always get upstream information without manual copy/paste.

### Automation

GitHub Actions (`.github/workflows/update-cdn-lists.yml`) executes the script every 12 hours and commits changes whenever new prefixes appear.

---

## Русский

`cdn_ip_ranges` собирает списки IPv4/IPv6 подсетей для популярных CDN (Hetzner, AWS, CDN77, OVH, Cloudflare, Oracle) и складывает их по папкам провайдеров (например, `aws/`, `hetzner/`). Внутри каждой папки:

- `<провайдер>_plain.txt` — по одной подсети на строку.
- `<провайдер>_plain_ipv4.txt` — только IPv4-вариант.
- `<провайдер>_clash.txt` — записи `IP-CIDR` / `IP-CIDR6` для Clash/Meta.
- `<провайдер>_clash_ipv4.txt` — Clash-правила с IPv4.

### Как обновить данные

Запустите локально `python3 scripts/update_cdn_lists.py`, чтобы скачать актуальные диапазоны и перезаписать файлы.

### Источники информации

Скрипт использует официальные публичные точки доступа провайдеров (RIPE Stat для Hetzner/CDN77/OVH, JSON‑фид AWS, страницы Cloudflare с IPv4/IPv6, JSON Oracle с публичными IP), поэтому данные всегда поступают напрямую от владельцев сетей.

### Автоматизация

GitHub Actions (`.github/workflows/update-cdn-lists.yml`) выполняет скрипт каждые 12 часов и коммитит изменения, когда появляются новые подсети.
