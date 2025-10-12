# PDF Processor 📝
Công cụ tiền xử lý file **PDF** thành **Markdown** và **JSON** có cấu trúc.
Hỗ trợ cả PDF dạng **text** và **PDF scan**.
Mục tiêu của công cụ này là chuẩn hóa dữ liệu văn bản, giữ được cấu trúc heading, title, bảng biểu, đồng thời loại bỏ các yếu tố gây nhiễu (header, footer).
***
##  Cách dùng
### Xử lý 1 file PDF:
```python
from pdf_processor import PDFprocessor

processor = PDFprocessor()
input_file = "data/raw documents/sample.pdf"
output_file = "data/markdown/sample.md"

data = processor.run(input_file, output_file)
for block in data:
    print(block["metadata"]["heading"], ":", block["metadata"]["is_title"])
```
### Xử lý cả thư mục
```python
processor = PDFprocessor()
data = processor.preprocess_and_save_data(
    "data/raw documents",   # input folder
    "data/markdown",        # output folder
    generate_md=True        # lưu file .md + all_data.json
)
```
***
## Chức năng chính
1. **Xử lý PDF**
- Nhận diện loại file:
    - PDF text: đọc được bằng pdfplumber.
    - PDF scan: cần OCR với Tesseract.
- Cơ chế xử lý theo loại file:
    - PDF text: che trắng các vùng ngoài bbox text để giữ được chính xác toạ độ khi xử lý.
    - PDF scan: giữ nguyên ảnh, chỉ áp dụng OCR để trích xuất chữ.

2. **Xác định title và heading của file**
- Tự động xác định title của file PDF
- Tự động nhận diện heading theo nhiều chiến lược:
    - dieu → "Điều 1:", "Điều 2."
    - muc → "Mục 1:"
    - roman → I, II, III...
    - numbered → 1., 2.1, 2.2...
    - general → dòng chữ HOA (≥ 80%).

3. **Chuyển sang Markdown**
- PDF text → trích xuất nội dung, thay thế bảng bằng Markdown.
- PDF scan → OCR bằng Tesseract (vie).
- Tự động phát hiện dữ liệu dạng bảng, chuyển về dạng md.
- Tự động phát hiện và loại bỏ footer và header của file.

4. **Xuất kết quả**
- Lưu thành Markdown (nếu bật generate_md=True).
- Tách thành các block JSON:
```json 
{
  "text": "Nội dung...",
  "metadata": {
    "heading": "Điều 1. Quy định chung",
    "is_title": "0",
    "original_filename": "dieukhoan.pdf",
    "file_type": "pdf"
  }
}
```
- Merge heading liền kề, lọc các heading giả.
5. **Chạy toàn thư mục**
- Hàm process_folder: duyệt toàn bộ folder PDF → xuất Markdown + JSON.
- Hàm preprocess_and_save_data: pipeline chính (copy file json gốc, xử lý PDF, sinh kết quả).
***
## Cài đặt ⚙️
- Cài đặt các thư viện cần thiết trong file requirements.txt
```bash
pip install -r requirements.txt
```

- Các thư viện chính:
    - pdfplumber → xử lý PDF text, trích xuất bbox.
    - camelot → phát hiện bảng, xuất dữ liệu bảng.
    - pytesseract → OCR cho PDF scan.
    - re, difflib, tqdm → tiền xử lý chuỗi, so khớp, log tiến trình.
***
## Cơ chế xử lý
### Chuyển đổi dữ liệu trong file PDF về dưới dạng markdown
- Đọc file PDF bằng pdfplumber.
- Phát hiện bảng bằng Camelot:
    - Lấy toạ độ bảng.
    - Chuyển dữ liệu bảng → Markdown.
    - Mapping hệ toạ độ Camelot ↔ pdfplumber.
- Kết hợp dữ liệu:
    - Giữ text gốc.
    - Thay thế vùng bảng bằng Markdown, sử dụng hệ tọa độ.

-> Link ví dụ giải thích tại đây: [Xem chi tiết](https://www.canva.com/design/DAG0EOqLgU4/-Ad1b4UO11GUai32GoHr1Q/edit?utm_content=DAG0EOqLgU4&utm_campaign=designshare&utm_medium=link2&utm_source=sharebutton)

### Xác định title của tài liệu
- Lấy ra 1 số lượng dòng đầu tiên của file PDF đồng thời tọa độ bbox của các dòng.
- Từ danh sách trên, chọn ra những dòng bị thụt lề.
- Xác định title của file dựa theo vị trí và các tiêu chí khác: Dạng chữ,...
- Đối với file **scan PDF**, không có dữ liệu bbox, chỉ có thể sử dụng Định dạng chữ và vị trí của chúng.

-> Link ví dụ giải thích tại đây: [Xem chi tiết](https://www.canva.com/design/DAG0EOqLgU4/-Ad1b4UO11GUai32GoHr1Q/edit?utm_content=DAG0EOqLgU4&utm_campaign=designshare&utm_medium=link2&utm_source=sharebutton)

### Xác định heading của tài liệu
- Xác định chiến lược chia heading của tài liệu các chiến lược sau:
    - Dữ liệu kiểu **điều/mục**.
    - Dữ liệu dạng **la mã** I, II,...
    - Dữ liệu dạng **số**: 1, 2,...
    - Dữ liệu **không thuộc** các kiểu trên.
- Sau khi xác định chiến lược, duyệt qua từng dòng dữ liệu đã chuyển sang dạng markdown, nếu trùng khớp với các kiểu dữ liệu đã được đặt ra thì sẽ đánh dầu heading.

-> Link ví dụ giải thích tại đây: [Xem chi tiết](https://www.canva.com/design/DAG0EOqLgU4/-Ad1b4UO11GUai32GoHr1Q/edit?utm_content=DAG0EOqLgU4&utm_campaign=designshare&utm_medium=link2&utm_source=sharebutton)

### Xác định header và footer của tài liệu
- Tách text từng trang.
- Lấy k dòng đầu/cuối của mỗi trang.
- Chuẩn hóa chuỗi, tính tương đồng (SequenceMatcher).
- Gom các chuỗi lặp thành cụm.
- Chọn đại diện (chuỗi dài nhất).
- Xóa trong toàn bộ văn bản.
- Loại bỏ dòng trống dư thừa.

-> Link ví dụ giải thích tại đây: [Xem chi tiết](https://www.canva.com/design/DAG0EOqLgU4/-Ad1b4UO11GUai32GoHr1Q/edit?utm_content=DAG0EOqLgU4&utm_campaign=designshare&utm_medium=link2&utm_source=sharebutton)

