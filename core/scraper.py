import cloudscraper
from trafilatura import extract
from playwright.sync_api import sync_playwright

def scrape_page(url: str) -> str | None:
    try:
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        res = scraper.get(url, timeout=25)
        text = extract(res.text)
        if text and len(text) > 500:
            return text
    except:
        pass

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=60000)
            content = extract(page.content())
            browser.close()
            if content and len(content) > 200:
                return content
    except:
        pass

    return None
