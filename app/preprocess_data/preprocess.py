import os
import fitz
from dotenv import load_dotenv
import shutil
from pdf2image import convert_from_path
import pytesseract
import re
from table_pdf_to_md import *
from table_pdf_to_md_text import PDFTableToTextConverter
from get_pos_func import *
import tempfile
import json

load_dotenv()

class PDFprocessor:
    def __init__(self, footer_height_ratio=0.1):
        self.footer_height_ratio = footer_height_ratio
        self.pdftabletotext = PDFTableToTextConverter()
        self.input_file = None
        self.output_file = None
        self.temp_clean_dir = None

    def get_num_pages(self, pdf_file_path):
        doc = fitz.open(pdf_file_path)

        num_pages = doc.page_count
        return num_pages
    
    def get_title_with_pos(self, pdf_path):
        text_with_pos = get_first_lines_with_coords(pdf_path)
        if text_with_pos:
            cen_text = extract_indented_lines(text_with_pos)
            # Chuẩn hóa cen_text: xóa khoảng trắng và chuyển thành chữ thường
            return [re.sub(r'\s+', '', t.strip()).lower() for t, _ in cen_text]
        return []

    def is_scanned_pdf_fitz(self, pdf_path):
        doc = None
        try:
            doc = fitz.open(pdf_path)
            # Kiểm tra xem file có ít văn bản hay không
            text = doc[0].get_text("text")
            if len(text.strip()) < 50:
                return True
            else:
                return False
        except Exception as e:
            print(f"Lỗi khi kiểm tra file {pdf_path}: {e}")
            return True 
        finally:
            if doc and not doc.is_closed:
                doc.close()

    def _remove_footer_from_pdf(self, in_path, out_path):
        doc_in = None
        doc_out = None
        try:
            doc_in = fitz.open(in_path)
            doc_out = fitz.open()

            for page in doc_in:
                page_height = page.rect.height
                footer_rect = fitz.Rect(
                    0,
                    page_height * (1 - self.footer_height_ratio),
                    page.rect.width,
                    page_height
                )
                
                page_out = doc_out.new_page(
                    width=page.rect.width,
                    height=page.rect.height
                )
                page_out.show_pdf_page(page_out.rect, doc_in, page.number)
                page_out.add_redact_annot(footer_rect)
                page_out.apply_redactions()

            doc_out.save(out_path)
            print(f"-> Đã lưu file sạch tại: {out_path}")
            return True

        except Exception as e:
            print(f"Lỗi khi xử lý file PDF để cắt footer ({in_path}): {e}")
            return False
        finally:
            if doc_in and not doc_in.is_closed:
                doc_in.close()
            if doc_out and not doc_out.is_closed:
                doc_out.close()
    
    def copy_json_file(self, pdf_root_dir, output_md_dir):
        """
        Copy toàn bộ file .json từ pdf_root_dir sang output_md_dir,
        giữ nguyên cấu trúc thư mục.
        """
        for root, _, files in os.walk(pdf_root_dir):
            for file_name in files:
                if file_name.endswith('.json'):
                    original_json_path = os.path.join(root, file_name)
                    relative_path = os.path.relpath(original_json_path, pdf_root_dir)
                    output_json_path = os.path.join(output_md_dir, relative_path)

                    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)

                    try:
                        shutil.copy(original_json_path, output_json_path)
                        print(f"-> Đã sao chép: {original_json_path} -> {output_json_path}")
                    except Exception as e:
                        print(f"Lỗi khi sao chép file {original_json_path}: {e}")
    
    def get_markdown_strategy(self, lines):
        """
        Xác định chiến lược chia chunk ưu tiên nhất cho tài liệu.
        """
        if any(re.match(r'^\s*#?\s*Điều\s+\d+[\.:]', line, re.IGNORECASE) for line in lines):
            return 'dieu'
        if any(re.match(r'^\s*(?=[LXVI]+\b)[LXVI]+\s*[\.:]', line) for line in lines):
            return 'roman'
        if any(re.match(r'^\s*\d+[\.:]', line) for line in lines) or any(re.match(r'^\s*\d+\.\s+[a-zA-Z]', line) for line in lines):
            return 'numbered'
        return 'general'
    
    def make_heading(self, lines):
        all_text = ''
        tmp_num = 0
        stategy = self.get_markdown_strategy(lines)
        print(stategy)

        headings = []  # lưu lại heading dạng (vị trí, text)

        for idx, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) <= 5:
                continue
            
            if line == line.upper() and re.search(r'[A-ZÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ]', line) and len(line) > 30:
                if not line.startswith('#'):
                    all_text += f"# {line}\n"
                    headings.append(line)
                    print('general')
                continue

            if idx == 0 and len(line) > 10:
                all_text += f"# {line}\n"
                headings.append(line)
                continue

            if stategy == 'dieu':
                if re.match(r'^Điều\s+\d+(\.|:)', line, re.IGNORECASE):
                    all_text += f"# {line} \n"
                    headings.append(line)
                    print('Dieu')
                else:
                    all_text += f"{line}\n"

            elif stategy == 'roman':
                if re.match(r'^\s*(?=[LXVI]+\b)[LXVI]+\s*[\.:]', line):
                    all_text += f"# {line} \n"
                    headings.append(line)
                    print('roman')
                else:
                    all_text += f"{line}\n"

            elif stategy == 'numbered':
                m1 = re.match(r'^\s*(\d+)\s*\.\s*$', line)
                m2 = re.match(r'^\s*(\d+)\.(\s*[a-zA-Z].*)', line)
                
                if m1:
                    number = int(m1.group(1))
                    if number > tmp_num:
                        all_text += f"# {line} \n"
                        headings.append(line)
                        print('number')
                        tmp_num = number
                    else:
                        all_text += f"{line}\n"
                elif m2:
                    number = int(m2.group(1))
                    if number > tmp_num:
                        all_text += f"# {line}\n"
                        headings.append(line)
                        tmp_num = number
                    else:
                        all_text += f"{line}\n"
                else:
                    all_text += f'{line}\n'

        if stategy == 'numbered' and headings:
            if all(len(h) > 50 for h in headings):
                def replace_heading(match):
                    line = match.group(0).lstrip("#").strip()
                    # Nếu line toàn chữ hoa thì giữ lại #
                    if line == line.upper():
                        return f"# {line}"
                    else:
                        return line

                all_text = re.sub(r'^#\s*(.*)', replace_heading, all_text, flags=re.MULTILINE)

        return all_text.strip()

    def scanned_pdf_to_markdown(self, pdf_path):
        print(f'Tesseract-OCR: Chuyển file scanned {pdf_path} thành dạng markdown')
        all_text = ""
        try:
            images = convert_from_path(pdf_path)
            for image in images:
                text = pytesseract.image_to_string(image, lang='vie')

                lines = text.splitlines()
                for line in lines:
                    line = line.strip()
                    if not line or len(line) <= 5:
                        continue

                    if line == line.upper() and re.search(r'[a-zA-ZáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệiíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆIÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ]', line) and len(line) > 20:
                        all_text += f"# {line}\n"
                    elif re.match(r'^Điều\s+\d+(\.|:)', line, re.IGNORECASE):
                        all_text += f"# {line} \n"
                    else:
                        all_text += f"{line}\n"
        except Exception as e:
            print(f"Lỗi khi thực hiện OCR cho file {pdf_path}: {e}")
            return None
            
        return all_text.strip()
    
    def turn_pdf_to_markdown_local(self, pdf_path):
        try:
            print('Chuyen ve md bang local')
            text = extract_content_in_order(pdf_path=pdf_path)
            # text = self.pdftabletotext.process_pdf(pdf_path=pdf_path)

            lines = text.splitlines()

            all_text = self.make_heading(lines)
            return all_text
        except:
            print('Loi khi chuyen ve md local')
            return None
    
    def run(self, input_pdf_path, output_md_path):
        self.input_file = input_pdf_path
        self.output_file = output_md_path
        print(f"Bắt đầu xử lý file: {input_pdf_path}")
        
        if not self.temp_clean_dir:
            self.temp_clean_dir = tempfile.mkdtemp(prefix="pdf_clean_")
        os.makedirs(self.temp_clean_dir, exist_ok=True)

        temp_pdf_path = os.path.join(self.temp_clean_dir, os.path.basename(input_pdf_path))
        os.makedirs(os.path.dirname(temp_pdf_path), exist_ok=True)        

        # Loại bỏ footer (hàm giả định)
        if not self._remove_footer_from_pdf(input_pdf_path, temp_pdf_path):
            print("Lỗi khi loại bỏ footer. Dừng xử lý.")
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
            return []

        # OCR hoặc local parse (hàm giả định)
        markdown_content = None
        if self.is_scanned_pdf_fitz(temp_pdf_path):
            scanned_text = self.scanned_pdf_to_markdown(temp_pdf_path)
            if scanned_text:
                markdown_content = "\n".join([line for line in scanned_text.splitlines() if line.strip()])
        else:
            tmp_text = self.turn_pdf_to_markdown_local(temp_pdf_path)
            if tmp_text:
                markdown_content = "\n".join([line for line in tmp_text.splitlines() if line.strip()])

        if not markdown_content:
            print("Không có nội dung markdown.")
            return []

        # Lưu file markdown ra output_md_path
        os.makedirs(os.path.dirname(output_md_path), exist_ok=True)
        try:
            with open(output_md_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            print(f"-> Đã lưu nội dung markdown tại: {output_md_path}")
        except Exception as e:
            print(f"Lỗi khi lưu file markdown {output_md_path}: {e}")

        # LOGIC MỚI: Lấy title từ vị trí và so sánh với heading
        cen_text_normalized = self.get_title_with_pos(temp_pdf_path)
        print(cen_text_normalized)
        
        use_first_heading_as_default = not cen_text_normalized
        first_heading_found = False
        
        data = []
        current_heading = None
        current_text = []
        
        for line in markdown_content.splitlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith("#"):  # heading mới
                if current_heading is not None:
                    # Lưu heading và nội dung của khối trước
                    data.append({
                        "heading": current_heading,
                        "text": "\n".join(current_text).strip() if current_text else None,
                        "file_title": current_is_title
                    })

                current_is_title = 0
                heading_text = line.strip("# ").strip()
                # Chuẩn hóa heading_text để so sánh
                heading_text_normalized = re.sub(r'\s+', '', heading_text).lower()
                print(heading_text_normalized)

                if use_first_heading_as_default and not first_heading_found:
                    # Trường hợp mặc định: sử dụng heading đầu tiên làm title
                    current_is_title = 1
                    first_heading_found = True
                elif heading_text_normalized in cen_text_normalized:
                    # Trường hợp so khớp: heading khớp với một trong các dòng thụt vào
                    current_is_title = 1

                current_heading = line
                current_text = []

            else:
                current_text.append(line)

        # Lưu heading và nội dung cuối cùng
        if current_heading is not None:
            data.append({
                "heading": current_heading,
                "text": "\n".join(current_text).strip() if current_text else None,
                "file_title": current_is_title
            })

        return data
    
    
    def process_folder(self, input_pdf_dir, output_md_dir, output_json_path="all_data.json"):
        if not os.path.exists(input_pdf_dir):
            print(f"Thư mục input không tồn tại: {input_pdf_dir}")
            return

        all_data = []

        for root, dirs, files in os.walk(input_pdf_dir):
            relative_path = os.path.relpath(root, input_pdf_dir)
            output_root = os.path.join(output_md_dir, relative_path)
            os.makedirs(output_root, exist_ok=True)

            topic_feature = os.path.basename(root)

            for file_name in files:
                if not file_name.lower().endswith(".pdf"):
                    continue

                input_path = os.path.join(root, file_name)
                base_name = os.path.splitext(file_name)[0]
                output_md_path = os.path.join(output_root, base_name + ".md")

                print(f"\n=== Đang xử lý: {input_path} ===")
                try:
                    data = self.run(input_path, output_md_path)

                    # Thêm metadata cho từng block
                    for block in data:
                        all_data.append({
                            "text": block.get("text", ""),
                            "metadata": {
                                "heading": block.get("heading", ""),
                                "is_title": str(block.get("file_title", "")),
                                "original_filename": file_name,
                                "file_type": "pdf",
                                "topic_feature": topic_feature
                            }
                        })

                    print(f"-> Hoàn thành: {output_md_path}, tổng {len(data)} block")
                except Exception as e:
                    print(f"Lỗi khi xử lý {input_path}: {e}")

        # Sau khi duyệt xong toàn bộ file thì lưu JSON duy nhất
        final_json_path = os.path.join(output_md_dir, output_json_path)
        with open(final_json_path, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

        print(f"\n>>> Đã lưu toàn bộ dữ liệu JSON vào: {final_json_path}, tổng {len(all_data)} block")

    def preprocess_and_save_data(self, input_folder_dir, output_folder_dir):
        """
        Hàm chính để xử lý toàn bộ quá trình: copy json, loại bỏ footer, chuyển đổi và lưu markdown.
        pdf_root_dir: thư mục gốc chứa các file pdf (có thể có nhiều folder con).
        """
        self.copy_json_file(input_folder_dir, output_folder_dir)
        self.process_folder(input_folder_dir, output_folder_dir)

if __name__ == '__main__':
    processor = PDFprocessor()
    # res = processor.get_file_title('data/raw documents/Vay/THÔNG TIN CHI TIẾT CÁC LOẠI VAY DÀNH CHO KHÁCH HÀNG CÁ NHÂN.pdf')
    # for tmp in res:
    #     print(tmp['text'])
    #     print(tmp['size'])
    #     print(tmp['font'])
    #     print(tmp['page'])
    #     print('*'*50)

    processor.preprocess_and_save_data("data/raw documents", "data/markdown")

    # input_file = 'data/raw documents/Thẻ/Điều khoản và điều kiện phát hành và sử dụng thẻ.pdf'
    # output_file = 'data/raw documents/Thẻ/Điều khoản và điều kiện phát hành và sử dụng thẻ.pdf.md'
    # res = processor.run(input_file, output_file)
    # for i in res[0:5]:
    #     print(i['heading'])
    #     print(i['text'])
    #     print(f"title: {i['file_title']}")
    #     if i['text'] is not None:
    #         print(len(i['text']))
    #     print('------------------------------------------------------------------\n')