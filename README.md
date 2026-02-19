# cdn_ip_ranges

**🌐 Language / Язык:** [English](README.md) | [Русский](README.ru.md)

---

`cdn_ip_ranges` collects IPv4/IPv6 subnet lists for popular CDN and hosting providers and stores them inside per-provider folders. Each folder (e.g., `aws/`, `hetzner/`) contains:

- `<provider>_plain.txt` – one subnet per line (IPv4 + IPv6).
- `<provider>_plain_ipv4.txt` – the same, but IPv4-only.
- `<provider>_amnezia_ipv4.json` – JSON for [Amnezia VPN](https://amnezia.org/) (IPv4-only, array of objects with `hostname`/`ip` fields).
- `<provider>_geoip.dat` – binary [V2Ray GeoIP](https://github.com/v2fly/geoip) format (IPv4 + IPv6).
- `<provider>_geoip_ipv4.dat` – the same, but IPv4-only.
- `<provider>_singbox.srs` – binary [sing-box ruleset](https://sing-box.sagernet.org/configuration/rule-set) format (IPv4 + IPv6).
- `<provider>_singbox_ipv4.srs` – the same, but IPv4-only.

Need every provider in a single rule set? Use the `all/` directory, which aggregates every prefix before generating the same files.

### Providers

| Provider | AS | In `all` |
|---|---|:---:|
| Akamai | AS20940, AS63949 | ✅ |
| AWS | — | ✅ |
| CDN77 | AS60068 | ✅ |
| Cloudflare | AS13335 | ✅ |
| Cogent | AS174 | ✅ |
| Constant | AS20473 | ✅ |
| Contabo | AS51167 | ✅ |
| DataCamp | AS212238 | ✅ |
| DigitalOcean | AS14061 | ✅ |
| Fastly | AS54113 | ✅ |
| GCore | AS199524 | ✅ |
| GleSYS | AS42708 | ✅ |
| Hetzner | AS24940, AS213230, AS212317 | ✅ |
| MelBiCom | AS8849, AS56630 | ✅ |
| Meta | AS32934 | ❌ |
| Oracle | AS31898 | ✅ |
| OVH | AS16276 | ✅ |
| Roblox | AS22697 | ❌ |
| Scaleway | AS12876 | ✅ |
| Scalaxy | AS58061 | ✅ |
| Telegram | AS62041, AS62014, AS211157, AS44907, AS59930 | ❌ |
| Vercel | — | ✅ |

### Usage

Guides for different apps are available in the wiki: https://github.com/123jjck/cdn-ip-ranges/wiki/Usage-(EN)

### Refreshing the data

Run `python3 scripts/update_cdn_lists.py` locally to pull the latest ranges and rewrite the text files.

### Where the data comes from

The script reads official public endpoints provided by the vendors (RIPE Stat, AWS JSON feed, Oracle public IP range JSON, DigitalOcean geo CSV feed, Vercel API) so you always get upstream information without manual copy/paste.

### Automation

GitHub Actions (`.github/workflows/update-cdn-lists.yml`) executes the script every 12 hours and commits changes whenever new prefixes appear.
