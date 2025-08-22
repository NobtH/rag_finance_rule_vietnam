import pdfplumber
from typing import List, Tuple, Optional, Dict, Any

def _process_and_fill_table(table_data: List[List[Optional[str]]]) -> Optional[Tuple[List[str], List[List[str]]]]:
    """
    Hàm nội bộ để xử lý và điền dữ liệu cho bảng có ô gộp và header nhiều tầng.
    Đây là bộ não xử lý bảng phức tạp.
    """
    if not table_data:
        return None

    # 1. Dọn dẹp dữ liệu ban đầu: thay thế None bằng chuỗi rỗng và \n bằng dấu cách
    clean_table = []
    for row in table_data:
        # clean_row = [(cell.replace('\n', ' ').strip() if cell is not None else "") for cell in row]
        clean_row = row
        clean_table.append(clean_row)

    # 2. Heuristic để xác định số hàng header
    header_row_count = 0
    if len(clean_table) > 1:
        for i, row in enumerate(clean_table):
            is_potential_sub_header = (i > 0 and not row[0] and any(cell for cell in row))
            if i > 0 and row[0] and not is_potential_sub_header:
                break
            header_row_count += 1
    elif len(clean_table) == 1:
        header_row_count = 1

    if header_row_count >= len(clean_table) and len(clean_table) > 1:
        header_row_count = 1

    header_rows = clean_table[:header_row_count]
    data_rows = clean_table[header_row_count:]

    if not header_rows:
        return None

    # 3. Làm phẳng header (xử lý gộp cột) và kết hợp các hàng header
    processed_headers = [list(row) for row in header_rows]
    for r in range(len(processed_headers)):
        for c in range(1, len(processed_headers[r])):
            if not processed_headers[r][c] and c > 0:
                processed_headers[r][c] = processed_headers[r][c-1]
    
    final_header = list(processed_headers[0])
    for r in range(1, len(processed_headers)):
        for c in range(len(final_header)):
            if processed_headers[r][c] != processed_headers[r-1][c]:
                final_header[c] = f"{final_header[c]} {processed_headers[r][c]}".strip()

    if not data_rows:
        return final_header, []

    # 4. Điền dữ liệu cho các ô gộp hàng
    filled_data_rows = []
    for r, row in enumerate(data_rows):
        filled_row = list(row)
        if r > 0:
            for c, cell in enumerate(filled_row):
                if not cell and c < len(filled_data_rows[r-1]):
                    # Điền giá trị từ ô tương ứng của hàng đã xử lý trước đó
                    filled_row[c] = filled_data_rows[r-1][c]
        filled_data_rows.append(filled_row)

    return final_header, filled_data_rows


def format_table_as_structured_text(table_data: List[List[str]], table_name: str = "") -> str:
    """Định dạng bảng dạng cấu trúc sau khi đã được xử lý."""
    processed = _process_and_fill_table(table_data)
    if not processed:
        return ""
    header, filled_rows = processed
    
    output = [f"--- BẢNG BIỂU [Tên: {table_name}] ---" if table_name else "--- BẢNG BIỂU ---"]
    output.append(f"Cột: {', '.join(header)}")
    for i, row in enumerate(filled_rows, 1):
        output.append(f"Dòng {i}: {', '.join(row)}")
    output.append("--- KẾT THÚC BẢNG ---")
    return "\n".join(output)


def generate_natural_language_summary(table_data: List[List[str]], table_name: str = "") -> str:
    """Tạo diễn giải ngôn ngữ tự nhiên từ dữ liệu bảng đã được xử lý."""
    processed = _process_and_fill_table(table_data)
    if not processed:
        return ""
    headers, filled_rows = processed

    if not filled_rows:
        return ""

    summary_lines = [f"--- Diễn giải thông tin từ {table_name} ---" if table_name else "--- Diễn giải thông tin từ bảng ---"]
    for row in filled_rows:
        subject = row[0] if row else ""
        if not subject: continue

        clauses = []
        for i in range(1, len(headers)):
            if i < len(row):
                column_header = headers[i]
                cell_value = row[i]
                if cell_value and column_header:
                    clauses.append(f"'{column_header}' là '{cell_value}'")
        
        if clauses:
            full_sentence = f"Với '{subject}', thì {', '.join(clauses)}."
            summary_lines.append(full_sentence)

    return "\n".join(summary_lines) if len(summary_lines) > 1 else ""


def extract_content_in_order(pdf_path: str) -> str:
    """
    Hàm chính, sử dụng phương pháp "cắt lát" đáng tin cậy để sắp xếp
    và bộ xử lý nâng cao để diễn giải bảng.
    """
    full_content = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            # full_content.append(f"\n=============== TRANG {page_num} ===============\n")

            # 1. Tìm tất cả các bảng và tạo "phần tử" bảng
            tables = page.find_tables(table_settings={
                "vertical_strategy": "lines", "horizontal_strategy": "lines", "snap_tolerance": 4
            })
            
            elements = []
            for i, table in enumerate(tables):
                elements.append({
                    "type": "table",
                    "bbox": table.bbox,
                    "data": table.extract(),
                    "name": f"Bảng {i+1} trên trang {page_num}"
                })

            # 2. Sử dụng kỹ thuật "cắt lát" để trích xuất văn bản giữa các bảng
            sorted_tables = sorted(elements, key=lambda x: x['bbox'][1])
            last_bottom = 0

            for el in sorted_tables:
                table_top = el['bbox'][1]
                # Vùng không gian phía trên bảng hiện tại
                top_bbox = (page.bbox[0], last_bottom, page.bbox[2], table_top)
                text_crop = page.crop(top_bbox)
                text = text_crop.extract_text(x_tolerance=2, layout=True)
                if text and text.strip():
                    elements.append({"type": "text", "bbox": top_bbox, "data": text.strip()})
                
                last_bottom = el['bbox'][3]

            # Trích xuất văn bản cuối cùng, nằm dưới bảng cuối cùng
            bottom_bbox = (page.bbox[0], last_bottom, page.bbox[2], page.height)
            text_crop = page.crop(bottom_bbox)
            text = text_crop.extract_text(x_tolerance=2, layout=True)
            if text and text.strip():
                elements.append({"type": "text", "bbox": bottom_bbox, "data": text.strip()})

            # 3. Sắp xếp TẤT CẢ các phần tử (text và table) theo vị trí từ trên xuống
            sorted_elements = sorted(elements, key=lambda x: x['bbox'][1])

            # 4. Tạo kết quả cuối cùng từ các phần tử đã sắp xếp
            for el in sorted_elements:
                if el['type'] == 'text':
                    full_content.append(el['data'])
                elif el['type'] == 'table':
                    # Lấy dữ liệu bảng và tên
                    table_data = el['data']
                    table_name = el.get('name', '')
                    
                    # Định dạng bảng dạng cấu trúc
                    structured_table = format_table_as_structured_text(table_data, table_name)
                    full_content.append(structured_table)
                    
                    # Tạo phần diễn giải ngôn ngữ tự nhiên
                    natural_summary = generate_natural_language_summary(table_data, table_name)
                    if natural_summary:
                        # Thêm phần diễn giải ngay sau bảng
                        full_content.append("\n" + natural_summary)
                
                # Thêm khoảng cách giữa các phần tử để dễ đọc
                full_content.append("\n")

    return "\n".join(full_content)