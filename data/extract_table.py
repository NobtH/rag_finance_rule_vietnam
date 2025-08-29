import fitz  # PyMuPDF
import camelot

def extract_pdf_with_camelot(pdf_path, output_txt=None, col_sep=" * "):
    """
    Đọc PDF, lấy full text bằng PyMuPDF + bảng bằng Camelot.
    Bảng sẽ được chèn vào full_text dưới dạng text có ký hiệu phân cách cột.
    
    Args:
        pdf_path (str): Đường dẫn file PDF
        output_txt (str, optional): Lưu text ra file
        col_sep (str, optional): Ký hiệu phân cách cột
    
    Returns:
        str: Full text gồm cả bảng
    """
    doc = fitz.open(pdf_path)
    all_pages_text = []

    # Dùng Camelot để trích xuất bảng
    tables = camelot.read_pdf(pdf_path, pages="all", flavor="lattice")  # thử 'lattice' trước, nếu fail thì 'stream'

    table_idx = 0
    for page_num, page in enumerate(doc, start=1):
        page_text_parts = [f"--- Trang {page_num} ---\n"]

        # Lấy text (PyMuPDF)
        text = page.get_text("text")
        if text:
            page_text_parts.append(text.strip())

        # Lấy bảng Camelot trên đúng trang
        page_tables = [t for t in tables if t.parsing_report["page"] == page_num]
        for pt in page_tables:
            df = pt.df  # dataframe
            table_lines = []
            for _, row in df.iterrows():
                row_text = col_sep.join([str(cell).strip() for cell in row])
                table_lines.append(row_text)
            table_text = "\n".join(table_lines)
            table_idx += 1
            page_text_parts.append(f"\n[Table_{table_idx}]\n{table_text}\n")

        all_pages_text.append("\n".join(page_text_parts))

    full_text = "\n".join(all_pages_text)

    # Lưu ra file nếu cần
    if output_txt:
        with open(output_txt, "w", encoding="utf-8") as f:
            f.write(full_text)
        print(f"✅ Đã lưu text + table vào {output_txt}")

    return full_text


# Ví dụ sử dụng
pdf_path = "data/raw documents/Tiết kiệm/LÃI SUẤT HUY ĐỘNG - KHÁCH HÀNG CÁ NHÂN.pdf"
full_text = extract_pdf_with_camelot(pdf_path, "output_text_camelot.txt")

print("📄 Full text (1000 ký tự đầu):")
print(full_text[:1000])
