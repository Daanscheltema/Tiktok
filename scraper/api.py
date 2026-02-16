import json


# ============================================================
#  EXTRACT UNIVERSAL DATA
# ============================================================

async def extract_universal_data(page):
    raw_json = await page.evaluate("""
    () => {
        const el = document.querySelector('#__UNIVERSAL_DATA_FOR_REHYDRATION__');
        return el ? el.textContent : null;
    }
    """)

    if not raw_json:
        print("[HTML] No UNIVERSAL_DATA found")
        return None

    try:
        return json.loads(raw_json)
    except Exception as e:
        print("[HTML] Failed to parse UNIVERSAL JSON:", e)
        return None


# ============================================================
#  FIND FULL ITEM STRUCT (NOT JUST STATS)
# ============================================================

def _find_item_struct(obj):
    """
    Recursively search for an object that looks like TikTok's itemStruct.
    """
    if isinstance(obj, dict):
        # itemStruct always contains id + desc + video + stats
        if {"id", "desc", "video", "stats"} <= set(obj.keys()):
            return obj

        for v in obj.values():
            found = _find_item_struct(v)
            if found:
                return found

    elif isinstance(obj, list):
        for item in obj:
            found = _find_item_struct(item)
            if found:
                return found

    return None


# ============================================================
#  PARSE UNIVERSAL DATA → VIDEO STATS
# ============================================================

def parse_video_stats_from_universal(data):
    default_scope = data.get("__DEFAULT_SCOPE__", {})

    # Try typical video-detail paths
    item = None
    for key, value in default_scope.items():
        if "video" in key or "detail" in key:
            item = _find_item_struct(value)
            if item:
                break

    # Fallback: brute-force search
    if item is None:
        item = _find_item_struct(data)

    if item is None:
        print("[HTML] No itemStruct found")
        return {
            "video_id": None,
            "description": "",
            "hashtags": [],
            "create_time": None,
            "duration": None,
            "stats": {},
        }

    stats = item.get("stats", {})

    return {
        "video_id": item.get("id"),
        "description": item.get("desc") or "",
        "hashtags": [h.get("hashtagName") for h in item.get("textExtra", []) if h.get("hashtagName")],
        "create_time": item.get("createTime"),
        "duration": item.get("video", {}).get("duration"),
        "stats": {
            "views": stats.get("playCount"),
            "likes": stats.get("diggCount"),
            "comments": stats.get("commentCount"),
            "shares": stats.get("shareCount"),
            "saves": stats.get("collectCount"),
            "downloads": stats.get("downloadCount"),
            "forwards": stats.get("forwardCount"),
        },
    }


# ============================================================
#  MAIN FUNCTION: FETCH VIDEO STATS VIA HTML
# ============================================================

async def fetch_video_stats_html(page, video_url: str):
    print(f"[HTML] Fetching stats via HTML for: {video_url}")

    await page.goto(video_url, wait_until="networkidle")

    universal = await extract_universal_data(page)
    if not universal:
        return {
            "video_id": None,
            "description": "",
            "hashtags": [],
            "create_time": None,
            "duration": None,
            "stats": {},
        }

    parsed = parse_video_stats_from_universal(universal)
    print("[HTML] FINAL PARSED RESULT:", parsed)
    return parsed


# ============================================================
#  COMPATIBILITY WRAPPER (USED BY search.py)
# ============================================================

async def fetch_video_stats_api(context, video_url):
    page = await context.new_page()
    try:
        return await fetch_video_stats_html(page, video_url)
    finally:
        await page.close()

