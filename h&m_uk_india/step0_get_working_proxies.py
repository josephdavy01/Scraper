import asyncio
import os
from playwright.async_api import async_playwright

working_file = 'working_proxies.txt'
non_working_file = 'non_working_proxies.txt'
semaphore = asyncio.Semaphore(4)

# Ensure output files exist
open(working_file, 'a').close()
open(non_working_file, 'a').close()

async def test_proxy(proxy_str, url):
    async with semaphore:
        try:
            server, port, username, password = proxy_str.split(':')
        except ValueError:
            print(f"Invalid proxy format: {proxy_str}")
            return

        proxy_config = {
            "server": f"http://{server}:{port}",
            "username": username,
            "password": password
        }

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False, proxy=proxy_config)
            page = await browser.new_page()

            try:
                response = await page.goto(url, timeout=60000)
                status = response.status if response else 'No response'
                print(f"Proxy {server} responded with status: {status}")

                content = await page.content()

                if response and response.ok and 'access denied' not in content.lower():
                    with open(working_file, 'a') as wf:
                        wf.write(proxy_str + '\n')
                    print(f"Proxy {server} is working.")
                else:
                    with open(non_working_file, 'a') as nf:
                        nf.write(proxy_str + '\n')
                    print(f"Proxy {server} failed or blocked.")
            except Exception as e:
                print(f"Exception with proxy {server}: {e}")
                with open(non_working_file, 'a') as nf:
                    nf.write(proxy_str + '\n')
            finally:
                await browser.close()

async def async_get_page_source_proxy_separation(url):
    print(f'Processing {url}...')

    with open('proxies.txt', 'r') as f:
        proxies = [line.strip() for line in f if line.strip()]

    tasks = [test_proxy(proxy, url) for proxy in proxies]
    await asyncio.gather(*tasks)

    print("Proxy testing complete.")

if __name__ == "__main__":
    asyncio.run(async_get_page_source_proxy_separation('https://www2.hm.com/en_in/index.html'))