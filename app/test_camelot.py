import re
import fitz
import camelot


def clean_text(s: str) -> str:
    if not isinstance(s, str):
        return s
    
    # Gom nhiều khoảng trắng
    s = re.sub(r"\s+", " ", s)
    
    # Xóa khoảng trắng giữa ký tự tiếng Việt
    s = re.sub(
        r"([a-zA-Zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễ"
        r"ìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữ"
        r"ýỳỵỷỹđ])\s+(?=[a-zA-Zàáạảãâầấậẩẫăằắặẳẵ"
        r"èéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡ"
        r"ùúụủũưừứựửữýỳỵỷỹđ])", 
        r"\1", 
        s
    )
    
    return s.strip()


def extract_text_per_page(pdf_file: str):
    """Trích text theo từng trang"""
    doc = fitz.open(pdf_file)
    texts = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text")
        texts.append((i, text))
    doc.close()
    return texts


def extract_clean_tables_per_page(pdf_file: str):
    """Trích bảng theo từng trang"""
    tables_by_page = {}
    tables = camelot.read_pdf(pdf_file, pages="all", flavor="lattice")
    for table in tables:
        df = table.df.applymap(clean_text)
        table_str = "\n".join(["*".join(row) for row in df.values.tolist()])
        p = table.page  # camelot cho biết bảng nằm ở trang nào
        tables_by_page.setdefault(p, []).append(table_str)
    return tables_by_page


def pdf_text_and_tables(pdf_file: str) -> str:
    # Lấy text từng trang
    texts = extract_text_per_page(pdf_file)
    # Lấy bảng từng trang
    tables_by_page = extract_clean_tables_per_page(pdf_file)

    final_pages = []
    for page_num, text in texts:
        page_content = text.strip()
        if page_num in tables_by_page:
            for i, tbl in enumerate(tables_by_page[page_num], start=1):
                page_content += f"\n\n=== Bảng {page_num}.{i} ===\n{tbl}"
        final_pages.append(f"\n\n===== Trang {page_num} =====\n{page_content}")
    
    return "\n".join(final_pages)


# ---- Test thử ----
pdf_file = "data/raw documents/Tiết kiệm/LÃI SUẤT HUY ĐỘNG - KHÁCH HÀNG CÁ NHÂN.pdf"
result = pdf_text_and_tables(pdf_file)

# In ra 800 ký tự đầu tiên
print(result)
