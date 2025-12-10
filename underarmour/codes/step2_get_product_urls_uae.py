import logging
import json
import asyncio
from datetime import date
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
countries = {"UAE": "UAE"}
Browser_Limit = 4

async def get_product_links(url, save_path, gender, category, temp_urls):
    links = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=False)
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1329, "height": 654})
        await page.goto(url, timeout=60000)
        await page.wait_for_load_state("domcontentloaded")
        async def close_popup_if_present(page, context=""):
            popup_close_selector = ".brz-popup2__close"
            try:
                popup = await page.query_selector(popup_close_selector)
                if popup:
                    await popup.click()
                    logging.info(f"[{gender}-{category}] Popup closed ({context}).")
                else:
                    logging.info(f"[{gender}-{category}] No popup detected ({context}).")
            except Exception as e:
                logging.warning(f"[{gender}-{category}] Error closing popup ({context}): {e}")
        await close_popup_if_present(page, context="initial")
        async def auto_scroll_inner(page):
            logging.info(f"[{gender}-{category}] Starting slow scroll...")
            await page.evaluate(
                """
                async () => {
                    const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
                    let lastHeight = document.body.scrollHeight;
                    let noChangeCount = 0;
                    const maxAttempts = 10;
                    while (noChangeCount < maxAttempts) {
                        window.scrollBy(0, 100);
                        await delay(100);
                        let newHeight = document.body.scrollHeight;
                        if (newHeight === lastHeight) {
                            noChangeCount++;
                        } else {
                            noChangeCount = 0;
                            lastHeight = newHeight;
                        }
                    }
                }
                """
            )
            logging.info(f"[{gender}-{category}] Finished scrolling.")
        while True:
            await close_popup_if_present(page, context="loop-top")
            await auto_scroll_inner(page)
            await close_popup_if_present(page, context="after-scroll")
            html_content = await page.content()
            soup = BeautifulSoup(html_content, "html.parser")
            script_tag = soup.find("script", {"type": "application/ld+json"})
            if script_tag:
                try:
                    data = json.loads(script_tag.string.strip())
                    if "itemListElement" in data:
                        for item in data["itemListElement"]:
                            if "url" in item:
                                links.append(item["url"])
                except Exception as e:
                    logging.error(f"Error parsing JSON: {e}")
            temp_urls[gender][category] = list(links)
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(temp_urls, f, indent=2)
            load_more = await page.query_selector("button.js-show-more-btn")
            if load_more:
                logging.info(f"[{gender}-{category}] Clicking Load More...")
                await load_more.click()
                await close_popup_if_present(page, context="after-load-more")
                await asyncio.sleep(5)
                continue
            else:
                break
        await browser.close()
    return list(links)

async def main():
    today = date.today().strftime("%Y-%m-%d")
    # today = '2025-11-19'
    for country, _ in countries.items():
        input_file = Path(country).joinpath("Data", today, "Item_urls", f"Category_urls.json")
        if not input_file.is_file():
            logging.error(f"Input file not found: {input_file}")
            continue
        with open(input_file, "r", encoding="utf-8") as f:
            url_dict = json.load(f)
        logging.info(f"Fetching {country} product URLs...")
        temp_urls = {}
        output_dir = Path(country).joinpath("Data", today, "Item_urls")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"product_urls.json"
        queue = asyncio.Queue()
        for gender, categories in url_dict.items():
            temp_urls.setdefault(gender, {})
            logging.info(f"Gender: {gender}")
            for category, url in categories.items():
                logging.info(f"Queueing {gender}-{category}")
                await queue.put((url, output_path, gender, category, temp_urls))
        async def worker(worker_id: int):
            while not queue.empty():
                url, save_path, gender, category, temp_urls = await queue.get()
                logging.info(f"[Worker {worker_id}] Starting {gender}-{category}")
                try:
                    await get_product_links(url, save_path, gender, category, temp_urls)
                except Exception as e:
                    logging.error(f"[Worker {worker_id}] Error while scraping {gender}-{category}: {e}")
                finally:
                    queue.task_done()
                    logging.info(f"[Worker {worker_id}] Finished {gender}-{category}")
        workers = [asyncio.create_task(worker(i)) for i in range(Browser_Limit)]
        await queue.join()
        for w in workers:
            w.cancel()
        logging.info(f"All done! {country} product URLs saved to {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
