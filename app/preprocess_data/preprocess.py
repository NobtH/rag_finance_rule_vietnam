import os
import fitz
from dotenv import load_dotenv
import shutil
from pdf2image import convert_from_path
import pytesseract
import re
from table_pdf_to_md import *
from table_pdf_to_md_text import PDFTableToTextConverter

load_dotenv()

class PDFprocessor:
    def __init__(self, footer_height_ratio=0.1):
        self.footer_height_ratio = footer_height_ratio
        self.pdftabletotext = PDFTableToTextConverter()
        self.input_file = None
        self.output_file = None
        self.temp_clean_dir = None

    def read_pdf_infomation(self, pdf_file_path):
        doc = fitz.open(pdf_file_path)

        num_pages = doc.page_count
        return num_pages
    
    def get_file_title(self, pdf_file_path):
        """
        Returns:
            list: Danh sách các dictionary chứa thông tin về text và trang, hoặc None nếu có lỗi.
        """
        try:
            doc = fitz.open(pdf_file_path)
            max_font_size = 0.0
            text_info = []

            for so_trang, trang in enumerate(doc):
                text_dict = trang.get_text("dict")

                for block in text_dict["blocks"]:
                    if "lines" in block:
                        for line in block["lines"]:
                            for span in line["spans"]:
                                current_font_size = span["size"]
                                if current_font_size > max_font_size:
                                    max_font_size = current_font_size
                                    text_info = []

                                if current_font_size == max_font_size:
                                    text_info.append({
                                        "text": span["text"],
                                        "page": so_trang + 1,
                                        "size": current_font_size,
                                        "font": span["font"]
                                    })
            doc.close()
            return text_info

        except Exception as e:
            print(f"Có lỗi xảy ra: {e}")
            return None
        
    def get_headings_with_position(self, pdf_file_path, max_check_pages=1, max_candidates=5):
        """
        Lấy ra danh sách heading đầu tiên cùng tọa độ (bbox).
        Args:
            pdf_file_path (str): đường dẫn pdf
            max_check_pages (int): chỉ kiểm tra bao nhiêu trang đầu
            max_candidates (int): số lượng heading đầu tiên cần xét
        Returns:
            list[dict]: [{'text': ..., 'page': ..., 'bbox': (x0,y0,x1,y1)}]
        """
        res = []
        try:
            doc = fitz.open(pdf_file_path)
            for page_index in range(min(max_check_pages, len(doc))):
                page = doc[page_index]
                text_dict = page.get_text("dict")
                for block in text_dict["blocks"]:
                    if "lines" in block:
                        for line in block["lines"]:
                            line_text = " ".join([span["text"] for span in line["spans"]]).strip()
                            if not line_text:
                                continue
                            # chỉ lấy những dòng dài một chút
                            if len(line_text) < 8:
                                continue
                            # bbox line
                            bbox = line["bbox"]  # (x0,y0,x1,y1)
                            res.append({
                                "text": line_text,
                                "page": page_index+1,
                                "bbox": bbox
                            })
                            if len(res) >= max_candidates:
                                return res
            doc.close()
        except Exception as e:
            print(f"Lỗi khi lấy heading với tọa độ: {e}")
        return res

    def decide_file_title(self, pdf_file_path):
        """
        Quyết định file_title dựa vào vị trí heading trong trang đầu.
        Ưu tiên heading nào nằm trong vùng giữa (30% - 60% chiều cao trang).
        """
        candidates = self.get_headings_with_position(pdf_file_path)
        if not candidates:
            return None

        doc = fitz.open(pdf_file_path)
        first_page = doc[0]
        page_height = first_page.rect.height
        doc.close()

        for cand in candidates:
            y0 = cand["bbox"][1]
            y_mid_ratio = y0 / page_height
            if 0.3 <= y_mid_ratio <= 0.6:  # trong vùng giữa trang
                return cand["text"]
        # fallback: lấy heading đầu tiên
        return candidates[0]["text"]
        
    def get_title(self, pdf_file_path):
        text_info = self.get_file_title(pdf_file_path)
        res = []
        for tmp in text_info:
            if tmp['page'] == 1:
                res.append(tmp['text'])
        return res

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
            import tempfile
            self.temp_clean_dir = tempfile.mkdtemp(prefix="pdf_clean_")
        os.makedirs(self.temp_clean_dir, exist_ok=True)

        temp_pdf_path = os.path.join(self.temp_clean_dir, os.path.basename(input_pdf_path))
        os.makedirs(os.path.dirname(temp_pdf_path), exist_ok=True)        

        # loại bỏ footer
        if not self._remove_footer_from_pdf(input_pdf_path, temp_pdf_path):
            print("Lỗi khi loại bỏ footer. Dừng xử lý.")
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
            return []

        # OCR hoặc local parse
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

                # thử lấy title từ font lớn nhất
        pdf_title = self.get_title(input_pdf_path)
        print(f"PDF title (font lớn nhất): {pdf_title}")

        data = []
        current_heading = None
        current_text = []
        first_heading_found = False 
        
        for line in markdown_content.splitlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith("#"):  # heading mới
                if current_heading is not None:
                    data.append({
                        "heading": current_heading,
                        "text": "\n".join(current_text).strip() if current_text else None,
                        "file_title": current_is_title
                    })

                if not first_heading_found:
                    current_is_title = 1
                    first_heading_found = True
                else:
                    current_is_title = 0

                current_heading = line
                current_text = []

            else:
                current_text.append(line)

        if current_heading is not None:
            data.append({
                "heading": current_heading,
                "text": "\n".join(current_text).strip() if current_text else None,
                "file_title": current_is_title
            })

        return data 
    
    def process_folder(self, input_pdf_dir, output_md_dir):
        """
        Xử lý toàn bộ file PDF trong input_pdf_dir (kể cả subfolder),
        và lưu file .md tương ứng trong output_md_dir,
        giữ nguyên cấu trúc folder.
        """
        if not os.path.exists(input_pdf_dir):
            print(f"Thư mục input không tồn tại: {input_pdf_dir}")
            return
        
        for root, dirs, files in os.walk(input_pdf_dir):
            # Tính đường dẫn tương ứng trong output
            relative_path = os.path.relpath(root, input_pdf_dir)
            output_root = os.path.join(output_md_dir, relative_path)
            os.makedirs(output_root, exist_ok=True)

            for file_name in files:
                if not file_name.lower().endswith(".pdf"):
                    continue  # bỏ qua file không phải pdf

                input_path = os.path.join(root, file_name)
                output_path = os.path.join(
                    output_root, 
                    os.path.splitext(file_name)[0] + ".md"
                )

                print(f"\n=== Đang xử lý: {input_path} ===")
                try:
                    data = self.run(input_path, output_path)
                    print(f"-> Hoàn thành: {output_path}, tổng {len(data)} block")
                except Exception as e:
                    print(f"Lỗi khi xử lý {input_path}: {e}")

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

    # input_file = 'data/raw documents/Khuyến mãi/Các chương trình khuyến mãi.pdf'
    # output_file = 'data/markdown/Khuyến mãi/Các chương trình khuyến mãi.md'
    # res = processor.run(input_file, output_file)
    # for i in res:
    #     print(i['heading'])
    #     print(i['text'])
    #     print(f"title: {i['file_title']}")
    #     if i['text'] is not None:
    #         print(len(i['text']))
    #     print('-----------------------------------------------\n')