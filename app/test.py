# import pytesseract
# from pdf2image import convert_from_path

# images = convert_from_path('data/raw documents/Thẻ/Thẻ/Tín dụng/Platinum American Express/DANH SACH MCC HOAN TIEN 1.pdf')
# for image in images:
#     text = pytesseract.image_to_string(image, lang='vie')
#     print(text)       

# import pdfplumber

# with pdfplumber.open("data/raw documents/Thẻ/Thẻ/Tín dụng/Visa Infinitie/Dkdk-Nghi-duong.pdf") as pdf:
#     for page in pdf.pages:
#         tables = page.find_tables(table_settings={
#             "vertical_strategy": "lines",
#             "horizontal_strategy": "lines",
#             "snap_tolerance": 4,
#         })
#         for i, table in enumerate(tables, 1):
#             print(f"\n--- Trang {page.page_number}, Bảng {i} ---")
#             print(table.extract())

# extract_tables("data/raw documents/Thẻ/Thẻ/Tín dụng/Visa Infinitie/Dkdk-Nghi-duong.pdf")

import fitz

def get_top_lines(pdf_path, top_n=20):
    doc = fitz.open(pdf_path)
    lines_info = []

    for page_num, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    # Gộp text trong 1 dòng
                    text_line = " ".join(s["text"] for s in l["spans"]).strip()
                    if not text_line:
                        continue
                    # Lấy span lớn nhất trong dòng (thường là size chính)
                    max_size = max(s["size"] for s in l["spans"])
                    font_names = [s["font"] for s in l["spans"]]
                    flags = [s["flags"] for s in l["spans"]]
                    lines_info.append({
                        "page": page_num,
                        "text": text_line,
                        "size": max_size,
                        "fonts": list(set(font_names)),
                        "flags": flags
                    })

    # Sắp xếp theo size giảm dần
    lines_info.sort(key=lambda x: x["size"], reverse=True)
    return lines_info[:top_n]


# Ví dụ dùng
pdf_file = "data/raw documents/Tài khoản/Điều khoản và điều kiện mở và sử dụng tài khoản.pdf"
top_lines = get_top_lines(pdf_file, top_n=20)

for line in top_lines:
    print(f"[Page {line['page']}] size={line['size']} font={line['fonts']} flags={line['flags']}: {line['text']}")

