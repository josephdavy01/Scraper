#!/usr/bin/env python3
"""
Full scraper script (updated):
- kids/baby sizes (chip-long / chip-short)
- price extraction (single and sale+original)
- explicit Playwright waits for JS-rendered elements
- accordion parsing driven by the <button> label (Details, Features, Materials/Care, Production/Impact)
- cleaned & deduplicated features
- origin extraction returns only "Country/Countries of Production" if present
- atomic JSON writes
"""

import os
import json
import re
from datetime import date
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup, Tag
from playwright.sync_api import sync_playwright
from multiprocessing import Pool, cpu_count, set_start_method
from multiprocessing.pool import ThreadPool
from functools import partial
from tqdm import tqdm

# ----------------- CONFIG -----------------
today = date.today().strftime("%Y-%m-%d")
countries = ["USA", "Australia", "Canada", "Spain", "UK"]

# Playwright timing constants (ms)
WAIT_AFTER_NAV_MS = 2000               # small fixed pause after navigation
WAIT_FOR_SELECTOR_TIMEOUT_MS = 8000    # how long to wait for important selectors
FALLBACK_WAIT_MS = 4000                # extra wait if selectors never show up

# Browser settings
PLAYWRIGHT_HEADLESS = False

# ----------------- Helpers -----------------
def _normalize_for_compare(s: str) -> str:
    s2 = re.sub(r'[\W_]+', ' ', s, flags=re.UNICODE).strip().lower()
    s2 = re.sub(r'\s+', ' ', s2)
    return s2

def clean_features(raw_feats):
    """
    Normalize, dedupe and preserve order. Prefer longer/more informative variants.
    raw_feats: list[str]
    returns: list[str]
    """
    seen_norm = []
    cleaned = []

    for f in raw_feats:
        if not f:
            continue
        s = f.strip()
        if not s:
            continue
        norm = _normalize_for_compare(s)
        if not norm:
            continue

        skip = False
        # If exact normalized present -> skip
        for ex_norm in list(seen_norm):
            if norm == ex_norm:
                skip = True
                break
            # If norm is substring of existing normalized, skip (existing is longer)
            if norm in ex_norm:
                skip = True
                break
            # If existing normalized is substring of this norm, remove the existing in favor of the longer one
            if ex_norm in norm:
                try:
                    idx = seen_norm.index(ex_norm)
                    seen_norm.pop(idx)
                    cleaned.pop(idx)
                except ValueError:
                    pass
        if skip:
            continue

        seen_norm.append(norm)
        cleaned.append(s)
    return cleaned

def find_element_by_class_re(soup, tag, class_re):
    try:
        return soup.find(tag, class_=re.compile(class_re))
    except Exception:
        return None

def find_nested_element(parent, selector_list):
    current_element = parent
    for idx, sel in enumerate(selector_list):
        if current_element is None:
            return None
        if not isinstance(sel, (list, tuple)) or len(sel) not in [2, 3]:
            tqdm.write(f"Warning: selector at index {idx} unexpected: {sel}")
            return None
        tag_name, class_info = sel[0], sel[1]
        attrs = sel[2] if len(sel) == 3 else None
        search_criteria = {}
        if isinstance(class_info, str):
            try:
                search_criteria['class'] = re.compile(class_info)
            except re.error:
                search_criteria['class'] = class_info
        elif isinstance(class_info, dict):
            search_criteria.update(class_info)
        if attrs and isinstance(attrs, dict):
            for k, v in attrs.items():
                if isinstance(v, str):
                    try:
                        search_criteria[k] = re.compile(v)
                    except re.error:
                        search_criteria[k] = v
                else:
                    search_criteria[k] = v
        try:
            current_element = current_element.find(tag_name, **search_criteria)
        except Exception as e:
            tqdm.write(f"Warning: find() error at selector {sel}: {type(e).__name__} - {e}. Falling back to tag find.")
            current_element = current_element.find(tag_name)
    return current_element

# ----------------- Variant extraction with waits -----------------
def extract_variant_urls(page, base_url, country):
    try:
        page.goto(base_url, wait_until="domcontentloaded")
    except Exception:
        page.goto(base_url)

    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    page.wait_for_timeout(WAIT_AFTER_NAV_MS)

    selectors_to_wait = [
        "button[data-testid='ITOChip']",
        "div.size-chip-group",
        "ul.collection-list-horizontal",
        "div.fr-ec-price",
    ]
    found_selector = False
    for sel in selectors_to_wait:
        try:
            page.wait_for_selector(sel, timeout=WAIT_FOR_SELECTOR_TIMEOUT_MS)
            found_selector = True
            break
        except Exception:
            continue
    if not found_selector:
        page.wait_for_timeout(FALLBACK_WAIT_MS)

    soup = BeautifulSoup(page.content(), "html.parser")
    variant_urls = []
    base_url_no_params = base_url.split("?")[0]

    ul_candidates = soup.find_all("ul", class_=re.compile("collection-list-horizontal"))
    for ul in ul_candidates:
        for btn in ul.find_all("button", {"data-testid": "ITOChip"}):
            if btn.has_attr("value"):
                color_code = btn["value"].strip()
                variant_urls.append(f"{base_url_no_params}?colorDisplayCode={color_code}")

    if not variant_urls:
        for btn in soup.find_all("button", {"data-testid": "ITOChip"}):
            if btn.has_attr("value"):
                color_code = btn["value"].strip()
                variant_urls.append(f"{base_url_no_params}?colorDisplayCode={color_code}")

    if not variant_urls:
        variant_urls = [base_url_no_params]

    return list(set(variant_urls))

# ----------------- Main parser -----------------
def parse_variant(page, url, country, gender_hint=None):
    try:
        page.goto(url, wait_until="domcontentloaded")
    except Exception:
        page.goto(url)

    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    page.wait_for_timeout(WAIT_AFTER_NAV_MS)

    important_selectors = [
        "div.size-chip-group",
        "button[data-testid='ITOChip']",
        "div.fr-ec-price",
        "p.fr-ec-price-text",
        "div.gutter-container",
    ]
    selector_found = False
    for sel in important_selectors:
        try:
            page.wait_for_selector(sel, timeout=WAIT_FOR_SELECTOR_TIMEOUT_MS)
            selector_found = True
            break
        except Exception:
            continue
    if not selector_found:
        page.wait_for_timeout(FALLBACK_WAIT_MS)

    soup = BeautifulSoup(page.content(), "html.parser")

    # product id from URL
    match = re.search(r"/products/([^/]+)/", url)
    product_id = match.group(1) if match else "NA"

    # color id from query params
    color_id = "NA"
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "colorDisplayCode" in qs and qs["colorDisplayCode"]:
            color_id = qs["colorDisplayCode"][0]
        elif "color" in qs and qs["color"]:
            color_id = qs["color"][0]
    except Exception:
        color_id = "NA"

    # find root element
    layer_div = soup.find("div", class_=re.compile(r"\bfr-layer-base\b.*\bfr-spa-root\b"))
    if layer_div:
        root_element = layer_div.find('div', style=re.compile(r"min-height:\s*268px;\s*position:\s*relative;")) or soup.body
    else:
        root_element = soup.find('div', style=re.compile(r"min-height:\s*268px;\s*position:\s*relative;")) or soup.body

    # item_id_from_html
    item_id_from_html = None
    product_id_container_selector_html = (
        ('div', 'fr-ec-template-pdp'),
        ('div', 'fr-ec-layout-wrapper fr-ec-mt-spacing-05'),
        ('div', 'fr-ec-layout fr-ec-layout--gutter-md fr-ec-layout--gutter-lg fr-ec-layout--span-4-sm fr-ec-layout--span-12-md fr-ec-layout--span-12-lg'),
        ('aside', 'fr-ec-layout fr-ec-layout--gutter-md fr-ec-layout--gutter-lg fr-ec-layout--span-4-sm fr-ec-layout--span-7-md fr-ec-layout--span-8-lg fr-ec-layout--inset-right-lg fr-ec-template-pdp-product-details-container fr-ec-template-pdp__ec-renewal-padding'),
        ('div', 'gutter-container'),
        ('p', 'typography typography-reset ito-font-family-uq-en-like ito-font-weight-400 ito-font-size-15 ito-font-lh-1-4 text-align-left text-transform-normal ito-margin-bottom-16')
    )
    try:
        product_id_tag_html = find_nested_element(root_element, product_id_container_selector_html)
        if product_id_tag_html:
            match_html = re.search(r"Product ID:\s*(\d+)", product_id_tag_html.get_text(strip=True))
            if match_html:
                item_id_from_html = match_html.group(1)
    except Exception:
        item_id_from_html = None

    # main_tag
    main_tag_selector = (
        ('div', 'template-base'),
        ('div', 'template-base-wrapper'),
        ('div', 'template-base__page-content'),
        ('div', 'fr-ec-template-pdp'),
        ('div', 'fr-ec-layout-wrapper fr-ec-mt-spacing-05'),
        ('div', 'fr-ec-layout fr-ec-layout--gutter-md fr-ec-layout--gutter-lg fr-ec-layout--span-4-sm fr-ec-layout--span-12-md fr-ec-layout--span-12-lg'),
        ('main', 'fr-ec-layout fr-ec-layout--gutter-md fr-ec-layout--gutter-lg fr-ec-layout--span-4-sm fr-ec-layout--span-5-md fr-ec-layout--span-4-lg fr-ec-mb-spacing-03-lg fr-ec-mb-spacing-03-md fr-ec-template-pdp-product-selector-container')
    )
    main_tag = find_nested_element(root_element, main_tag_selector) or soup

    # ---------- TITLE ----------
    product_name = None
    try:
        gutter = main_tag.find('div', class_=re.compile(r'\bgutter-container\b.*\bito-margin-bottom-16\b'))
        if gutter:
            title_div = gutter.find('div', class_=re.compile(r'typography typography-reset .*ito-font-size-18.*'), attrs={"data-testid": re.compile(r"ITOTypography")})
            if title_div:
                product_name = title_div.get_text(strip=True)
    except Exception:
        product_name = None

    # ---------- COLOR NAME ----------
    color_name = None
    try:
        color_div = None
        for g in main_tag.find_all('div', class_=re.compile(r'\bgutter-container\b')):
            candidate = g.find('div', class_=re.compile(r'typography typography-reset .*ito-font-size-13.*'), attrs={"data-testid": re.compile(r"ITOTypography")})
            if candidate and re.search(r"(?:Colour|Color):", candidate.get_text("", strip=True), re.IGNORECASE):
                color_div = candidate
                break
        if color_div:
            txt = color_div.get_text(" ", strip=True)
            m = re.search(r"(?:Colour|Color):\s*(.+)", txt, re.IGNORECASE)
            if m:
                color_full = m.group(1).strip()
                color_name = color_full
                if color_id == "NA":
                    id_match = re.match(r"(\d+)", color_full)
                    if id_match:
                        color_id = id_match.group(1)
    except Exception:
        color_name = None

    # ---------- PRICES ----------
    launch_price = None
    offer_price = None
    def extract_price_number(text):
        if not text:
            return None
        m = re.search(r"[\d\.,]+", text)
        return m.group(0) if m else None
    try:
        price_nodes = main_tag.find_all('p', class_=re.compile(r'fr-ec-price-text'))
        promo_node = None
        large_node = None
        for p in price_nodes:
            cls = " ".join(p.get("class", []))
            if "fr-ec-price-text--color-promotional" in cls:
                promo_node = p
                break
            if "fr-ec-price-text--large" in cls and not large_node:
                large_node = p
        strike_node = main_tag.find('p', class_=re.compile(r'fr-ec-price__strike-through|fr-ec-price-text--extra-small'))

        if promo_node:
            offer_price = extract_price_number(promo_node.get_text(" ", strip=True))
        elif large_node:
            offer_price = extract_price_number(large_node.get_text(" ", strip=True))

        if strike_node:
            launch_price_candidate = extract_price_number(strike_node.get_text(" ", strip=True))
            if launch_price_candidate:
                launch_price = launch_price_candidate
                if not offer_price:
                    offer_price = launch_price

        if not offer_price:
            currency_match = re.search(r'([€$£]\s?[\d\.,]+|[\d\.,]+\s?[€$£])', main_tag.get_text(" ", strip=True))
            if currency_match:
                offer_price = extract_price_number(currency_match.group(0))
                if not launch_price:
                    launch_price = offer_price

        if offer_price and not launch_price:
            launch_price = offer_price
        if launch_price and not offer_price:
            offer_price = launch_price
    except Exception:
        pass

    # ---------- SIZES ----------
    sizes = []
    try:
        size_group = main_tag.find('div', class_=re.compile(r'\bsize-chip-group\b'))
        if not size_group:
            candidates = main_tag.find_all('div', class_=re.compile(r'\bgutter-container\b|\bito-margin-top-16\b|\bito-margin-bottom-24\b'))
            for c in candidates:
                sg = c.find('div', class_=re.compile(r'\bsize-chip-group\b'))
                if sg:
                    size_group = sg
                    break

        if size_group:
            size_wrappers = size_group.find_all('div', class_=re.compile(r'\bsize-chip-wrapper\b'))
            for idx, wrapper in enumerate(size_wrappers):
                btn = wrapper.find('button', attrs={'data-testid': 'ITOChip'}) or wrapper.find('button')
                if not btn:
                    btn = wrapper.find('button', class_=re.compile(r'chip'))
                size_name = None
                size_value = None
                if btn:
                    size_text_tag = btn.find('div', class_=re.compile(r'typography[-\s]reset|typography'))
                    if size_text_tag:
                        size_name = size_text_tag.get_text(" ", strip=True)
                    else:
                        size_name = btn.get_text(" ", strip=True)

                    if btn.has_attr('value') and btn['value'].strip():
                        size_value = btn['value'].strip()
                    elif btn.has_attr('id') and btn['id'].strip():
                        size_value = btn['id'].strip()
                    else:
                        size_value = str(idx + 1)

                available = "in_stock"
                strike_div = wrapper.find('div', class_=re.compile(r'\bstrike\b'))
                if strike_div:
                    available = "out_of_stock"
                else:
                    sib = wrapper.find_next_sibling()
                    if isinstance(sib, Tag) and 'strike' in " ".join(sib.get("class", [])):
                        available = "out_of_stock"

                if size_name and not size_name.lower().startswith("helpful"):
                    sizes.append({
                        "size_id": size_value,
                        "size_name": size_name,
                        "availability": available
                    })
    except Exception:
        sizes = []

    # ---------- ACCORDION: FEATURES / DESCRIPTION / COMPOSITION / ORIGIN ----------
    features, description, composition, country_origin = [], None, None, None
    try:
        li_tags = main_tag.find_all('li', class_=re.compile('list--keyline-all'))
        if not li_tags:
            ul_list = find_nested_element(root_element, (
                ('div', 'fr-ec-layout fr-ec-layout--gutter-md fr-ec-layout--gutter-lg fr-ec-layout--span-4-sm fr-ec-layout--span-12-md fr-ec-layout--span-12-lg'),
                ('aside', 'fr-ec-layout fr-ec-layout--gutter-md fr-ec-layout--gutter-lg fr-ec-layout--span-4-sm fr-ec-layout--span-7-md fr-ec-layout--span-8-lg fr-ec-layout--inset-right-lg fr-ec-template-pdp-product-details-container fr-ec-template-pdp__ec-renewal-padding'),
                ('div', 'gutter-container'),
                ('ul', 'list collection-list'),
            ))
            if ul_list:
                li_tags = ul_list.find_all('li', class_=re.compile('list--keyline-all'))

        for i, li in enumerate(li_tags):
            try:
                btn = li.find('button', class_=re.compile(r'accordion__label-wrapper')) or li.find('button', attrs={'type': 'button'})
                label_text = None
                if btn:
                    first_span = btn.find('span')
                    if first_span:
                        p_tag = first_span.find('p')
                        if p_tag:
                            label_text = p_tag.get_text(" ", strip=True)
                        else:
                            label_text = btn.get_text(" ", strip=True)
                # content
                content_div = li.find('div', class_=re.compile(r'\bito-padding-vertical-16\b'))
                content_text = content_div.get_text("\n", strip=True) if content_div else None

                if label_text:
                    lbl = label_text.strip().lower()
                    # DESCRIPTION (Details)
                    if 'details' in lbl:
                        if content_div:
                            desc_par = []
                            for p in content_div.find_all('p', class_=re.compile(r'typography')):
                                txt = p.get_text(" ", strip=True)
                                if txt:
                                    desc_par.append(txt)
                            description = "\n".join(desc_par).strip() if desc_par else (content_text or description)
                    # FEATURES
                    elif 'feature' in lbl:
                        if content_div:
                            raw_feats = []
                            for node in content_div.find_all(['p', 'div', 'li']):
                                txt = node.get_text("\n", strip=True)
                                if not txt:
                                    continue
                                lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
                                for ln in lines:
                                    ln = re.sub(r'^[\-\u2022\*]+\s*', '', ln).strip()
                                    if ln:
                                        raw_feats.append(ln)
                            if not raw_feats and content_text:
                                for ln in [ln.strip() for ln in content_text.splitlines() if ln.strip()]:
                                    ln = re.sub(r'^[\-\u2022\*]+\s*', '', ln).strip()
                                    if ln:
                                        raw_feats.append(ln)
                            features = clean_features(raw_feats)
                    # COMPOSITION / MATERIALS / CARE
                    elif 'material' in lbl or 'care' in lbl:
                        if content_div:
                            comp_parts = []
                            for p in content_div.find_all('p', class_=re.compile(r'typography')):
                                txt = p.get_text(" ", strip=True)
                                if txt:
                                    comp_parts.append(txt)
                            composition = "\n".join(comp_parts).strip() if comp_parts else (content_text or composition)
                    # ORIGIN / PRODUCTION / IMPACT
                    elif 'production' in lbl or 'impact' in lbl:
                        if content_div:
                            ct = content_div.get_text("\n", strip=True)
                            # try to extract explicit Country/Countries of Production line
                            m = re.search(
                                r"(?:Country(?:/Countries)? of Production|Production):\s*([A-Za-z0-9 ,&()-]+)",
                                ct,
                                re.IGNORECASE
                            )

                            if m:
                                country_origin = m.group(1).strip()
                                # truncate at first blank-line or sentence end if overly long
                                country_origin = country_origin.split("\n")[0].strip()
                            else:
                                # fallback: look for "Country/Countries of Production" exact in content (line-by-line)
                                for line in ct.splitlines():
                                    if re.search(
                                        r"(?:Country(?:/Countries)? of Production|Production):\s*([A-Za-z0-9 ,&()-]+)",
                                        ct,
                                        re.IGNORECASE):
                                        parts = line.split(":", 1)
                                        if len(parts) > 1:
                                            country_origin = parts[1].strip()
                                            break
                                # fallback best-effort: pick the first line that is short and comma-separated of country names
                                if not country_origin:
                                    lines = [ln.strip() for ln in ct.splitlines() if ln.strip()]
                                    for ln in lines:
                                        # if looks like "Bangladesh" or "Bangladesh, China" etc (letters, comma, spaces)
                                        if re.match(r'^[A-Za-z][A-Za-z ,&()-]+$', ln) and len(ln) < 120:
                                            country_origin = ln
                                            break
                    else:
                        # unknown label -> fallback index-based mapping (only if that field not already set)
                        if content_div:
                            if i == 0 and not features:
                                feature_tags = content_div.find_all('p', class_=re.compile('image-plus-text__horizontal-large-description'))
                                ftmp = [f.get_text(strip=True) for f in feature_tags if f.get_text(strip=True)]
                                if not ftmp:
                                    # try lines
                                    lines = [ln.strip() for ln in re.split(r'[\r\n]+', content_div.get_text("\n", strip=True)) if ln.strip()]
                                    ftmp = lines
                                features = clean_features(ftmp)
                            elif i == 1 and not description:
                                desc_tag = content_div.find('p', class_=re.compile('typography typography-reset ito-font-family-uq-en-like ito-font-weight-400 ito-font-size-15 ito-font-lh-1-4'))
                                if desc_tag:
                                    description = desc_tag.get_text(" ", strip=True)
                                else:
                                    description = content_text or description
                            elif i == 2 and not composition:
                                comp_tag = content_div.find('p', class_=re.compile('typography typography-reset ito-font-family-uq-en-like ito-font-weight-400 ito-font-size-15 ito-font-lh-1-4'))
                                if comp_tag:
                                    composition = comp_tag.get_text(strip=True)
                                else:
                                    composition = content_text or composition
                            elif i == len(li_tags) - 1 and content_div and not country_origin:
                                origin_tag = content_div.find('p', class_=re.compile('typography typography-reset ito-font-family-uq-en-like ito-font-weight-400 ito-font-size-14 ito-font-lh-1-3'))
                                if origin_tag:
                                    text = origin_tag.get_text(strip=True)
                                    m = re.search(r"(?:Production|Country of Origin|Country(?:/Countries)? of Production):\s*(.*)", text)
                                    if m:
                                        country_origin = m.group(1).strip()
                                    else:
                                        ct = content_div.get_text("\n", strip=True)
                                        m2 = re.search(r"(?:Production|Country of Origin|Country(?:/Countries)? of Production):\s*(.+)", ct, re.IGNORECASE)
                                        if m2:
                                            country_origin = m2.group(1).strip()
            except Exception:
                continue
        # NOTE: intentionally DO NOT copy description into features if features missing.
    except Exception:
        pass

    # ---------- IMAGES ----------
    try:
        images = [img["src"].split("?")[0] for img in soup.find_all("img", src=True) if img.find_parent(class_=re.compile("media-gallery--grid"))]
    except Exception:
        images = []

    # ---------- GENDER ----------
    detected_gender = gender_hint
    try:
        gender_selector = (
            ('div', 'gutter-container ito-margin-top-16 ito-margin-bottom-24'),
            ('div', 'typography typography-reset ito-font-family-uq-en-like ito-font-weight-400 ito-font-size-13 ito-font-lh-1-3 ito-secondary-text-color text-align-left text-transform-normal')
        )
        gender_tag = find_nested_element(main_tag, gender_selector)
        if gender_tag:
            t = gender_tag.get_text(strip=True)
            m = re.search(r"Size:\s*([A-Za-z]+)(?:\s+.*)?", t)
            if m:
                detected_gender = m.group(1).strip().lower()
    except Exception:
        pass
    gender = detected_gender if detected_gender else gender_hint

    # final result
    return {
        "product_id": product_id,
        "title": product_name,
        "color_name": color_name,
        "color_id": color_id,
        "gender": gender,
        "variant_url": url,
        "sizes": sizes,
        "prices": {"launch_price": launch_price, "price": offer_price},
        "description": description,
        "composition": composition,
        "origin": country_origin,
        "images": images,
        "features": features,
        "item_id_from_html": item_id_from_html
    }

# ----------------- Worker -----------------
def scrape_worker(country, gender, category, urls_chunk):
    processed_variants = 0
    variant_url_map = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
        page = browser.new_page()

        with tqdm(total=len(urls_chunk), desc=f"[{country}-{gender}-{category}]", unit="page") as pbar:
            for url in urls_chunk:
                try:
                    variants = extract_variant_urls(page, url, country)
                except Exception as e:
                    tqdm.write(f"[{country}] Error in extract_variant_urls for {url}: {type(e).__name__} - {e}")
                    pbar.update(1)
                    continue

                if not variants:
                    pbar.update(1)
                    continue

                variant_url_map[url] = variants

                for v_url in variants:
                    try:
                        data = parse_variant(page, v_url, country, gender)
                        product_id_for_file = data.get('product_id', 'NA')
                        if product_id_for_file == 'NA':
                            tqdm.write(f"[{country}] Skipping variant with no URL Product ID: {v_url}")
                            continue

                        color_id_for_file = data.get('color_id') or "NA"
                        if color_id_for_file == "NA":
                            tqdm.write(f"[{country}] Skipping variant with no Color ID: {v_url}")
                            continue

                        out_dir = os.path.join(country, "data", today, "Json_data", gender, category)
                        os.makedirs(out_dir, exist_ok=True)
                        filename = f"{product_id_for_file}_{today}_{color_id_for_file}.json"
                        out_file = os.path.join(out_dir, filename)

                        if not os.path.exists(out_file):
                            tmp_file = out_file + ".tmp"
                            try:
                                with open(tmp_file, "w", encoding="utf-8") as jf:
                                    json.dump(data, jf, indent=2, ensure_ascii=False)
                                os.replace(tmp_file, out_file)
                                processed_variants += 1
                                tqdm.write(f"[{country}] Saved: {out_file}")
                            except Exception as write_e:
                                tqdm.write(f"[{country}] Error writing file {out_file}: {type(write_e).__name__} - {write_e}")
                                if os.path.exists(tmp_file):
                                    try:
                                        os.remove(tmp_file)
                                    except Exception:
                                        pass
                        else:
                            tqdm.write(f"[{country}] Already exists: {out_file}")
                    except Exception as e:
                        tqdm.write(f"[{country}] Error parsing {v_url}: {type(e).__name__} - {e}")

                pbar.update(1)

        browser.close()

    # write variant_urls.json atomically
    variant_out_dir = os.path.join(country, "data", today, "Item_urls")
    os.makedirs(variant_out_dir, exist_ok=True)
    variant_file = os.path.join(variant_out_dir, "variant_urls.json")

    if os.path.exists(variant_file):
        with open(variant_file, "r", encoding="utf-8") as vf:
            try:
                variant_data = json.load(vf)
            except json.JSONDecodeError:
                tqdm.write(f"[{country}] Warning: variant_urls.json corrupted, overwriting.")
                variant_data = {}
    else:
        variant_data = {}

    if gender not in variant_data:
        variant_data[gender] = {}
    if category not in variant_data[gender]:
        variant_data[gender][category] = {}

    variant_data[gender][category].update(variant_url_map)

    try:
        tmp_variant = variant_file + ".tmp"
        with open(tmp_variant, "w", encoding="utf-8") as vf:
            json.dump(variant_data, vf, indent=2, ensure_ascii=False)
        os.replace(tmp_variant, variant_file)
    except Exception as e:
        tqdm.write(f"[{country}] Error writing variant URLs to file: {e}")

    tqdm.write(f"[{country}] Completed {gender}/{category}: {processed_variants} variants saved and variant URLs logged.")
    return processed_variants

# ----------------- Orchestration -----------------
def scrape_country_products(country):
    product_file = os.path.join(country, "data", today, "Item_urls", "unique_product_url.json")
    if not os.path.exists(product_file):
        print(f"[{country}] No unique_product_url.json found → {product_file}")
        return

    with open(product_file, "r", encoding="utf-8") as f:
        product_urls = json.load(f)

    for gender, categories in product_urls.items():
        for category, urls in categories.items():
            if not urls:
                continue

            print(f"\n[{country}] Starting {gender}/{category} → {len(urls)} products")

            thread_count = 3
            url_chunks = [urls[i::thread_count] for i in range(thread_count)]

            worker = partial(scrape_worker, country, gender, category)

            with ThreadPool(processes=thread_count) as pool:
                results = pool.imap(worker, url_chunks)
                list(tqdm(results, total=len(url_chunks), desc=f"[{country}] Threads", unit="chunk"))

    print(f"\n[{country}] All categories completed.")

def main():
    try:
        set_start_method("spawn")
    except RuntimeError:
        pass

    max_processes = min(cpu_count(), len(countries))
    print(f"Starting main scrape process with {max_processes} country processes.")

    with Pool(processes=max_processes) as pool:
        list(tqdm(pool.imap(scrape_country_products, countries), total=len(countries), desc="Overall Progress", unit="country"))

if __name__ == "__main__":
    main()
