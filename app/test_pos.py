import fitz

def get_sentence_positions(pdf_path):
    """
    Trích xuất câu và vị trí của chúng từ một tệp PDF.

    Args:
        pdf_path (str): Đường dẫn đến tệp PDF.

    Returns:
        dict: Một từ điển, trong đó khóa là số trang (dựa trên 0),
              và giá trị là một danh sách các tuple (câu, rect),
              trong đó rect là một đối tượng fitz.Rect chứa tọa độ.
    """
    doc = fitz.open(pdf_path)
    all_sentences = {}

    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        
        # Lấy danh sách các từ và tọa độ của chúng.
        # Mỗi từ là một tuple: (x0, y0, x1, y1, "text", ...)
        words = page.get_text("words")
        
        if not words:
            continue

        page_sentences = []
        current_sentence = ""
        current_sentence_rect = fitz.Rect(words[0][:4])

        for i, word in enumerate(words):
            word_text = word[4]
            word_rect = fitz.Rect(word[:4])
            
            # Thêm từ hiện tại vào câu
            if current_sentence:
                current_sentence += " " + word_text
            else:
                current_sentence = word_text
            
            # Mở rộng hộp giới hạn của câu để bao gồm từ hiện tại
            current_sentence_rect.include_rect(word_rect)
            
            # Kiểm tra xem từ hiện tại có kết thúc một câu không (dùng dấu chấm, chấm than, hoặc chấm hỏi)
            if word_text.endswith(('.', '!', '?')):
                page_sentences.append({'text': current_sentence, 'rect': current_sentence_rect})
                # Đặt lại các biến để bắt đầu câu mới
                current_sentence = ""
                if i + 1 < len(words):
                    current_sentence_rect = fitz.Rect(words[i+1][:4])
        
        # Xử lý trường hợp câu cuối cùng trên trang không kết thúc bằng dấu câu
        if current_sentence:
            page_sentences.append({'text': current_sentence, 'rect': current_sentence_rect})

        all_sentences[page_num] = page_sentences

    doc.close()
    return all_sentences

# Ví dụ sử dụng:
pdf_file = "data/raw documents/Tài khoản/Điều khoản và điều kiện mở và sử dụng tài khoản.pdf"  # Thay đổi đường dẫn đến tệp PDF của bạn
sentence_positions = get_sentence_positions(pdf_file)

if sentence_positions:
    first_page_sentences = sentence_positions[0]
    if first_page_sentences:
        first_sentence = first_page_sentences[0]
        print(f"Câu: {first_sentence['text']}")
        print(f"Tọa độ hộp giới hạn: {first_sentence['rect'].x0}, {first_sentence['rect'].y0}, {first_sentence['rect'].x1}, {first_sentence['rect'].y1}")