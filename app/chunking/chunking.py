import os
import pandas as pd
import re

class Chunking:
    def __init__(self, mark_down_dir='data/markdown', corpus_out_dir='data', max_chunk_size=500):
        self.mark_down_dir = mark_down_dir
        self.corpus_out_dir = corpus_out_dir
        os.makedirs(self.corpus_out_dir, exist_ok=True)
        self.max_chunk_size = max_chunk_size

    def get_chunking_strategy(self, lines):
        """
        Xác định chiến lược chia chunk ưu tiên nhất cho tài liệu.
        """
        if any(re.match(r'^\s*# *\s*Điều\s+\d+[\.:]?', line, re.IGNORECASE) for line in lines):
            return 'dieu'
        if any(re.match(r'^\s*# *\s*(?=[MDCLXVI]+\b)[MDCLXVI]+\s*[\.:]?', line, re.IGNORECASE) for line in lines):
            return 'roman'
        if any(re.match(r'^\s*# *\s*\d+[\.:]?', line) for line in lines):
            return 'numbered'
        return 'general'
    
    # def llm_chunking()
        
    def chunk_single_md_file(self, md_file_path):
        """
        Chia một file markdown thành các chunk dựa trên cấu trúc tài liệu.
        Không gán 'cid' tại bước này, chỉ trả về các chunk thô.
        """
        print(f'-----Bắt đầu chia chunk file: {md_file_path}')

        with open(md_file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        lines = text.splitlines()
        chunks = []

        # Xác định chiến lược duy nhất cho tài liệu
        chunking_strategy = self.get_chunking_strategy(lines)
        print(f"-> Cấu trúc tài liệu: Dạng '{chunking_strategy}'")

        # Tìm file_topic
        file_topic = None
        for line in lines:
            line = line.strip()
            if (line.startswith('# ') and len(line.split()) > 3) or (line == line.upper() and len(line.split()) > 3):
                file_topic = line.replace('#', '').strip()
                break
        
        # Logic xác định một dòng có phải là tiêu đề hợp lệ không
        def is_new_chunk_start(line, strategy):
            line = line.strip() 
            if strategy == 'dieu':
                # Ví dụ: "Điều 5.", "Điều 10:"
                return re.match(r'^#\s*Điều\s+\d+[\.:]?', line, re.IGNORECASE)
            
            elif strategy == 'roman':
                # Ví dụ: "# I"
                return re.match(r'^#\s*(?=[MDCLXVI]+\b)[MDCLXVI]+\s*[\.:]?', line, re.IGNORECASE)

            elif strategy == 'numbered':
                # Ví dụ: "# 1."
                return re.match(r'^#\s*\d+[\.:]?', line)
            
            elif strategy == 'general':
                # Tiêu đề dạng "# ..." hoặc dòng in HOA dài > 3 từ
                return (line.startswith('# ') or (line == line.upper() and len(line.split()) > 3))

            return False
        
        # Xử lý phần mở đầu và các chunk còn lại
        current_chunk = {'text': '', 'topic': file_topic}
        title_found = False

        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            is_title = is_new_chunk_start(line, chunking_strategy)
            
            if not title_found and not is_title:
                # Gom phần mở đầu
                current_chunk['text'] += line + '\n'
            else:
                title_found = True
                if is_title:
                    if current_chunk['text']:
                        current_chunk['topic'] = file_topic
                        if len(current_chunk['text'].splitlines()) >= 3:
                            chunks.append(current_chunk)
                    
                    current_chunk = {
                        'text': line + '\n'
                    }
                else:
                    current_chunk['text'] += line + '\n'
        
        # Lưu chunk cuối cùng
        if current_chunk['text']:
            current_chunk['topic'] = file_topic
            chunks.append(current_chunk)


        final_chunks = []
        for chunk in chunks:
            if len(chunk['text'].split()) > self.max_chunk_size:
                # Chia nhỏ theo đoạn văn
                paragraphs = chunk['text'].split('\n\n')
                current_small_chunk_text = ""
                for para in paragraphs:
                    if len((current_small_chunk_text + ' ' + para).split()) <= self.max_chunk_size:
                        current_small_chunk_text += '\n\n' + para if current_small_chunk_text else para
                    else:
                        if current_small_chunk_text:
                            final_chunks.append({'text': current_small_chunk_text, 'topic': chunk['topic']})
                        current_small_chunk_text = para
                
                # Thêm chunk nhỏ cuối cùng
                if current_small_chunk_text:
                    final_chunks.append({'text': current_small_chunk_text, 'topic': chunk['topic']})
            else:
                final_chunks.append(chunk)

        print(f'-----Hoàn thành chia chunk file: {md_file_path}. Đã tạo ra {len(final_chunks)} chunks.')
        return final_chunks

    def chunk_all_md_file(self):
        """
        Chia tất cả các file markdown trong thư mục và gộp thành một danh sách.
        """
        all_chunks = []
        for root, _, files in os.walk(self.mark_down_dir):
            for file_name in files:
                if file_name.endswith('.md'):
                    md_file_path = os.path.join(root, file_name)
                    chunks = self.chunk_single_md_file(md_file_path)
                    all_chunks.extend(chunks)
        return all_chunks

    def save_to_csv(self, chunks):
        """
        Tạo DataFrame từ danh sách chunks, thêm cột 'cid' dựa trên chỉ mục và lưu vào CSV.
        """
        if not chunks:
            print("Không có chunks nào để lưu.")
            return

        output_file = os.path.join(self.corpus_out_dir, 'corpus.csv')
        df = pd.DataFrame(chunks)
        
        df.insert(1, 'cid', df.index + 1)

        df = df[['cid', 'topic', 'text']]
        
        df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"-> Đã lưu tất cả chunks vào file: {output_file}")
    
test = Chunking()
res = test.chunk_all_md_file()
test.save_to_csv(res)
