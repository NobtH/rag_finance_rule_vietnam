import pdfplumber
from PIL import Image
import os

def extract_images_pdfplumber(pdf_path, output_dir="plumber_images"):
    os.makedirs(output_dir, exist_ok=True)

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_w, page_h = page.width, page.height

            for idx, img in enumerate(page.images, start=1):
                # bbox gốc
                x0, top, x1, bottom = img["x0"], img["top"], img["x1"], img["bottom"]

                # clamp để không vượt ra ngoài trang
                x0 = max(0, x0)
                top = max(0, top)
                x1 = min(page_w, x1)
                bottom = min(page_h, bottom)

                bbox = (x0, top, x1, bottom)

                # crop và render
                cropped = page.crop(bbox).to_image(resolution=150)

                out_path = os.path.join(output_dir, f"page{page_number}_img{idx}.png")
                cropped.save(out_path, format="PNG")
                print(f"Đã lưu: {out_path}")

    print(f"Tất cả ảnh đã được lưu trong thư mục: {output_dir}")

extract_images_pdfplumber('data/raw documents/Thẻ/Thẻ/Tín dụng/Quyen_loi_bao_hiem_the_cao_cap.pdf')

