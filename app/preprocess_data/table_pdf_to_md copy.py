import re
import pdfplumber
from typing import List, Tuple, Optional
from difflib import SequenceMatcher
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from pypdf import PdfReader, PdfWriter
from remove_header_footer_func import *
import camelot
import textwrap


# ======================
# XỬ LÝ BẢNG
# ======================

def normalize_line(s: str) -> str:
    if not s:
        return ""
    # remove zero-width / non-breaking spaces, tabs; collapse whitespace
    s = s.replace("\u200b", "").replace("\xa0", " ").replace("\t", " ")
    s = s.strip()
    s = re.sub(r'\s+', ' ', s)
    return s

def best_match_index(target: str, candidates: list[str], min_ratio: float = 0.7):
    best_idx, best_r = None, 0.0
    for i, c in enumerate(candidates):
        r = SequenceMatcher(None, target, c).ratio()
        if r > best_r:
            best_r = r
            best_idx = i
    if best_r >= min_ratio:
        return best_idx, best_r
    return None, best_r

def replace_table_by_line_block(page_text: str, table_text_region: str, full_table_content: str,
                                min_ratio: float = 0.75, debug: bool = False) -> str:
    """
    Tìm dòng đầu & dòng cuối của table_text_region trong page_text theo dòng (normalize),
    nếu exact match fail -> thử fuzzy match, rồi thay block dòng đó bằng full_table_content.
    Trả về page_text đã thay.
    """
    page_lines = page_text.splitlines()
    table_lines = [ln for ln in table_text_region.splitlines() if ln.strip()]

    if not table_lines:
        if debug: print("table_text_region rỗng -> append ở cuối")
        return page_text.rstrip() + "\n\n" + full_table_content + "\n"

    page_norm = [normalize_line(ln) for ln in page_lines]
    table_norm = [normalize_line(ln) for ln in table_lines]

    # Tìm start index (ưu tiên exact, nếu ko thì fuzzy)
    start_idx = None
    for i, pl in enumerate(page_norm):
        if pl == table_norm[0]:
            start_idx = i
            if debug: print("Exact start at", i)
            break
    if start_idx is None:
        idx, r = best_match_index(table_norm[0], page_norm, min_ratio=min_ratio)
        if idx is not None:
            start_idx = idx
            if debug: print(f"Fuzzy start at {idx}, ratio={r:.2f}")

    if start_idx is None:
        if debug: print("Không tìm dòng bắt đầu -> fallback append")
        return page_text.rstrip() + "\n\n" + full_table_content + "\n"

    # Tìm end index: tìm last exact match of last table line **sau start_idx**
    end_idx = None
    for j in range(start_idx, len(page_norm)):
        if page_norm[j] == table_norm[-1]:
            end_idx = j  # keep last occurrence
    if end_idx is not None and debug:
        print("Exact end at", end_idx)

    # Nếu chưa tìm được, thử fuzzy trên phần page_norm[start_idx:]
    if end_idx is None:
        idx, r = best_match_index(table_norm[-1], page_norm[start_idx:], min_ratio=min_ratio)
        if idx is not None:
            end_idx = start_idx + idx
            if debug: print(f"Fuzzy end at {end_idx}, ratio={r:.2f}")

    # Nếu vẫn chưa, thử dò các dòng giữa (từ cuối table -> lên) để tìm dòng nào khớp
    if end_idx is None:
        for tline in reversed(table_norm):
            for j in range(start_idx, len(page_norm)):
                if page_norm[j] == tline:
                    end_idx = j
                    if debug: print("Found intermediate exact line as end:", j)
                    break
            if end_idx is not None:
                break
    # tiếp tục thử fuzzy cho các dòng giữa với threshold thấp hơn
    if end_idx is None:
        for tline in reversed(table_norm):
            idx, r = best_match_index(tline, page_norm[start_idx:], min_ratio=0.6)
            if idx is not None:
                end_idx = start_idx + idx
                if debug: print(f"Found intermediate fuzzy as end: {end_idx}, ratio={r:.2f}")
                break

    if end_idx is None:
        if debug: print("Không tìm được dòng kết thúc -> fallback append")
        return page_text.rstrip() + "\n\n" + full_table_content + "\n"

    # Ghép lại văn bản: giữ phần trước start, chèn bảng, giữ phần sau end
    new_lines = []
    if start_idx > 0:
        new_lines.extend(page_lines[:start_idx])
    new_lines.append(full_table_content)
    if end_idx + 1 < len(page_lines):
        new_lines.extend(page_lines[end_idx+1:])

    result = "\n".join(new_lines)
    # giữ 1 newline cuối cho consistency
    return result.rstrip() + "\n"

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

def wrap_text(cell: str, width: int = 70) -> str:
    """Xuống dòng thật trong cell nếu vượt quá width."""
    if not cell:
        return ""
    words = cell.split()
    lines, current = [], ""
    for word in words:
        if len(current) + len(word) + 1 <= width:
            current += (" " if current else "") + word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


def format_table_as_markdown(table_data: List[List[str]], table_name: str = "") -> str:
    processed = _process_and_fill_table(table_data)
    if not processed:
        return ""
    headers, filled_rows = processed

    # Áp dụng wrap cho header + data
    headers = [wrap_text(h, 70) for h in headers]
    filled_rows = [[wrap_text(cell, 70) for cell in row] for row in filled_rows]

    # Ghép header + data thành matrix
    matrix = [headers] + filled_rows

    # Tính độ rộng tối đa (chỉ trên từng dòng lớn nhất của cell)
    col_widths = [max(len(line) for row in matrix for line in str(row[c]).split("\n")) 
                  for c in range(len(headers))]

    def format_row(row):
        # Tách từng cell thành nhiều dòng -> align bằng zip_longest
        split_cells = [str(cell).split("\n") for cell in row]
        max_lines = max(len(cell) for cell in split_cells)
        lines = []
        for i in range(max_lines):
            line_parts = []
            for c, cell_lines in enumerate(split_cells):
                text = cell_lines[i] if i < len(cell_lines) else ""
                line_parts.append(text.ljust(col_widths[c]))
            lines.append("| " + " | ".join(line_parts) + " |")
        return "\n".join(lines)

    # Header + separator
    header_line = format_row(headers)
    separator_line = "| " + " | ".join("-" * col_widths[i] for i in range(len(headers))) + " |"

    # Data
    data_lines = [format_row(row) for row in filled_rows]

    table_title = f"**{table_name}**\n\n" if table_name else ""
    return table_title + "\n".join([header_line, separator_line] + data_lines)


# ======================
# HÀM CHÍNH
# ======================

def extract_content_in_order(pdf_path: str, k_lines: int = 5,
                             sim_threshold: float = 0.9, min_ratio: float = 0.8) -> str:
    """
    Trích xuất nội dung từ PDF, thay thế khu vực bảng bằng nội dung đã xử lý,
    rồi xoá header/footer lặp (bỏ qua dòng trống) theo fuzzy-matching.
    """

    per_page_text = []

    with pdfplumber.open(pdf_path) as pdf:
        num_pages = len(pdf.pages)

        for page_num, page in enumerate(pdf.pages, 1):
            # Lấy text gốc của trang
            page_text = page.extract_text(layout=True) or ""

            # Tìm bảng bằng Camelot
            tables = camelot.read_pdf(
                pdf_path,
                pages=str(page_num),
                flavor="lattice"  # hoặc "stream"
            )

            # Thay thế từng bảng trong text
            for i, table in enumerate(tables):
                tbl_name = ''  # hoặc f"Bảng {i+1} trang {page_num}"
                table_data = table.df.values.tolist()  # DataFrame -> list[list]

                # Chuyển bảng sang Markdown
                full_table_content = format_table_as_markdown(table_data, tbl_name)
                print(full_table_content)

                # Dùng chính dữ liệu table để build text_region thay vì crop(bbox)
                table_text_region = "\n".join(
                    [" ".join(row) for row in table_data if any(cell.strip() for cell in row)]
                )

                # Thay thế trong text
                page_text = replace_table_by_line_block(
                    page_text,
                    table_text_region,
                    full_table_content,
                    min_ratio=0.75,
                    debug=True
                )

            per_page_text.append(page_text)

    # Xoá header/footer lặp
    if num_pages > 1:
        cleaned_pages = remove_headers_and_footers_v2(
            per_page_text,
            num_pages=num_pages,
            max_check_lines=k_lines,
            sim_threshold=sim_threshold,
            min_ratio=min_ratio
        )
    else:
        cleaned_pages = per_page_text

    # Ghép & nén dòng trống
    final_text = squeeze_blank_lines("\n\n".join(cleaned_pages))
    return final_text


# ======================
# DEMO
# ======================
if __name__ == "__main__":
    pdf_file_path = r"data/raw documents/Thẻ/Thẻ/Tín dụng/Visa Infinitie/DKDK-am-thuc.pdf"
    try:
        extracted_content = extract_content_in_order(pdf_file_path, k_lines=5)
        print(extracted_content)

        with open("extracted_content_advanced.md", "w", encoding="utf-8") as f:
            f.write(extracted_content)
        print("\n\nNội dung đã được trích xuất và lưu vào file 'extracted_content_advanced.md'")

    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file '{pdf_file_path}'.")
    except Exception as e:
        print(f"Đã xảy ra lỗi: {e}")
