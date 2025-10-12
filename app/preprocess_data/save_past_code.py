    # def _remove_header_footer_from_pdf(self, in_path, out_path):
    #     doc_in = None
    #     doc_out = None
    #     try:
    #         doc_in = fitz.open(in_path)
    #         doc_out = fitz.open()

    #         for page in doc_in:
    #             page_width, page_height = page.rect.width, page.rect.height

    #             # Vùng header (phía trên cùng)
    #             header_rect = fitz.Rect(
    #                 0,
    #                 0,
    #                 page_width,
    #                 page_height * self.header_height_ratio  # tỉ lệ chiều cao header
    #             )

    #             # Vùng footer (phía dưới cùng)
    #             footer_rect = fitz.Rect(
    #                 0,
    #                 page_height * (1 - self.footer_height_ratio),
    #                 page_width,
    #                 page_height
    #             )

    #             # Tạo trang mới và copy nội dung
    #             page_out = doc_out.new_page(width=page_width, height=page_height)
    #             page_out.show_pdf_page(page_out.rect, doc_in, page.number)

    #             # Thêm vùng cần xoá
    #             page_out.add_redact_annot(header_rect)
    #             page_out.add_redact_annot(footer_rect)

    #             # Áp dụng xoá
    #             page_out.apply_redactions()

    #         doc_out.save(out_path)
    #         print(f"-> Đã lưu file sạch tại: {out_path}")
    #         return True

    #     except Exception as e:
    #         print(f"Lỗi khi xử lý file PDF để cắt header/footer ({in_path}): {e}")
    #         return False
    #     finally:
    #         if doc_in and not doc_in.is_closed:
    #             doc_in.close()
    #         if doc_out and not doc_out.is_closed:
    #             doc_out.close()

def remove_repeated_footer(pages_text: List[str], max_check_lines: int = 5,
                           sim_threshold: float = 0.8, min_ratio: float = 0.6) -> List[str]:
    pages_lines = [txt.splitlines() for txt in pages_text]
    common_foot = find_repeated_lines(pages_lines, from_top=False,
                                      max_check_lines=max_check_lines,
                                      sim_threshold=sim_threshold,
                                      min_ratio=min_ratio)

    cleaned_pages = []
    for lines in pages_lines:
        new_lines = lines[:]
        for cand in common_foot:
            # từ dưới lên
            for i in range(len(new_lines)-1, -1, -1):
                if similar(normalize_line(new_lines[i]), cand) >= sim_threshold:
                    new_lines.pop(i)
                    break
        cleaned_pages.append("\n".join(new_lines))

    return [squeeze_blank_lines(t) for t in cleaned_pages]


def remove_repeated_header(pages_text: List[str], max_check_lines: int = 5,
                           sim_threshold: float = 0.8, min_ratio: float = 0.6) -> List[str]:
    pages_lines = [txt.splitlines() for txt in pages_text]
    common_head = find_repeated_lines(pages_lines, from_top=True,
                                      max_check_lines=max_check_lines,
                                      sim_threshold=sim_threshold,
                                      min_ratio=min_ratio)

    cleaned_pages = []
    for lines in pages_lines:
        new_lines = lines[:]
        for cand in common_head:
            # từ trên xuống
            for i in range(len(new_lines)):
                if similar(normalize_line(new_lines[i]), cand) >= sim_threshold:
                    new_lines.pop(i)
                    break
        cleaned_pages.append("\n".join(new_lines))

    return [squeeze_blank_lines(t) for t in cleaned_pages]


def remove_headers_and_footers(pages_text: List[str], max_check_lines: int = 10,
                                        sim_threshold: float = 0.8, min_ratio: float = 0.6) -> List[str]:
    cleaned = remove_repeated_header(pages_text, max_check_lines, sim_threshold, min_ratio)
    cleaned = remove_repeated_footer(cleaned, max_check_lines, sim_threshold, min_ratio)
    return cleaned
