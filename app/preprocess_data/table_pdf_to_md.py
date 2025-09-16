import re
import pdfplumber
from typing import List, Tuple, Optional
from difflib import SequenceMatcher
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from pypdf import PdfReader, PdfWriter
import tqdm
import tempfile, os
from remove_header_footer_func import *

# ======================
# XỬ LÝ BẢNG
# ======================

def _process_and_fill_table(table_data: List[List[Optional[str]]]) -> Optional[Tuple[List[str], List[List[str]]]]:
    if not table_data:
        return None

    # 1) Clean
    clean_table = []
    for row in table_data:
        clean_row = [(cell.replace('\n', ' ').strip() if cell is not None else "") for cell in row]
        clean_table.append(clean_row)

    # 2) Ước lượng số hàng header
    header_row_count = 0
    for i, row in enumerate(clean_table):
        is_potential_sub_header = (i > 0 and not row[0] and any(cell for cell in row))
        if i > 0 and row[0] and not is_potential_sub_header:
            break
        if i == 0 or is_potential_sub_header or any(cell == "" for cell in row):
            header_row_count += 1
        else:
            break
    if header_row_count >= len(clean_table):
        header_row_count = 1 if len(clean_table) > 1 else len(clean_table)

    header_rows = clean_table[:header_row_count]
    data_rows = clean_table[header_row_count:]
    if not header_rows:
        return None

    # 3) Làm phẳng header
    processed_headers = [list(row) for row in header_rows]
    for r in range(len(processed_headers)):
        for c in range(1, len(processed_headers[r])):
            if not processed_headers[r][c]:
                processed_headers[r][c] = processed_headers[r][c - 1]

    final_header = list(processed_headers[0])
    for r in range(1, len(processed_headers)):
        for c in range(len(final_header)):
            if processed_headers[r][c] != processed_headers[r - 1][c]:
                final_header[c] = f"{final_header[c]} {processed_headers[r][c]}".strip()

    if not data_rows:
        return final_header, []

    # 4) Điền dữ liệu gộp hàng
    filled_data_rows = []
    for r, row in enumerate(data_rows):
        filled_row = list(row)
        if r > 0:
            for c, cell in enumerate(filled_row):
                if not cell:
                    filled_row[c] = filled_data_rows[r - 1][c] + '|'
        filled_data_rows.append(filled_row)

    return final_header, filled_data_rows

def format_table_as_structured_text(table_data: List[List[str]], table_name: str = "") -> str:
    processed = _process_and_fill_table(table_data)
    if not processed:
        return ""
    header, filled_rows = processed

    output = []
    table_title = f" [Tên: {table_name}]" if table_name else ""
    output.append(f"--- BẢNG BIỂU{table_title} ---")
    output.append(f"Cột: {', '.join(header)}")

    for i, row in enumerate(filled_rows, 1):
        output.append(f"Dòng {i}: {', '.join(row)}")

    output.append("--- KẾT THÚC BẢNG ---")
    return "\n".join(output)

def generate_natural_language_summary(table_data: List[List[str]], table_name: str = "") -> str:
    processed = _process_and_fill_table(table_data)
    if not processed:
        return ""
    headers, filled_rows = processed
    if not filled_rows:
        return ""

    summary_lines = []
    table_title = table_name or "bảng"
    summary_lines.append(f"--- Diễn giải thông tin từ {table_title} ---")

    for row in filled_rows:
        subject = row[0]
        if not subject:
            continue
        clauses = []
        for i in range(1, len(headers)):
            if i < len(row):
                column_header = headers[i]
                cell_value = row[i]
                if cell_value and column_header:
                    clauses.append(f"{column_header} là {cell_value}")
        if clauses:
            summary_lines.append(f"{subject}, {', '.join(clauses)}.")
    return "\n".join(summary_lines) if len(summary_lines) > 1 else ""

def format_table_as_markdown(table_data: List[List[str]], table_name: str = "") -> str:
    processed = _process_and_fill_table(table_data)
    if not processed:
        return ""
    headers, filled_rows = processed

    # Ghép header + data thành matrix
    matrix = [headers] + filled_rows

    # Tính độ rộng tối đa cho mỗi cột
    col_widths = [max(len(str(row[c])) for row in matrix) for c in range(len(headers))]

    def format_row(row):
        return "| " + " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)) + " |"

    # Header + separator
    header_line = format_row(headers)
    separator_line = "| " + " | ".join("-" * col_widths[i] for i in range(len(headers))) + " |"

    # Data
    data_lines = [format_row(row) for row in filled_rows]

    table_title = f"**{table_name}**\n\n" if table_name else ""
    return table_title + "\n".join([header_line, separator_line] + data_lines)


# ======================
# Marker
# ======================
def extract_pages_text(pdf_path: str) -> List[str]:
    """Trích xuất text của từng trang PDF thành list[str]."""
    artifact_dict = create_model_dict(device="cuda:0")
    converter = PdfConverter(artifact_dict=artifact_dict)

    reader = PdfReader(pdf_path)
    pages_text: List[str] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, page in enumerate(reader.pages):
            one_page_path = os.path.join(tmpdir, f"page_{i+1}.pdf")
            writer = PdfWriter()
            writer.add_page(page)
            with open(one_page_path, "wb") as fh:
                writer.write(fh)

            rendered = converter(one_page_path)
            text, _, _ = text_from_rendered(rendered)
            # pages_text.append(text.replace('#', '').replace('*', '').replace('<br>', '    ').strip() + '\n\n')
            pages_text.append(text.replace('####','').replace('###',''))

    return pages_text

def pdf_has_table(file_path: str) -> bool:
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            # Dùng cơ chế detect_table của pdfplumber
            tables = page.extract_tables()
            if tables and len(tables) > 0:
                return True
    return False

def extract_content_marker(pdf_path, k_lines: int = 10, sim_threshold: float = 0.8, min_ratio: float = 0.6):
    per_page_text = extract_pages_text(pdf_path)

    # cleaned_pages = remove_headers_and_footers(
    #     per_page_text, max_check_lines=k_lines, sim_threshold=sim_threshold, min_ratio=min_ratio
    # )

    # print(cleaned_pages)

    # Ghép và nén dòng trống lần cuối
    final_text = squeeze_blank_lines("\n\n".join(per_page_text))
    return final_text

# ======================
# HÀM CHÍNH
# ======================

def extract_content_in_order(pdf_path: str, k_lines: int = 5, sim_threshold: float = 0.9, min_ratio: float = 0.8) -> str:
    """
    Trích xuất nội dung từ PDF, thay thế khu vực bảng bằng nội dung đã xử lý,
    rồi xoá header/footer lặp (bỏ qua dòng trống) theo fuzzy-matching.
    """
    # if pdf_has_table(pdf_path):
    #     print('File có bảng - dùng marker')
    # per_page_text = extract_pages_text(pdf_path)
    # else:
    # print('File không có bảng')
    per_page_text = []

    with pdfplumber.open(pdf_path) as pdf:
        num_pages = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text(layout=True) or ""

            # Tìm bảng theo line-based strategies
            tables = page.find_tables(table_settings={
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "snap_tolerance": 4,
            })

            # Thay thế văn bản trong bbox của từng bảng bằng phiên bản cấu trúc + diễn giải
            for i, table in enumerate(tables):
                # tbl_name = f"Bảng {i+1} trên trang {page_num}"
                tbl_name = ''
                table_data = table.extract()
                # structured_table = format_table_as_structured_text(table_data, tbl_name)
                # natural_summary = generate_natural_language_summary(table_data, tbl_name)
                # full_table_content = f"{structured_table}\n\n{natural_summary}"

                full_table_content = format_table_as_markdown(table_data, tbl_name)

                # Văn bản gốc trong khu vực bảng (để replace)
                table_text_region = page.crop(table.bbox).extract_text(layout=True) or ""

                if table_text_region.strip():
                    page_text = page_text.strip().replace(table_text_region, full_table_content)
                else:
                    page_text = f"{page_text.rstrip()}\n\n{full_table_content}\n"

            per_page_text.append(page_text)

    # Xoá header/footer lặp (bỏ qua dòng trống)
    if num_pages > 1:
        cleaned_pages = remove_headers_and_footers_v2(
            per_page_text, num_pages=num_pages, max_check_lines=k_lines, sim_threshold=sim_threshold, min_ratio=min_ratio
        )
    else:
        cleaned_pages = per_page_text
    # print(cleaned_pages)

    # Ghép và nén dòng trống lần cuối
    final_text = squeeze_blank_lines("\n\n".join(cleaned_pages))
    return final_text


# ======================
# DEMO
# ======================
if __name__ == "__main__":
    pdf_file_path = r"data/raw documents/Thẻ/Thẻ/Tín dụng/Visa Infinitie/DKDK-am-thuc.pdf"
    try:
        extracted_content = extract_content_marker(pdf_file_path, k_lines=5)
        # print(extracted_content)

        with open("extracted_content_advanced.md", "w", encoding="utf-8") as f:
            f.write(extracted_content)
        print("\n\nNội dung đã được trích xuất và lưu vào file 'extracted_content_advanced.md'")

    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file '{pdf_file_path}'.")
    except Exception as e:
        print(f"Đã xảy ra lỗi: {e}")
