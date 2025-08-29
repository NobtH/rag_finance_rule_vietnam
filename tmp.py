import json
import csv
import string

def normalize(text: str) -> str:
    """Xóa khoảng trắng, dấu câu, lowercase để so khớp heading."""
    if not text:
        return ""
    # loại bỏ dấu câu
    table = str.maketrans("", "", string.punctuation)
    text = text.translate(table)
    # bỏ khoảng trắng và lowercase
    return text.replace(" ", "").strip().lower()

# ---- 1. Load JSON ----
with open("data/markdown/all_data.json", "r", encoding="utf-8") as f:
    datas = json.load(f)

# Chuyển JSON thành dict {heading chuẩn hóa : context}
lookup = {}
for d in datas:
    heading_raw = d["metadata"]["heading"]
    heading_key = normalize(heading_raw)
    context = heading_raw + "\n" + d["text"]
    lookup[heading_key] = context

# ---- 2. Đọc CSV gốc ----
csv_file = "data/Chatbot-DataCSCN.csv"
rows = []

with open(csv_file, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames

    # nếu chưa có cột Context thì thêm vào
    if "Context" not in fieldnames:
        fieldnames.append("Context")

    for row in reader:
        h = row.get("Heading", "")
        key = normalize(h)
        if key in lookup:
            row["Context"] = lookup[key]   # thêm/ghi đè context
        rows.append(row)

# ---- 3. Ghi đè lại file CSV gốc ----
with open(csv_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print("✅ File CSV đã được cập nhật thêm cột Context (so khớp bỏ dấu câu).")
