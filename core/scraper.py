import time
import logging
import urllib3
import cloudscraper
import requests
from trafilatura import extract
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def _extract_supplemental_html(html: str) -> str:
    """
    Extract small, high-signal HTML snippets that trafilatura may drop.
    Returns a compact string (NOT full HTML).
    """
    soup = BeautifulSoup(html, "lxml")

    snippets = []

    # Headings (often contain notices)
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        text = tag.get_text(strip=True)
        if len(text) > 20:
            snippets.append(f"[HEADING] {text}")

    # Tables (dates, schedules)
    for table in soup.find_all("table"):
        table_text = table.get_text(" ", strip=True)
        if len(table_text) > 50:
            snippets.append(f"[TABLE] {table_text[:800]}")

    # Strong / emphasized notices
    for tag in soup.find_all(["strong", "b"]):
        text = tag.get_text(strip=True)
        if len(text) > 20:
            snippets.append(f"[NOTICE] {text}")

    return "\n".join(snippets[:10])  # hard cap to avoid noise


def scrape_page(url: str) -> str | None:
    retries = 3
    timeout = 25

    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )

    # ---------- Phase 1: cloudscraper ----------
    for attempt in range(retries):
        try:
            res = scraper.get(url, timeout=timeout, verify=True)

            if res.status_code == 200:
                main_text = extract(res.text)
                supplemental = _extract_supplemental_html(res.text)

                if main_text and len(main_text) > 500:
                    return (
                        "PRIMARY_CONTENT:\n"
                        + main_text
                        + "\n\nSUPPLEMENTAL_SNIPPETS:\n"
                        + supplemental
                    )

            else:
                logger.warning(f"[cloudscraper] Status {res.status_code} for {url}")

        except Exception as e:
            is_ssl_error = (
                "SSLError" in str(e)
                or "certificate verify failed" in str(e)
                or "check_hostname" in str(e)
            )

            if is_ssl_error:
                try:
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    logger.warning(f"[SSL fallback] Retrying without verification: {url}")

                    res = requests.get(
                        url,
                        timeout=timeout,
                        verify=False,
                        headers={
                            "User-Agent": (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/120.0.0.0 Safari/537.36"
                            )
                        },
                    )

                    if res.status_code == 200:
                        main_text = extract(res.text)
                        supplemental = _extract_supplemental_html(res.text)

                        if main_text and len(main_text) > 500:
                            return (
                                "PRIMARY_CONTENT:\n"
                                + main_text
                                + "\n\nSUPPLEMENTAL_SNIPPETS:\n"
                                + supplemental
                            )

                except Exception as ssl_e:
                    logger.error(f"[fallback-requests] Failed for {url}: {ssl_e}")

            logger.error(f"[cloudscraper] Error for {url}: {e}")

        if attempt < retries - 1:
            time.sleep(15)

    # ---------- Phase 2: Playwright ----------
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=60000)

            html = page.content()
            main_text = extract(html)
            supplemental = _extract_supplemental_html(html)

            browser.close()

            if main_text and len(main_text) > 200:
                return (
                    "PRIMARY_CONTENT:\n"
                    + main_text
                    + "\n\nSUPPLEMENTAL_SNIPPETS:\n"
                    + supplemental
                )

    except Exception as e:
        logger.error(f"[playwright] Failed for {url}: {e}")

    return None
