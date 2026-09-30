import asyncio,base64
from urllib.parse import urlparse
from ..config import BROWSER_HEADLESS,ALLOWED_DOMAINS
def allowed(url):
 h=(urlparse(url).hostname or '').lower();return bool(h) and ('*' in ALLOWED_DOMAINS or any(h==d or h.endswith('.'+d) for d in ALLOWED_DOMAINS))
def browse(url,action='inspect',selector='',text=''):
 if not allowed(url):return {'error':'Domain blocked by browser policy','url':url}
 try:
  from playwright.async_api import async_playwright
  async def run():
   async with async_playwright() as p:
    b=await p.chromium.launch(headless=BROWSER_HEADLESS);page=await b.new_page(viewport={'width':1440,'height':900});await page.goto(url,wait_until='domcontentloaded',timeout=30000)
    if action=='click' and selector:await page.locator(selector).first.click(timeout=10000)
    elif action=='fill' and selector:await page.locator(selector).first.fill(text,timeout=10000)
    await page.wait_for_timeout(500);title=await page.title();body=(await page.locator('body').inner_text())[:4000];shot=await page.screenshot(type='png');final=page.url;await b.close()
    return {'url':final,'title':title,'text':body,'screenshot_base64':base64.b64encode(shot).decode()}
  return asyncio.run(run())
 except Exception as e:return {'error':str(e),'hint':'Run: python -m playwright install chromium'}
