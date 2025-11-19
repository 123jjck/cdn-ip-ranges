# cdn_ip_ranges

## English

`cdn_ip_ranges` collects IPv4/IPv6 subnet lists for popular CDN providers (Hetzner, AWS, CDN77, OVH, Cloudflare, Contabo, Constant, Scaleway, Akamai, Oracle, DigitalOcean and Vercel) and stores them inside per-provider folders. Each folder (e.g., `aws/`, `hetzner/`) contains:

- `<provider>_plain.txt` – one subnet per line (IPv4 + IPv6).
- `<provider>_plain_ipv4.txt` – the same, but IPv4-only.

Need every provider in a single rule set? Use the `all/` directory, which aggregates every prefix before generating the same two files.

### Using the data in Clash/Meta

Clash can load the plain lists directly. Define a ruleset with `behavior: ipcidr` and point it at the raw GitHub URL, for example:

```yaml
hetzner:
  behavior: ipcidr
  type: http
  url: "https://raw.githubusercontent.com/123jjck/cdn-ip-ranges/refs/heads/main/hetzner/hetzner_plain_ipv4.txt"
  interval: 86400
  path: ./ruleset/hetzner.txt
  format: text
```

### Refreshing the data

Run `python3 scripts/update_cdn_lists.py` locally to pull the latest ranges and rewrite the text files.

### Where the data comes from

The script reads official public endpoints provided by the vendors (RIPE Stat for Hetzner/CDN77/OVH/Cloudflare/Contabo/Constant/Scaleway/Akamai, AWS JSON feed, Oracle public IP range JSON, DigitalOcean geo CSV feed) so you always get upstream information without manual copy/paste.

### Automation

GitHub Actions (`.github/workflows/update-cdn-lists.yml`) executes the script every 12 hours and commits changes whenever new prefixes appear.

---

## Русский

`cdn_ip_ranges` собирает списки IPv4/IPv6 подсетей для популярных CDN  
(Hetzner, AWS, CDN77, OVH, Cloudflare, Contabo, Constant, Scaleway, Akamai, Oracle, DigitalOcean и Vercel)  
и складывает их по папкам провайдеров (например, `aws/`, `hetzner/`).  
Внутри каждой папки:

- `<провайдер>_plain.txt` — по одной подсети на строку (IPv4+IPv6).
- `<провайдер>_plain_ipv4.txt` — только IPv4-вариант.

Нужен единый набор правил сразу для всех CDN?  
Берите файлы из папки `all/` — туда попадают все подсети перед генерацией тех же двух файлов.

Также доступен сервис [cheburcheck.ru](https://github.com/LowderPlay/cheburcheck) — он позволяет проверить домен или IP-адрес на наличие в любых списках проекта, а также в списках РКН.

### Использование в Clash/Meta

Clash может подцепить plain-файлы напрямую через ruleset с `behavior: ipcidr`. Пример:

```yaml
hetzner:
  behavior: ipcidr
  type: http
  url: "https://raw.githubusercontent.com/123jjck/cdn-ip-ranges/refs/heads/main/hetzner/hetzner_plain_ipv4.txt"
  interval: 86400
  path: ./ruleset/hetzner.txt
  format: text
```

### Как обновить данные

Запустите локально:

~~~bash
python3 scripts/update_cdn_lists.py
~~~

Скрипт скачает актуальные диапазоны и перезапишет файлы.

### Источники информации

Скрипт использует официальные публичные точки доступа провайдеров (RIPE Stat для Hetzner/CDN77/OVH/Cloudflare/Contabo/Constant/Scaleway/Akamai, JSON‑фид AWS, JSON Oracle с публичными IP, DigitalOcean geo CSV feed), поэтому данные всегда поступают напрямую от владельцев сетей.

### Автоматизация

GitHub Actions (`.github/workflows/update-cdn-lists.yml`) выполняет обновление каждые 12 часов и коммитит изменения, если появились новые подсети.
