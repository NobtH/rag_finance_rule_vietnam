import pytesseract
from pdf2image import convert_from_path

images = convert_from_path('data/raw documents/Thẻ/Thẻ/Tín dụng/Platinum American Express/DANH SACH MCC HOAN TIEN 1.pdf')
for image in images:
    text = pytesseract.image_to_string(image, lang='vie')
    print(text)

