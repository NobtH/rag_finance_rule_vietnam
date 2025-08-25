import os
import fitz
from dotenv import load_dotenv
from llama_index.core import SimpleDirectoryReader
import asyncio
import shutil
from pdf2image import convert_from_path
import pytesseract
import pypandoc
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

    def create_temp_pdf(self):
        print(f"Bắt đầu loại bỏ footer từ các file trong: {self.input_file}")
        temp_pdf_files = []
        for root, _, files in os.walk(self.output_file):
            for file_name in files:
                if file_name.endswith('.pdf'):
                    original_pdf_path = os.path.join(root, file_name)
                    relative_path = os.path.relpath(original_pdf_path, self.input_file)
                    temp_pdf_path = os.path.join(self.temp_clean_dir, relative_path)
                    
                    os.makedirs(os.path.dirname(temp_pdf_path), exist_ok=True)
                    
                    if self._remove_footer_from_pdf(original_pdf_path, temp_pdf_path):
                        temp_pdf_files.append(temp_pdf_path)
        
        return temp_pdf_files
    
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

                    if line == line.upper() and re.search(r'[a-zA-ZáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệiíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆIÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ]', line):
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

    def save_markdown(self, temp_pdf_files):
        print("Bắt đầu chuyển đổi các file PDF tạm sang markdown...")
        
        for pdf_file in temp_pdf_files:
            markdown_content = None 
            
            if self.is_scanned_pdf_fitz(pdf_file):
                scaned_pdf_text =  self.scanned_pdf_to_markdown(pdf_file)
                if scaned_pdf_text:
                    markdown_content = "\n".join([line for line in scaned_pdf_text.splitlines() if line.strip()])
            else:
                tmp_text =  self.turn_pdf_to_markdown_local(pdf_file)
                if tmp_text:
                    markdown_content = "\n".join([line for line in tmp_text.splitlines() if line.strip()])
            
            if markdown_content:
                file_name_without_ext = os.path.splitext(os.path.basename(pdf_file))[0]
                markdown_file_name = f"{file_name_without_ext}.md"
                
                relative_path = os.path.relpath(os.path.dirname(pdf_file), self.temp_clean_dir)
                markdown_folder_path = os.path.join(self.output_file, relative_path)
                os.makedirs(markdown_folder_path, exist_ok=True)
                
                markdown_output_path = os.path.join(markdown_folder_path, markdown_file_name)
                
                try:
                    with open(markdown_output_path, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    print(f"-> Đã lưu nội dung markdown tại: {markdown_output_path}")
                except Exception as e:
                    print(f"Lỗi khi lưu file markdown {markdown_output_path}: {e}")
            else:
                print(f"Không có nội dung markdown được tạo cho file: {pdf_file}")
        
        if os.path.exists(self.temp_clean_dir):
            shutil.rmtree(self.temp_clean_dir)
            print(f"-> Đã dọn dẹp thư mục tạm: {self.temp_clean_dir}")

    def copy_json_file(self):
        for root, _, files in os.walk(self.input_file):
            for file_name in files:
                if file_name.endswith('.json'):
                    original_json_path = os.path.join(root, file_name)
                    relative_path = os.path.relpath(original_json_path, self.input_file)
                    output_json_path = os.path.join(self.output_file, relative_path)

                    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
                    
                    try:
                        shutil.copy(original_json_path, output_json_path)
                        print(f"-> Đã sao chép: {original_json_path} -> {output_json_path}")
                    except Exception as e:
                        print(f"Lỗi khi sao chép file {original_json_path}: {e}")

    def markdown_single_file(self, input_pdf_path, output_md_path):
        self.input_file = input_pdf_path
        self.output_file = output_md_path
        print(f"Bắt đầu xử lý file: {input_pdf_path}")
        
        os.makedirs(os.path.dirname(output_md_path), exist_ok=True)
        
        temp_pdf_path = os.path.join(self.temp_clean_dir, os.path.basename(input_pdf_path))
        print(temp_pdf_path)
        os.makedirs(os.path.dirname(temp_pdf_path), exist_ok=True)
        
        if not self._remove_footer_from_pdf(input_pdf_path, temp_pdf_path):
            print("Lỗi khi loại bỏ footer. Dừng xử lý.")
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
            return

        markdown_content = None

        if self.is_scanned_pdf_fitz(temp_pdf_path):
            scanned_text =  self.scanned_pdf_to_markdown(temp_pdf_path)
            if scanned_text:
                markdown_content = "\n".join([line for line in scanned_text.splitlines() if line.strip()])
            else:
                print('Noi dung rong')
        else:
            tmp_text = self.turn_pdf_to_markdown_local(temp_pdf_path)
            if tmp_text:
                markdown_content = "\n".join([line for line in tmp_text.splitlines() if line.strip()])

        if markdown_content:
            try:
                with open(output_md_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                print(f"-> Đã lưu nội dung markdown tại: {output_md_path}")
            except Exception as e:
                print(f"Lỗi khi lưu file markdown: {e}")
        else:
            print("Không thể chuyển đổi file sang markdown.")

        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
            print(f"-> Đã xóa file tạm: {temp_pdf_path}")
    
    def run(self, input_pdf_path, output_md_path):
        self.input_file = input_pdf_path
        self.output_file = output_md_path
        print(f"Bắt đầu xử lý file: {input_pdf_path}")
        
        # tạo thư mục tạm nếu chưa có
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

        # tách heading và text
        data = []
        current_heading = None
        current_text = []

        for line in markdown_content.splitlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith("#"):  # heading mới
                if current_heading is not None:
                    data.append({
                        "heading": current_heading,
                        "text": "\n".join(current_text).strip() if current_text else None
                    })
                current_heading = line
                current_text = []
            else:
                current_text.append(line)

        if current_heading is not None:
            data.append({
                "heading": current_heading,
                "text": "\n".join(current_text).strip() if current_text else None
            })

        return data

    def preprocess_and_save_data(self):
        """
        Hàm chính để xử lý toàn bộ quá trình: loại bỏ footer, chuyển đổi và lưu markdown.
        """
        self.copy_json_file()
        temp_pdf_files = self.create_temp_pdf()

        self.save_markdown(temp_pdf_files)

# async def main():

#     processor = PDFprocessor(root_dir='data') 
    
#     processor.preprocess_and_save_data()
#     # await processor.markdown_single_file('data/raw documents/Tài khoản/Điều khoản và điều kiện mở và sử dụng tài khoản.pdf',
#     #                                      'data/markdown/Tài khoản/Điều khoản và điều kiện mở và sử dụng tài khoản.md')

if __name__ == '__main__':
    processor = PDFprocessor()
    # processor.preprocess_and_save_data()
    input_file = 'data/raw documents/Tài khoản/Hành vi không được thực hiện-TKTT&thẻ.pdf'
    output_file = 'data/markdown/Tài khoản/Hành vi không được thực hiện-TKTT&thẻ.md'
    res = processor.run(input_file, output_file)
    for i in res:
        print(i['heading'])
        print(i['text'])
        print(len(i['text']))

        print('\n-----------------------------------------------\n')
        

# processor = PDFprocessor(root_dir='data')
# test = processor._remove_footer_from_pdf(in_path='data/raw_documents/Tiết kiệm/Điều khoản, điều kiện về tiền gửi có kỳ hạn.pdf',out_path='data/markdown/temp_clean/test.pdf')
