import fitz # PyMuPDF

def doc_tat_ca_thong_tin_text_pdf(duong_dan_file):
    """
    Đọc và trả về thông tin của tất cả các đoạn text trong một file PDF.

    Args:
        duong_dan_file (str): Đường dẫn đến file PDF.

    Returns:
        list: Danh sách các dictionary chứa thông tin về text, trang, kích thước và font.
              Trả về None nếu có lỗi.
    """
    try:
        doc = fitz.open(duong_dan_file)
        tat_ca_text = []

        # Lặp qua từng trang của tài liệu
        for so_trang, trang in enumerate(doc):
            # Trích xuất thông tin text dưới dạng dictionary
            text_dict = trang.get_text("dict")
            
            # Duyệt qua các khối, dòng và đoạn text
            for block in text_dict["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            # Thu thập thông tin của từng đoạn text (span)
                            thong_tin_span = {
                                "text": span["text"],
                                "page": so_trang + 1,
                                "size": span["size"],
                                "font": span["font"],
                                "bbox": span["bbox"] # Vị trí (x0, y0, x1, y1)
                            }
                            tat_ca_text.append(thong_tin_span)
        doc.close()
        return tat_ca_text

    except Exception as e:
        print(f"Có lỗi xảy ra: {e}")
        return None

# Ví dụ sử dụng
duong_dan_pdf = 'data/raw documents/Khuyến mãi/Các chương trình khuyến mãi.pdf'
thong_tin_full = doc_tat_ca_thong_tin_text_pdf(duong_dan_pdf)

if thong_tin_full:
    print(f"Đã đọc được {len(thong_tin_full)} đoạn text.")
    print("Thông tin của một vài đoạn text đầu tiên:")
    # In ra thông tin của 5 đoạn text đầu tiên để minh họa
    for i in range(len(thong_tin_full)):
        text = thong_tin_full[i]
        print(f"  - Trang {text['page']}, Cỡ: {text['size']:.2f}, Font: {text['font']}, Nội dung: '{text['text']}'")