import fitz  # PyMuPDF

def extract_headings(pdf_path, min_font_size=14):
    headings = []
    doc = fitz.open(pdf_path)
    for page in doc:
        # Lấy danh sách các text block trên trang
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            # Lọc các khối là text
            if "lines" in block:
                for line in block["lines"]:
                    # Lấy thông tin về span (phần văn bản có cùng định dạng)
                    for span in line["spans"]:
                        # Kiểm tra kích thước phông chữ
                        if span["size"] > min_font_size:
                            text = span["text"].strip()
                            # Lọc các dòng trống hoặc chỉ có số
                            if text and not text.isdigit():
                                headings.append(text)
    doc.close()
    return headings


pdf_file = "data/raw documents/Tài khoản/Điều khoản và điều kiện mở và sử dụng tài khoản.pdf"
found_headings = extract_headings(pdf_file)
for heading in found_headings:
    print(heading)

