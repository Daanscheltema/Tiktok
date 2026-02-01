# scraper/hashtag.py
import json
import asyncio

async def scrape_hashtag(page, tag: str):
    url = f"https://www.tiktok.com/tag/{tag}"

    try:
        await page.goto(url, timeout=60000)
    except Exception:
        return {}

    try:
        await page.wait_for_selector("script[id='SIGI_STATE']", timeout=8000)
    except Exception:
        return {}

    try:
        data = await page.evaluate("document.querySelector('#SIGI_STATE').textContent")
        state = json.loads(data)
        return state
    except Exception:
        return {}
