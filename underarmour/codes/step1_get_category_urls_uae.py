import logging
import os
import json
import asyncio
from datetime import date
from urllib.parse import urljoin
from playwright.async_api import async_playwright

countries = {
    'UAE': 'https://www.underarmour.ae/en/home'
}
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

async def main():
    today_str = date.today().strftime('%Y-%m-%d')
    country = 'UAE'
    base_dir = f'{country}/Data/{today_str}/Item_urls'
    os.makedirs(base_dir, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=False)  
        context = await browser.new_context()
        page = await context.new_page()
        logging.info(f"Opening {countries[country]} ...")
        await page.goto(countries[country], wait_until="domcontentloaded", timeout=60000)
        popup_close_selector = ".brz-popup2__close"
        try:
            popup = await page.query_selector(popup_close_selector)
            if popup:
                await popup.click()
                logging.info("Popup closed successfully.")
            else:
                logging.info("No popup detected.")
        except Exception as e:
            logging.warning(f"Could not close popup: {e}")
        category_links = {}
        spans = await page.query_selector_all("span.megamenu__link-text")
        logging.info(f"Found {len(spans)} menu items.")
        for span in spans:
            text = (await span.inner_text()).strip()
            if not text:
                continue
            await span.hover()
            await page.wait_for_timeout(800)
            parent = await span.evaluate_handle("el => el.closest('li')")
            if parent:
                links = await parent.query_selector_all("a[href]")
                hrefs = {}
                seen_urls = set()  
                for link in links:
                    href = await link.get_attribute("href")
                    link_text = (await link.inner_text() or "").strip()
                    if link_text:
                        link_text = link_text.strip()
                        link_text = link_text.replace("®", "").replace("™", "").replace(":", "").strip()
                    if href and link_text:
                        full_url = urljoin(countries[country], href)
                        if full_url not in seen_urls: 
                            hrefs[link_text.upper()] = full_url
                            seen_urls.add(full_url)
                if hrefs:
                    category_links[text.upper()] = hrefs
        global_seen = {}
        for cat, hrefs in category_links.items():
            unique_hrefs = {}
            for name, url in hrefs.items():
                if url not in global_seen:  
                    unique_hrefs[name] = url
                    global_seen[url] = (cat, name)
            category_links[cat] = unique_hrefs
        exclude_keys = {"NEW", "SPORTS", "SALE"}
        category_links = {k: v for k, v in category_links.items() if k not in exclude_keys}
        for cat in list(category_links.keys()):
            if cat in category_links[cat]:
                category_links[cat].pop(cat, None)
        pop_keys = {
            "ACCESSORIES",
            "BACKPACKS & BAGS",
            "HEAD GEAR",
            "SOCKS",
            "SPORTS GLOVES",
            "GLOVES",
            "BELTS"
        }
        for cat, hrefs in category_links.items():
            for key in list(hrefs.keys()):
                if key in pop_keys:
                    hrefs.pop(key, None)
        men_keys = set(category_links.get("MEN", {}).keys())
        women_keys = set(category_links.get("WOMEN", {}).keys())
        kids_keys = set(category_links.get("KIDS", {}).keys())
        shoes_dict = category_links.get("SHOES", {})
        shoes_to_remove = {"INFINITE", "UA HOVR PHANTOM", "UA SLIPSPEED"}
        unique_shoes = {
            k: v
            for k, v in shoes_dict.items()
            if k not in men_keys and k not in women_keys and k not in kids_keys and k not in shoes_to_remove
        }
        category_links["SHOES"] = unique_shoes
        json_path = os.path.join(base_dir, f'Category_urls.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(category_links, f, indent=4, ensure_ascii=False)
        logging.info(f"Saved updated category links to {json_path}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
