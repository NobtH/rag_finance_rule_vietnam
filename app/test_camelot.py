import re
import camelot

def clean_text(s: str) -> str:
    if not isinstance(s, str):
        return s
    
    # Thay thế nhiều khoảng trắng thành một khoảng trắng
    s = re.sub(r"\s+", " ", s)
    
    # Xóa khoảng trắng giữa các ký tự tiếng Việt
    # Biểu thức này khớp một chữ cái tiếng Việt (có dấu hoặc không dấu),
    # theo sau là một hoặc nhiều khoảng trắng, và tiếp tục là một chữ cái tiếng Việt khác.
    s = re.sub(r"([a-zA-Zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữýỳỵỷỹđ])\s+(?=[a-zA-Zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữýỳỵỷỹđ])", r"\1", s)
    
    return s.strip()

def extract_clean_tables(pdf_file):
    tables = camelot.read_pdf(pdf_file, pages="all", flavor="lattice")
    clean_tables = []
    for table in tables:
        df = table.df.applymap(clean_text)
        clean_tables.append(df)
    return clean_tables

# ---- Dùng thử ----
pdf_file = "data/raw documents/Tiết kiệm/LÃI SUẤT HUY ĐỘNG - KHÁCH HÀNG CÁ NHÂN.pdf"
tables = extract_clean_tables(pdf_file)

for i, df in enumerate(tables, start=1):
    print(f"\n=== Bảng {i} ===")
    print(df)
