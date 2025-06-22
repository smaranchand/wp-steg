# WP-STEG

WP-STEG is a WordPress security tool that identifies orphaned or draft media files in a WordPress instance. These are files such as images, documents, or PDFs that have been uploaded to the server but are either attached to draft posts or not attached to any published content. For example, a PDF uploaded to a draft post or a file uploaded but never referenced publicly in a post.

If a WordPress site runs on a single- or two-tier architecture without any Content Delivery Network (CDN) and directory listing is enabled, one can browse the /wp-content/uploads/ directory and access media files, including those not intended for public viewing — at least for the moment. This may result in the unintentional exposure of sensitive or private content using simple logic.

WP-STEG operates by using the WP REST API to retrieve a list of media files that are currently linked to published posts. It then compares this list with the actual files present in the uploads directory (retrieved via directory listing). Any files found in the directory but missing from the API response are flagged as orphaned and potential leaks.

![](https://github.com/smaranchand/wp-steg/blob/main/illustration.svg)

---

## Features

* Detects orphaned (unlinked) media files in WordPress.
* Runs precondition checks: verifies WordPress existence, Public API, and open directory listing.
* Recursive crawl of `/wp-content/uploads/` for all accessible files.
* Compares disk files to those referenced by the WP REST API.
* Batch scan multiple sites or scan a single URL.
* Prints a clear summary and saves the orphaned file list per target.
* Verbose mode for full crawling details.

---

## How It Works?

1. Checks site: Ensures target is WordPress, API is accessible, and directory listing is enabled.
2. Fetches media from API: Collects all file URLs referenced by published posts.
3. Crawls uploads directory: Recursively finds all files in `/wp-content/uploads/`.
4. Compares results: Finds files on disk not referenced by the API (“orphans”).
5. Reports: CLI summary and saves a text file with orphaned file URLs.

---

## Installation

```brew install python3``` | ```apt install python3```

```pip install -r requirements.txt```

---

## Usage

Scan a single site:
```python3 wp-steg.py -t https://example.com```

Scan multiple sites from a file:
```python3 wp-steg.py -l targets.txt```

Verbose mode:
```python3 wp-steg.py -t https://example.com -v```

Options:

* -t, --target — Single target URL (e.g., https://example.com
* -l, --list — Path to file with one target URL per line
* -v, --verbose — Enable detailed crawling output

---

## Example Output
![working](https://github.com/smaranchand/wp-steg/blob/main/working.png)

---

## FAQ

Q: What are “Orphaned” files?<br>
A: Files in /wp-content/uploads/ not attached to any published post, often forgotten or left by drafts.

Q: Why does directory listing need to be enabled?
A: Without it, the script can’t see all files in uploads for comparison unless you find a way to do it with brute forcing.<br>

Q: Does this tool modify the website?<br>
A: No. It only reads public data and never writes or deletes anything.

---

## Troubleshooting

* Failed precondition: Ensure directory listing and WP-JSON are enabled and public.
* SSL errors: Self-signed/expired certs are ignored, but network issues may block scans.
* Blocked by plugins: Security plugins may block API or directory listing.

---

## Author

Concept by [Smaran Chand](https://x.com/smaranchand) | [https://smaranchand.com.np](https://smaranchand.com.np)

@ Rosemont 


---

## Legal Notice

WP-STEG is intended solely for security testing and media audits. You must only use this tool on websites you own or have been granted explicit written permission to test.

Unauthorized use of WP-STEG may violate local, national, or international laws. The developers and contributors of WP-STEG, including Author, accept no responsibility or liability for any misuse or damage caused by this tool.

Use responsibly. Always act within the bounds of applicable laws and ethical guidelines.
