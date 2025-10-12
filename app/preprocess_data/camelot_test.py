import camelot
from typing import List

# Đọc toàn bộ bảng trong PDF (stream hoặc lattice tùy file)
# lattice = phát hiện đường kẻ bảng, stream = phát hiện cột bằng khoảng trắng
tables = camelot.read_pdf("data/test_data/Dkdk-Nghi-duong.pdf", pages="all", flavor="lattice")

def generate_natural_language_summary(table_data: List[List[str]], headers: List[str], table_name: str = "") -> str:
    """Tạo diễn giải ngôn ngữ tự nhiên từ dữ liệu bảng đã được xử lý."""
    filled_rows = table_data

    if not filled_rows:
        return ""

    summary_lines = [f"--- Diễn giải thông tin từ {table_name} ---" if table_name else "--- Diễn giải thông tin từ bảng ---"]
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
                if cell_value and column_header:
                    clauses.append(f"'{column_header.replace('\n', '')}': '{cell_value.replace('\n', '')}'")
        
        if clauses:
            # full_sentence = f"Với '{subject}', thì {', '.join(clauses)}."
            full_sentence = f"{', '.join(clauses)}."
            summary_lines.append(full_sentence)

    return "\n".join(summary_lines) if len(summary_lines) > 1 else ""

print(f"👉 Số bảng phát hiện được: {len(tables)}\n")

for i, table in enumerate(tables):
    df = table.df.copy()

    # Lưu header (hàng đầu tiên)
    headers = df.iloc[0].tolist()

    # Gán header cho DataFrame
    df.columns = headers  

    # Xóa hàng header cũ khỏi dữ liệu
    df = df.drop(0).reset_index(drop=True)
    table_name = f"Bảng {i+1} (Page {table.page}) ==="

    print(f"=== Bảng {i+1} (Page {table.page}) ===")
    print(df.to_markdown(index=False, tablefmt="grid"))
    
    table_data = df.values.tolist()
    # for row in table_data:
    #     for cell in table

    table_sumary = generate_natural_language_summary(table_data, headers, table_name)
    print(table_sumary)


