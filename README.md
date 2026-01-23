# cdn_ip_ranges

## English

`cdn_ip_ranges` collects IPv4/IPv6 subnet lists for popular CDN providers (Akamai, AWS, CDN77, Cloudflare, Cogent, Constant, Contabo, DataCamp, DigitalOcean, Fastly, Hetzner, Oracle, OVH, Roblox, Scaleway, and Vercel) and stores them inside per-provider folders. Each folder (e.g., `aws/`, `hetzner/`) contains:

- `<provider>_plain.txt` – one subnet per line (IPv4 + IPv6).
- `<provider>_plain_ipv4.txt` – the same, but IPv4-only.

Need every provider in a single rule set? Use the `all/` directory, which aggregates every prefix before generating the same two files.

### Usage

Guides for different apps are available in the wiki: https://github.com/123jjck/cdn-ip-ranges/wiki/Usage-(EN)

### Refreshing the data

Run `python3 scripts/update_cdn_lists.py` locally to pull the latest ranges and rewrite the text files.

### Where the data comes from

The script reads official public endpoints provided by the vendors (RIPE Stat for Akamai/CDN77/Cloudflare/Cogent/Constant/Contabo/DataCamp/Fastly/Hetzner/OVH/Roblox/Scaleway, AWS JSON feed, Oracle public IP range JSON, DigitalOcean geo CSV feed, Vercel API) so you always get upstream information without manual copy/paste.

### Automation

GitHub Actions (`.github/workflows/update-cdn-lists.yml`) executes the script every 12 hours and commits changes whenever new prefixes appear.

---

## Русский

`cdn_ip_ranges` собирает списки IPv4/IPv6 подсетей для популярных CDN
(Akamai, AWS, CDN77, Cloudflare, Cogent, Constant, Contabo, DataCamp, DigitalOcean, Fastly, Hetzner, Oracle, OVH, Roblox, Scaleway и Vercel)
и складывает их по папкам провайдеров (например, `aws/`, `hetzner/`).
Внутри каждой папки:

- `<провайдер>_plain.txt` — по одной подсети на строку (IPv4+IPv6).
- `<провайдер>_plain_ipv4.txt` — только IPv4-вариант.

Нужен единый набор правил сразу для всех CDN?  
Берите файлы из папки `all/` — туда попадают все подсети перед генерацией тех же двух файлов.

Также доступен сервис [cheburcheck.ru](https://github.com/LowderPlay/cheburcheck) — он позволяет проверить домен или IP-адрес на наличие в любых списках проекта, а также в списках РКН.

### Использование

Гайды для разных приложений есть в вики: https://github.com/123jjck/cdn-ip-ranges/wiki/Usage-(RU)

### Как обновить данные

Запустите локально:

~~~bash
python3 scripts/update_cdn_lists.py
~~~

Скрипт скачает актуальные диапазоны и перезапишет файлы.

### Источники информации

Скрипт использует официальные публичные точки доступа провайдеров (RIPE Stat для Akamai/CDN77/Cloudflare/Cogent/Constant/Contabo/DataCamp/Fastly/Hetzner/OVH/Roblox/Scaleway, JSON‑фид AWS, JSON Oracle с публичными IP, DigitalOcean geo CSV feed, Vercel API), поэтому данные всегда поступают напрямую от владельцев сетей.

### Автоматизация

GitHub Actions (`.github/workflows/update-cdn-lists.yml`) выполняет обновление каждые 12 часов и коммитит изменения, если появились новые подсети.
