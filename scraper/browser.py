from playwright.async_api import async_playwright

DESKTOP = {
    "viewport": {"width": 1280, "height": 800},
    "device_scale_factor": 1,
    "is_mobile": False,
    "has_touch": False,
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

CHROME_CDP_URL = "http://localhost:9222"


async def get_browser(proxy: str | None = None, browser_type: str = "chromium"):
    playwright = await async_playwright().start()

    # --- Attach to real Chrome via CDP ---
    if browser_type == "cdp-chrome":
        print("Connecting to existing Chrome via CDP...")
        browser = await playwright.chromium.connect_over_cdp(CHROME_CDP_URL)

        print(f"Contexts found: {len(browser.contexts)}")
        if not browser.contexts:
            raise Exception(
                "❌ No Chrome contexts found.\n"
                "Start Chrome with:\n"
                '  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" '
                '--remote-debugging-port=9222 '
                '--user-data-dir="C:\\tiktok_chrome_profile"\n'
                "and open TikTok before running the scraper."
            )

        context = browser.contexts[0]
        print(f"Using context: {context}")

        print(f"Pages in context: {len(context.pages)}")
        for i, p in enumerate(context.pages):
            try:
                title = await p.title()
            except Exception:
                title = "<no title>"
            print(f" - Page {i}: {title} | URL: {p.url}")

        # Prefer a TikTok tab if present, else new tab
        tiktok_pages = [p for p in context.pages if "tiktok.com" in p.url.lower()]
        if tiktok_pages:
            page = tiktok_pages[-1]
            print(f"✔ Using TikTok tab: {page.url}")
        else:
            page = await context.new_page()
            print("⚠ No TikTok tab found, opened a new one.")

        cookies = await context.cookies()
        cookie_names = [c["name"] for c in cookies]
        print("Cookies in context:", cookie_names)

        if any(name in cookie_names for name in ["sessionid", "sid_tt", "ttwid"]):
            print("✔ TikTok login cookies detected — you ARE logged in.")
        else:
            print("⚠ No TikTok login cookies detected — TikTok may treat this as logged out.")

        return playwright, browser, context, page

    # --- Normal Playwright launch path ---
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-web-security",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-infobars",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
    ]

    browser = await playwright.chromium.launch(
        headless=False,  # visible
        args=launch_args,
        proxy={"server": proxy} if proxy else None,
    )

    context = await browser.new_context(
        **DESKTOP,
        locale="en-US",
        timezone_id="Europe/Amsterdam",
        geolocation={"longitude": 4.899, "latitude": 52.372},
        permissions=["geolocation"],
    )

    await context.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters)
        );
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Intel Inc.';
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return getParameter(parameter);
        };
        """
    )

    page = await context.new_page()
    return playwright, browser, context, page