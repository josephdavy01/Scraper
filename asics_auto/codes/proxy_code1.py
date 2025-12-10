import time
import random
import asyncio
import logging
from patchright.async_api import async_playwright
from fake_useragent import UserAgent


class AdvancedAntiDetection:
    def __init__(self):
        self.ua = UserAgent()
        self.canvas_noise = self._generate_canvas_noise()
        self.webgl_vendor = random.choice([
            "Google Inc. (Intel)", "Google Inc. (NVIDIA)", "Google Inc. (AMD)",
            "Intel Inc.", "NVIDIA Corporation", "ATI Technologies Inc."
        ])
        
    def _generate_canvas_noise(self):
        """Generate canvas fingerprint noise"""
        return {
            'r': random.randint(0, 255),
            'g': random.randint(0, 255), 
            'b': random.randint(0, 255),
            'a': random.uniform(0.1, 1.0)
        }
    
    def get_random_viewport(self):
        """Common real device viewports"""
        viewports = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1536, "height": 864},
            {"width": 1440, "height": 900},
            {"width": 1280, "height": 720}
        ]
        return random.choice(viewports)
    
    def get_stealth_headers(self):
        """Generate realistic browser headers"""
        return {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }


async def apply_advanced_stealth(context, anti_detect):
    """Apply comprehensive anti-detection techniques"""
    await context.add_init_script(f"""
        Object.defineProperty(navigator, 'webdriver', {{
            get: () => undefined
        }});
        
        Object.defineProperty(navigator, 'plugins', {{
            get: () => {{
                const plugins = [];
                plugins.length = {random.randint(3, 8)};
                return plugins;
            }}
        }});
        
        Object.defineProperty(navigator, 'languages', {{
            get: () => ['en-US', 'en']
        }});
        
        const getContext = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function(type) {{
            const context = getContext.apply(this, arguments);
            if (type === '2d') {{
                const getImageData = context.getImageData;
                context.getImageData = function(...args) {{
                    const imageData = getImageData.apply(this, args);
                    for (let i = 0; i < imageData.data.length; i += 4) {{
                        imageData.data[i] += Math.floor(Math.random() * 3) - 1;
                    }}
                    return imageData;
                }};
            }}
            return context;
        }};
        
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {{
            if (parameter === 37445) {{
                return '{anti_detect.webgl_vendor}';
            }}
            if (parameter === 37446) {{
                return 'ANGLE (Intel, Intel(R) HD Graphics Direct3D11 vs_5_0 ps_5_0, D3D11-27.20.100.8853)';
            }}
            return getParameter.apply(this, arguments);
        }};
        
        Object.defineProperty(screen, 'availWidth', {{
            get: () => window.innerWidth
        }});
        Object.defineProperty(screen, 'availHeight', {{
            get: () => window.innerHeight
        }});
        
        Date.prototype.getTimezoneOffset = function() {{
            return 300;
        }};
        
        let mouseMovements = 0;
        document.addEventListener('mousemove', () => {{
            mouseMovements++;
        }});
        
        window.chrome = {{
            runtime: {{}}
        }};
        
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({{ state: Notification.permission }}) :
                originalQuery(parameters)
        );
    """)


async def human_like_behavior(page):
    """Simulate realistic human browsing patterns"""
    viewport = await page.evaluate('() => ({ width: window.innerWidth, height: window.innerHeight })')
    
    for _ in range(random.randint(2, 5)):
        x = random.randint(50, viewport['width'] - 50)
        y = random.randint(50, viewport['height'] - 50)
        await page.mouse.move(x, y, steps=random.randint(3, 10))
        await asyncio.sleep(random.uniform(0.1, 0.3))
    
    scroll_distance = random.randint(100, 500)
    await page.evaluate(f"window.scrollBy(0, {scroll_distance})")
    await asyncio.sleep(random.uniform(0.5, 1.5))
    
    await page.evaluate("window.focus()")
    await asyncio.sleep(random.uniform(0.2, 0.8))


async def async_get_page_source(url, elements_to_wait=None, sleep_time=0):
    print(f'Processing {url} with advanced anti-detection...')
    
    with open('proxies.txt', 'r') as f:
        proxies = [line.strip() for line in f if line.strip()]
    
    tried = set()
    anti_detect = AdvancedAntiDetection()
    
    while True:
        available = [p for p in proxies if p not in tried]
        if not available:
            raise Exception("All proxies failed or blocked.")
        
        proxy_str = random.choice(available)
        tried.add(proxy_str)
        
        parts = proxy_str.split(':')
        if len(parts) != 4:
            continue
        server, port, username, password = parts
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=False,
                    args=[
                        # '--window-position=-32000,0',
                        '--no-sandbox',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        f'--user-agent={anti_detect.ua.random}'
                    ],
                    proxy={
                        "server": f"http://{server}:{port}",
                        "username": username,
                        "password": password
                    }
                )
                
                viewport = anti_detect.get_random_viewport()
                context = await browser.new_context(
                    viewport=viewport,
                    user_agent=anti_detect.ua.random,
                    extra_http_headers=anti_detect.get_stealth_headers(),
                    timezone_id='America/New_York',
                    locale='en-US',
                    permissions=['notifications'],
                    color_scheme='light'
                )
                
                await apply_advanced_stealth(context, anti_detect)
                
                page = await context.new_page()
                
                await page.goto(url, wait_until='domcontentloaded', timeout=100000)
                await asyncio.sleep(random.uniform(8, 10))
                
                await human_like_behavior(page)
                
                if elements_to_wait:
                    elements = [elements_to_wait] if isinstance(elements_to_wait, str) else elements_to_wait
                    for selector in elements:
                        try:
                            await page.wait_for_selector(selector, timeout=10000, state="attached")
                            await human_like_behavior(page)
                        except Exception as e:
                            print(f"Selector wait failed: {selector}")
                            await browser.close()
                            raise Exception(f"Required element not found")
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(random.uniform(1, 2))
                
                content = await page.content()
                await browser.close()
                
                if content and 'access denied' not in content.lower():
                    return content
                else:
                    print("Blocked, trying next proxy...")
                    
        except Exception as e:
            print(f"Attempt failed: {e}")
            continue