import fitz  # PyMuPDF PDFファイルからテキストや画像を抽出するためのライブラリ。
import os
from flask import Flask, request, redirect, url_for, send_from_directory

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
EXTRACTED_FOLDER = 'extracted'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['EXTRACTED_FOLDER'] = EXTRACTED_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXTRACTED_FOLDER, exist_ok=True)

def extract_text_and_qr(pdf_path):
    document = fitz.open(pdf_path)
    text = ""
    qr_code_images = []

    for page_num in range(len(document)):
        page = document.load_page(page_num)
        text += page.get_text()

        images = page.get_images(full=True)
        for img_index in range(len(images)):
            xref = images[img_index][0]
            base_image = document.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            if image_ext == 'png':
                qr_code_images.append(image_bytes)

    return text, qr_code_images

def save_extracted_content(filename, text, qr_code_images):
    base_filename = os.path.splitext(filename)[0]

    # Save text
    text_path = os.path.join(app.config['EXTRACTED_FOLDER'], f"{base_filename}.txt")
    with open(text_path, "w", encoding="utf-8") as text_file:
        text_file.write(text)

    # Save QR codes
    qr_code_paths = []
    for i, qr_code_image in enumerate(qr_code_images):
        qr_code_path = os.path.join(app.config['EXTRACTED_FOLDER'], f"{base_filename}_qr_{i+1}.png")
        with open(qr_code_path, "wb") as f:
            f.write(qr_code_image)
        qr_code_paths.append(qr_code_path)

    return text_path, qr_code_paths

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            text, qr_code_images = extract_text_and_qr(filepath)
            text_path, qr_code_paths = save_extracted_content(file.filename, text, qr_code_images)
            return {
                "text_file": text_path,
                "qr_code_files": qr_code_paths
            }

    return '''
    <!doctype html>
    <title>Upload PDF</title>
    <h1>Upload PDF to extract text and QR codes</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    '''

@app.route('/extracted/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['EXTRACTED_FOLDER'], filename)

if __name__ == "__main__":
    app.run(debug=True)
