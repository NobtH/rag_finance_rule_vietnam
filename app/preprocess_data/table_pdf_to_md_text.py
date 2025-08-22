import pdfplumber
import pandas as pd
import re
from typing import List, Dict, Tuple

class PDFTableToTextConverter:
    def __init__(self):
        self.debug = True
        
    def clean_text(self, text: str) -> str:
        """Làm sạch văn bản"""
        if not text:
            return ""
        text = str(text).strip()
        # Loại bỏ khoảng trắng thừa
        text = re.sub(r'\s+', ' ', text)
        return text
    
    def is_meaningful_table(self, table: List[List]) -> bool:
        """Kiểm tra xem bảng có ý nghĩa không"""
        if not table or len(table) < 2:
            return False
        
        # Đếm số ô có dữ liệu
        filled_cells = 0
        total_cells = 0
        
        for row in table:
            for cell in row:
                total_cells += 1
                if cell and str(cell).strip():
                    filled_cells += 1
        
        # Bảng phải có ít nhất 30% ô chứa dữ liệu
        return (filled_cells / total_cells) > 0.3 if total_cells > 0 else False
    
    def table_to_sentences(self, table: List[List]) -> List[str]:
        """Chuyển bảng thành câu văn tự nhiên"""
        if not table or len(table) < 2:
            return []
        
        sentences = []
        
        # Lấy header (hàng đầu tiên)
        headers = []
        for cell in table[0]:
            clean_cell = self.clean_text(str(cell) if cell else "")
            headers.append(clean_cell)
        
        if self.debug:
            print(f"Headers: {headers}")
        
        # Xử lý từng hàng dữ liệu
        for i, row in enumerate(table[1:], 1):
            if not row:
                continue
                
            # Làm sạch dữ liệu hàng
            clean_row = []
            for cell in row:
                clean_cell = self.clean_text(str(cell) if cell else "")
                clean_row.append(clean_cell)
            
            # Bỏ qua hàng trống
            if not any(clean_row):
                continue
            
            # Tạo câu mô tả cho hàng này
            row_name = clean_row[0] if clean_row[0] else f"Hàng {i}"
            
            # Tạo các mô tả cho từng cột
            descriptions = []
            for j, value in enumerate(clean_row[1:], 1):
                if value and j < len(headers) and headers[j]:
                    desc = f"{headers[j]} là {value}"
                    descriptions.append(desc)
            
            # Kết hợp thành câu hoàn chỉnh
            if descriptions:
                sentence = f"{row_name}, " + ", ".join(descriptions) + "."
                sentences.append(sentence)
                
                if self.debug:
                    print(f"Sentence: {sentence}")
        
        return sentences
    
    def extract_text_blocks(self, page_text: str) -> List[str]:
        """Chia văn bản thành các khối"""
        if not page_text:
            return []
        
        # Chia theo dòng và loại bỏ dòng trống
        lines = [line.strip() for line in page_text.split('\n') if line.strip()]
        
        # Nhóm các dòng liên quan thành khối
        blocks = []
        current_block = []
        
        for line in lines:
            # Nếu dòng quá ngắn hoặc chỉ chứa ký tự đặc biệt, bỏ qua
            if len(line) < 3 or re.match(r'^[-=_\s]*$', line):
                if current_block:
                    blocks.append(" ".join(current_block))
                    current_block = []
                continue
            
            current_block.append(line)
        
        # Thêm khối cuối cùng
        if current_block:
            blocks.append(" ".join(current_block))
        
        return blocks
    
    def process_pdf(self, pdf_path: str) -> str:
        """Xử lý file PDF chính"""
        try:
            print(f"Đang mở file: {pdf_path}")
            result_parts = []
            
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                print(f"Tổng số trang: {total_pages}")
                
                for page_num, page in enumerate(pdf.pages, 1):
                    print(f"\n--- Xử lý trang {page_num}/{total_pages} ---")
                    
                    # 1. Trích xuất văn bản
                    page_text = page.extract_text()
                    if self.debug:
                        print(f"Độ dài văn bản trang {page_num}: {len(page_text) if page_text else 0}")
                    
                    # 2. Trích xuất bảng
                    tables = page.extract_tables()
                    if self.debug:
                        print(f"Số bảng tìm thấy: {len(tables)}")
                    
                    # 3. Xử lý văn bản thường
                    if page_text:
                        text_blocks = self.extract_text_blocks(page_text)
                        for block in text_blocks:
                            if len(block) > 10:  # Chỉ lấy khối có nội dung đủ dài
                                result_parts.append(block)
                    
                    # 4. Xử lý bảng
                    for table_idx, table in enumerate(tables):
                        if self.is_meaningful_table(table):
                            print(f"Xử lý bảng {table_idx + 1} (kích thước: {len(table)}x{len(table[0]) if table else 0})")
                            
                            sentences = self.table_to_sentences(table)
                            if sentences:
                                result_parts.append(f"\n--- Thông tin từ bảng {table_idx + 1} ---")
                                result_parts.extend(sentences)
                                result_parts.append("")  # Dòng trống
                        else:
                            if self.debug:
                                print(f"Bỏ qua bảng {table_idx + 1} (không có đủ dữ liệu)")
                    
                    print(f"Hoàn thành trang {page_num}")
                    
                    # Giải phóng bộ nhớ
                    del page_text, tables
            
            result = "\n".join(result_parts)
            print(f"\nTổng độ dài kết quả: {len(result)} ký tự")
            return result
            
        except Exception as e:
            error_msg = f"Lỗi khi xử lý PDF: {str(e)}"
            print(error_msg)
            return error_msg