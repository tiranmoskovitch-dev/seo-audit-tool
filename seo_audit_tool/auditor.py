"""Core SEO auditing engine."""

import re
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from seo_audit_tool.licensing import check_limit, get_tier


@dataclass
class SEOIssue:
    severity: str  # 'critical', 'warning', 'info'
    category: str
    message: str
    element: str = ""
    suggestion: str = ""


@dataclass
class PageAudit:
    url: str
    status_code: int
    load_time: float
    title: str = ""
    title_length: int = 0
    meta_description: str = ""
    meta_description_length: int = 0
    h1_tags: list = field(default_factory=list)
    h2_tags: list = field(default_factory=list)
    images_total: int = 0
    images_without_alt: int = 0
    internal_links: int = 0
    external_links: int = 0
    broken_links: list = field(default_factory=list)
    word_count: int = 0
    has_canonical: bool = False
    has_robots_meta: bool = False
    has_og_tags: bool = False
    has_twitter_cards: bool = False
    has_structured_data: bool = False
    has_sitemap: bool = False
    has_robots_txt: bool = False
    mobile_viewport: bool = False
    https: bool = False
    issues: list = field(default_factory=list)
    score: int = 0


class SEOAuditor:
    """Analyze web pages for SEO best practices."""

    def __init__(self, timeout=30, user_agent=None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent or (
                "Mozilla/5.0 (compatible; SEOAuditTool/1.0; "
                "+https://github.com/tiranmoskovitch-dev/seo-audit-tool)"
            )
        })
        self.timeout = timeout

    def audit_page(self, url):
        """Run a full SEO audit on a single page.

        Args:
            url: The URL to audit.

        Returns:
            PageAudit with all findings and a score out of 100.
        """
        start = time.time()
        resp = self.session.get(url, timeout=self.timeout)
        load_time = time.time() - start
        soup = BeautifulSoup(resp.text, "html.parser")

        audit = PageAudit(
            url=url,
            status_code=resp.status_code,
            load_time=round(load_time, 2),
            https=urlparse(url).scheme == "https",
        )

        self._analyze_title(soup, audit)
        self._analyze_meta(soup, audit)
        self._analyze_headings(soup, audit)
        self._analyze_images(soup, audit)
        self._analyze_links(soup, url, audit)
        self._analyze_content(soup, audit)
        self._analyze_technical(soup, url, audit)
        self._calculate_score(audit)

        return audit

    def audit_site(self, url, max_pages=50):
        """Crawl and audit an entire site (Premium feature).

        Args:
            url: The starting URL.
            max_pages: Maximum pages to crawl.

        Returns:
            List of PageAudit objects.
        """
        allowed, msg = check_limit("full_site_crawl")
        if not allowed:
            raise PermissionError(msg)

        visited = set()
        to_visit = [url]
        results = []
        domain = urlparse(url).netloc

        while to_visit and len(visited) < max_pages:
            current = to_visit.pop(0)
            if current in visited:
                continue

            visited.add(current)
            try:
                audit = self.audit_page(current)
                results.append(audit)

                # Find internal links to crawl
                resp = self.session.get(current, timeout=self.timeout)
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    link = urljoin(current, a["href"])
                    if urlparse(link).netloc == domain and link not in visited:
                        to_visit.append(link)

                time.sleep(0.5)
            except Exception:
                continue

        return results

    def generate_report(self, audits, format="html", output_path=None):
        """Generate an SEO audit report.

        Args:
            audits: PageAudit or list of PageAudit objects.
            format: 'html', 'json', or 'pdf'.
            output_path: File path for the report.
        """
        allowed, msg = check_limit("report_format", format)
        if not allowed:
            raise PermissionError(msg)

        if isinstance(audits, PageAudit):
            audits = [audits]

        if format == "html":
            return self._report_html(audits, output_path)
        elif format == "json":
            return self._report_json(audits, output_path)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _analyze_title(self, soup, audit):
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            audit.title = title_tag.string.strip()
            audit.title_length = len(audit.title)
        if not audit.title:
            audit.issues.append(SEOIssue("critical", "title", "Missing page title",
                                         suggestion="Add a <title> tag between 50-60 characters"))
        elif audit.title_length < 30:
            audit.issues.append(SEOIssue("warning", "title",
                                         f"Title too short ({audit.title_length} chars)",
                                         suggestion="Aim for 50-60 characters"))
        elif audit.title_length > 60:
            audit.issues.append(SEOIssue("warning", "title",
                                         f"Title too long ({audit.title_length} chars)",
                                         suggestion="Keep under 60 characters"))

    def _analyze_meta(self, soup, audit):
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            audit.meta_description = meta_desc["content"]
            audit.meta_description_length = len(audit.meta_description)
        if not audit.meta_description:
            audit.issues.append(SEOIssue("critical", "meta",
                                         "Missing meta description",
                                         suggestion="Add a meta description between 150-160 characters"))
        elif audit.meta_description_length < 120:
            audit.issues.append(SEOIssue("warning", "meta",
                                         f"Meta description short ({audit.meta_description_length} chars)",
                                         suggestion="Aim for 150-160 characters"))
        elif audit.meta_description_length > 160:
            audit.issues.append(SEOIssue("warning", "meta",
                                         f"Meta description too long ({audit.meta_description_length} chars)",
                                         suggestion="Keep under 160 characters"))

        # OG tags
        audit.has_og_tags = bool(soup.find("meta", property=re.compile(r"^og:")))
        if not audit.has_og_tags:
            audit.issues.append(SEOIssue("info", "social",
                                         "Missing Open Graph tags",
                                         suggestion="Add og:title, og:description, og:image"))

        # Twitter cards
        audit.has_twitter_cards = bool(soup.find("meta", attrs={"name": re.compile(r"^twitter:")}))
        if not audit.has_twitter_cards:
            audit.issues.append(SEOIssue("info", "social",
                                         "Missing Twitter Card tags"))

    def _analyze_headings(self, soup, audit):
        audit.h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1")]
        audit.h2_tags = [h.get_text(strip=True) for h in soup.find_all("h2")]

        if not audit.h1_tags:
            audit.issues.append(SEOIssue("critical", "headings", "Missing H1 tag",
                                         suggestion="Add exactly one H1 tag per page"))
        elif len(audit.h1_tags) > 1:
            audit.issues.append(SEOIssue("warning", "headings",
                                         f"Multiple H1 tags ({len(audit.h1_tags)})",
                                         suggestion="Use exactly one H1 per page"))

    def _analyze_images(self, soup, audit):
        images = soup.find_all("img")
        audit.images_total = len(images)
        audit.images_without_alt = sum(1 for img in images if not img.get("alt"))
        if audit.images_without_alt > 0:
            audit.issues.append(SEOIssue("warning", "images",
                                         f"{audit.images_without_alt} images missing alt text",
                                         suggestion="Add descriptive alt text to all images"))

    def _analyze_links(self, soup, url, audit):
        domain = urlparse(url).netloc
        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"])
            if urlparse(link).netloc == domain:
                audit.internal_links += 1
            else:
                audit.external_links += 1

    def _analyze_content(self, soup, audit):
        text = soup.get_text(separator=" ", strip=True)
        words = text.split()
        audit.word_count = len(words)
        if audit.word_count < 300:
            audit.issues.append(SEOIssue("warning", "content",
                                         f"Thin content ({audit.word_count} words)",
                                         suggestion="Aim for at least 300 words per page"))

    def _analyze_technical(self, soup, url, audit):
        # Canonical
        canonical = soup.find("link", rel="canonical")
        audit.has_canonical = bool(canonical)
        if not audit.has_canonical:
            audit.issues.append(SEOIssue("warning", "technical",
                                         "Missing canonical URL",
                                         suggestion="Add <link rel='canonical'> tag"))

        # Viewport (mobile-friendliness)
        viewport = soup.find("meta", attrs={"name": "viewport"})
        audit.mobile_viewport = bool(viewport)
        if not audit.mobile_viewport:
            audit.issues.append(SEOIssue("critical", "mobile",
                                         "Missing viewport meta tag",
                                         suggestion="Add <meta name='viewport' content='width=device-width, initial-scale=1'>"))

        # HTTPS
        if not audit.https:
            audit.issues.append(SEOIssue("critical", "security",
                                         "Not using HTTPS",
                                         suggestion="Switch to HTTPS"))

        # Structured data
        audit.has_structured_data = bool(
            soup.find("script", type="application/ld+json")
            or soup.find(attrs={"itemscope": True})
        )

        # Robots meta
        robots = soup.find("meta", attrs={"name": "robots"})
        audit.has_robots_meta = bool(robots)

        # Check robots.txt and sitemap
        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        try:
            r = self.session.get(f"{base}/robots.txt", timeout=5)
            audit.has_robots_txt = r.status_code == 200
        except Exception:
            pass
        try:
            r = self.session.get(f"{base}/sitemap.xml", timeout=5)
            audit.has_sitemap = r.status_code == 200
        except Exception:
            pass

    def _calculate_score(self, audit):
        score = 100
        for issue in audit.issues:
            if issue.severity == "critical":
                score -= 15
            elif issue.severity == "warning":
                score -= 5
            elif issue.severity == "info":
                score -= 2
        audit.score = max(0, min(100, score))

    def _report_html(self, audits, path):
        path = path or "seo_audit_report.html"
        html_parts = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'>",
            "<title>SEO Audit Report</title>",
            "<style>body{font-family:sans-serif;max-width:900px;margin:0 auto;padding:20px}",
            ".score{font-size:3em;font-weight:bold}.critical{color:#dc3545}",
            ".warning{color:#ffc107}.info{color:#17a2b8}.good{color:#28a745}",
            "table{width:100%;border-collapse:collapse}td,th{padding:8px;border:1px solid #ddd;text-align:left}",
            "th{background:#f5f5f5}</style></head><body>",
            "<h1>SEO Audit Report</h1>",
            f"<p>Pages analyzed: {len(audits)}</p>",
        ]

        for audit in audits:
            score_class = "good" if audit.score >= 80 else "warning" if audit.score >= 50 else "critical"
            html_parts.append(f"<h2>{audit.url}</h2>")
            html_parts.append(f"<p class='score {score_class}'>{audit.score}/100</p>")
            html_parts.append(f"<p>Load time: {audit.load_time}s | Words: {audit.word_count} | Links: {audit.internal_links} int / {audit.external_links} ext</p>")

            if audit.issues:
                html_parts.append("<table><tr><th>Severity</th><th>Category</th><th>Issue</th><th>Suggestion</th></tr>")
                for issue in audit.issues:
                    html_parts.append(
                        f"<tr><td class='{issue.severity}'>{issue.severity.upper()}</td>"
                        f"<td>{issue.category}</td><td>{issue.message}</td>"
                        f"<td>{issue.suggestion}</td></tr>"
                    )
                html_parts.append("</table>")

        html_parts.append("<hr><p>Generated by <a href='https://github.com/tiranmoskovitch-dev/seo-audit-tool'>SEO Audit Tool</a></p>")
        html_parts.append("</body></html>")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(html_parts))
        return path

    def _report_json(self, audits, path):
        import json
        path = path or "seo_audit_report.json"
        data = []
        for audit in audits:
            data.append({
                "url": audit.url,
                "score": audit.score,
                "status_code": audit.status_code,
                "load_time": audit.load_time,
                "title": audit.title,
                "meta_description": audit.meta_description,
                "word_count": audit.word_count,
                "h1_tags": audit.h1_tags,
                "images_total": audit.images_total,
                "images_without_alt": audit.images_without_alt,
                "internal_links": audit.internal_links,
                "external_links": audit.external_links,
                "https": audit.https,
                "has_sitemap": audit.has_sitemap,
                "has_robots_txt": audit.has_robots_txt,
                "mobile_viewport": audit.mobile_viewport,
                "issues": [
                    {"severity": i.severity, "category": i.category,
                     "message": i.message, "suggestion": i.suggestion}
                    for i in audit.issues
                ],
            })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return path
