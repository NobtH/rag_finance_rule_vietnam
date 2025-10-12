import pdfplumber
from typing import List, Tuple, Optional
from remove_header_footer_func import *
import camelot
import textwrap

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

def format_table_as_markdown(table_data: List[List[str]], table_name: str = "", max_col_width: int = 45) -> str:
    processed = _process_and_fill_table(table_data)
    if not processed:
        return ""
    headers, filled_rows = processed

    matrix = [headers] + filled_rows

    # Bọc text theo max_col_width
    wrapped_matrix = []
    for row in matrix:
        wrapped_row = []
        for cell in row:
            text = str(cell) if cell is not None else ""
            wrapped = textwrap.wrap(text, width=max_col_width) or [""]
            wrapped_row.append(wrapped)
        wrapped_matrix.append(wrapped_row)

    # Tính độ rộng tối đa từng cột sau khi wrap
    col_widths = [
        max(max(len(line) for line in cell) for cell in col)
        for col in zip(*wrapped_matrix)
    ]

    def format_row(row_wrapped):
        # Tìm số dòng cao nhất trong row
        max_lines = max(len(cell) for cell in row_wrapped)
        lines = []
        for line_idx in range(max_lines):
            line_cells = []
            for col_idx, cell in enumerate(row_wrapped):
                if line_idx < len(cell):
                    line_cells.append(cell[line_idx].ljust(col_widths[col_idx]))
                else:
                    line_cells.append("".ljust(col_widths[col_idx]))
            lines.append("| " + " | ".join(line_cells) + " |")
        return "\n".join(lines)

    header_line = format_row(wrapped_matrix[0])
    separator_line = "| " + " | ".join("-" * col_widths[i] for i in range(len(headers))) + " |"
    data_lines = [format_row(row) for row in wrapped_matrix[1:]]

    table_title = f"**{table_name}**\n\n" if table_name else ""
    return table_title + "\n".join([header_line, separator_line] + data_lines)

def get_table_bbox_from_camelot(table) -> Tuple[float, float, float, float]:
    """
    Trích xuất bbox từ Camelot table object.
    Returns: (x0, y0, x1, y1) - tọa độ bbox của bảng
    """
    try:
        # Camelot table có thuộc tính _bbox hoặc tương tự
        if hasattr(table, '_bbox'):
            return table._bbox
        elif hasattr(table, 'bbox'):
            return table.bbox
        else:
            # Fallback: tính từ parsing_report nếu có
            if hasattr(table, 'parsing_report') and 'table_bbox' in table.parsing_report:
                bbox = table.parsing_report['table_bbox']
                return (bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2'])
            else:
                # Nếu không có bbox, return None để skip
                return None
    except Exception:
        return None

def extract_text_outside_tables(page, tables_bbox: List[Tuple[float, float, float, float]]) -> str:
    """
    Trích xuất text ngoài vùng bảng dựa trên bbox.
    """
    if not tables_bbox:
        return page.extract_text(layout=True) or ""
    
    # Lấy tất cả text objects từ page
    try:
        chars = page.chars
        filtered_chars = []
        
        for char in chars:
            char_x = (char['x0'] + char['x1']) / 2
            char_y = (char['y0'] + char['y1']) / 2
            
            # Kiểm tra xem char có nằm trong bbox nào không
            is_in_table = False
            for x0, y0, x1, y1 in tables_bbox:
                if x0 <= char_x <= x1 and y0 <= char_y <= y1:
                    is_in_table = True
                    break
            
            if not is_in_table:
                filtered_chars.append(char)
        
        # Tạo page object mới với chars đã filtered
        if filtered_chars:
            # Sắp xếp chars theo vị trí để tạo text có thứ tự
            filtered_chars.sort(key=lambda c: (-c['y0'], c['x0']))
            
            # Tạo text từ filtered chars (đơn giản)
            text_lines = []
            current_line = []
            current_y = None
            
            for char in filtered_chars:
                if current_y is None or abs(char['y0'] - current_y) > 2:  # New line
                    if current_line:
                        text_lines.append(''.join(current_line))
                    current_line = [char['text']]
                    current_y = char['y0']
                else:
                    current_line.append(char['text'])
            
            if current_line:
                text_lines.append(''.join(current_line))
            
            return '\n'.join(text_lines)
        else:
            return ""
            
    except Exception as e:
        # Fallback về phương pháp cũ nếu có lỗi
        print(f"Warning: Error in bbox-based extraction, falling back: {e}")
        return page.extract_text(layout=True) or ""

def replace_table_with_markdown_bbox(page, camelot_tables: List, markdown_tables: List[str]) -> str:
    """
    Thay thế bảng bằng Markdown dựa trên bbox của Camelot tables.
    """
    if not camelot_tables:
        return page.extract_text(layout=True) or ""
    
    # Lấy bbox của tất cả bảng
    tables_bbox = []
    for table in camelot_tables:
        bbox = get_table_bbox_from_camelot(table)
        if bbox:
            tables_bbox.append(bbox)
    
    # Trích xuất text ngoài vùng bảng
    text_outside_tables = extract_text_outside_tables(page, tables_bbox)
    
    # Tìm vị trí tốt nhất để chèn bảng
    result_parts = [text_outside_tables]
    
    # Sắp xếp bảng theo vị trí từ trên xuống dưới
    if tables_bbox:
        sorted_indices = sorted(range(len(tables_bbox)), 
                              key=lambda i: -tables_bbox[i][1])  # Sắp xếp theo y coordinate (top to bottom)
        
        # Chèn bảng theo thứ tự
        for i in sorted_indices:
            if i < len(markdown_tables):
                result_parts.append(f"\n\n{markdown_tables[i]}\n\n")
    else:
        # Nếu không có bbox, chèn tất cả bảng cuối trang
        for markdown_table in markdown_tables:
            result_parts.append(f"\n\n{markdown_table}\n\n")
    
    return ''.join(result_parts)

def smart_table_integration(page, camelot_tables: List, markdown_tables: List[str]) -> str:
    """
    Tích hợp thông minh bảng vào text, kết hợp nhiều phương pháp.
    """
    if not camelot_tables or not markdown_tables:
        return page.extract_text(layout=True) or ""
    
    try:
        # Phương pháp 1: Dựa trên bbox (ưu tiên)
        result = replace_table_with_markdown_bbox(page, camelot_tables, markdown_tables)
        
        # Kiểm tra kết quả có hợp lý không
        if len(result.strip()) > 0:
            print('!!!!! Đã thay bảng bằng bbox')
            return result
            
    except Exception as e:
        print(f"Warning: Bbox method failed: {e}")
    
    # Phương pháp 2: Fallback - chèn bảng dựa trên vị trí text gần nhất
    try:
        page_text = page.extract_text(layout=True) or ""
        
        for i, (table, markdown_table) in enumerate(zip(camelot_tables, markdown_tables)):
            # Lấy một số cell đầu tiên của bảng để tìm vị trí
            if table.data and len(table.data) > 0:
                search_text = ' '.join([cell for cell in table.data[0] if cell and cell.strip()])[:50]
                
                if search_text and search_text in page_text:
                    # Thay thế text gần nhất
                    page_text = page_text.replace(search_text, f"\n\n{markdown_table}\n\n", 1)
        

        return page_text
        
    except Exception as e:
        print(f"Warning: Text-based method failed: {e}")
    
    # Phương pháp 3: Cuối cùng - chèn tất cả bảng cuối trang
    page_text = page.extract_text(layout=True) or ""

    print('!!!! Không phát hiện vị trí bảng, chèn xuống cuối bảng')

    for markdown_table in markdown_tables:
        page_text += f"\n\n{markdown_table}\n\n"
    
    return page_text

# ======================
# HÀM CHÍNH
# ======================

def extract_content_in_order(pdf_path: str, k_lines: int = 5, sim_threshold: float = 0.9, min_ratio: float = 0.6) -> str:
    """
    Trích xuất nội dung từ PDF, thay thế khu vực bảng bằng nội dung Markdown,
    rồi xoá header/footer lặp (bỏ qua dòng trống).
    """
    per_page_text = []

    # 1. Chạy Camelot một lần cho toàn bộ file
    all_tables = camelot.read_pdf(pdf_path, pages="all", flavor="lattice")

    # 2. Gom bảng theo số trang
    tables_by_page = {}
    for tbl in all_tables:
        tables_by_page.setdefault(tbl.page, []).append(tbl)

    with pdfplumber.open(pdf_path) as pdf:
        num_pages = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, 1):
            
            # 3. Lấy bảng của trang hiện tại
            page_tables = tables_by_page.get(page_num, [])
            
            if page_tables:
                print(f"Phát hiện bảng trên file {pdf_path} trang {page_num}")
                # Tạo markdown cho tất cả bảng trên trang
                markdown_tables = []
                for i, table in enumerate(page_tables):
                    tbl_name = f'Bảng {i+1}' if len(page_tables) > 1 else ''
                    table_data = table.data
                    full_table_content = format_table_as_markdown(table_data, tbl_name)
                    markdown_tables.append(full_table_content)
                
                # Sử dụng phương pháp tích hợp thông minh
                page_text = smart_table_integration(page, page_tables, markdown_tables)
            else:
                # Không có bảng, chỉ lấy text thông thường
                page_text = page.extract_text(layout=True) or ""

            per_page_text.append(page_text)

    # 4. Xoá header/footer lặp
    if num_pages > 1:
        cleaned_pages = remove_headers_and_footers_v2(
            per_page_text, num_pages=num_pages, max_check_lines=k_lines,
            sim_threshold=sim_threshold, min_ratio=min_ratio
        )
    else:
        cleaned_pages = per_page_text

    # 5. Ghép và nén dòng trống lần cuối
    final_text = squeeze_blank_lines("\n\n".join(cleaned_pages))
    return final_text

# ======================
# DEMO
# ======================
if __name__ == "__main__":
    # pdf_file_path = r"data/raw documents/Thẻ/Thẻ/Tín dụng/Quyen_loi_bao_hiem_the_cao_cap.pdf"
    # pdf_file_path = r"data/raw documents/Thẻ/Thẻ/Tín dụng/Visa Infinitie/Dkdk-Nghi-duong.pdf"
    # pdf_file_path = r"data/raw documents/Thẻ/Thẻ/Tín dụng/Sacombank Visa Signature/Sacombank_DKDK_Tich_dam_bay.pdf"
    pdf_file_path = r"/tmp/pdf_clean_i07n1_n1/Sacombank_QDPhongChoThuongGiaSanBayNoiDia.pdf"
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