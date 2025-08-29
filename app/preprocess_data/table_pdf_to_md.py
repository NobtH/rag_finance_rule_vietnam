import re
import pdfplumber
from typing import List, Tuple, Optional
from difflib import SequenceMatcher

# chuẩn hoá & so khớp

def normalize_line(s: str) -> str:
    """Chuẩn hoá 1 dòng: strip + gộp khoảng trắng liên tiếp."""
    if s is None:
        return ""
    return re.sub(r"\s+", " ", s.strip())

def similar(a: str, b: str) -> float:
    """Tính độ tương đồng giữa 2 chuỗi (0..1)."""
    a = normalize_line(a)
    b = normalize_line(b)
    return SequenceMatcher(None, a, b).ratio()

def first_k_nonempty(lines: List[str], k: int) -> List[str]:
    """Lấy k dòng đầu KHÔNG TRỐNG (đã normalize)."""
    out = []
    for ln in lines:
        n = normalize_line(ln)
        if n:
            out.append(n)
            if len(out) == k:
                break
    return out

def last_k_nonempty(lines: List[str], k: int) -> List[str]:
    """Lấy k dòng cuối KHÔNG TRỐNG (đã normalize)."""
    out = []
    for ln in reversed(lines):
        n = normalize_line(ln)
        if n:
            out.append(n)
            if len(out) == k:
                break
    return list(reversed(out))

def choose_consensus(candidates: List[str], threshold: float = 0.8, min_ratio: float = 0.6) -> str:
    """
    Chọn chuỗi 'consensus' có nhiều trang ủng hộ nhất (similar >= threshold).
    Cần >= max(2, ceil(min_ratio * số trang)) phiếu để được chấp nhận.
    """
    n = len(candidates)
    need = max(2, int(n * min_ratio + 0.999))
    best = ""
    best_support = 0
    for i, c in enumerate(candidates):
        if not c:
            continue
        support = sum(1 for x in candidates if x and similar(c, x) >= threshold)
        if support > best_support:
            best_support = support
            best = c
    return best if best_support >= need else ""

def remove_top_candidate(lines: List[str], candidate_lines: List[str], k: int, threshold: float) -> List[str]:
    """
    Xoá k dòng đầu KHÔNG TRỐNG nếu giống candidate (>= threshold).
    Bảo toàn vị trí các dòng TRỐNG.
    """
    if not candidate_lines:
        return lines

    # Lấy index của k dòng không trống đầu tiên
    nonempty_idx = []
    for idx, ln in enumerate(lines):
        if normalize_line(ln):
            nonempty_idx.append(idx)
            if len(nonempty_idx) == k:
                break

    if not nonempty_idx:
        return lines

    got = [normalize_line(lines[i]) for i in nonempty_idx]
    if similar("\n".join(got), "\n".join(candidate_lines)) >= threshold:
        # Xoá đúng các dòng không trống đó
        to_delete = set(nonempty_idx)
        return [ln for i, ln in enumerate(lines) if i not in to_delete]
    return lines

def remove_bottom_candidate(lines: List[str], candidate_lines: List[str], k: int, threshold: float) -> List[str]:
    """
    Xoá k dòng cuối KHÔNG TRỐNG nếu giống candidate (>= threshold).
    Bảo toàn vị trí các dòng TRỐNG.
    """
    if not candidate_lines:
        return lines

    # Lấy index của k dòng không trống cuối cùng
    nonempty_idx = []
    for idx in range(len(lines) - 1, -1, -1):
        if normalize_line(lines[idx]):
            nonempty_idx.append(idx)
            if len(nonempty_idx) == k:
                break
    nonempty_idx.reverse()

    if not nonempty_idx:
        return lines

    got = [normalize_line(lines[i]) for i in nonempty_idx]
    if similar("\n".join(got), "\n".join(candidate_lines)) >= threshold:
        to_delete = set(nonempty_idx)
        return [ln for i, ln in enumerate(lines) if i not in to_delete]
    return lines

def squeeze_blank_lines(text: str) -> str:
    """Loại bỏ tất cả dòng trống hoàn toàn."""
    out_lines = []
    for ln in text.splitlines():
        if ln.strip():  # chỉ giữ dòng có nội dung
            out_lines.append(ln.rstrip())
    return "\n".join(out_lines).strip()

def remove_headers_and_footers(pages_text: List[str], k_lines: int = 3, sim_threshold: float = 0.8, min_ratio: float = 0.4) -> List[str]:
    """
    Xoá header/footer lặp giữa các trang, bỏ qua dòng TRỐNG, so sánh fuzzy.
    - k_lines: số dòng KHÔNG TRỐNG ở đầu/cuối để xét.
    - sim_threshold: ngưỡng tương đồng.
    - min_ratio: tỉ lệ trang tối thiểu đồng thuận để coi là header/footer chung.
    """
    # Chuẩn bị lines theo từng trang (giữ nguyên dòng trống để bảo toàn layout)
    pages_lines = [txt.splitlines() for txt in pages_text]

    # Thu thập candidate (dạng string đã join)
    head_cands = []
    foot_cands = []
    for lines in pages_lines:
        head = first_k_nonempty(lines, k_lines)
        foot = last_k_nonempty(lines, k_lines)
        head_cands.append("\n".join(head))
        foot_cands.append("\n".join(foot))

    # Chọn consensus theo đa số
    common_head = choose_consensus(head_cands, threshold=sim_threshold, min_ratio=min_ratio)
    common_foot = choose_consensus(foot_cands, threshold=sim_threshold, min_ratio=min_ratio)

    # Xoá
    cleaned_pages = []
    head_list = common_head.split("\n") if common_head else []
    foot_list = common_foot.split("\n") if common_foot else []

    for lines in pages_lines:
        new_lines = lines[:]
        if head_list:
            new_lines = remove_top_candidate(new_lines, head_list, k_lines, sim_threshold)
        if foot_list:
            new_lines = remove_bottom_candidate(new_lines, foot_list, k_lines, sim_threshold)
        cleaned_pages.append("\n".join(new_lines))

    # Dọn loãng dòng trống để tránh ảnh hưởng về sau
    return [squeeze_blank_lines(t) for t in cleaned_pages]


# XỬ LÝ BẢNG
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


# ======================
# HÀM CHÍNH
# ======================
def extract_content_in_order(pdf_path: str, k_lines: int = 3, sim_threshold: float = 0.8, min_ratio: float = 0.6) -> str:
    """
    Trích xuất nội dung từ PDF, thay thế khu vực bảng bằng nội dung đã xử lý,
    rồi xoá header/footer lặp (bỏ qua dòng trống) theo fuzzy-matching.
    """
    per_page_text = []

    with pdfplumber.open(pdf_path) as pdf:
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
                tbl_name = f"Bảng {i+1} trên trang {page_num}"
                table_data = table.extract()
                structured_table = format_table_as_structured_text(table_data, tbl_name)
                natural_summary = generate_natural_language_summary(table_data, tbl_name)
                full_table_content = f"{structured_table}\n\n{natural_summary}"

                # Văn bản gốc trong khu vực bảng (để replace)
                table_text_region = page.crop(table.bbox).extract_text(layout=True) or ""
                if table_text_region:
                    page_text = page_text.replace(table_text_region, full_table_content, 1)
                else:
                    # fallback: nếu không trích được text ở bbox, chèn thêm khối bảng ở cuối trang
                    page_text = f"{page_text.rstrip()}\n\n{full_table_content}\n"

            per_page_text.append(page_text)

    # Xoá header/footer lặp (bỏ qua dòng trống)
    cleaned_pages = remove_headers_and_footers(
        per_page_text, k_lines=k_lines, sim_threshold=sim_threshold, min_ratio=min_ratio
    )
    # print(cleaned_pages)

    # Ghép và nén dòng trống lần cuối
    final_text = squeeze_blank_lines("\n\n".join(cleaned_pages))
    return final_text


# ======================
# DEMO
# ======================
if __name__ == "__main__":
    pdf_file_path = r"data/raw documents/Thẻ/Thẻ/Tín dụng/Platinum American Express/DANH SACH MCC HOAN TIEN 1.pdf"
    try:
        extracted_content = extract_content_in_order(pdf_file_path, k_lines=3, sim_threshold=0.7, min_ratio=0.6)
        print(extracted_content)

        with open("extracted_content_advanced.md", "w", encoding="utf-8") as f:
            f.write(extracted_content)
        print("\n\nNội dung đã được trích xuất và lưu vào file 'extracted_content_advanced.md'")

    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file '{pdf_file_path}'.")
    except Exception as e:
        print(f"Đã xảy ra lỗi: {e}")
