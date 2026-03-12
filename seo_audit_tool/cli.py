"""Command-line interface for SEO Audit Tool."""

import argparse
import json
import sys

from seo_audit_tool import __version__
from seo_audit_tool.auditor import SEOAuditor
from seo_audit_tool.licensing import activate_license, get_status


def main():
    parser = argparse.ArgumentParser(
        prog="seo-audit",
        description="SEO Audit Tool - Comprehensive website SEO analysis",
    )
    parser.add_argument("--version", action="version", version=f"seo-audit-tool {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # audit command
    audit_parser = subparsers.add_parser("audit", help="Audit a URL")
    audit_parser.add_argument("url", help="URL to audit")
    audit_parser.add_argument("--crawl", action="store_true", help="Crawl entire site (Premium)")
    audit_parser.add_argument("--max-pages", type=int, default=50)
    audit_parser.add_argument("--format", choices=["html", "json"], default="html")
    audit_parser.add_argument("--output", "-o", default=None)

    # license command
    license_parser = subparsers.add_parser("license", help="Manage license")
    license_parser.add_argument("action", choices=["status", "activate"])
    license_parser.add_argument("--key", default=None)

    args = parser.parse_args()

    if args.command == "audit":
        auditor = SEOAuditor()

        if args.crawl:
            try:
                audits = auditor.audit_site(args.url, max_pages=args.max_pages)
            except PermissionError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            audits = [auditor.audit_page(args.url)]

        for audit in audits:
            print(f"\n{audit.url}")
            print(f"  Score: {audit.score}/100")
            print(f"  Title: {audit.title}")
            print(f"  Load time: {audit.load_time}s")
            print(f"  Issues: {len(audit.issues)}")
            for issue in audit.issues:
                print(f"    [{issue.severity.upper()}] {issue.message}")

        try:
            path = auditor.generate_report(audits, format=args.format, output_path=args.output)
            print(f"\nReport saved to: {path}")
        except PermissionError as e:
            print(f"Report error: {e}", file=sys.stderr)

    elif args.command == "license":
        if args.action == "status":
            status = get_status()
            print(json.dumps(status, indent=2))
        elif args.action == "activate":
            if not args.key:
                print("Error: --key required", file=sys.stderr)
                sys.exit(1)
            ok, msg = activate_license(args.key)
            print(msg)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
