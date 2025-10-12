import camelot
import pdfplumber
from remove_header_footer_func import remove_headers_and_footers_v2, squeeze_blank_lines
from typing import List

def normalize_bbox(bbox, page_width, page_height):
    """
    Chuẩn hóa bbox để dùng trong pdfplumber:
    - Clamp về trong trang
    - Đảm bảo (x0 < x1) và (top < bottom)
    """
    x0, top, x1, bottom = bbox

    # Clamp trong phạm vi trang
    x0 = max(0, min(page_width, x0))
    x1 = max(0, min(page_width, x1))
    top = max(0, min(page_height, top))
    bottom = max(0, min(page_height, bottom))

    # Đảm bảo thứ tự đúng
    if x0 > x1:
        x0, x1 = x1, x0
    if top > bottom:
        top, bottom = bottom, top

    return (x0, top, x1, bottom)


def camelot_to_pdfplumber_bbox(camelot_bbox, page_height, page_width):
    """
    Chuyển bbox Camelot -> pdfplumber bbox (có chuẩn hóa).
    """
    x0, y0, x1, y1 = map(float, camelot_bbox)
    top = page_height - y1
    bottom = page_height - y0
    bbox = (x0, top, x1, bottom)
    return normalize_bbox(bbox, page_width, page_height)


def generate_natural_language_summary(table_data: List[List[str]], headers: List[str], table_name: str = "") -> str:
    """Tạo diễn giải ngôn ngữ tự nhiên từ dữ liệu bảng đã được xử lý."""
    filled_rows = table_data

    if not filled_rows:
        return ""

    summary_lines = [f"=== Diễn giải thông tin từ {table_name} ===" if table_name else "=== Diễn giải thông tin từ bảng ==="]
    for row in filled_rows:
        subject = row[0] if row else ""
        if not subject: continue

        clauses = []
        for i in range(0, len(headers)):
            if i < len(row):
                column_header = headers[i]
                if column_header.lower() == 'STT'.lower():
                    continue
                cell_value = row[i]
                if cell_value:
                    clauses.append(f'"{column_header.replace('\n', '')}": "{cell_value.replace('\n', '')}"')
        
        if clauses:
            # full_sentence = f"Với '{subject}', thì {', '.join(clauses)}."
            full_sentence = f"{', '.join(clauses)}."
            summary_lines.append(full_sentence)
            
    res = "\n".join(summary_lines) if len(summary_lines) > 1 else ""
    res += f"\n === Kết thúc diễn giải thông tin bảng {table_name}. ===\n"
    return res

def extract_content_in_order(pdf_path: str, k_lines: int = 5, sim_threshold: float = 0.8, min_ratio: float = 0.8) -> str:
    """
    Duyệt từng trang PDF, dùng Camelot xác định bbox bảng,
    cắt bỏ text gốc trong bbox và thay bằng Markdown table.
    """
    per_page_text = []

    with pdfplumber.open(pdf_path) as pdf:
        num_pages = len(pdf.pages)

        for page_num in range(1, num_pages + 1):
            page = pdf.pages[page_num - 1]
            page_height = page.height
            page_width = page.width

            # Dò bảng và trích xuất thông tin
            tables = camelot.read_pdf(pdf_path, pages=str(page_num), flavor="lattice")
            

            if not tables:
                per_page_text.append(page.extract_text().replace('•', '-') or "")
                continue

            # Sắp xếp bảng từ trên xuống
            sorted_tables = sorted(tables, key=lambda t: t._bbox[3], reverse=True)

            modified_parts = []
            current_top = 0  # y theo hệ pdfplumber (top=0)

            for i, table in enumerate(sorted_tables):
                # print(table.df.to_markdown(index=False, tablefmt="grid"))
                # print(table._bbox)
                pdfplumber_bbox = camelot_to_pdfplumber_bbox(table._bbox, page_height, page_width)

                # Vùng text từ current_top đến top của bảng
                non_table_region = normalize_bbox((0, current_top, page_width, pdfplumber_bbox[1]),
                                                  page_width, page_height)
                top_text = page.within_bbox(non_table_region).extract_text() or ""
                if top_text.strip():
                    modified_parts.append(top_text.replace('•', '-').strip())

                # Nếu bảng rỗng thì bỏ qua
                if table.df.dropna(how="all").shape[0] > 0 and table.df.dropna(how="all").shape[1] > 0:
                    df = table.df.copy()
                    headers = df.iloc[0].to_list()
                    df.columns = headers
                    df = df.drop(0).reset_index(drop=True)
                    
                    table_data = df.values.tolist()

                    markdown_table = df.to_markdown(index=False, tablefmt="grid")
                    table_name = f"Bảng {i+1} (trang {page_num})"

                    # modified_parts.append(f"\n\n**{table_name}**\n\n{markdown_table}\n\n")ss

                    table_summary = generate_natural_language_summary(table_data=table_data, headers=headers, table_name=table_name)

                    modified_parts.append(f"\n{table_summary}\n")

                # Cập nhật current_top = bottom của bảng
                
                current_top = pdfplumber_bbox[3]

            # Text sau bảng cuối cùng
            bottom_region = normalize_bbox((0, current_top, page_width, page_height),
                                           page_width, page_height)
            bottom_text = page.within_bbox(bottom_region).extract_text() or ""
            if bottom_text.strip():
                modified_parts.append(bottom_text.replace('•', '-').strip())

            per_page_text.append("\n\n".join(modified_parts))

    # Xử lý header/footer
    if num_pages > 1:
        cleaned_pages = remove_headers_and_footers_v2(
            per_page_text, num_pages=num_pages, max_check_lines=k_lines,
            sim_threshold=sim_threshold, min_ratio=min_ratio
        )
    else:
        cleaned_pages = per_page_text

    return squeeze_blank_lines("\n\n".join(cleaned_pages))


if __name__ == "__main__":
    pdf_path = "data/test_data/Điều khoản và điều kiện mở và sử dụng tài khoản copy.pdf"
    result = extract_content_in_order(pdf_path)

    print("=== KẾT QUẢ CUỐI CÙNG ===")
    # print(result)

    with open("output_processed.md", "w", encoding="utf-8") as f:
        f.write(result)
    print("\nĐã lưu kết quả vào output_processed.md")
