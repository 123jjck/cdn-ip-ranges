# cdn_ip_ranges

**🌐 Language / Язык:** [English](README.md) | [Русский](README.ru.md)

---

`cdn_ip_ranges` collects IPv4/IPv6 subnet lists for popular CDN providers (Akamai, AWS, CDN77, Cloudflare, Cogent, Constant, Contabo, DataCamp, DigitalOcean, Fastly, Hetzner, Oracle, OVH, Roblox, Scaleway, and Vercel) and stores them inside per-provider folders. Each folder (e.g., `aws/`, `hetzner/`) contains:

- `<provider>_plain.txt` – one subnet per line (IPv4 + IPv6).
- `<provider>_plain_ipv4.txt` – the same, but IPv4-only.
- `<provider>_amnezia_ipv4.json` – JSON for [Amnezia VPN](https://amnezia.org/) (IPv4-only, array of objects with `hostname`/`ip` fields).
- `<provider>_geoip.dat` – binary [V2Ray GeoIP](https://github.com/v2fly/geoip) format (IPv4 + IPv6).
- `<provider>_geoip_ipv4.dat` – the same, but IPv4-only.

Need every provider in a single rule set? Use the `all/` directory, which aggregates every prefix before generating the same files.

### Usage

Guides for different apps are available in the wiki: https://github.com/123jjck/cdn-ip-ranges/wiki/Usage-(EN)

### Refreshing the data

Run `python3 scripts/update_cdn_lists.py` locally to pull the latest ranges and rewrite the text files.

### Where the data comes from

The script reads official public endpoints provided by the vendors (RIPE Stat for Akamai/CDN77/Cloudflare/Cogent/Constant/Contabo/DataCamp/Fastly/Hetzner/OVH/Roblox/Scaleway, AWS JSON feed, Oracle public IP range JSON, DigitalOcean geo CSV feed, Vercel API) so you always get upstream information without manual copy/paste.

### Automation

GitHub Actions (`.github/workflows/update-cdn-lists.yml`) executes the script every 12 hours and commits changes whenever new prefixes appear.
