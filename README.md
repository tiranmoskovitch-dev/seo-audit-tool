# SEO Audit Tool

Comprehensive website SEO analysis. Get actionable insights to improve your search rankings.

![Python](https://img.shields.io/badge/Python-3.8+-blue) ![License](https://img.shields.io/badge/License-MIT-green) ![Version](https://img.shields.io/badge/Version-1.0.0-orange)

## Features

| Feature | Free | Premium |
|---------|:----:|:-------:|
| Single page audit | Yes | Yes |
| HTML report with scores | Yes | Yes |
| Meta tags, headings, images | Yes | Yes |
| Links, performance, security | Yes | Yes |
| **Full site crawl** | - | Yes |
| **Competitor comparison** | - | Yes |
| **JSON export** | - | Yes |
| **Scheduled audits** | - | Yes |
| **Up to 50 pages per crawl** | - | Yes |

**30-day free trial** includes all Premium features.

## Checks Performed

- **Meta Tags** - title, description, viewport, canonical, Open Graph
- **Headings** - H1 count, hierarchy, structure
- **Images** - alt text coverage, lazy loading
- **Links** - broken links, noopener/noreferrer, internal/external ratio
- **Performance** - load time, HTML size
- **Security** - HTTPS, HSTS, security headers

## Install

```bash
pip install requests beautifulsoup4 lxml
```

## Quick Start

```bash
# Basic single-page audit
python seo_audit.py --url "https://example.com" --output report.html

# Crawl entire site (Premium)
python seo_audit.py --url "https://example.com" --crawl --depth 3

# Compare with competitor (Premium)
python seo_audit.py --url "https://mysite.com" --competitor "https://rival.com"

# JSON output (Premium)
python seo_audit.py --url "https://example.com" --format json -o audit.json
```

## Report Output

Beautiful dark-themed HTML report with:
- Overall SEO score (0-100)
- Category breakdown with individual scores
- Issues sorted by severity (Critical / Warning / Info)
- Actionable fix recommendations for every issue
- Competitor comparison table (Premium)

## Activate Premium

```bash
python seo_audit.py --activate YOUR-LICENSE-KEY
```

Get your key at [tirandev.gumroad.com](https://tirandev.gumroad.com)

## License

MIT License - free for personal and commercial use.
Premium features require a license key after the 30-day trial.
