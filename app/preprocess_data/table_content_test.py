import fitz  # PyMuPDF

pdf_path = "data/raw documents/Cài đặt/HDSD_Sacombank_Pay.pdf"
doc = fitz.open(pdf_path)

toc = doc.get_toc()  # trả về list: [level, title, page]
for level, title, page in toc:
    indent = "  " * (level - 1)
    print(f"{indent}- {title} (trang {page})")
