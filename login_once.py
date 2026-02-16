import asyncio
from scraper.browser import get_browser


async def main():
    playwright, browser, context, page = await get_browser()

    print("Go to TikTok and log in manually...")
    await page.goto("https://www.tiktok.com/login")

    # Wait until you confirm login
    input("Press ENTER after you are fully logged in...")

    # Save session
    await context.storage_state(path="tiktok_session.json")
    print("✔ Session saved to tiktok_session.json")

    await browser.close()
    await playwright.stop()


asyncio.run(main())