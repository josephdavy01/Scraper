import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright

EXCLUDE = {"Shop All", "Collections", "Accessories", "Lifestyle", 
           "Kith Summer 2025", "Kith Women Summer 2025 Delivery I",
           "Kith Kids Summer 2025 Delivery I"}

async def close_frequent_popups(page, config):
    for selector in config.get("popup_selectors", []):
        try:
            popup = await page.wait_for_selector(selector, timeout=2000, state="visible")
            await popup.click()
            print(f"Closed popup: {selector}")
        except:
            pass

async def close_welcome_mat(page, config):
    try:
        await page.click(config["welcome_mat_selector"], timeout=3000)
        print("Closed main welcome mat")
        return
    except: pass

    try:
        btn = await page.wait_for_selector("button[js-close-welcome-mat]", timeout=3000)
        await btn.click()
        print("Closed EU Stay popup")
        return
    except: pass

    try:
        await page.click("button:has-text('Stay on')", timeout=3000)
        print("Closed popup (text match)")
    except: pass

async def extract_urls_from_panel(page, panel_id, domain):
    result = {}
    try:
        # Try getting grandchildren links first (specific sub-collections)
        try:
            await page.wait_for_selector(f"#{panel_id} a.desktop-drawer__grandchild-link", timeout=3000)
            grandchild_urls = await page.query_selector_all(f"#{panel_id} a.desktop-drawer__grandchild-link")
        except:
            grandchild_urls = []

        for link in grandchild_urls:
            name = (await link.inner_text()).strip()
            href = await link.get_attribute("href")
            if name and href and all(ex.lower() not in name.lower() for ex in EXCLUDE):
                result[name] = f"https://{domain}{href}"

        # Then get standard list links if needed
        try:
            await page.wait_for_selector(f"ul#{panel_id} li a", timeout=3000)
            list_urls = await page.query_selector_all(f"ul#{panel_id} li a")
        except:
            list_urls = []

        for link in list_urls:
            name = (await link.inner_text()).strip()
            href = await link.get_attribute("href")
            if name and href and name not in result and all(ex.lower() not in name.lower() for ex in EXCLUDE):
                result[name] = f"https://{domain}{href}"

    except Exception as e:
        print(f"Error extracting links from panel {panel_id}: {str(e)}")

    return result

async def process_sub_category(page, tab_id, panel_id, sub_tab_id, domain, config):
    try:
        sub_tab = await page.wait_for_selector(f"#{sub_tab_id}", timeout=5000)
        await sub_tab.click()
        
        # Re-open logic if panel closed
        if not await page.query_selector(f"#{panel_id}[aria-hidden='false']"):
            print("Panel closed. Reopening...")
            await page.click(f"#{tab_id}")
            await page.wait_for_selector(f"#{panel_id}[aria-hidden='false']", state="visible", timeout=5000)
            await page.wait_for_timeout(500)
            await page.click(f"#{sub_tab_id}")

        sub_panel_id = await sub_tab.get_attribute("aria-controls")
        await page.wait_for_selector(f"#{sub_panel_id}[aria-hidden='false']", state="visible", timeout=5000)

        return await extract_urls_from_panel(page, sub_panel_id, domain)

    except Exception as e:
        print(f"Failed sub-category {sub_tab_id}: {str(e)}")
        return {}

async def process_country(country, config, date_str, re_run=False):
    output = {}
    output_dir = Path(country) / date_str / "Category"
    output_dir.mkdir(parents=True, exist_ok=True)

    file_path = output_dir / f"{country}_category_links.json"
    if not re_run and file_path.exists() and file_path.stat().st_size > 0:
        print(f"[{country}] Category links file already exists and is not empty. Skipping as re-run is False.")
        return

    print(f"[{country}] Launching Browser...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()
        
        try:
            await page.goto(config["base_url"], wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            await close_welcome_mat(page, config)
            await asyncio.sleep(2)
            await close_frequent_popups(page, config)

            nav = config['nav_config']
            
            for category_name, tab_id in nav["category_tabs"].items():
                print(f"[{country}] Processing {category_name}...")
                try:
                    await page.click(f"#{tab_id}")
                    panel_id = await page.get_attribute(f"#{tab_id}", "aria-controls")
                    await page.wait_for_selector(f"#{panel_id}[aria-hidden='false']", timeout=8000)
                    
                    # Process Main Kith Section
                    cat_result = {}
                    try:
                        kith_btn = await page.wait_for_selector(f"#{panel_id} button:has-text('Kith')", timeout=5000)
                        await kith_btn.click()
                        kith_panel_id = await kith_btn.get_attribute("aria-controls")
                        await page.wait_for_selector(f"#{kith_panel_id}[aria-hidden='false']", timeout=5000)
                        cat_result["Kith"] = await extract_urls_from_panel(page, kith_panel_id, config["domain"])
                    except:
                        pass 

                    # Process Sub Categories
                    sub_cats = nav["sub_categories"].get(category_name, {})
                    for sub_name, sub_tab_id in sub_cats.items():
                        cat_result[sub_name] = await process_sub_category(page, tab_id, panel_id, sub_tab_id, config["domain"], config)
                    
                    output[category_name] = cat_result
                except Exception as e:
                    print(f"[{country}] Error in {category_name}: {e}")

            # Save Results
            file_path = output_dir / f"{country}_category_links.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump([output], f, indent=2)
            print(f"[{country}] Saved data to {file_path}")

        except Exception as e:
            print(f"[{country}] Critical Failure: {e}")
        finally:
            await browser.close()

async def run_all_countries(config_dict, date_str, re_run=False):
    """
    Creates a list of async tasks for every country in the config
    and runs them simultaneously.
    """
    tasks = []
    for country, settings in config_dict.items():
        # Create a task for each country
        tasks.append(process_country(country, settings, date_str, re_run))
    
    # Run all tasks concurrently
    await asyncio.gather(*tasks)

def get_category_urls(config_dict, date_str, re_run=False):
    # Entry point called by master.py
    asyncio.run(run_all_countries(config_dict, date_str, re_run))