import fitz  # PyMuPDF

doc = fitz.open("복지용구포털사용방법.pdf")  # PDF 열기
for page in doc:
    text = page.get_text()  # 페이지 텍스트 추출
    print(text)