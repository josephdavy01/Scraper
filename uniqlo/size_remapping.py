import json
import re

# Load input JSON
with open("size_mapping_raw.json", "r", encoding="utf-8") as f:
    size_map = json.load(f)

SPECIAL_CASES = {
    "108": ["4y"]
}

def extract_age_values(text):
    txt = text.lower().strip()
    # Check for ranges like 3–6m or 3-6 years
    m = re.search(r'(\d{1,2})\s*[–\-]\s*(\d{1,2})\s*(months?|m)\b', txt)
    if m:
        return [f"{m.group(1)}m", f"{m.group(2)}m"]
    m = re.search(r'(\d{1,2})\s*[–\-]\s*(\d{1,2})\s*(years?|y)\b', txt)
    if m:
        return [f"{m.group(1)}y", f"{m.group(2)}y"]
    # Single values like 3m, 3y, 3 years
    m = re.search(r'(\d{1,2})\s*(months?|m)\b', txt)
    if m:
        return [f"{m.group(1)}m"]
    m = re.search(r'(\d{1,2})\s*(years?|y)\b', txt)
    if m:
        return [f"{m.group(1)}y"]
    # Nothing matched
    return []
remapped = {}
for key, labels in size_map.items():
    if key in SPECIAL_CASES:
        remapped[key] = SPECIAL_CASES[key]
        continue
    result = []
    for label in labels:
        if any(x in label.lower() for x in ["year", "month", "y", "m"]):
            result.extend(extract_age_values(label))
    # Clean and remove duplicates
    clean = sorted(set(result), key=lambda x: (x[-1], int(re.findall(r'\d+', x)[0])))
    # If nothing found, skip or leave empty
    if clean:
        remapped[key] = clean
with open("remapped_size.json", "w", encoding="utf-8") as f:
    json.dump(remapped, f, indent=4, ensure_ascii=False)
print("remapped_size.json created successfully")
