# scraper/browser.py
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
    )
}

async def get_browser(proxy: str | None = None, browser_type: str = "chromium"):
    playwright = await async_playwright().start()

    # --- Browser Launch (stealth-friendly) ---
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

    if browser_type == "chromium":
        browser = await playwright.chromium.launch(
            headless=False,
            args=launch_args,
            proxy={"server": proxy} if proxy else None
        )
    elif browser_type == "firefox":
        browser = await playwright.firefox.launch(
            headless=False,
            args=launch_args,
            proxy={"server": proxy} if proxy else None
        )
    else:
        browser = await playwright.webkit.launch(
            headless=False,
            args=launch_args,
            proxy={"server": proxy} if proxy else None
        )

    # --- Context (human-like environment) ---
    context = await browser.new_context(
        **DESKTOP,
        locale="en-US",
        timezone_id="Europe/Amsterdam",
        geolocation={"longitude": 4.899, "latitude": 52.372},
        permissions=["geolocation"],
    )

    # --- Stealth patches ---
    await context.add_init_script("""
        // Remove webdriver flag
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

        // Fake plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });

        // Fake languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });

        // Fake platform
        Object.defineProperty(navigator, 'platform', {
            get: () => 'Win32'
        });

        // Fix permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters)
        );

        // WebGL fingerprint patch
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Intel Inc.';
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return getParameter(parameter);
        };
    """)

    page = await context.new_page()
    return playwright, browser, context, page
