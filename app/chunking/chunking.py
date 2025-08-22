import os
import pandas as pd
import re
import tiktoken
import json

class Chunking:
    def __init__(self, mark_down_dir='data/markdown', corpus_out_dir='data', max_chunk_size=600):
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
    
    def split_text_by_size(self, text, topic, metadata):
        """
        Chia text thành các chunk, ưu tiên cắt tại '.\n' gần giới hạn từ nhất.
        """
        word_spans = [m.span() for m in re.finditer(r'\S+', text)]
        total_words = len(word_spans)
        final_chunks = []

        start_word = 0
        start_char = 0  # vị trí char bắt đầu cho chunk hiện tại

        # Nếu không có từ (ví dụ file chỉ là newline / whitespace) -> trả nguyên text
        if total_words == 0:
            if text:
                final_chunks.append({'text': text, 'topic': topic, 'metadata': metadata})
            return final_chunks

        while start_word < total_words:
            remaining = total_words - start_word
            # nếu còn ít hơn giới hạn thì lấy hết phần còn lại
            if remaining <= self.max_chunk_size:
                chunk_text = text[start_char:]
                final_chunks.append({'text': chunk_text, 'topic': topic, 'metadata': metadata})
                break

            end_word = start_word + self.max_chunk_size
            end_char = word_spans[end_word - 1][1]  # vị trí char kết thúc của từ cuối trong cửa sổ

            # đảm bảo end_char > start_char
            if end_char <= start_char:
                end_char = start_char + 1

            segment = text[start_char:end_char]

            # tìm ranh giới ưu tiên (ưu tiên dấu câu kết + newline)
            cut_pos = -1
            for delim in ('.\n', '!\n', '?\n', '.\r\n', '\n\n', '\r\n'):
                idx = segment.rfind(delim)
                if idx != -1:
                    cut_pos = start_char + idx + len(delim)
                    break

            # fallback: tìm newline cuối cùng trong đoạn
            if cut_pos == -1:
                idx = segment.rfind('\n')
                if idx != -1:
                    cut_pos = start_char + idx + 1  # bao gồm '\n'

            # nếu vẫn chưa có thì cắt tại end_char (last resort)
            if cut_pos == -1:
                cut_pos = end_char

            chunk_text = text[start_char:cut_pos]

            # đảm bảo chunk không rỗng (tránh loop)
            if not chunk_text.strip():
                # nếu rỗng thì cắt tại end_char
                cut_pos = end_char
                chunk_text = text[start_char:cut_pos]
                # nếu vẫn rỗng -> break để tránh infinite loop
                if not chunk_text.strip():
                    break

            final_chunks.append({'text': chunk_text, 'topic': topic, 'metadata': metadata})

            # cập nhật start_word sao cho span[0] >= cut_pos
            new_start = start_word
            while new_start < total_words and word_spans[new_start][0] < cut_pos:
                new_start += 1

            # cập nhật start_char cho lần tiếp theo (giữ nguyên newline nếu có)
            start_char = cut_pos

            # an toàn: nếu new_start không tiến triển, nhảy qua end_word để tránh loop
            if new_start == start_word:
                new_start = end_word
                # cập nhật start_char theo vị trí kết thúc của từ mới (nếu có)
                if new_start - 1 < total_words:
                    start_char = word_spans[new_start - 1][1]

            start_word = new_start

        return final_chunks
    
    def extract_file_topic(self, lines):
        """
        Trích xuất 'file_topic' từ danh sách các dòng văn bản.
        Tiêu chí:
        - Dòng bắt đầu bằng '# ' và có hơn 3 từ, hoặc
        - Dòng viết HOA hoàn toàn và có hơn 3 từ.
        """
        for line in lines:
            stripped = line.strip()
            if (stripped.startswith('# ') and len(stripped.split()) > 3) or (
                stripped == stripped.upper() and len(stripped.split()) > 3
            ):
                return stripped.replace('#', '').strip()
        return None

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

        file_topic = self.extract_file_topic(lines)

        json_file_path = os.path.splitext(md_file_path)[0] + '.pdf.json'

        metadata = None
        if os.path.exists(json_file_path):
            try:
                with open(json_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data:
                        metadata = json.dumps(data, ensure_ascii=False)
                    else:
                        metadata = None
            except:
                print(f'Loi doc metadata tu file {json_file_path}')
        
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
        current_chunk = {'text': '', 'topic': file_topic, 'metadata': metadata}
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
                    if 'tmp_chunk' in locals() and tmp_chunk:
                        current_chunk['text'] = tmp_chunk['text'] + current_chunk['text']
                        tmp_chunk = None

                    if current_chunk['text']:
                        current_chunk['topic'] = file_topic

                        if len(current_chunk['text'].splitlines()) >= 4 and len(current_chunk['text']) > 40:
                            chunks.append(current_chunk)
                        else: 
                            tmp_chunk = current_chunk
                    
                    current_chunk = {
                        'text': line + '\n',
                        'topic': file_topic,
                        'metadata': metadata
                    }
                    # print(current_chunk['metadata'])
                else:
                    current_chunk['text'] += line + '\n'
        
        # Lưu chunk cuối cùng
        if current_chunk['text']:
            current_chunk['topic'] = file_topic
            chunks.append(current_chunk)


        final_chunks = []
        for chunk in chunks:
            if len(chunk['text'].split()) > self.max_chunk_size:
                final_chunks.extend(self.split_text_by_size(chunk['text'], chunk['topic'], chunk['metadata']))
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

        df = df[['cid', 'topic', 'text', 'metadata']]
        
        df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"-> Đã lưu tất cả chunks vào file: {output_file}")
    