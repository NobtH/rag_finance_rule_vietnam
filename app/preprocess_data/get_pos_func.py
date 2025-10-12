import fitz  

def get_first_lines_with_coords(pdf_path, num_lines=10):
    """
    Trích xuất nội dung văn bản và tọa độ của các dòng đầu tiên trong file PDF.
    Args:
        pdf_path (str): Đường dẫn đến file PDF.
        num_lines (int): Số dòng cần lấy. Mặc định là 10.
    Returns:
        list: Một danh sách các tuple, mỗi tuple chứa (text, coordinates).
              'text' là nội dung của dòng.
              'coordinates' là một tuple (x0, y0, x1, y1) biểu thị tọa độ của dòng.
    """
    lines_with_coords = []
    
    try:
        # Mở file PDF
        doc = fitz.open(pdf_path)
        
        # Chỉ làm việc với trang đầu tiên
        page = doc.load_page(0)
        
        # Trích xuất văn bản dưới dạng các từ có tọa độ
        words = page.get_text("words")
        
        # Sắp xếp các từ theo trục Y (dòng) và sau đó là trục X (thứ tự trong dòng)
        words.sort(key=lambda w: (w[3], w[0]))
        
        current_line_y = -1
        current_line_text = ""
        current_line_coords = None
        line_count = 0
        
        for word in words:
            word_y = word[3]  # Lấy tọa độ y1 của từ
            
            # Kiểm tra xem có phải là dòng mới không (sự thay đổi đáng kể về trục Y)
            if abs(word_y - current_line_y) > 2 or current_line_y == -1:
                # Nếu không phải là dòng đầu tiên, lưu dòng trước đó vào danh sách
                if current_line_text and line_count < num_lines:
                    lines_with_coords.append((current_line_text.strip(), current_line_coords))
                    line_count += 1
                
                # Bắt đầu một dòng mới
                current_line_text = word[4]  # Nội dung của từ
                current_line_coords = (word[0], word[1], word[2], word[3]) # Tọa độ của từ
                current_line_y = word_y
            else:
                # Nếu vẫn trên cùng một dòng, nối văn bản và cập nhật tọa độ
                current_line_text += " " + word[4]
                # Cập nhật tọa độ của dòng bằng cách mở rộng giới hạn
                x0 = min(current_line_coords[0], word[0])
                y0 = min(current_line_coords[1], word[1])
                x1 = max(current_line_coords[2], word[2])
                y1 = max(current_line_coords[3], word[3])
                current_line_coords = (x0, y0, x1, y1)

            # Đã đủ số dòng thì dừng lại
            if line_count >= num_lines:
                break
        
        # Thêm dòng cuối cùng vào danh sách
        if current_line_text and line_count < num_lines:
            lines_with_coords.append((current_line_text.strip(), current_line_coords))

        doc.close()
        return lines_with_coords
        
    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file tại đường dẫn {pdf_path}")
        return None
    except Exception as e:
        print(f"Đã xảy ra lỗi: {e}")
        return None

def extract_indented_lines(lines_data):
    """
    Lọc và trích xuất các dòng có vị trí thụt vào.
    Args:
        lines_data (list): Danh sách các tuple (văn bản, tọa độ).
    Returns:
        list: Danh sách các tuple (văn bản, tọa độ) của các dòng thụt vào.
    """
    if not lines_data:
        return []

    # Lấy tọa độ x0 của tất cả các dòng
    x0_values = [line[1][0] for line in lines_data]
    
    # Tìm tọa độ x0 nhỏ nhất, đây sẽ là lề chuẩn
    min_x0 = min(x0_values)
    
    # Một ngưỡng nhỏ để xử lý sai số của số thực
    epsilon = 10 

    indented_lines = []
    
    # Duyệt qua các dòng và kiểm tra điều kiện
    for line in lines_data:
        text, coords = line
        x0 = coords[0]
        
        # Nếu x0 của dòng lớn hơn x0 nhỏ nhất một chút
        if x0 > min_x0 + epsilon:
            indented_lines.append(line)
            
    return indented_lines

pdf_file_path = "data/raw documents/Khuyến mãi/Các chương trình khuyến mãi.pdf"

if __name__ == "__main__":
    # Bước 1: Lấy 10 dòng đầu tiên với tọa độ
    all_lines = get_first_lines_with_coords(pdf_file_path, num_lines=12)

    if all_lines:
        print("--------------------------------------------------")
        print("Tất cả 10 dòng đầu tiên được trích xuất:")
        print("--------------------------------------------------")
        for i, (text, coords) in enumerate(all_lines):
            print(f"Dòng {i+1}: '{text}' -> Tọa độ: {coords}")
        
        # Bước 2: Lọc các dòng bị thụt vào từ danh sách đã trích xuất
        indented_lines_result = extract_indented_lines(all_lines)
        
        print("\n--------------------------------------------------")
        print("Các dòng có vị trí thụt vào:")
        print("--------------------------------------------------")
        if indented_lines_result:
            for text, coords in indented_lines_result:
                print(f"{text}\n")
        else:
            print("Không tìm thấy dòng nào thụt vào trong dữ liệu.")
    else:
        print("Không thể trích xuất dữ liệu từ file PDF.")