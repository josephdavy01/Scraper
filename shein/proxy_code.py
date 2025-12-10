import time
import random
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright

def get_page_source(url, elements_to_wait=None):
    print(f'processing {url}...')
    # Read proxies from proxies.txt
    with open('proxies.txt', 'r') as f:
        proxies = [line.strip() for line in f if line.strip()]
    tried = set()
    while True:
        available = [p for p in proxies if p not in tried]
        if not available:
            raise Exception("All proxies failed or blocked.")
        proxy_str = random.choice(available)
        tried.add(proxy_str)
        server, port, username, password = proxy_str.split(':')
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                proxy={
                    "server": f"http://{server}:{port}",
                    "username": username,
                    "password": password
                }
            )
            page = browser.new_page()
            try:
                page.goto(url, timeout=60000)
                if elements_to_wait:
                    # Ensure elements_to_wait is a list
                    if isinstance(elements_to_wait, str):
                        elements = [elements_to_wait]
                    else:
                        elements = elements_to_wait
                    for selector in elements:
                        page.wait_for_selector(selector, timeout=60000)
                page_source = page.content()
            except Exception:
                browser.close()
                continue
            browser.close()
            # Check for blockage (customize as needed)
            if page_source and 'access denied' not in page_source.lower():
                return page_source

async def async_get_page_source(url, elements_to_wait=None, sleep_time=0):
    print(f'processing {url}...')
    # Read proxies from proxies.txt
    with open('proxies.txt', 'r') as f:
        proxies = [line.strip() for line in f if line.strip()]
    tried = set()
    while True:
        available = [p for p in proxies if p not in tried]
        if not available:
            raise Exception("All proxies failed or blocked.")
        proxy_str = random.choice(available)
        tried.add(proxy_str)
        server, port, username, password = proxy_str.split(':')
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                proxy={
                    "server": f"http://{server}:{port}",
                    "username": username,
                    "password": password
                }
            )
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=60000)
                if elements_to_wait:
                    if isinstance(elements_to_wait, str):
                        elements = [elements_to_wait]
                    else:
                        elements = elements_to_wait
                    for selector in elements:
                        try:
                            await page.wait_for_selector(selector, timeout=60000, state="attached")
                        except Exception as e:
                            print(f"Selector wait failed: {selector} - {e}")
                            await browser.close()
                            raise Exception(f"Selector {selector} not found")
                else:
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                content = await page.content()
            except Exception as e:
                print(f"Exception: {e}")
                await browser.close()
                continue
            await browser.close()
            # Check for blockage (customize as needed)
            if content and 'access denied' not in content.lower():
                return content