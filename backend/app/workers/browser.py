import os

class BrowserWorker:
    """Playwright worker. Install playwright + browser binaries to enable it."""
    def __init__(self, headless=True): self.headless=headless
    def _pw(self):
        try: from playwright.sync_api import sync_playwright
        except ImportError as e: raise RuntimeError('Playwright is not installed. Run: pip install playwright && playwright install chromium') from e
        return sync_playwright
    def open(self, url, wait_until='domcontentloaded'):
        with self._pw()() as pw:
            browser=pw.chromium.launch(headless=self.headless)
            page=browser.new_page()
            page.goto(url, wait_until=wait_until, timeout=30000)
            out={'url':page.url,'title':page.title(),'text':page.locator('body').inner_text(timeout=10000)[:50000], 'links':page.locator('a').evaluate_all('(els)=>els.slice(0,200).map(a=>({text:a.innerText,href:a.href}))')}
            browser.close(); return out
    def screenshot(self, url, path='artifacts/browser.png'):
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with self._pw()() as pw:
            browser=pw.chromium.launch(headless=self.headless); page=browser.new_page(viewport={'width':1440,'height':900})
            page.goto(url, wait_until='domcontentloaded', timeout=30000); page.screenshot(path=path, full_page=True); browser.close()
        return {'path':path}
