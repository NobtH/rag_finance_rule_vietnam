import pdfplumber
from typing import List, Tuple, Optional

def _process_and_fill_table(table_data: List[List[Optional[str]]]) -> Optional[Tuple[List[str], List[List[str]]]]:
    """
    Hàm nội bộ để xử lý và điền dữ liệu cho bảng có ô gộp và header nhiều tầng.
    
    Returns:
        Một tuple chứa: (final_header, filled_data_rows) hoặc None nếu bảng không hợp lệ.
    """
    if not table_data:
        return None

    # 1. Dọn dẹp dữ liệu ban đầu: thay thế None bằng chuỗi rỗng và \n bằng dấu cách
    clean_table = []
    for row in table_data:
        clean_row = [(cell.replace('\n', ' ').strip() if cell is not None else "") for cell in row]
        clean_table.append(clean_row)

    # 2. Heuristic để xác định số hàng header
    # Giả định: các hàng header là các hàng ở đầu mà có ô trống ở cột đầu tiên,
    # hoặc các hàng có ô gộp (dẫn đến các ô trống).
    header_row_count = 0
    for i, row in enumerate(clean_table):
        # Nếu dòng đầu tiên trống ở cột đầu -> có thể là header 2 tầng
        is_potential_sub_header = (i > 0 and not row[0] and any(cell for cell in row))
        # Dừng lại khi gặp dòng đầu tiên trông giống dữ liệu (không có ô trống ở cột 1)
        if i > 0 and row[0] and not is_potential_sub_header:
            break
        # Nếu dòng có vẻ là header, ta đếm nó
        if i == 0 or is_potential_sub_header or any(cell == "" for cell in row):
             header_row_count +=1
        else:
             break
    # Đảm bảo không lấy quá nhiều hàng làm header
    if header_row_count >= len(clean_table):
        header_row_count = 1 if len(clean_table) > 1 else len(clean_table)

    header_rows = clean_table[:header_row_count]
    data_rows = clean_table[header_row_count:]

    if not header_rows:
        return None

    # 3. Làm phẳng header
    # Điền các ô gộp cột trong header
    processed_headers = [list(row) for row in header_rows]
    for r in range(len(processed_headers)):
        for c in range(1, len(processed_headers[r])):
            if not processed_headers[r][c]:
                processed_headers[r][c] = processed_headers[r][c-1]
    
    # Kết hợp các hàng header lại
    final_header = list(processed_headers[0])
    for r in range(1, len(processed_headers)):
        for c in range(len(final_header)):
            if processed_headers[r][c] != processed_headers[r-1][c]:
                final_header[c] = f"{final_header[c]} {processed_headers[r][c]}".strip()

    if not data_rows:
        return final_header, []

    # 4. Điền dữ liệu cho các ô gộp hàng trong các dòng dữ liệu
    filled_data_rows = []
    for r, row in enumerate(data_rows):
        filled_row = list(row)
        if r > 0:
            for c, cell in enumerate(filled_row):
                # Nếu ô hiện tại trống, lấy giá trị từ ô tương ứng của hàng đã điền trước đó
                if not cell:
                    filled_row[c] = filled_data_rows[r-1][c] + '|'
        filled_data_rows.append(filled_row)

    return final_header, filled_data_rows


def format_table_as_structured_text(table_data: List[List[str]], table_name: str = "") -> str:
    """Chuyển đổi dữ liệu bảng thành văn bản mô tả dạng cấu trúc (sau khi đã xử lý)."""
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
    """Tạo ra một đoạn diễn giải nội dung bảng bằng ngôn ngữ tự nhiên (sau khi đã xử lý)."""
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
        if not subject: continue

        clauses = []
        for i in range(1, len(headers)):
            # Đảm bảo không truy cập index ngoài phạm vi nếu hàng bị lỗi
            if i < len(row):
                column_header = headers[i]
                cell_value = row[i]
                if cell_value and column_header:
                    clauses.append(f"{column_header} là {cell_value}")
        
        if clauses:
            full_sentence = f"{subject}, {', '.join(clauses)}."
            summary_lines.append(full_sentence)

    return "\n".join(summary_lines) if len(summary_lines) > 1 else ""


def extract_content_in_order(pdf_path: str) -> str:
    """
    Hàm chính: Trích xuất nội dung từ PDF, giữ nguyên thứ tự, và xử lý bảng phức tạp.
    """
    full_content = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            # full_content.append(f"\n=============== TRANG {page_num} ===============\n")

            # Tìm bảng
            tables = page.find_tables(table_settings={
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "snap_tolerance": 4,
            })
            
            elements = []
            for i, table in enumerate(tables):
                elements.append({
                    "type": "table",
                    "bbox": table.bbox,
                    "data": table.extract(),
                    "name": f"Bảng {i+1} trên trang {page_num}"
                })

            # Kỹ thuật "cắt lát" để lấy text
            sorted_tables = sorted([el for el in elements if el['type'] == 'table'], key=lambda x: x['bbox'][1])
            last_bottom = 0
            
            text_elements = []
            page_crop_box = (page.bbox[0], 0, page.bbox[2], page.height)
            
            # Sử dụng page.dedupe_chars() để cải thiện chất lượng text, đặc biệt là khoảng cách
            # Dùng extract_words thay vì extract_text để kiểm soát tốt hơn
            words = page.dedupe_chars(tolerance=1).extract_words(keep_blank_chars=True)

            # Lấy toàn bộ text trước
            all_text_content = page.extract_text(x_tolerance=2, layout=True)
            if all_text_content:
                 text_elements.append({
                    "type": "text",
                    "bbox": (page.bbox[0], 0, page.bbox[2], page.height), # Bbox của toàn trang
                    "data": all_text_content
                })

            # Lọc bỏ phần text nằm trong bbox của bảng
            for table_el in sorted_tables:
                t_bbox = table_el['bbox']
                remaining_text_elements = []
                for text_el in text_elements:
                    # Đây là một cách tiếp cận đơn giản: thay thế text của bảng bằng placeholder
                    # Một cách phức tạp hơn là phải tính toán lại bbox của text
                    table_as_text = page.crop(t_bbox).extract_text()
                    if table_as_text:
                        text_el['data'] = text_el['data'].replace(table_as_text, f"[[PLACEHOLDER_FOR_{table_el['name']}]]")
                
                text_elements = remaining_text_elements if remaining_text_elements else text_elements


            # Sắp xếp và tạo kết quả cuối cùng
            final_elements = elements # Gồm cả text và table
            # Logic sắp xếp cũ vẫn đúng vì nó dựa trên vị trí top của bbox
            sorted_elements = sorted(final_elements, key=lambda x: x['bbox'][1])

            # Thay đổi logic render kết quả
            im_a_placeholder = page.crop(page.bbox).extract_text(layout=True)
            for el in sorted_tables:
                 table_text_placeholder = f"[[PLACEHOLDER_FOR_{el['name']}]]"
                 
                 structured_table = format_table_as_structured_text(el['data'], el.get('name', ''))
                 natural_summary = generate_natural_language_summary(el['data'], el.get('name', ''))
                 
                 full_table_content = f"{structured_table}\n\n{natural_summary}"
                 
                 im_a_placeholder = im_a_placeholder.replace(page.crop(el['bbox']).extract_text(layout=True) or "UNFOUND_TABLE_TEXT", full_table_content, 1)

            full_content.append(im_a_placeholder)
    
    # Dọn dẹp các dòng trống dư thừa
    lines = full_content
    cleaned_text = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        cleaned_text += f'{line}\n'
    return cleaned_text
    
# --- VÍ DỤ SỬ DỤNG ---
if __name__ == "__main__":
    # Tạo một file PDF mẫu có bảng phức tạp để kiểm tra
    # Hoặc dùng một file có sẵn và thay đổi đường dẫn
    pdf_file_path = r"data/raw_documents/Tiết kiệm/LÃI SUẤT HUY ĐỘNG - KHÁCH HÀNG CÁ NHÂN.pdf" # Hãy đảm bảo có file này trong cùng thư mục
    
    try:
        extracted_content = extract_content_in_order(pdf_file_path)
        print(extracted_content)
        
        with open("extracted_content_advanced.md", "w", encoding="utf-8") as f:
            f.write(extracted_content)
        print(f"\n\nNội dung đã được trích xuất và lưu vào file 'extracted_content_advanced.md'")

    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file '{pdf_file_path}'. Vui lòng tạo file PDF mẫu để kiểm tra.")
    except Exception as e:
        print(f"Đã xảy ra lỗi: {e}")