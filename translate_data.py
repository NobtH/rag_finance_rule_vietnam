import csv
import requests
import time
import json

API_URL = "https://api.deepseek.com/v1/chat/completions"
API_KEY = "sk-4708c0250f54425ca590a6aa9a08fc48"  # thay API key của bạn vào

def call_deepseek(question, answer):
    """Gửi request đến DeepSeek để dịch 1 dòng dữ liệu."""
    prompt = f"""
    Hãy dịch các văn bản sau sang tiếng Việt, cấu trúc trả về là JSON có định dạng sau:
    {{
        "Question": ,
        "Answer": 
    }}
    Chỉ trả về đúng JSON, không hiển thị gì khác.
    Dữ liệu cần dịch:
    {{
        "Question": "{question}",
        "Answer": "{answer}"
    }}
    """

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0
    }

    resp = requests.post(API_URL, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()

    result_text = data["choices"][0]["message"]["content"].strip()
    # Nếu model trả về có ```json ... ``` thì làm sạch
    if result_text.startswith("```"):
        result_text = result_text.strip("`").replace("json", "").strip()

    return json.loads(result_text)

def process_csv(input_file, output_file, start_row=0):
    with open(input_file, "r", encoding="utf-8") as fin, \
         open(output_file, "a", encoding="utf-8", newline="") as fout:

        reader = csv.DictReader(fin)
        fieldnames = ["Question", "Answer"]

        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        if fout.tell() == 0:  # nếu file output trống thì viết header
            writer.writeheader()

        for i, row in enumerate(reader, start=1):
            if i < start_row:   # bỏ qua các dòng đã dịch
                continue

            q, a = row.get("input", ""), row.get("output", "")

            try:
                result = call_deepseek(q, a)
                writer.writerow({
                    "Question": result.get("Question", ""),
                    "Answer": result.get("Answer", "")
                })
                print(f"OK (row {i}):", result)
            except Exception as e:
                print(f"Error at row {i}:", e)
                # fallback: ghi nguyên văn input/output
                writer.writerow({
                    "Question": q,
                    "Answer": a
                })

            time.sleep(1)  # tránh spam API


if __name__ == "__main__":
    process_csv("bank-assistant-qa.csv", "translated-bank-assistant-qa2.csv", start_row=2000)
