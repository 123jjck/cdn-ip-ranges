# cdn_ip_ranges

**🌐 Language / Язык:** [English](README.md) | [Русский](README.ru.md)

---

`cdn_ip_ranges` собирает списки IPv4/IPv6 подсетей для популярных CDN и хостинг-провайдеров
и складывает их по папкам (например, `aws/`, `hetzner/`).
Внутри каждой папки:

- `<провайдер>_plain.txt` — по одной подсети на строку (IPv4+IPv6).
- `<провайдер>_plain_ipv4.txt` — только IPv4-вариант.
- `<провайдер>_amnezia_ipv4.json` — JSON для [Amnezia VPN](https://amnezia.org/) (только IPv4, массив объектов с полями `hostname`/`ip`).
- `<провайдер>_geoip.dat` — бинарный формат [V2Ray GeoIP](https://github.com/v2fly/geoip) (IPv4+IPv6).
- `<провайдер>_geoip_ipv4.dat` — то же самое, но только IPv4.
- `<провайдер>_singbox.srs` — бинарный формат [sing-box ruleset](https://sing-box.sagernet.org/configuration/rule-set) (IPv4+IPv6).
- `<провайдер>_singbox_ipv4.dat` — то же самое, но только IPv4.

Нужен единый набор правил сразу для всех провайдеров?
Берите файлы из папки `all/` — туда попадают все подсети перед генерацией тех же файлов.

### Провайдеры

| Провайдер | AS | В `all` |
|---|---|:---:|
| Akamai | AS20940, AS63949 | ✅ |
| AWS | — | ✅ |
| BuyVM | AS53667 | ✅ |
| CDN77 | AS60068 | ✅ |
| Cloudflare | AS13335 | ✅ |
| Cogent | AS174 | ✅ |
| Constant | AS20473 | ✅ |
| Contabo | AS51167, AS141995 | ✅ |
| DataCamp | AS212238 | ✅ |
| DigitalOcean | AS14061 | ✅ |
| Discord Voice | — | ❌ |
| Fastly | AS54113 | ✅ |
| GCore | AS199524, AS202422 | ✅ |
| GleSYS | AS42708 | ✅ |
| GTHost | AS63023 | ✅ |
| Hetzner | AS24940, AS213230, AS212317 | ✅ |
| MelBiCom | AS8849, AS56630 | ✅ |
| Meta | AS32934 | ❌ |
| Oracle | AS31898, AS6142, AS20054, AS54253 | ✅ |
| OVH | AS16276 | ✅ |
| Roblox | AS22697 | ❌ |
| Scaleway | AS12876, AS29447 | ✅ |
| Scalaxy | AS58061 | ✅ |
| Telegram | AS62041, AS62014, AS211157, AS44907, AS59930 | ❌ |
| Vercel | — | ✅ |

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

Скрипт использует официальные публичные точки доступа провайдеров (RIPE Stat, JSON‑фид AWS, JSON Oracle с публичными IP, DigitalOcean geo CSV feed, Vercel API), поэтому данные всегда поступают напрямую от владельцев сетей.

### Автоматизация

GitHub Actions (`.github/workflows/update-cdn-lists.yml`) выполняет обновление каждые 12 часов и коммитит изменения, если появились новые подсети.
