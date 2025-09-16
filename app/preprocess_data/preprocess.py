import os
import fitz
from dotenv import load_dotenv
import shutil
from pdf2image import convert_from_path
import pytesseract
import re
from table_pdf_to_md import *
from get_pos_func import *
import tempfile
from remove_header_footer_func import *
import json

load_dotenv()

class PDFprocessor:
    def __init__(self, footer_height_ratio=0, header_height_ratio=0):
        self.footer_height_ratio = footer_height_ratio
        self.header_height_ratio = header_height_ratio
        self.input_file = None
        self.output_file = None
        self.temp_clean_dir = None

    def uppercase_ratio(self, line):
        no_space = line.replace(' ', '')
        tokens = re.findall(r'[A-Za-zÀ-Ỹà-ỹ]', line)

        if not tokens:
            return 0.0

        upper_count = sum(1 for ch in tokens if ch.isupper())

        return upper_count/len(tokens) * 100

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
            if len(text.replace(' ','').strip()) < 200:
                return True
            else:
                return False
        except Exception as e:
            print(f"Lỗi khi kiểm tra file {pdf_path}: {e}")
            return True 
        finally:
            if doc and not doc.is_closed:
                doc.close()

    def _remove_header_footer_from_pdf(self, in_path, out_path):
        doc_in = None
        doc_out = None
        try:
            doc_in = fitz.open(in_path)
            doc_out = fitz.open()

            for page in doc_in:
                page_width, page_height = page.rect.width, page.rect.height

                # Vùng header (phía trên cùng)
                header_rect = fitz.Rect(
                    0,
                    0,
                    page_width,
                    page_height * self.header_height_ratio  # tỉ lệ chiều cao header
                )

                # Vùng footer (phía dưới cùng)
                footer_rect = fitz.Rect(
                    0,
                    page_height * (1 - self.footer_height_ratio),
                    page_width,
                    page_height
                )

                # Tạo trang mới và copy nội dung
                page_out = doc_out.new_page(width=page_width, height=page_height)
                page_out.show_pdf_page(page_out.rect, doc_in, page.number)

                # Thêm vùng cần xoá
                page_out.add_redact_annot(header_rect)
                page_out.add_redact_annot(footer_rect)

                # Áp dụng xoá
                page_out.apply_redactions()

            doc_out.save(out_path)
            print(f"-> Đã lưu file sạch tại: {out_path}")
            return True

        except Exception as e:
            print(f"Lỗi khi xử lý file PDF để cắt header/footer ({in_path}): {e}")
            return False
        finally:
            if doc_in and not doc_in.is_closed:
                doc_in.close()
            if doc_out and not doc_out.is_closed:
                doc_out.close()

    def cleanup_temp(self):
        """Xoá toàn bộ thư mục tạm sau khi xử lý xong"""
        if self.temp_clean_dir and os.path.exists(self.temp_clean_dir):
            shutil.rmtree(self.temp_clean_dir, ignore_errors=True)
            print(f"-> Đã xoá thư mục tạm: {self.temp_clean_dir}")
            self.temp_clean_dir = None

    
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
        if any(re.match(r'^\s*#?\s*Mục\s+\d+[\.:]', line, re.IGNORECASE) for line in lines):
            return 'muc'
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
        
        headings = []  # lưu lại heading

        for idx, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) <= 3:
                continue

            marked = False  # gắn cờ: dòng này đã đánh heading chưa?

            # Trường hợp đặc biệt: dòng đầu tiên
            if idx == 0 and len(line) > 10:
                all_text += f"# {line}\n"
                headings.append(line)
                marked = True

            # Case chính theo stategy
            elif stategy in ['dieu', 'muc']:
                m = re.match(r'^(Điều|Mục)\s+\d+(\.|:)', line, re.IGNORECASE)
                if m:
                    all_text += f"# {line}\n"
                    headings.append(line)
                    marked = True
                else:
                    all_text += f"{line}\n"

            elif stategy == 'roman':
                if re.match(r'^\s*(?=[LXVI]+\b)[LXVI]+\s*[\.:]', line) and (not line.replace(' ','').startswith(('-'))):
                    all_text += f"# {line}\n"
                    headings.append(line)
                    marked = True
                else:
                    all_text += f"{line}\n"

            elif stategy == 'numbered':
                m1 = re.match(r'^\s*(\d+)\s*\.(?!\d)\s*$', line)
                m2 = re.match(r'^\s*(\d+)\.(?!\d)\s*(.+)', line)

                if m1:
                    number = int(m1.group(1))
                    if number == tmp_num + 1:
                        all_text += f"# {line}\n"
                        print('num')
                        headings.append(line)
                        tmp_num = number
                        marked = True
                    else:
                        all_text += f"{line}\n"

                elif m2:
                    number = int(m2.group(1))
                    if number == tmp_num + 1:
                        all_text += f"# {line}\n"
                        print('num')
                        headings.append(line)
                        tmp_num = number
                        marked = True
                    else:
                        all_text += f"{line}\n"
                else:
                    all_text += f"{line}\n"

            elif stategy == 'general':
                # với stategy general thì áp dụng luôn rule general
                if self.is_general_heading(line):
                    all_text += f"# {line}\n"
                    headings.append(line)
                    marked = True
                else:
                    all_text += f"{line}\n"
            else:
                all_text += f"{line}\n"

            # 🔁 Nếu chưa đánh heading thì check lại rule general
            if not marked and self.is_general_heading(line):
                # sửa dòng cuối thành heading
                all_text = all_text.rstrip('\n')
                all_text = re.sub(rf"{re.escape(line)}$", f"# {line}", all_text) + "\n"
                headings.append(line)

        # Xử lý đặc biệt cho numbered + heading dài
        if stategy == 'numbered' and headings:
            if all(len(h) > 50 for h in headings):
                def replace_heading(match):
                    line = match.group(0).lstrip("#").strip()
                    if line == line.upper():
                        return f"# {line}"
                    else:
                        return line

                all_text = re.sub(r'^#\s*(.*)', replace_heading, all_text, flags=re.MULTILINE)

        return all_text.strip()


    def is_general_heading(self, line: str) -> bool:
        return (
            self.uppercase_ratio(line) >= 60
            and re.search(r'[A-ZÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ]', line)
            and len(line.replace(' ','')) > 20
            and not line.startswith(('#', '-', '*', '+'))
        )

    def scanned_pdf_to_markdown(self, pdf_path):
        print(f'Tesseract-OCR: Chuyển file scanned {pdf_path} thành dạng markdown')
        try:
            full_lines = []
            page_text = []
            images = convert_from_path(pdf_path)
            for image in images:
                text = pytesseract.image_to_string(image, lang='vie')

                page_text.append(text)

                # lines = text.splitlines()

                # full_lines.extend(lines)
            
            pages = remove_headers_and_footers_v2(page_text, max_check_lines=5)
            for page in pages:
                lines = page.splitlines()
                full_lines.extend(lines)
            all_text = self.make_heading(full_lines)

            return all_text.strip()

        except Exception as e:
            print(f"Lỗi khi thực hiện OCR cho file {pdf_path}: {e}")
            return None
    
    def turn_pdf_to_markdown_local(self, pdf_path):
        try:
            print('Chuyen ve md bang local')
            text = extract_content_in_order(pdf_path=pdf_path, k_lines=5)
            # print(text)

            lines = text.splitlines()

            all_text = self.make_heading(lines)
            # print(all_text)

            return all_text
        except Exception as e:
            print(f'Loi khi chuyen ve md local: {e}')
            return None
        
    def prepare_temp_pdf(self, input_pdf_path):
        """Tạo bản PDF tạm và loại bỏ footer"""
        if not self.temp_clean_dir:
            self.temp_clean_dir = tempfile.mkdtemp(prefix="pdf_clean_")
        os.makedirs(self.temp_clean_dir, exist_ok=True)

        temp_pdf_path = os.path.join(self.temp_clean_dir, os.path.basename(input_pdf_path))
        os.makedirs(os.path.dirname(temp_pdf_path), exist_ok=True)

        if not self._remove_header_footer_from_pdf(input_pdf_path, temp_pdf_path):
            print("Lỗi khi loại bỏ footer. Dừng xử lý.")
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
            return None

        return temp_pdf_path

    def extract_markdown(self, pdf_path):
        """OCR hoặc parse PDF thành Markdown"""
        if not pdf_path:
            return None

        if self.is_scanned_pdf_fitz(pdf_path):
            scanned_text = self.scanned_pdf_to_markdown(pdf_path)
            if scanned_text:
                return "\n".join([line for line in scanned_text.splitlines() if line.strip()])
        else:
            tmp_text = self.turn_pdf_to_markdown_local(pdf_path)
            if tmp_text:
                return "\n".join([line for line in tmp_text.splitlines() if line.strip()])
        return None

    def save_markdown(self, output_md_path, markdown_content):
        """Lưu file markdown ra disk"""
        os.makedirs(os.path.dirname(output_md_path), exist_ok=True)
        try:
            with open(output_md_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            print(f"-> Đã lưu nội dung markdown tại: {output_md_path}")
        except Exception as e:
            print(f"Lỗi khi lưu file markdown {output_md_path}: {e}")

    def split_heading_text(self, markdown_content, temp_pdf_path, input_pdf_path):
        """Tách nội dung Markdown thành danh sách {text, metadata}"""

        cen_text_normalized = self.get_title_with_pos(temp_pdf_path)
        use_first_heading_as_default = not cen_text_normalized
        first_heading_found = False

        all_data = []
        current_heading = None
        current_text = []
        current_is_title = 0

        for line in markdown_content.splitlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith("#"):  # heading mới
                if current_heading is not None:
                    all_data.append({
                        "text": "\n".join(current_text).strip() if current_text else "",
                        "metadata": {
                            "heading": current_heading.replace("#", '').strip(),
                            "is_title": str(current_is_title),
                            "original_filename": os.path.basename(input_pdf_path),
                            "file_type": "pdf",
                        }
                    })

                current_is_title = 0
                heading_text = line.strip("# ").strip()
                heading_text_normalized = re.sub(r'\s+', '', heading_text).lower()

                if use_first_heading_as_default and not first_heading_found:
                    current_is_title = 1
                    first_heading_found = True
                elif heading_text_normalized in cen_text_normalized:
                    current_is_title = 1

                current_heading = line
                current_text = []

            else:
                current_text.append(line)

        if current_heading is not None:
            all_data.append({
                "text": "\n".join(current_text).strip() if current_text else "",
                "metadata": {
                    "heading": current_heading.replace("#", '').strip(),
                    "is_title": str(current_is_title),
                    "original_filename": os.path.basename(input_pdf_path),
                    "file_type": "pdf",
                }
            })

        return all_data

    def merge_headings(self, all_data):
        """Merge heading theo rule"""
        merged_data = []
        i = 0
        while i < len(all_data):
            current_item = all_data[i]

            # CASE 1: is_title=1, không text, +1 không text, +2 có text
            if (current_item["metadata"]["is_title"] == "1" and not current_item["text"]
                and i + 1 < len(all_data) and not all_data[i + 1]["text"]):

                if i + 2 < len(all_data) and all_data[i + 2]["text"]:
                    merged_heading = (current_item["metadata"]["heading"] + " " +
                                      all_data[i + 1]["metadata"]["heading"]).replace('# ', '')
                    merged_item = {
                        "text": "",
                        "metadata": {
                            **current_item["metadata"],
                            "heading": merged_heading
                        }
                    }
                    merged_data.append(merged_item)
                    i += 2
                    continue

            # CASE 2: is_title=0, không có text → gộp với cái dưới
            if current_item["metadata"]["is_title"] == "0" and not current_item["text"]:
                if i + 1 < len(all_data):
                    line = all_data[i + 1]["metadata"]["heading"].replace('# ', '')
                    m1 = re.match(r'^\s*(\d+)\s*\.\s*$', line)
                    m2 = re.match(r'^\s*(\d+)\.\s*(.+)', line)
                    m3 = re.match(r'^Điều\s+\d+(\.|:)', line, re.IGNORECASE)
                    m4 = re.match(r'^\s*(?=[LXVI]+\b)[LXVI]+\s*[\.:]', line)
                    m5 = re.match(r'^Mục\s+\d+(\.|:)', line, re.IGNORECASE)

                    # print(line)

                    if not (m1 or m2 or m3 or m4 or m5):
                        merged_heading = (current_item["metadata"]["heading"] + " " +
                                        all_data[i + 1]["metadata"]["heading"]).replace('# ', '')
                        merged_item = {
                            "text": all_data[i + 1]["text"],
                            "metadata": {
                                **all_data[i + 1]["metadata"],
                                "heading": merged_heading
                            }
                        }
                        merged_data.append(merged_item)
                        i += 2
                        continue

            merged_data.append(current_item)
            i += 1

        return merged_data
    
    def run(self, input_pdf_path, output_md_path=None):
        print(f"Bắt đầu xử lý file: {input_pdf_path}")
        temp_pdf_path = self.prepare_temp_pdf(input_pdf_path)
        if not temp_pdf_path:
            return []

        try:
            markdown_content = self.extract_markdown(temp_pdf_path)
            if not markdown_content:
                print("Không có nội dung markdown.")
                return []

            # Lấy số trang
            num_pages = self.get_num_pages(temp_pdf_path)

            # Nếu PDF > 2 trang → xử lý bình thường
            # if num_pages > 2:
            if output_md_path:
                self.save_markdown(output_md_path, markdown_content)

            all_data = self.split_heading_text(markdown_content, temp_pdf_path, input_pdf_path)
            merged_data = self.merge_headings(all_data)
            return merged_data
        
         # # Nếu PDF ≤ 2 trang → chỉ lấy file_title từ heading is_title=1
            # all_data = self.split_heading_text(markdown_content, temp_pdf_path, input_pdf_path)

            # file_title_parts = []
            # merged_texts = []

            # for item in all_data:
            #     if item["metadata"]["is_title"] == "1":
            #         clean_heading = item["metadata"]["heading"].replace("#", "").strip()
            #         if clean_heading:
            #             file_title_parts.append(clean_heading)
            #         if item["text"]:
            #             merged_texts.append(item["text"])
            #     else:
            #         tmp_text = item['metadata']['heading'].replace('# ','').strip() + '\n' + item['text']
            #         if tmp_text:
            #             merged_texts.append(tmp_text)

            # file_title = " - ".join(file_title_parts) if file_title_parts else os.path.basename(input_pdf_path)
            # merged_text = "\n".join(merged_texts).strip()

            # # Ghi lại markdown đã chỉnh sửa
            # fixed_markdown = f"# {file_title}\n\n{merged_text}" if merged_text else f"# {file_title}"

            # if output_md_path:
            #     self.save_markdown(output_md_path, fixed_markdown)

            # data = [{
            #     "text": merged_text,
            #     "metadata": {
            #         "heading": file_title.replace('#', '').strip(),
            #         "is_title": "1",
            #         "original_filename": os.path.basename(input_pdf_path),
            #         "file_type": "pdf",
            #     }
            # }]

            # return data

        finally:
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
                print(f"-> Đã xoá file tạm: {temp_pdf_path}")


    def process_folder(self, input_pdf_dir, output_md_dir, output_json_path="all_data.json", generate_md=True):
        if not os.path.exists(input_pdf_dir):
            print(f"Thư mục input không tồn tại: {input_pdf_dir}")
            return

        all_data = []

        for root, dirs, files in os.walk(input_pdf_dir):
            relative_path = os.path.relpath(root, input_pdf_dir)

            for file_name in files:
                if not file_name.lower().endswith(".pdf"):
                    continue

                input_path = os.path.join(root, file_name)
                base_name = os.path.splitext(file_name)[0]
                output_md_path = os.path.join(output_md_dir, relative_path, base_name + ".md")

                if generate_md:
                    os.makedirs(os.path.dirname(output_md_path), exist_ok=True)

                print(f"\n=== Đang xử lý: {input_path} ===")
                try:
                    data = self.run(
                        input_path, 
                        output_md_path if generate_md else None, 
                    )

                    all_data.extend(data)
                    print(f"-> Hoàn thành {file_name}, tổng {len(data)} block")
                except Exception as e:
                    print(f"Lỗi khi xử lý {input_path}: {e}")

        # Lưu JSON cuối cùng
        final_json_path = os.path.join(output_md_dir, output_json_path)
        os.makedirs(output_md_dir, exist_ok=True)
        with open(final_json_path, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

        print(f"\n>>> Đã lưu toàn bộ dữ liệu JSON vào: {final_json_path}, tổng {len(all_data)} block")

        if self.temp_clean_dir and os.path.exists(self.temp_clean_dir):
            shutil.rmtree(self.temp_clean_dir, ignore_errors=True)
            print(f"-> Đã xoá thư mục tạm: {self.temp_clean_dir}")
            self.temp_clean_dir = None

        return all_data

    def preprocess_and_save_data(self, input_folder_dir, output_folder_dir, generate_md=False):
        # Nếu generate_md thì có thể muốn copy json file gốc
        if generate_md:
            self.copy_json_file(input_folder_dir, output_folder_dir)
        data = self.process_folder(input_folder_dir, output_folder_dir, generate_md=generate_md)
        return data

if __name__ == '__main__':
    processor = PDFprocessor()
    # print(processor.uppercase_ratio('# - Ngoại tệ: EUR, USD, AUD, CAD, CHF, GBP, JPY, SGD: 0%năm.'))

    # Cho folder
    data = processor.preprocess_and_save_data("data/raw documents", "data/markdown", generate_md=True)
    # for i in data:
    #     if i['metadata']['heading'] == 1:
    #         print(i['metadata']['original_filename'])
    #         print(i['metadata']['heading'])
    #         print(i['metadata']['is_title'])
    #         print('-' * 80)

    # Cho file

    # input_file = 'data/raw documents/Cài đặt/DIEU KHOAN CHUNG VE BAO VE VA XU LY DU LIEU CA NHAN.pdf'
    # output_file = 'data/raw documents/Cài đặt/DIEU KHOAN CHUNG VE BAO VE VA XU LY DU LIEU CA NHAN.pdf.md'
    # input_file = 'data/raw documents/Thẻ/Thẻ/Tín dụng/Sacombank Visa Signature/Quyen_loi_bao_hiem_the_cao_cap (1).pdf'
    # output_file = 'data/raw documents/Thẻ/Thẻ/Tín dụng/Sacombank Visa Signature/Quyen_loi_bao_hiem_the_cao_cap (1).pdf.md'
    # input_file = 'data/raw documents/Tiết kiệm/Điều khoản và điều kiện mở và sử dụng tiết kiệm tích góp siêu linh hoạt.pdf'
    # output_file = 'data/raw documents/Tiết kiệm/Điều khoản và điều kiện mở và sử dụng tiết kiệm tích góp siêu linh hoạt.pdf.md'
    
    # print('start')
    # res = processor.run(input_file, output_file)
    # for i in res:
    #     print(i['metadata']['heading'])

    #     print(i['metadata']['is_title'])
    #     # print(i['text'])
    #     print('------------------------------------------------------------------\n')