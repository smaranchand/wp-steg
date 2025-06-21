#!/usr/bin/env python3
# Standard library imports
import argparse
import logging
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse, unquote

# Third-party imports
import requests
import urllib3
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table

print('''
 __          _______        _____ _______ ______ _____ 
 \ \        / /  __ \      / ____|__   __|  ____/ ____|
  \ \  /\  / /| |__) |____| (___    | |  | |__ | |  __ 
   \ \/  \/ / |  ___/______\___ \   | |  |  __|| | |_ |
    \  /\  /  | |          ____) |  | |  | |___| |__| |
     \/  \/   |_|         |_____/   |_|  |______\_____| v1.0      
      
Authored by : @smaranchand | https://smaranchand.com.np                                
''')
# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Constants
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.svg', '.pdf', '.doc', '.docx', '.xls', '.xlsx'}
THUMBNAIL_SUFFIX_RE = re.compile(r'(-\d+x\d+|-scaled|-smush-original)+(\?=.*)?(?=\.[A-Za-z0-9]+$)')
FALLBACK_USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/105.0.0.0 Safari/537.36'
)
DEFAULT_TIMEOUT = 10  # seconds

console = Console()

def normalize_base_url(target):
    if not re.match(r'^[a-zA-Z]+://', target):
        target = 'http://' + target
    parsed = urlparse(target)
    netloc = parsed.netloc.lower()
    if netloc.startswith('www.'):
        netloc = netloc[4:]
    return f"{parsed.scheme}://{netloc}".rstrip('/')


def strip_www_and_scheme(url):
    p = urlparse(url)
    host = (p.hostname or '').lower()
    if host.startswith('www.'):
        host = host[4:]
    return host + p.path


def clean_url_suffix(url):
    no_query = url.split('?', 1)[0]
    return unquote(THUMBNAIL_SUFFIX_RE.sub('', no_query))


def probe_scheme(netloc):
    for scheme in ('https', 'http'):
        url = f"{scheme}://{netloc}"
        try:
            r = requests.get(url,
                             headers={'User-Agent': FALLBACK_USER_AGENT},
                             timeout=DEFAULT_TIMEOUT,
                             verify=False)
            if r.status_code < 400:
                return url
        except requests.RequestException:
            pass
    return None


def check_website_up(base_url: str) -> bool:
    try:
        resp = requests.get(base_url, timeout=DEFAULT_TIMEOUT, verify=False)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        logging.error('Website not reachable: %s', e)
        return False


def check_wordpress(base_url: str) -> bool:
    try:
        # Check wp-login.php
        resp = requests.get(f"{base_url}/wp-login.php",
                             timeout=DEFAULT_TIMEOUT,
                             verify=False)
        if resp.status_code == 200:
            return True
        # Additional check: look for 'wp-content' in homepage HTML
        resp_home = requests.get(base_url, timeout=DEFAULT_TIMEOUT, verify=False)
        if 'wp-content' in resp_home.text:
            return True
        logging.error('wp-login.php returned %d and wp-content not found on homepage', resp.status_code)
    except requests.RequestException as e:
        logging.error('Error checking WordPress login: %s', e)
    return False


def check_wp_json(base_url: str) -> bool:
    try:
        resp = requests.get(f"{base_url}/wp-json/",
                             timeout=DEFAULT_TIMEOUT,
                             verify=False)
        if resp.status_code == 200 and 'application/json' in resp.headers.get('Content-Type', ''):
            return True
        logging.error('WP-JSON API unavailable or wrong content-type')
    except requests.RequestException as e:
        logging.error('Error checking WP-JSON: %s', e)
    return False


def check_directory_listing(upload_url: str) -> bool:
    try:
        resp = requests.get(upload_url,
                             timeout=DEFAULT_TIMEOUT,
                             allow_redirects=True,
                             verify=False)
        if resp.status_code == 200 and '<title>Index of' in resp.text:
            return True
        logging.error('Directory listing not enabled or returned %d', resp.status_code)
    except requests.RequestException as e:
        logging.error('Error checking directory listing: %s', e)
    return False


def pre_check(base: str) -> bool:
    """
    Run precondition checks and report status. If any check fails, display an error and advise to fix.
    """
    upload = f"{base}/wp-content/uploads/"
    checks = [
        ('Website Reachablity', check_website_up(base)),
        ('WordPress Detection', check_wordpress(base)),
        ('WP-JSON API Availability', check_wp_json(base)),
        ('Directory Listing', check_directory_listing(upload))
    ]
    ok = True
    failed_labels = []
    print('\nPrecondition Checks:\n')
    for label, passed in checks:
        status = '✅OK' if passed else '❌FAIL'
        print(f"[{status}] {label}")
        if not passed:
            ok = False
            failed_labels.append(label)
    if not ok:
        print(f"ERROR: Failed checks: {', '.join(failed_labels)}")
        print('Condition not met for a successful audit.')
    return ok


def fetch_api_urls(base_url, verbose=False):
    page, urls, total = 1, set(), None
    headers = {'User-Agent': FALLBACK_USER_AGENT}
    while True:
        r = requests.get(
            f"{base_url}/wp-json/wp/v2/media",
            params={'per_page':100, 'page':page},
            headers=headers,
            verify=False)
        if r.status_code != 200:
            break
        if total is None:
            total = int(r.headers.get('X-WP-TotalPages', 1))
        if verbose:
            console.print(f"[cyan]Fetching API page {page}/{total}[/cyan]")
        items = r.json()
        if not items:
            break
        for item in items:
            if item.get('post') and item.get('source_url'):
                urls.add(clean_url_suffix(item['source_url']))
        if page >= total:
            break
        page += 1
    return sorted(urls)


def crawl_uploads(upload_url, verbose=False):
    found, visited = set(), set()
    skipped = 0
    def walk(url):
        nonlocal skipped
        if url in visited:
            return
        visited.add(url)
        r = requests.get(url, allow_redirects=True, verify=False)
        if r.status_code != 200:
            return
        if verbose:
            console.print(f"[magenta]Crawling {url}[/magenta]")
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('../'):
                continue
            full = urljoin(r.url, href)
            if href.endswith('/') and re.search(r'/\d{4}/(\d{2}/)?$', full):
                walk(full)
            else:
                c = clean_url_suffix(full)
                ext = os.path.splitext(c)[1].lower()
                if ext in ALLOWED_EXTENSIONS:
                    found.add(c)
                else:
                    skipped += 1
    walk(upload_url.rstrip('/') + '/')
    return sorted(found), skipped


def print_summary(api_urls, crawl_urls, skipped, orphans):
    table = Table(title="\nAudit Summary")
    table.add_column("Metric", style="bold")
    table.add_column("Count", justify="right")
    table.add_row("Files from API", str(len(api_urls)))
    table.add_row("Files from directory listing", str(len(crawl_urls)))
    table.add_row("Skipped non-media files", str(skipped))
    table.add_row("Orphaned/Uncovered files", str(len(orphans)), style="red" if orphans else "green")
    console.print(table)


def process_target(target, verbose=False):
    console.print(f"\n[bold]{datetime.now():%Y-%m-%d %H:%M:%S} Auditing {target}[/bold]")
    base = normalize_base_url(target)
    if not pre_check(base):
        return False
    probed = probe_scheme(urlparse(base).netloc)
    if not probed:
        console.print(f"[red]Error: {target} unreachable[/red]")
        return False
    console.print(f"[green]\nUsing base URL:[/] {probed}")

    api_urls = fetch_api_urls(probed, verbose)
    crawl_urls, skipped = crawl_uploads(probed + "/wp-content/uploads/", verbose)
    api_set = {strip_www_and_scheme(u) for u in api_urls}
    orphans = [u for u in crawl_urls if strip_www_and_scheme(u) not in api_set]

    # Show up to 10 orphan links and save full list
    if orphans:
        filename = f"WP_STEG_{re.sub(r'[^a-zA-Z0-9]', '_', target)}_uncovered_files.txt"
        with open(filename, 'w') as f:
            for u in orphans:
                f.write(u + '\n')
        console.print("\n[bold]Orphaned URLs (showing up to 10):[/bold]")
        for u in orphans[:10]:
            console.print(f" - {u}")
        console.print(f"\nFull list available at [magenta]{filename}[/magenta]")

    print_summary(api_urls, crawl_urls, skipped, orphans)
    return bool(orphans)


def main():
    parser = argparse.ArgumentParser(
        description="WP-Steg : WordPress Media Audit Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-t', '--target', help='Single target URL', default=None)
    parser.add_argument('-l', '--list', help='Path to file with targets, one per line')
    parser.add_argument('-v', '--verbose', help='Enable verbose output (show detailed URLs and orphan entries)', action='store_true')
    args = parser.parse_args()

    targets = []
    if args.list:
        try:
            with open(args.list) as f:
                targets = [line.strip() for line in f if line.strip()]
        except IOError as e:
            parser.error(f"Could not read list file: {e}")
    elif args.target:
        targets = [args.target]
    else:
        parser.error('Please specify a target with -t or a list of targets with -l')

    any_orphans = False
    for tgt in targets:
        if process_target(tgt, args.verbose):
            any_orphans = True

    sys.exit(1 if any_orphans else 0)


if __name__ == '__main__':
    main()
