import json
import os
from pathlib import Path
from datetime import date
from tempfile import NamedTemporaryFile
from typing import Any

# -------------------------
# CONFIG (edit if needed)
# -------------------------
ROOT_FOLDER = "India/Data"
COLOR_MAP_FILE = "color_id_map.json"
# -------------------------

def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def save_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(path.parent)) as tf:
        json.dump(obj, tf, ensure_ascii=False, indent=2)
        tmp = tf.name
    Path(tmp).replace(path)

def extract_records(data: Any):
    # product dict, list of products, or wrappers
    if isinstance(data, dict):
        if "products" in data and isinstance(data["products"], list):
            return data["products"]
        if "product" in data:
            prod = data["product"]
            return [prod] if isinstance(prod, dict) else prod
        return [data]
    elif isinstance(data, list):
        return data
    return []

def normalize_color(val) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    return s

def next_id_for(used_ids_set):
    if not used_ids_set:
        return "001"
    max_id = max(int(x) for x in used_ids_set)
    return str(max_id + 1).zfill(3)

def is_gift_card_title(title):
    if not title:
        return False
    return "gift card" in str(title).lower()

def main():
    today_str = date.today().isoformat()
    # today_str = '2025-11-17'
    json_base = Path(ROOT_FOLDER) / today_str / "Json_data"

    if not json_base.exists():
        print(f"ERROR: folder not found: {json_base}")
        return

    map_path = Path(COLOR_MAP_FILE)
    existing_map = load_json(map_path)
    if not isinstance(existing_map, dict):
        existing_map = {}

    used_ids = set(existing_map.values())
    added = []

    # Walk files
    for dirpath, _, filenames in os.walk(json_base):
        for fname in filenames:
            if not fname.lower().endswith(".json"):
                continue
            file_path = Path(dirpath) / fname
            data = load_json(file_path)
            if data is None:
                continue

            for rec in extract_records(data):
                if not isinstance(rec, dict):
                    continue

                title = rec.get("title")
                # NEW: skip products whose title contains "gift card"
                if is_gift_card_title(title):
                    continue

                # variants may be missing or not a list
                variants = rec.get("variants")
                if not isinstance(variants, list):
                    # sometimes product-level variant info not present - skip
                    continue

                for v in variants:
                    if not isinstance(v, dict):
                        continue
                    color_raw = v.get("option1")
                    color = normalize_color(color_raw)
                    if not color:
                        continue

                    # If not present, assign next id
                    if color not in existing_map:
                        nid = next_id_for(used_ids)
                        existing_map[color] = nid
                        used_ids.add(nid)
                        added.append((color, nid))

    # Save map
    save_json_atomic(map_path, existing_map)

    print(f"Saved {len(existing_map)} colors to {map_path} (added {len(added)} new).")
    if added:
        print("New colors added:")
        for c, i in added:
            print(f"  {i} -> {c}")

if __name__ == "__main__":
    main()
