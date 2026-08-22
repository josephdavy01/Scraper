import json
import os
from pathlib import Path
from datetime import date
from tempfile import NamedTemporaryFile

ROOT_FOLDER = "India/Data"
OUTPUT_FILE = "product_id_map.json"

def load_json(p: Path):
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None

def save_json_atomic(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(path.parent)) as tf:
        json.dump(obj, tf, ensure_ascii=False, indent=2)
        tmp = tf.name
    Path(tmp).replace(path)

def extract_records(data):
    if isinstance(data, dict):
        if "products" in data and isinstance(data["products"], list):
            return data["products"]
        if "product" in data:
            p = data["product"]
            return [p] if isinstance(p, dict) else p
        return [data]
    elif isinstance(data, list):
        return data
    return []

def normalize_type(t):
    if not t:
        return ""
    return str(t).strip()

def main():
    today_str = date.today().isoformat()
    today_str = '2025-10-29'
    json_base = Path(ROOT_FOLDER) / today_str / "Json_data"
    if not json_base.exists():
        print(f"ERROR: Folder not found: {json_base}")
        return
    out_path = Path(OUTPUT_FILE)
    existing_map = load_json(out_path)
    if not isinstance(existing_map, dict):
        existing_map = {}
    used_ids = set(existing_map.values())
    def next_id():
        if not used_ids:
            return "000001"
        max_id = max(int(x) for x in used_ids)
        return str(max_id + 1).zfill(6)
    new_added = []
    for dirpath, _, files in os.walk(json_base):
        for fname in files:
            if not fname.lower().endswith(".json"):
                continue
            f = Path(dirpath) / fname
            data = load_json(f)
            if data is None:
                continue
            for rec in extract_records(data):
                if not isinstance(rec, dict):
                    continue
                t = normalize_type(rec.get("type"))
                if not t:
                    continue
                if t not in existing_map:
                    nid = next_id()
                    existing_map[t] = nid
                    used_ids.add(nid)
                    new_added.append((t, nid))
    save_json_atomic(out_path, existing_map)
    print(f"Updated {out_path}:")
    print(f"- Total types: {len(existing_map)}")
    print(f"- New types added: {len(new_added)}")
    for t, i in new_added:
        print(f"  + {t} → {i}")

if __name__ == "__main__":
    main()
