import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from datetime import date

today = date.today().strftime("%Y-%m-%d")
API_URL = "https://api.tenxyou.com/saleor/navbar-data"
OUT_FILE = f"India/Data/{today}/Item_urls/Category_urls.json"
BASE_PRODUCT_LISTING = "https://tenxyou.com/product-listing/{}"


async def build_urls_from_json(raw):
    out = {}
    data = raw.get("data", []) if isinstance(raw, dict) else []
    skipped = 0

    for main in data:
        main_name = (main.get("name") or "").strip()
        if not main_name:
            continue
        out.setdefault(main_name, {})

        children_level2 = main.get("children", [])
        # If there are no second-level children, fall back to using main's collection id
        if not children_level2:
            coll_id = (main.get("collection") or {}).get("id") or None
            if coll_id:
                key = f"{main_name}_{main_name}"
                out[main_name][key] = BASE_PRODUCT_LISTING.format(coll_id)
            else:
                skipped += 1
            continue

        for lvl2 in children_level2:
            lvl2_name = (lvl2.get("name") or "").strip()
            lvl2_children = lvl2.get("children", [])

            # If there are third-level children, use them
            if lvl2_children:
                for lvl3 in lvl2_children:
                    lvl3_name = (lvl3.get("name") or "").strip()
                    # ID should be taken from the collection object inside the third-level item
                    coll_id = (lvl3.get("collection") or {}).get("id") or None

                    # Fallbacks: lvl2.collection then main.collection
                    if not coll_id:
                        coll_id = (lvl2.get("collection") or {}).get("id") or None
                    if not coll_id:
                        coll_id = (main.get("collection") or {}).get("id") or None

                    if not coll_id:
                        skipped += 1
                        continue

                    # Build key and URL
                    key = f"{lvl2_name}_{lvl3_name}" if lvl2_name and lvl3_name else f"{(lvl2_name or lvl3_name)}_{(lvl2_name or lvl3_name)}"
                    out[main_name][key] = BASE_PRODUCT_LISTING.format(coll_id)

            else:
                # No third-level children: use lvl2.collection id
                coll_id = (lvl2.get("collection") or {}).get("id") or None
                if not coll_id:
                    # fallback to main.collection
                    coll_id = (main.get("collection") or {}).get("id") or None
                if not coll_id:
                    skipped += 1
                    continue
                key = f"{lvl2_name}_{lvl2_name}" if lvl2_name else f"{main_name}_{main_name}"
                out[main_name][key] = BASE_PRODUCT_LISTING.format(coll_id)

    return out, skipped


async def main():
    # ensure output directory exists
    out_path = Path(OUT_FILE)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        # Launch a visible browser (headless=False) as requested
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Open blank so the window appears
        await page.goto("about:blank")

        # Use a request context to fetch the API JSON
        req_ctx = await p.request.new_context()
        try:
            response = await req_ctx.get(API_URL, timeout=30000)  # 30s timeout
        except Exception as e:
            print(f"Request to API failed: {e}")
            await req_ctx.dispose()
            await browser.close()
            return

        if response.status != 200:
            text = await response.text()
            print(f"Failed to fetch API (status={response.status})\nResponse body: {text[:1000]}")
            await req_ctx.dispose()
            await browser.close()
            return

        raw_json = await response.json()

        # Build urls
        result, skipped = await build_urls_from_json(raw_json)

        # Save to file
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"Wrote {len(result)} main categories to {out_path}")
            if skipped:
                print(f"Note: skipped {skipped} items because no valid collection id was found.")
        except Exception as e:
            print(f"Error writing output file: {e}")

        await req_ctx.dispose()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
