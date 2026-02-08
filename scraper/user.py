# scraper/user.py
import re
import urllib.parse

# Regex for URLs inside bio text
BIO_LINK_REGEX = (
    r"(https?://[^\s]+|"          # full URLs
    r"www\.[^\s]+|"               # www. links
    r"(?:t\.me|discord\.gg|discord\.com|"
    r"snapchat\.com|linktr\.ee|beacons\.ai|"
    r"onlyfans\.com|patreon\.com|"
    r"instagram\.com|youtube\.com|twitch\.tv)"
    r"/[^\s]+)"
)


async def scrape_user_single_tab(page):
    """
    Scrapes a TikTok profile using the SAME tab (no new pages).
    Returns only extracted links, because SIGI_STATE is not reliable on profiles.
    """

    # -----------------------------
    # Extract bio text
    # -----------------------------
    bio_text = ""
    bio_selectors = [
        "h2[data-e2e='user-bio']",
        "span[data-e2e='user-bio']",
        "p[data-e2e='user-bio']",
        "div[data-e2e='user-bio']"
    ]

    for sel in bio_selectors:
        try:
            text = await page.inner_text(sel)
            if text.strip():
                bio_text = text.strip()
                break
        except:
            continue

    extracted_links = []

    # -----------------------------
    # Extract URLs from bio text
    # -----------------------------
    if bio_text:
        found_links = re.findall(BIO_LINK_REGEX, bio_text)
        for link in found_links:
            if isinstance(link, tuple):
                link = link[0]
            if link not in extracted_links:
                extracted_links.append(link)

    # -----------------------------
    # Extract TikTok "official" bio links (wrapped links)
    # -----------------------------
    try:
        link_elements = await page.query_selector_all("a[data-e2e='user-link']")
        for el in link_elements:
            href = await el.get_attribute("href")
            text = await el.inner_text()

            real_url = None

            # TikTok wraps links like:
            # https://www.tiktok.com/link/v2?...&target=https%3A%2F%2Ft.me%2Frebounder77b
            if href and "target=" in href:
                parsed = urllib.parse.urlparse(href)
                qs = urllib.parse.parse_qs(parsed.query)
                real_url = qs.get("target", [None])[0]
            else:
                real_url = href

            if real_url and real_url not in extracted_links:
                extracted_links.append(real_url)

            if text and text not in extracted_links:
                extracted_links.append(text)

    except Exception:
        pass

    # -----------------------------
    # Extract any visible <a> links in profile
    # -----------------------------
    try:
        anchors = await page.query_selector_all("a")
        for a in anchors:
            href = await a.get_attribute("href")
            if href and (
                "http" in href
                or "t.me" in href
                or "linktr.ee" in href
                or "discord" in href
            ):
                if href not in extracted_links:
                    extracted_links.append(href)
    except:
        pass

    return list(set(extracted_links))
