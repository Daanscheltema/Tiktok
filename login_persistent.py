import asyncio
from playwright.async_api import async_playwright

async def login_persistent():
    async with async_playwright() as p:
        # Persistent context = TikTok ziet dit als een echt apparaat
        context = await p.chromium.launch_persistent_context(
            user_data_dir="tiktok_session",
            headless=False,
            viewport={"width": 1400, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        page = await context.new_page()
        await page.goto("https://www.tiktok.com/login", timeout=60000)

        print("\n👉 Log handmatig in.")
        print("👉 Als je de TikTok feed ziet, sluit dan de browser.\n")

        # Browser blijft open tot jij hem sluit
        await page.wait_for_timeout(999999999)

asyncio.run(login_persistent())
