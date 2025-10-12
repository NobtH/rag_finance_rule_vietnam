import camelot
import pdfplumber

file_path = "data/raw documents/Khuyến mãi/Các chương trình khuyến mãi.pdf"

# Mở PDF với pdfplumber để lấy chiều cao trang
with pdfplumber.open(file_path) as pdf:
    for page_num, page in enumerate(pdf.pages, start=1):
        print(f"\n=== Page {page_num} ===")
        page_height = page.height
        
        # Lấy các bảng trên trang bằng Camelot
        tables = camelot.read_pdf(file_path, pages=str(page_num), flavor='lattice')
        
        if not tables:
            print("No tables found on this page.")
            continue
        
        for i, table in enumerate(tables):
            camelot_bbox = table._bbox  # Camelot bbox: [x1, y1, x2, y2]
            print(f"\nTable {i+1} Camelot bbox:", camelot_bbox)
            
            # Chuyển bbox Camelot -> pdfplumber
            x0 = float(camelot_bbox[0])
            y0 = float(camelot_bbox[1])
            x1 = float(camelot_bbox[2])
            y1 = float(camelot_bbox[3])
            pdfplumber_bbox = (x0, page_height - y1, x1, page_height - y0)
            print("Converted pdfplumber bbox:", pdfplumber_bbox)
            
            # Trích xuất text trong bbox pdfplumber
            cropped = page.within_bbox(pdfplumber_bbox)
            text_in_bbox = cropped.extract_text()
            
            print("Text extracted in bbox:")
            print(text_in_bbox)
