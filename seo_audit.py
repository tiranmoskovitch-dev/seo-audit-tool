#!/usr/bin/env python3
"""
SEO Audit Tool - Comprehensive website SEO analysis.
Get actionable insights to improve your search rankings.

Free tier:  Single page audit, HTML report
Premium:    Full site crawl, competitor analysis, JSON/CSV export, scheduled audits

Usage:
  seo-audit --url "https://example.com" --output report.html
  seo-audit --url "https://example.com" --crawl --depth 3 --output full_report.html
  seo-audit --url "https://example.com" --competitor "https://rival.com"
  seo-audit --activate YOUR-LICENSE-KEY
"""

__version__ = "1.0.0"

import argparse
import csv
import json
import sys
import re
from urllib.parse import urlparse, urljoin
from pathlib import Path
from datetime import datetime
from collections import deque

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Install dependencies: pip install requests beautifulsoup4 lxml")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
try:
    from license_gate import LicenseGate
except ImportError:
    class LicenseGate:
        def __init__(self, n): pass
        def check(self, silent=False): return "trial"
        def is_premium(self): return True
        def require_premium(self, f=""): return True
        def handle_activate_flag(self, a=None): return None
        @staticmethod
        def add_activate_arg(p): p.add_argument('--activate', help='License key')

gate = LicenseGate("seo-audit-tool")

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
FREE_PAGE_LIMIT = 1


def fetch_page(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        load_time = resp.elapsed.total_seconds()
        return resp, load_time
    except Exception as e:
        return None, str(e)


def check_meta_tags(soup, url):
    issues = []
    score = 100

    title = soup.find('title')
    if not title or not title.string:
        issues.append({'severity': 'critical', 'issue': 'Missing <title> tag', 'fix': 'Add a unique, descriptive title tag (50-60 characters)'})
        score -= 20
    elif len(title.string.strip()) < 10:
        issues.append({'severity': 'warning', 'issue': f'Title too short ({len(title.string.strip())} chars)', 'fix': 'Expand title to 50-60 characters'})
        score -= 10
    elif len(title.string.strip()) > 60:
        issues.append({'severity': 'warning', 'issue': f'Title too long ({len(title.string.strip())} chars)', 'fix': 'Shorten title to under 60 characters'})
        score -= 5

    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if not meta_desc or not meta_desc.get('content'):
        issues.append({'severity': 'critical', 'issue': 'Missing meta description', 'fix': 'Add meta description (150-160 characters)'})
        score -= 15
    elif len(meta_desc['content']) < 50:
        issues.append({'severity': 'warning', 'issue': 'Meta description too short', 'fix': 'Expand to 150-160 characters'})
        score -= 5

    viewport = soup.find('meta', attrs={'name': 'viewport'})
    if not viewport:
        issues.append({'severity': 'critical', 'issue': 'Missing viewport meta tag', 'fix': 'Add <meta name="viewport" content="width=device-width, initial-scale=1">'})
        score -= 10

    canonical = soup.find('link', attrs={'rel': 'canonical'})
    if not canonical:
        issues.append({'severity': 'warning', 'issue': 'Missing canonical tag', 'fix': f'Add <link rel="canonical" href="{url}">'})
        score -= 5

    og_title = soup.find('meta', attrs={'property': 'og:title'})
    og_image = soup.find('meta', attrs={'property': 'og:image'})
    if not og_title:
        issues.append({'severity': 'info', 'issue': 'Missing Open Graph title', 'fix': 'Add og:title for social sharing'})
        score -= 3
    if not og_image:
        issues.append({'severity': 'info', 'issue': 'Missing Open Graph image', 'fix': 'Add og:image for social sharing previews'})
        score -= 3

    return issues, max(score, 0)


def check_headings(soup):
    issues = []
    score = 100

    h1s = soup.find_all('h1')
    if len(h1s) == 0:
        issues.append({'severity': 'critical', 'issue': 'No H1 tag found', 'fix': 'Add exactly one H1 tag with your primary keyword'})
        score -= 20
    elif len(h1s) > 1:
        issues.append({'severity': 'warning', 'issue': f'Multiple H1 tags ({len(h1s)})', 'fix': 'Use only one H1 per page'})
        score -= 10

    h2s = soup.find_all('h2')
    if len(h2s) == 0:
        issues.append({'severity': 'warning', 'issue': 'No H2 tags found', 'fix': 'Add H2 subheadings to structure content'})
        score -= 10

    headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    prev_level = 0
    for h in headings:
        level = int(h.name[1])
        if level > prev_level + 1 and prev_level > 0:
            issues.append({'severity': 'info', 'issue': f'Heading hierarchy skip: H{prev_level} -> H{level}', 'fix': 'Maintain proper heading hierarchy'})
            score -= 3
            break
        prev_level = level

    return issues, max(score, 0)


def check_images(soup):
    issues = []
    score = 100
    images = soup.find_all('img')
    no_alt = [img for img in images if not img.get('alt')]

    if no_alt:
        pct = len(no_alt) / len(images) * 100 if images else 0
        issues.append({
            'severity': 'warning' if pct < 50 else 'critical',
            'issue': f'{len(no_alt)}/{len(images)} images missing alt text ({pct:.0f}%)',
            'fix': 'Add descriptive alt text to all images for accessibility and SEO'
        })
        score -= min(int(pct / 5), 30)

    large_images = [img for img in images if not img.get('loading')]
    if large_images and len(images) > 3:
        issues.append({'severity': 'info', 'issue': 'Images without lazy loading', 'fix': 'Add loading="lazy" to below-the-fold images'})
        score -= 5

    return issues, max(score, 0), len(images)


def check_links(soup, base_url):
    issues = []
    score = 100
    links = soup.find_all('a', href=True)
    internal = 0
    external = 0
    broken_format = 0

    parsed_base = urlparse(base_url)
    for link in links:
        href = link['href']
        if href.startswith('#') or href.startswith('mailto:') or href.startswith('tel:'):
            continue
        parsed = urlparse(href)
        if parsed.netloc and parsed.netloc != parsed_base.netloc:
            external += 1
        else:
            internal += 1
        if href == '' or href == '#':
            broken_format += 1

    if broken_format > 0:
        issues.append({'severity': 'warning', 'issue': f'{broken_format} links with empty/broken href', 'fix': 'Fix or remove empty links'})
        score -= 5

    nofollow_ext = [l for l in links if l.get('target') == '_blank' and not (l.get('rel') and 'noopener' in ' '.join(l.get('rel', [])))]
    if nofollow_ext:
        issues.append({'severity': 'info', 'issue': f'{len(nofollow_ext)} external links without rel="noopener"', 'fix': 'Add rel="noopener noreferrer" to target="_blank" links'})
        score -= 3

    return issues, max(score, 0), {'internal': internal, 'external': external}


def check_performance(load_time, html_size):
    issues = []
    score = 100

    if load_time > 3:
        issues.append({'severity': 'critical', 'issue': f'Slow page load: {load_time:.1f}s', 'fix': 'Optimize server response time, enable caching, compress assets'})
        score -= 20
    elif load_time > 1.5:
        issues.append({'severity': 'warning', 'issue': f'Page load could be faster: {load_time:.1f}s', 'fix': 'Consider CDN, image optimization, code minification'})
        score -= 10

    if html_size > 100000:
        issues.append({'severity': 'warning', 'issue': f'Large HTML size: {html_size/1024:.0f}KB', 'fix': 'Reduce inline CSS/JS, remove unnecessary elements'})
        score -= 10

    return issues, max(score, 0)


def check_security(resp, url):
    issues = []
    score = 100

    if not url.startswith('https'):
        issues.append({'severity': 'critical', 'issue': 'Site not using HTTPS', 'fix': 'Install SSL certificate and redirect HTTP to HTTPS'})
        score -= 25

    headers = resp.headers
    if 'Strict-Transport-Security' not in headers:
        issues.append({'severity': 'warning', 'issue': 'Missing HSTS header', 'fix': 'Add Strict-Transport-Security header'})
        score -= 5

    if 'X-Content-Type-Options' not in headers:
        issues.append({'severity': 'info', 'issue': 'Missing X-Content-Type-Options header', 'fix': 'Add X-Content-Type-Options: nosniff'})
        score -= 3

    return issues, max(score, 0)


def crawl_site(start_url, max_depth=3, max_pages=50):
    """Crawl site and return list of internal URLs. Premium feature."""
    visited = set()
    queue = deque([(start_url, 0)])
    parsed_base = urlparse(start_url)

    while queue and len(visited) < max_pages:
        url, depth = queue.popleft()
        if url in visited or depth > max_depth:
            continue
        visited.add(url)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, 'lxml')
            for a in soup.find_all('a', href=True):
                href = a['href']
                full = urljoin(url, href).split('#')[0].split('?')[0]
                parsed = urlparse(full)
                if parsed.netloc == parsed_base.netloc and full not in visited:
                    queue.append((full, depth + 1))
        except Exception:
            continue

    return list(visited)


def audit_page(url):
    """Run all checks on a single page."""
    resp, load_time = fetch_page(url)
    if not resp:
        return None

    soup = BeautifulSoup(resp.text, 'lxml')
    html_size = len(resp.text)

    results = {}
    meta_issues, meta_score = check_meta_tags(soup, url)
    results['Meta Tags'] = {'issues': meta_issues, 'score': meta_score}

    h_issues, h_score = check_headings(soup)
    results['Heading Structure'] = {'issues': h_issues, 'score': h_score}

    img_issues, img_score, img_count = check_images(soup)
    results['Images'] = {'issues': img_issues, 'score': img_score, 'extra': f'Total images: {img_count}'}

    link_issues, link_score, link_stats = check_links(soup, url)
    results['Links'] = {'issues': link_issues, 'score': link_score, 'extra': f'Internal: {link_stats["internal"]} | External: {link_stats["external"]}'}

    perf_issues, perf_score = check_performance(load_time, html_size)
    results['Performance'] = {'issues': perf_issues, 'score': perf_score, 'extra': f'Load time: {load_time:.2f}s | HTML size: {html_size/1024:.0f}KB'}

    sec_issues, sec_score = check_security(resp, url)
    results['Security'] = {'issues': sec_issues, 'score': sec_score}

    return results


def generate_html_report(url, results, output_path, competitor_results=None):
    overall_score = sum(r['score'] for r in results.values()) // len(results)
    all_issues = []
    for category, data in results.items():
        for issue in data['issues']:
            issue['category'] = category
            all_issues.append(issue)

    critical = len([i for i in all_issues if i['severity'] == 'critical'])
    warnings = len([i for i in all_issues if i['severity'] == 'warning'])
    info = len([i for i in all_issues if i['severity'] == 'info'])

    score_color = '#00d4aa' if overall_score >= 80 else '#ffcc00' if overall_score >= 60 else '#ff4466'

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>SEO Audit: {url}</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; background: #0a0a12; color: #e8e8f0; max-width: 900px; margin: 0 auto; padding: 40px 20px; }}
h1 {{ color: #00d4aa; }} h2 {{ color: #9898b8; border-bottom: 1px solid #2a2a45; padding-bottom: 8px; }}
.score {{ font-size: 72px; font-weight: 700; color: {score_color}; text-align: center; }}
.score-label {{ text-align: center; color: #9898b8; font-size: 14px; }}
.stats {{ display: flex; gap: 20px; justify-content: center; margin: 20px 0 40px; }}
.stat {{ background: #1a1a2e; padding: 16px 24px; border-radius: 10px; text-align: center; }}
.stat .num {{ font-size: 28px; font-weight: 700; }}
.stat .label {{ font-size: 12px; color: #9898b8; }}
.critical .num {{ color: #ff4466; }} .warning .num {{ color: #ffcc00; }} .info .num {{ color: #4488ff; }}
.issue {{ background: #1a1a2e; border-radius: 8px; padding: 16px; margin: 8px 0; border-left: 3px solid; }}
.issue.critical {{ border-color: #ff4466; }} .issue.warning {{ border-color: #ffcc00; }} .issue.info {{ border-color: #4488ff; }}
.issue .title {{ font-weight: 600; margin-bottom: 4px; }}
.issue .fix {{ font-size: 13px; color: #9898b8; }}
.category {{ background: #12121f; padding: 20px; border-radius: 10px; margin: 16px 0; }}
.cat-header {{ display: flex; justify-content: space-between; }}
.cat-score {{ font-size: 24px; font-weight: 700; }}
.footer {{ text-align: center; color: #686888; font-size: 12px; margin-top: 40px; }}
</style></head><body>
<h1>SEO Audit Report</h1>
<p style="color:#9898b8">URL: <a href="{url}" style="color:#00d4aa">{url}</a><br>Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<div class="score">{overall_score}/100</div>
<div class="score-label">Overall SEO Score</div>
<div class="stats">
  <div class="stat critical"><div class="num">{critical}</div><div class="label">Critical</div></div>
  <div class="stat warning"><div class="num">{warnings}</div><div class="label">Warnings</div></div>
  <div class="stat info"><div class="num">{info}</div><div class="label">Info</div></div>
</div>
"""

    for category, data in results.items():
        s = data['score']
        sc = '#00d4aa' if s >= 80 else '#ffcc00' if s >= 60 else '#ff4466'
        html += f"""<div class="category">
<div class="cat-header"><h2>{category}</h2><div class="cat-score" style="color:{sc}">{s}/100</div></div>
"""
        if data.get('extra'):
            html += f'<p style="font-size:13px;color:#9898b8">{data["extra"]}</p>'
        for issue in data['issues']:
            html += f"""<div class="issue {issue['severity']}">
<div class="title">[{issue['severity'].upper()}] {issue['issue']}</div>
<div class="fix">Fix: {issue['fix']}</div></div>"""
        if not data['issues']:
            html += '<p style="color:#00d4aa">All checks passed!</p>'
        html += '</div>'

    if competitor_results:
        html += '<h2>Competitor Comparison</h2>'
        for comp_url, comp_data in competitor_results.items():
            comp_score = sum(r['score'] for r in comp_data.values()) // len(comp_data)
            diff = overall_score - comp_score
            diff_label = f'+{diff}' if diff > 0 else str(diff)
            diff_color = '#00d4aa' if diff > 0 else '#ff4466'
            html += f'<div class="category"><p><a href="{comp_url}" style="color:#00d4aa">{comp_url}</a>: {comp_score}/100 (You: <span style="color:{diff_color}">{diff_label}</span>)</p></div>'

    html += f'<div class="footer">Generated by SEO Audit Tool v{__version__} | {datetime.now().strftime("%Y-%m-%d")}</div></body></html>'

    Path(output_path).write_text(html, encoding='utf-8')
    return overall_score, critical, warnings, info


def save_json_report(url, results, output_path):
    data = {
        'url': url,
        'date': datetime.now().isoformat(),
        'overall_score': sum(r['score'] for r in results.values()) // len(results),
        'categories': {}
    }
    for category, cat_data in results.items():
        data['categories'][category] = {
            'score': cat_data['score'],
            'issues': cat_data['issues']
        }
    Path(output_path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(
        description='SEO Audit Tool - Comprehensive website SEO analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  seo_audit --url "https://example.com" --output report.html
  seo_audit --url "https://example.com" --crawl --depth 3
  seo_audit --url "https://example.com" --competitor "https://rival.com"
  seo_audit --activate YOUR-KEY""")
    parser.add_argument('--url', help='URL to audit')
    parser.add_argument('--output', '-o', default='seo_report.html', help='Output file')
    parser.add_argument('--format', '-f', choices=['html', 'json'], default='html')
    parser.add_argument('--crawl', action='store_true', help='[Premium] Crawl entire site')
    parser.add_argument('--depth', type=int, default=2, help='[Premium] Crawl depth (default: 2)')
    parser.add_argument('--max-pages', type=int, default=50, help='[Premium] Max pages to crawl')
    parser.add_argument('--competitor', action='append', help='[Premium] Competitor URL to compare')
    parser.add_argument('--version', '-v', action='version', version=f'SEO Audit Tool {__version__}')
    LicenseGate.add_activate_arg(parser)
    args = parser.parse_args()

    gate.handle_activate_flag(args)
    if hasattr(args, 'activate') and args.activate:
        return

    gate.check()

    if not args.url:
        parser.print_help()
        return

    url = args.url
    if not url.startswith('http'):
        url = 'https://' + url

    # Premium feature gates
    if args.crawl and not gate.require_premium("Full site crawl"):
        args.crawl = False

    if args.competitor and not gate.require_premium("Competitor analysis"):
        args.competitor = None

    if args.format == 'json' and not gate.require_premium("JSON export"):
        args.format = 'html'

    urls_to_audit = [url]
    if args.crawl:
        print(f"  Crawling site (depth={args.depth}, max={args.max_pages})...")
        urls_to_audit = crawl_site(url, args.depth, args.max_pages)
        print(f"  Found {len(urls_to_audit)} pages")

    # Audit pages
    all_results = {}
    for page_url in urls_to_audit:
        print(f"  Auditing: {page_url}")
        results = audit_page(page_url)
        if results:
            all_results[page_url] = results

    if not all_results:
        print("  Failed to audit any pages.")
        return

    # Use first page results for single-page report
    primary_results = all_results[url] if url in all_results else list(all_results.values())[0]

    # Competitor analysis
    competitor_results = {}
    if args.competitor:
        for comp_url in args.competitor:
            if not comp_url.startswith('http'):
                comp_url = 'https://' + comp_url
            print(f"  Auditing competitor: {comp_url}")
            comp = audit_page(comp_url)
            if comp:
                competitor_results[comp_url] = comp

    # Output
    if args.format == 'json':
        save_json_report(url, primary_results, args.output)
        print(f"  JSON report saved to {args.output}")
    else:
        score, crit, warn, inf = generate_html_report(url, primary_results, args.output, competitor_results or None)
        print(f"  Report saved to {args.output}")
        print(f"  Score: {score}/100 | {crit} critical, {warn} warnings, {inf} info")


if __name__ == '__main__':
    main()
