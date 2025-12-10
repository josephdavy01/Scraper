import json
from urllib.parse import urlparse, urlunparse

def normalize_url(url):
    """
    Remove query parameters so variant URLs are treated as the same product.
    Example:
      https://www.site.com/p/item/123.html?dwvar_123_color=001
      → https://www.site.com/p/item/123.html
    """
    parsed = urlparse(url)
    normalized = parsed._replace(query="")  # remove everything after '?'
    return urlunparse(normalized)

def process_product_urls(file_path):
    # Load JSON
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    result = {}

    for category, sections in data.items():
        result[category] = {}
        for section_name, urls in sections.items():

            # Normalize each URL (remove query params)
            normalized_urls = [normalize_url(u) for u in urls]

            # Deduplicate
            unique_urls = set(normalized_urls)

            # Save result
            result[category][section_name] = {
                "unique_count": len(unique_urls),
                "unique_urls": list(unique_urls)
            }

    return result


if __name__ == "__main__":
    input_file = "UK_product_urls.json"  # <-- change your filename here
    output = process_product_urls(input_file)

    # Print summary
    for category, sections in output.items():
        print(f"\n=== {category} ===")
        for section, info in sections.items():
            print(f"{section}: {info['unique_count']} unique products")

    # Optional: save cleaned results
    with open("cleaned_product_urls.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
        print("\nCleaned data saved to cleaned_product_urls.json")
