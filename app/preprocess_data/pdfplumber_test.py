import pdfplumber
import camelot
import re

import re

# Các regex "bắt buộc xuống dòng"
force_newline_patterns = [
    r'^\s*(\d+)\s*\.\s*$',                   # số thứ tự: "1."
    r'^\s*(\d+)\.\s*(.+)',                   # "1. Nội dung"
    r'^Điều\s+\d+(\.|:)',                    # "Điều 5."
    r'^\s*(?=[LXVI]+\b)[LXVI]+\s*[\.:]',     # Số La Mã: "I.", "II:"
    r'^Mục\s+\d+(\.|:)',                     # "Mục 1."
    r'^[a-zA-Z]\s*\d*\s*[.):,]'               # A. a.
]

compiled_patterns = [re.compile(p, re.IGNORECASE) for p in force_newline_patterns]
def force_newline(line: str) -> bool:
    return any(p.match(line) for p in compiled_patterns)

def merge_lines(text: str) -> str:
    lines = text.splitlines()
    merged, buffer = [], ""
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Nếu dòng bắt đầu bằng "#" thì giữ nguyên, không merge
        if line.startswith("#"):
            if buffer:
                merged.append(buffer + '  ')
                buffer = ""
            merged.append(line)
            continue

        if line.startswith("-"):
            if buffer:
                merged.append(buffer + '  ')
            buffer = line
            continue
        if buffer:
            if force_newline(line):  
                merged.append(buffer + '  ')
                buffer = line
            elif not re.search(r'[.!?;:=]$', buffer):
                buffer += " " + line
            else:
                merged.append(buffer + '  ')
                buffer = line
        else:
            buffer = line
    
    if buffer:
        merged.append(buffer + '  ')
    
    return "\n".join(merged)
        
pdf_path = "data/test_data/Các chương trình khuyến mãi.pdf"

full_text = []
with pdfplumber.open(pdf_path) as pdf:
    for page_number, page in enumerate(pdf.pages[0:2], start=1):
        # Lấy text của trang
        page_text = page.extract_text()
        page_text = merge_lines(page_text)
        if page_text:
            print("Page Text:\n", page_text)
        full_text.append(page_text)

        # Lấy bảng bằng Camelot
        # print('*'*100)
        # tables = camelot.read_pdf(pdf_path, pages=str(page_number), flavor="lattice")
        # for i, table in enumerate(tables):
        #     print(table.data)
            
        print('*'*100)

with open('app/preprocess_data/test.md', "w", encoding="utf-8") as f:
    f.write('\n'.join(full_text))

        