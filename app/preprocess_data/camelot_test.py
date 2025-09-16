import camelot

# Đọc toàn bộ bảng trong PDF (stream hoặc lattice tùy file)
# lattice = phát hiện đường kẻ bảng, stream = phát hiện cột bằng khoảng trắng
tables = camelot.read_pdf("data/raw documents/Thẻ/Thẻ/Tín dụng/Visa Infinitie/DKDK-am-thuc.pdf", pages="all", flavor="lattice")

print(f"👉 Số bảng phát hiện được: {len(tables)}\n")

for i, table in enumerate(tables):
    print(f"=== Bảng {i+1} ===")
    print(table.df)  # In dữ liệu bảng dạng DataFrame


