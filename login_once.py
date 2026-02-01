import asyncio
from playwright.async_api import async_playwright
from scraper.browser import DESKTOP  # same config you already use

async def login_once():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # IMPORTANT: must be visible
            slow_mo=50
        )

        context = await browser.new_context(**DESKTOP)
        page = await context.new_page()

        # Open TikTok login page
        await page.goto("https://www.tiktok.com/login")

        print("\n👉 Log in manually in the browser window.")
        print("👉 When you're fully logged in and see your feed, press ENTER here.\n")
        input()

        # Save cookies / session
        await context.storage_state(path="tiktok.json")
        print("✅ Login session saved to tiktok.json")

        await browser.close()

asyncio.run(login_once())
