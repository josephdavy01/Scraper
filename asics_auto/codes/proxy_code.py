import time
import random
import asyncio
from playwright.async_api import async_playwright

async def dismiss_popups(page):
    try:
        selectors = [
            'form#promptForm',          # Main form
            '#customHeader',            # Header
            '#nextPageLink',            # Next button
            '.promptContainer',         # Prompt container
            '#overlayContainer',        # Potential overlay
            '.im_iframe_overlay',       # Another overlay
            'div#promptArea',           # Prompt area
            'fieldset',                 # Fieldset
            '#page1',                   # Page container
            '.progress-bar',            # Progress bar (specific to this survey)
            '#footerBar',               # Footer bar
            '#nav'                      # Navigation
        ]
        
        # Get viewport dimensions for dynamic clicking
        viewport = await page.evaluate('''() => ({ width: window.innerWidth, height: window.innerHeight })''')
        click_positions = [
            {'x': 10, 'y': 10},                     # Top-left
            {'x': viewport['width'] - 10, 'y': viewport['height'] - 10}  # Bottom-right
        ]
        
        dismissed = False
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    for pos in click_positions:
                        await page.mouse.click(pos['x'], pos['y'])
                        await asyncio.sleep(1)
                        # Check if still visible after click
                        if not await element.is_visible():
                            dismissed = True
                            break
                    if dismissed:
                        break
            except Exception as e:
                print(f"Error checking {selector}: {e}")
        
        if not dismissed:
            await page.evaluate('''() => {
                const form = document.querySelector('form#promptForm');
                if (form) form.style.display = 'none';
                const backdrop = document.querySelector('[ng-if="renderBackdropContainer()"]');
                if (backdrop) backdrop.style.display = 'none';
            }''')
            await asyncio.sleep(1)
    
    except Exception as e:
        print(f"Popup dismissal error: {e}")

async def load_more_with_dynamic_wait(page, load_more_selector):
    load_more_button = await page.query_selector(load_more_selector)
    if load_more_button:
        try:
            await load_more_button.click()
            await page.wait_for_load_state('domcontentloaded', timeout=90000)
            try:
                await page.wait_for_selector('.loader-bg', state='detached', timeout=20000)
            except:
                pass
        except Exception as e:
            print(f"Load more click failed: {e}")

async def async_get_page_scroll_load(url, elements_to_wait=None, sleep_time=0):
    print(f'processing {url}...')
    
    with open('proxies.txt', 'r') as f:
        proxies = [line.strip() for line in f if line.strip()]
    
    tried = set()
    
    while True:
        available = [p for p in proxies if p not in tried]
        if not available:
            raise Exception("All proxies failed or blocked.")
        
        proxy_str = random.choice(available)
        tried.add(proxy_str)
        
        parts = proxy_str.split(':')
        if len(parts) != 4:
            print("Invalid proxy format")
            continue
        server, port, username, password = parts
        
        try:
            async with async_playwright() as p:
                browser = await p.firefox.launch(
                    headless=False,
                    proxy={
                        "server": f"http://{server}:{port}",
                        "username": username,
                        "password": password
                    }
                )

                context = await browser.new_context(viewport={"width": 1665, "height": 915})

                try:
                    page = await context.new_page()
                except:
                    print("Failed to create page")
                    await browser.close()
                    continue
                
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=50000)
                    
                    try:
                        await page.wait_for_selector('#onetrust-banner-sdk', timeout=30000)
                        consent_button = await page.wait_for_selector('button#onetrust-accept-btn-handler', timeout=5000)
                        if consent_button:
                            await consent_button.click()
                            await asyncio.sleep(1)
                    except:
                        pass
                    
                    # Wait for specific elements
                    if elements_to_wait:
                        elements = [elements_to_wait] if isinstance(elements_to_wait, str) else elements_to_wait
                        for selector in elements:
                            try:
                                await page.wait_for_selector('.onetrust-pc-dark-filter', state='detached', timeout=10000)
                                await page.wait_for_selector(selector, timeout=10000)
                            except:
                                print("Element not found")
                                await browser.close()
                                raise Exception(f"Selector {selector} not found")
                    else:
                        if sleep_time > 0:
                            await asyncio.sleep(sleep_time)
                    
                    # Scroll and load logic
                    load_more_selector = '#view-load-more'
                    product_selector = '.grid-tile'
                    await page.wait_for_selector(product_selector, timeout=30000)
                    
                    previous_count = 0
                    no_change_count = 0
                    max_no_change = 5
                    current_position = 0
                    
                    while no_change_count < max_no_change:
                        try:
                            current_position += 1
                            await page.evaluate(f"window.scrollTo(0, window.innerHeight * {current_position});")
                            await asyncio.sleep(2)
                            
                            await dismiss_popups(page)  # Check after scroll
                            
                            # Loader wait
                            try:
                                await page.wait_for_selector('.loader-bg', state='detached', timeout=10000)
                            except:
                                pass
                            
                            # Load more with dynamic wait
                            await dismiss_popups(page)  # Check before click
                            await load_more_with_dynamic_wait(page, load_more_selector)
                            await dismiss_popups(page)  # Check after click
                            
                            current_products = await page.query_selector_all(product_selector)
                            current_count = len(current_products)
                            print(f'Products found after scroll: {current_count}')
                            
                            if current_count == previous_count:
                                no_change_count += 1
                                await dismiss_popups(page)  # Extra check on stall
                            else:
                                no_change_count = 0
                            
                            previous_count = current_count
                            if current_count > 3000:
                                break
                        except:
                            print("Scroll loop issue")
                            no_change_count += 1
                            await asyncio.sleep(2)
                    
                    content = await page.content()
                except:
                    print("Page interaction failed")
                    await browser.close()
                    continue
                
                await browser.close()
                
                if content and 'access denied' not in content.lower():
                    return content
        except:
            print("Playwright session failed")
            continue

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
                args=['--window-position=-32000,0'],
                proxy={
                    "server": f"http://{server}:{port}",
                    "username": username,
                    "password": password
                }
            )
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=100000)
                if elements_to_wait:
                    if isinstance(elements_to_wait, str):
                        elements = [elements_to_wait]
                    else:
                        elements = elements_to_wait
                    for selector in elements:
                        try:
                            await page.wait_for_selector(selector, timeout=10000, state="attached")
                        except Exception as e:
                            print(f"Selector wait failed")
                            await browser.close()
                            raise Exception(f"Selectornot found")
                else:
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                content = await page.content()
            except Exception as e:
                print(f"Exception:")
                await browser.close()
                continue
            await browser.close()
            # Check for blockage (customize as needed)
            if content and 'access denied' not in content.lower():
                return content