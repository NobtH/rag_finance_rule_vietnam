import pdfplumber

def extract_tables_from_pdf(pdf_path):
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_tables = page.extract_tables()
            for table in page_tables:
                tables.append({
                    "page": page_number,
                    "table": table
                })
    return tables

# Ví dụ dùng
pdf_file = "data/raw documents/Tiết kiệm/LÃI SUẤT HUY ĐỘNG - KHÁCH HÀNG CÁ NHÂN.pdf"
tables = extract_tables_from_pdf(pdf_file)

for t in tables:
    print(f"Trang {t['page']}:")
    for row in t['table']:
        print(row)
    print("="*50)
