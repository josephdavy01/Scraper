import pandas as pd
import re
import json

df = pd.read_csv("kids_baby_sizes.csv")
size_map = {}
for size_name in df["size_name"].dropna():
    size_name = str(size_name).strip()
    match = re.search(r'\(([^)]+)\)', size_name)
    if match:
        key = match.group(1)  
        size_map.setdefault(key, []).append(size_name)

def sort_key(k):
    num_match = re.search(r'\d+', k)
    return int(num_match.group()) if num_match else k
sorted_map = dict(sorted(size_map.items(), key=lambda x: sort_key(x[0])))
with open("size_mapping_raw.json", "w", encoding="utf-8") as f:
    json.dump(sorted_map, f, indent=4, ensure_ascii=False)
print(f"Size mapping saved to 'size_mapping_raw.json' ({len(sorted_map)} groups)")
