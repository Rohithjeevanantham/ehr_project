# extractor.py
import pdfplumber
from pdf2image import convert_from_path
import cv2
import numpy as np
from paddleocr import PaddleOCR

ocr = PaddleOCR(use_angle_cls=True, lang='en')

def extract_text_from_pdf(pdf_path, output_txt_file):
    extracted_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                extracted_text += f"\n--- Page {page_num + 1} ---\n" + text + "\n"
    if not extracted_text.strip():
        print("⚠ No direct text found! Using OCR...")
        images = convert_from_path(pdf_path)
        for i, img in enumerate(images):
            img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            results = ocr.ocr(img, cls=True)
            ocr_text = "\n".join([line[1][0] for res in results for line in res if line[1]])
            extracted_text += f"\n--- OCR Page {i + 1} ---\n" + ocr_text + "\n"
    with open(output_txt_file, "w", encoding="utf-8") as f:
        f.write(extracted_text)
    return extracted_text
