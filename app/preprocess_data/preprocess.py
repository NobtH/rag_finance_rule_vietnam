import os
import fitz
from llama_parse import LlamaParse
from dotenv import load_dotenv
from llama_index.core import SimpleDirectoryReader
import asyncio
import shutil
from pdf2image import convert_from_path
import pytesseract
import pypandoc
import re
from pdfplumber_preprocess_data import *

load_dotenv()

class PDFprocessor:
    def __init__(self, root_dir='data', footer_height_ratio=0.08):
        self.api_key = os.getenv('LLAMA_PARSE_API_KEY')
        self.root_dir = root_dir
        self.footer_height_ratio = footer_height_ratio
        self.raw_documents_dir = os.path.join(self.root_dir, 'raw_documents')
        self.markdown_dir = os.path.join(self.root_dir, 'markdown')
        self.temp_clean_dir = os.path.join(self.markdown_dir, 'temp_clean')

        os.makedirs(self.raw_documents_dir, exist_ok=True)
        os.makedirs(self.markdown_dir, exist_ok=True)
        os.makedirs(self.temp_clean_dir, exist_ok=True)
        
        # Thêm kiểm tra API key để báo lỗi sớm
        if not self.api_key:
            print("WARNING: LLAMA_PARSE_API_KEY is not set in environment variables.")

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
        print(f"Bắt đầu loại bỏ footer từ các file trong: {self.raw_documents_dir}")
        temp_pdf_files = []
        for root, _, files in os.walk(self.raw_documents_dir):
            for file_name in files:
                if file_name.endswith('.pdf'):
                    original_pdf_path = os.path.join(root, file_name)
                    relative_path = os.path.relpath(original_pdf_path, self.raw_documents_dir)
                    temp_pdf_path = os.path.join(self.temp_clean_dir, relative_path)
                    
                    os.makedirs(os.path.dirname(temp_pdf_path), exist_ok=True)
                    
                    if self._remove_footer_from_pdf(original_pdf_path, temp_pdf_path):
                        temp_pdf_files.append(temp_pdf_path)
        
        return temp_pdf_files
    
    def get_markdown_strategy(self, lines):
        """
        Xác định chiến lược chia chunk ưu tiên nhất cho tài liệu.
        """
        if any(re.match(r'^Điều\s+\d+[\.:]', line, re.IGNORECASE) for line in lines):
            return 'dieu'
        if any(re.match(r'^\s*(?=[MDCLXVI]+\b)[MDCLXVI]+\s*[\.:]', line, re.IGNORECASE) for line in lines):
            return 'roman'
        if any(re.match(r'^\s*\d+[\.:]', line) for line in lines) or any(re.match(r'^\s*\d+\.\s+[a-zA-Z]', line) for line in lines):
            return 'numbered'
        return 'general'
    
    def make_heading(self, lines):
        all_text = ''

        stategy = self.get_markdown_strategy(lines)
        print(stategy)

        for idx, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) <= 5:
                continue

            if idx == 0 and len(line) > 10:
                all_text += f"# {line}\n"
                continue

            if line == line.upper() and re.search(r'[a-zA-ZáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệiíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆIÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ]', line) and len(line) > 20:
                all_text += f"# {line}\n"
            elif stategy == 'dieu':
                if re.match(r'^Điều\s+\d+(\.|:)', line, re.IGNORECASE):
                    all_text += f"# {line} \n"
                else:
                    all_text += f"{line}\n"
            elif stategy == 'roman':
                if re.match(r'^\s*(?=[MDCLXVI]+\b)[MDCLXVI]+\s*[\.:]', line, re.IGNORECASE):
                    all_text += f"# {line} \n"
                else:
                    all_text += f"{line}\n"
            elif stategy == 'numbered':
                if re.match(r'^\s*\d+\s*\.\s*$', line, re.IGNORECASE):
                    all_text += f"# {line} \n"
                elif re.match(r'^\s*\d+\.[a-zA-Z]', line):
                    all_text += f"# {line}\n"
                elif re.match(r'^\s*\d+\.\s+[a-zA-Z]', line):
                    all_text += f"# {line}\n"
                else:
                    all_text += f'{line}\n'
            else:
                all_text += f"{line}\n"            
        return all_text.strip()
    
    async def scanned_pdf_to_markdown(self, pdf_path):
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

    async def turn_pdf_to_markdown_llamaparse(self, pdf_path):
        if not self.api_key:
            print("Lỗi: API key của LlamaParse chưa được cung cấp. Không thể sử dụng LlamaParse.")
            return None
            
        print(f'LlamaParse: Chuyển file {pdf_path} thành dạng markdown bằng LlamaParse...')
        parse = LlamaParse(
            result_type='markdown',
            verbose=True,
            api_key=self.api_key,
            auto_mode=True
        )
        try:
            reader = SimpleDirectoryReader(
                input_files=[pdf_path],
                file_extractor={'.pdf': parse}
            )
            documents = await reader.aload_data()

            all_text = ""

            for doc in documents:
                text = doc.text
                cleaned_text = '\n'.join([line for line in text.splitlines() if line.strip()])
                all_text += cleaned_text + '\n'

            return all_text.strip()
        except Exception as e:
            print(f'Lỗi LlamaParse khi xử lý file {pdf_path}: {e}')
            return None
    
    async def turn_pdf_to_markdown_local(self, pdf_path):
        try:
            print('Chuyen ve md bang local')
            text = extract_content_in_order(pdf_path=pdf_path)

            lines = text.splitlines()

            all_text = self.make_heading(lines)
            return all_text
        except:
            print('Loi khi chuyen ve md local')
            return None

    async def save_markdown(self, temp_pdf_files):
        print("Bắt đầu chuyển đổi các file PDF tạm sang markdown...")
        
        for pdf_file in temp_pdf_files:
            markdown_content = None 
            
            if self.is_scanned_pdf_fitz(pdf_file):
                scaned_pdf_text = await self.scanned_pdf_to_markdown(pdf_file)
                if scaned_pdf_text:
                    markdown_content = "\n".join([line for line in scaned_pdf_text.splitlines() if line.strip()])
            else:
                # llamaparse_text = await self.turn_pdf_to_markdown_llamaparse(pdf_file)
                # if llamaparse_text:
                #     markdown_content = "\n".join([line for line in llamaparse_text.splitlines() if line.strip()])
                tmp_text = await self.turn_pdf_to_markdown_local(pdf_file)
                if tmp_text:
                    markdown_content = "\n".join([line for line in tmp_text.splitlines() if line.strip()])
            
            if markdown_content:
                file_name_without_ext = os.path.splitext(os.path.basename(pdf_file))[0]
                markdown_file_name = f"{file_name_without_ext}.md"
                
                relative_path = os.path.relpath(os.path.dirname(pdf_file), self.temp_clean_dir)
                markdown_folder_path = os.path.join(self.markdown_dir, relative_path)
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

    async def markdown_single_file(self, input_pdf_path, output_md_path):
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
            scanned_text = await self.scanned_pdf_to_markdown(temp_pdf_path)
            if scanned_text:
                markdown_content = "\n".join([line for line in scanned_text.splitlines() if line.strip()])
            else:
                print('Noi dung rong')
        else:
            parsed_text = await self.turn_pdf_to_markdown_llamaparse(temp_pdf_path)
            if parsed_text:
                markdown_content = "\n".join([line for line in parsed_text.splitlines() if line.strip()])

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
    
    async def preprocess_and_save_data(self):
        """
        Hàm chính để xử lý toàn bộ quá trình: loại bỏ footer, chuyển đổi và lưu markdown.
        """
        temp_pdf_files = self.create_temp_pdf()
        await self.save_markdown(temp_pdf_files)

async def main():

    processor = PDFprocessor(root_dir='data') 
    
    await processor.preprocess_and_save_data()
    # await processor.markdown_single_file('data/raw_documents/Tiết kiệm/Thông tin chi tiết các loại tiết kiệm dành cho khách hàng cá nhân.pdf',
    #                                      'data/markdown/Tiết kiệm/Thông tin chi tiết các loại tiết kiệm dành cho khách hàng cá nhân.md')

if __name__ == '__main__':

    asyncio.run(main())

# processor = PDFprocessor(root_dir='data')
# test = processor._remove_footer_from_pdf(in_path='data/raw_documents/Tiết kiệm/Điều khoản, điều kiện về tiền gửi có kỳ hạn.pdf',out_path='data/markdown/temp_clean/test.pdf')
