# scraper/trending.py
import json

async def scrape_trending(page):
    url = "https://www.tiktok.com/foryou"
    await page.goto(url, timeout=60000)

    await page.wait_for_selector("script[id='SIGI_STATE']")
    data = await page.evaluate("document.querySelector('#SIGI_STATE').textContent")

    return json.loads(data)
