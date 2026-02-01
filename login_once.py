import asyncio
from playwright.async_api import async_playwright

async def login_once():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir="tiktok_session",
            headless=False,
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        )

        page = await context.new_page()
        await page.goto("https://www.tiktok.com", timeout=60000)

        print("Log handmatig in. Sluit de browser als je klaar bent.")
        await page.wait_for_timeout(999999999)

asyncio.run(login_once())
