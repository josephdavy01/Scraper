import asyncio
import json
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from tqdm import tqdm

# Optional ZoneInfo for timezone-aware scheduling
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

# ---------------- CONFIG ----------------
Browser_Limit = 3
ITEMS_PER_PAGE = 7
PAGE_TIMEOUT = 10000
GOTO_TIMEOUT = 10000
COUNT_ATTEMPTS = 1
STOP_AFTER_CONSECUTIVE_FAILS = 3

# COUNTRY CONFIGS (unchanged)
COUNTRY_CONFIGS: Dict[str, Dict[str, str]] = {
    "India": {
        "Newborn Unisex": "https://www.nextdirect.com/in/en/shop/f/brand-next-gender-newbornunisex",
        "Older Boys": "https://www.nextdirect.com/in/en/shop/f/brand-next-gender-olderboys",
        "Younger Boys": "https://www.nextdirect.com/in/en/shop/f/brand-next-gender-youngerboys",
        "Newborn Boys": "https://www.nextdirect.com/in/en/shop/f/brand-next-gender-newbornboys",
        "Older Girls": "https://www.nextdirect.com/in/en/shop/f/brand-next-gender-oldergirls",
        "Younger Girls": "https://www.nextdirect.com/in/en/shop/f/brand-next-gender-youngergirls",
        "Newborn Girls": "https://www.nextdirect.com/in/en/shop/f/brand-next-gender-newborngirls",
        "Girls Nightwear": "https://www.nextdirect.com/in/en/shop/girls/nightwear/sleepwear/f/brand-next-gender-oldergirls~youngergirls",
        "Girls Underwear": "https://www.nextdirect.com/in/en/shop/girls/underwear/f/brand-next-gender-oldergirls~youngergirls",
        "Boys Nightwear": "https://www.nextdirect.com/in/en/shop/boys/nightwear/sleepwear/f/brand-next-gender-olderboys~youngerboys",
        "Boys Underwear": "https://www.nextdirect.com/in/en/shop/boys/underwear/f/brand-next-gender-olderboys~youngerboys",
        "Character Shop": "https://www.nextdirect.com/in/en/promotions/character-shop/girls/f/brand-next-department-boys~girls",
        "Women": "https://www.nextdirect.com/in/en/shop/womens/clothing/f/brand-next",
        "Women Dresses": "https://www.nextdirect.com/in/en/shop/womens/clothing/dresses/f/brand-next",
        "Women Lingerie": "https://www.nextdirect.com/in/en/shop/womens/lingerie/f/brand-next",
        "Men": "https://www.nextdirect.com/in/en/shop/mens/clothing/f/brand-next",
        "Men Suits": "https://www.nextdirect.com/in/en/shop/mens/clothing/suits/f/brand-next",
        "Men Nightwear": "https://www.nextdirect.com/in/en/shop/mens/nightwear/sleepwear/f/brand-next",
        "Men Underwear": "https://www.nextdirect.com/in/en/shop/mens/underwear/f/brand-next",
    },
    "UK": {
        "Newborn Unisex": "https://www.next.co.uk/shop/brand-next/gender-newbornunisex",
        "Older Boys": "https://www.next.co.uk/shop/brand-next/gender-olderboys",
        "Younger Boys": "https://www.next.co.uk/shop/brand-next/gender-youngerboys",
        "Newborn Boys": "https://www.next.co.uk/shop/brand-next/gender-newbornboys",
        "Older Girls": "https://www.next.co.uk/shop/brand-next/gender-oldergirls",
        "Younger Girls": "https://www.next.co.uk/shop/brand-next/gender-youngergirls",
        "Newborn Girls": "https://www.next.co.uk/shop/brand-next/gender-newborngirls",
        "Girls Nightwear": "https://www.next.co.uk/shop/gender-oldergirls-gender-youngergirls-productaffiliation-nightwear/brand-next",
        "Girls Schoolwear": "https://www.next.co.uk/shop/gender-oldergirls-gender-youngergirls-productaffiliation-schoolwear/brand-next",
        "Girls Underwear": "https://www.next.co.uk/shop/gender-oldergirls-gender-youngergirls-productaffiliation-underwear/brand-next",
        "Boys Nightwear": "https://www.next.co.uk/shop/gender-olderboys-gender-youngerboys-productaffiliation-nightwear/brand-next",
        "Boys Schoolwear": "https://www.next.co.uk/shop/gender-olderboys-gender-youngerboys-productaffiliation-schoolwear/brand-next",
        "Boys Underwear": "https://www.next.co.uk/shop/gender-olderboys-gender-youngerboys-productaffiliation-underwear/brand-next",
        "Character Shop Girl": "https://www.nextdirect.com/in/en/promotions/character-shop/girls/f/brand-next",
        "Character Shop Boy": "https://www.nextdirect.com/in/en/promotions/character-shop/boys/f/brand-next",
        "Women": "https://www.next.co.uk/shop/gender-women-productaffiliation-clothing/brand-next",
        "Women Dresses": "https://www.next.co.uk/shop/gender-women-category-dresses/brand-next",
        "Women Nightwear": "https://www.next.co.uk/shop/gender-women-productaffiliation-nightwear/brand-next",
        "Women Lingerie": "https://www.next.co.uk/shop/gender-women-productaffiliation-lingerie/brand-next",
        "Women Workwear": "https://www.next.co.uk/shop/gender-women/use-workwear/brand-next",
        "Men": "https://www.next.co.uk/shop/gender-men-productaffiliation-clothing/brand-next",
        "Men Suits": "https://www.next.co.uk/shop/gender-men-productaffiliation-suits/brand-next",
        "Men Nightwear": "https://www.next.co.uk/shop/gender-men-productaffiliation-nightwear/brand-next",
        "Men Underwear": "https://www.next.co.uk/shop/gender-men-productaffiliation-underwear/brand-next",
    },
    "UAE": {
        "Newborn Unisex": "https://www.next.ae/en/shop/brand-next/gender-newbornunisex",
        "Older Boys": "https://www.next.ae/en/shop/brand-next/gender-olderboys",
        "Younger Boys": "https://www.next.ae/en/shop/brand-next/gender-youngerboys",
        "Newborn Boys": "https://www.next.ae/en/shop/brand-next/gender-newbornboys",
        "Older Girls": "https://www.next.ae/en/shop/brand-next/gender-oldergirls",
        "Younger Girls": "https://www.next.ae/en/shop/brand-next/gender-youngergirls",
        "Newborn Girls": "https://www.next.ae/en/shop/brand-next/gender-newborngirls",
        "Girls Nightwear": "https://www.next.ae/en/shop/gender-oldergirls-gender-youngergirls-productaffiliation-nightwear/brand-next",
        "Girls Underwear": "https://www.next.ae/en/shop/gender-oldergirls-gender-youngergirls-productaffiliation-underwear/brand-next",
        "Boys Nightwear": "https://www.next.ae/en/shop/gender-olderboys-gender-youngerboys-productaffiliation-nightwear/brand-next",
        "Boys Underwear": "https://www.next.ae/en/shop/gender-olderboys-gender-youngerboys-productaffiliation-underwear/brand-next",
        "Character Shop": "https://www.next.ae/en/shop/promotion-charactershop/brand-next",
        "Women": "https://www.next.ae/en/shop/gender-women-productaffiliation-clothing/brand-next",
        "Women Dresses": "https://www.next.ae/en/shop/gender-women-category-dresses/brand-next",
        "Women Swimwear": "https://www.next.ae/en/shop/gender-women-productaffiliation-swimwear/brand-next-category-swimsuits",
        "Women Lingerie": "https://www.next.ae/en/shop/gender-women-productaffiliation-lingerie/brand-next",
        "Men": "https://www.next.ae/en/shop/gender-men-productaffiliation-clothing/brand-next",
        "Men Suits": "https://www.next.ae/en/shop/gender-men-productaffiliation-suits/brand-next",
        "Men Nightwear": "https://www.next.ae/en/shop/gender-men-productaffiliation-nightwear/brand-next",
        "Men Underwear": "https://www.next.ae/en/shop/gender-men-productaffiliation-underwear/brand-next",
    },
    "Saudi": {
        "Newborn Unisex": "https://www.next.sa/en/shop/brand-next/gender-newbornunisex",
        "Older Boys": "https://www.next.sa/en/shop/brand-next/gender-olderboys",
        "Younger Boys": "https://www.next.sa/en/shop/brand-next/gender-youngerboys",
        "Newborn Boys": "https://www.next.sa/en/shop/brand-next/gender-newbornboys",
        "Older Girls": "https://www.next.sa/en/shop/brand-next/gender-oldergirls",
        "Younger Girls": "https://www.next.sa/en/shop/brand-next/gender-youngergirls",
        "Newborn Girls": "https://www.next.sa/en/shop/brand-next/gender-newborngirls",
        "Girls Nightwear": "https://www.next.sa/en/shop/gender-oldergirls-gender-youngergirls-productaffiliation-nightwear/brand-next",
        "Girls Underwear": "https://www.next.sa/en/shop/gender-oldergirls-gender-youngergirls-productaffiliation-underwear/brand-next",
        "Boys Nightwear": "https://www.next.sa/en/shop/gender-olderboys-gender-youngerboys-productaffiliation-nightwear/brand-next",
        "Boys Underwear": "https://www.next.sa/en/shop/gender-olderboys-gender-youngerboys-productaffiliation-underwear/brand-next",
        "Character Shop": "https://www.next.sa/en/shop/promotion-charactershop/brand-next",
        "Women": "https://www.next.sa/en/shop/gender-women-productaffiliation-clothing/brand-next",
        "Women Dresses": "https://www.next.sa/en/shop/gender-women-category-dresses/brand-next",
        "Women Swimwear": "https://www.next.sa/en/shop/gender-women-productaffiliation-swimwear/brand-next-category-swimsuits",
        "Women Lingerie": "https://www.next.sa/en/shop/gender-women-productaffiliation-lingerie/brand-next",
        "Men": "https://www.next.sa/en/shop/gender-men-productaffiliation-clothing/brand-next",
        "Men Suits": "https://www.next.sa/en/shop/gender-men-productaffiliation-suits/brand-next",
        "Men Nightwear": "https://www.next.sa/en/shop/gender-men-productaffiliation-nightwear/brand-next",
        "Men Underwear": "https://www.next.sa/en/shop/gender-men-productaffiliation-underwear/brand-next",
    },
}

# --------------- HELPERS ---------------
def get_countries_to_run() -> List[str]:
    try:
        if ZoneInfo is not None:
            now_kolkata = datetime.now(tz=ZoneInfo("Asia/Kolkata"))
        else:
            now_kolkata = datetime.now()
    except Exception:
        now_kolkata = datetime.now()

    weekday = now_kolkata.strftime("%A").lower()
    day_map = {
        "monday": ["India", "UK"],
        "wednesday": ["India", "UK"],
        "friday": ["India", "UK"],
        "tuesday": ["UAE", "Saudi"],
        "thursday": ["UAE", "Saudi"],
        "saturday": ["UAE", "Saudi"],
        "sunday": [],
    }
    countries = day_map.get(weekday, [])
    print(f"[Scheduler] Today is {now_kolkata.strftime('%A, %Y-%m-%d %H:%M:%S %Z')}. Scheduled countries: {countries}")
    return countries


def setup_logger(country: str, log_dir: Path) -> logging.Logger:
    logger = logging.getLogger(f"scraper.{country}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{country.lower()}_log.txt"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    ch = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s - %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# ------------------- NEW FIXES -------------------
async def safe_goto(page, url):
    try:
        await page.goto(url, timeout=20000, wait_until="domcontentloaded")
    except:
        try:
            await page.goto(url, timeout=30000, wait_until="networkidle")
        except Exception as e:
            print(f"[safe_goto ERROR] {e}")


async def dismiss_popups(page):
    selectors = [
        "button:has-text('Accept All')",
        "button:has-text('I Accept')",
        "button:has-text('Continue Shopping')",
        "button:has-text('Allow all')",
    ]
    for sel in selectors:
        try:
            await page.locator(sel).click(timeout=2000)
        except:
            pass


# ---------------- PAGE SCRAPING LOGIC ----------------
async def extract_total_pages_from_soup(soup: BeautifulSoup) -> int:
    count_text = ""
    count_element = soup.find("div", {"class": "plp-1fp4ipz"}) or soup.find("div", {"class": "plp-mayzfo"})
    if count_element:
        spans = count_element.find_all("span")
        if spans:
            count_text = spans[-1].get_text(strip=True)

    if not count_text:
        esi_span = soup.find("span", {"class": "esi-count"})
        if esi_span:
            count_text = esi_span.get_text(strip=True)

    if not count_text:
        seo_div = soup.find("div", {"id": "plp-seo-heading"})
        if seo_div:
            seo_span = seo_div.find("span")
            if seo_span:
                count_text = seo_span.get_text(strip=True)

    if not count_text:
        all_text = soup.get_text(" ", strip=True)
        m_all = list(re.finditer(r"\((\d{1,7})\)", all_text))
        if m_all:
            count_text = m_all[-1].group(0)

    if count_text:
        nums = re.findall(r"\d+", count_text)
        if nums:
            count = int(nums[-1])
            pages = (count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
            return pages

    return 0


async def get_product_urls(
    page,
    base_url: str,
    country: str,
    gender: str,
    log_dir: Path,
    resume_file: Path,
    pbar: tqdm,
    lock: asyncio.Lock,
) -> List[str]:

    scraped_urls: Set[str] = set()
    last_scraped_page = 0
    failed_pages: List[int] = []

    # Load resume if exists
    if resume_file.exists():
        try:
            async with lock:
                with open(resume_file, "r", encoding="utf-8") as f:
                    resume = json.load(f)
                scraped_urls = set(resume.get("urls", []))
                last_scraped_page = resume.get("last_page", 0)
                failed_pages = resume.get("failed_pages", [])
        except:
            pass

    # ---- FIRST PAGE LOAD ----
    for attempt in range(COUNT_ATTEMPTS):
        try:
            await safe_goto(page, base_url)
            await dismiss_popups(page)
            await page.wait_for_selector('div[data-testid="plp-product-grid"]', timeout=PAGE_TIMEOUT)

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            total_pages = await extract_total_pages_from_soup(soup)

            if total_pages > 0:
                break
        except Exception as e:
            print(f"[{country}] Product count error for {gender}: {e}")
            await page.wait_for_timeout(2000)

    if total_pages == 0:
        total_pages = 1

    pbar.total = total_pages
    consecutive_failures = 0

    # -------- Pagination --------
    for page_num in range(last_scraped_page + 1, total_pages + 1):
        turl = f"{base_url}?p={page_num}"
        success = False

        try:
            await safe_goto(page, turl)
            await dismiss_popups(page)
            await page.wait_for_selector('div[data-testid="plp-product-grid"]', timeout=PAGE_TIMEOUT)

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            grid = soup.find("div", {"data-testid": "plp-product-grid"})
            items = grid.find_all("div", {"data-testid": "plp-product-grid-item"}) if grid else []

            for item in items:
                div_tag = item.find("a")
                link = div_tag.get("href") if div_tag else None
                if link:
                    scraped_urls.add(link)

            success = True

        except Exception as e:
            print(f"[{country}] Error page {page_num}: {e}")
            consecutive_failures += 1
            if consecutive_failures >= STOP_AFTER_CONSECUTIVE_FAILS:
                break

        # Write resume
        async with lock:
            with open(resume_file, "w", encoding="utf-8") as f:
                json.dump({
                    "urls": list(scraped_urls),
                    "last_page": page_num,
                    "failed_pages": failed_pages,
                    "status": "incomplete",
                }, f, indent=2)

        pbar.update(1)

    return list(scraped_urls)


async def retry_failed_pages(page, base_url: str, country: str, gender: str, failed_pages: List[int], scraped_urls: Set[str]) -> Set[str]:
    for page_num in failed_pages:
        try:
            turl = f"{base_url}?p={page_num}"

            await safe_goto(page, turl)
            await dismiss_popups(page)
            await page.wait_for_selector('div[data-testid="plp-product-grid"]', timeout=PAGE_TIMEOUT)

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            grid = soup.find("div", {"data-testid": "plp-product-grid"})
            items = grid.find_all("div", {"data-testid": "plp-product-grid-item"}) if grid else []

            for item in items:
                a = item.find("a")
                if a:
                    scraped_urls.add(a.get("href"))

        except Exception:
            pass

    return scraped_urls


# ---------------- COUNTRY PROCESS ----------------
async def process_country(country: str):
    today_str = date.today().strftime("%Y-%m-%d")

    base_dir = Path(f"{country}/Data/{today_str}")
    log_dir = base_dir / "logs"
    counts_file = base_dir / "counts.json"
    logger = setup_logger(country, log_dir)

    temp_dir = base_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    url_queue: asyncio.Queue = asyncio.Queue()

    # -------------- Skip Completed --------------
    for gender, url in COUNTRY_CONFIGS[country].items():
        resume_file = log_dir / f"{gender.replace(' ', '_')}_resume.json"

        if resume_file.exists():
            try:
                with open(resume_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                if state.get("status") == "complete":
                    print(f"[{country}] Skipping '{gender}' (already completed)")
                    continue
            except:
                pass

        await url_queue.put((gender, url))
    # ---------------------------------------------

    write_lock = asyncio.Lock()

    async def browser_worker(worker_id: int):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                channel="chrome"
            )

            page = await browser.new_page()

            while not url_queue.empty():
                try:
                    gender, url = await url_queue.get()
                except:
                    break

                resume_file = log_dir / f"{gender.replace(' ', '_')}_resume.json"
                pbar = tqdm(desc=f"{country} | {gender}", unit="page", position=worker_id, leave=True)

                try:
                    urls = await get_product_urls(page, url, country, gender, log_dir, resume_file, pbar, write_lock)

                    if resume_file.exists():
                        with open(resume_file, "r", encoding="utf-8") as f:
                            resume_state = json.load(f)
                        failed_pages = resume_state.get("failed_pages", [])
                        scraped_urls = set(resume_state.get("urls", []))
                    else:
                        failed_pages = []
                        scraped_urls = set(urls)

                    if failed_pages:
                        scraped_urls = await retry_failed_pages(page, url, country, gender, failed_pages, scraped_urls)

                    with open(resume_file, "w", encoding="utf-8") as f:
                        json.dump({
                            "urls": list(scraped_urls),
                            "last_page": resume_state.get("last_page", 0),
                            "failed_pages": [],
                            "status": "complete",
                        }, f, indent=2)

                    temp_file = temp_dir / f"{gender.replace(' ', '_')}.json"
                    with open(temp_file, "w", encoding="utf-8") as f:
                        json.dump({gender: list(scraped_urls)}, f, indent=2)

                    logger.info(f"[{country}] {gender}: {len(scraped_urls)} URLs scraped")

                    timestamp = datetime.utcnow().isoformat() + "Z"
                    if counts_file.exists():
                        with open(counts_file, "r", encoding="utf-8") as cf:
                            counts_data = json.load(cf)
                    else:
                        counts_data = {}

                    if country not in counts_data:
                        counts_data[country] = {}

                    counts_data[country][gender] = {
                        "count": len(scraped_urls),
                        "updated_at": timestamp,
                    }

                    with open(counts_file, "w", encoding="utf-8") as cf:
                        json.dump(counts_data, cf, indent=2)

                    print(f"[{country}] Completed category '{gender}' -> {len(scraped_urls)} URLs")

                except Exception as e:
                    logger.error(f"[{country}] Error scraping {gender}: {e}")

                pbar.close()
                url_queue.task_done()

            await browser.close()

    workers = [browser_worker(i) for i in range(Browser_Limit)]
    await asyncio.gather(*workers)

    output_dir = base_dir / "Item_urls"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{country}_product_urls.json"

    final_data = {}
    for file in temp_dir.glob("*.json"):
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
        final_data.update(data)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=2)

    for file in temp_dir.glob("*"):
        file.unlink()
    temp_dir.rmdir()

    print(f"[{country}] Completed: {sum(len(v) for v in final_data.values())} URLs saved.")


# ----------------- MAIN -----------------------
async def main():
    countries = get_countries_to_run()
    if not countries:
        print("No countries scheduled today.")
        return

    tasks = [process_country(c) for c in countries if c in COUNTRY_CONFIGS]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted.")
