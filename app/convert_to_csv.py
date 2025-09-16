import json
import csv

# Mở file JSON
with open("data/markdown/all_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)   # data là list

rows = []
for item in data:
    rows.append({
        "original_filename": item["metadata"]["original_filename"],
        "heading": item["metadata"]["heading"],
        "is_title": item["metadata"]["is_title"],
        "text": item["text"],
    })

# Ghi ra CSV
with open("data.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
