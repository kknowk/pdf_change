import fitz  # PyMuPDF PDFファイルから画像を抽出するためのライブラリ。
import os
import re
import io
from flask import Flask, request, redirect, url_for, send_file
from PIL import Image, ImageDraw, ImageFont, ImageOps
from zipfile import ZipFile

app = Flask(__name__)

# ファイルのアップロードフォルダを設定
BASE_IMAGE_PATH = 'Ticket.png'  # QRコードを貼り付ける画像のパス
FONT_PATH = 'Noto Sans JP/NotoSansJP-VariableFont_wght.ttf'  # 日本語フォントファイルを指定

def extract_fifth_qr(pdf_stream):
    """
    PDFから5個目のQRコード画像を抽出する関数
    """
    document = fitz.open(stream=pdf_stream, filetype="pdf")  # PDFファイルをメモリ上で開く
    qr_code_image = None
    qr_code_count = 0

    for page_num in range(len(document)):  # 各ページを処理
        page = document.load_page(page_num)
        images = page.get_images(full=True)  # ページから画像を取得

        for img_index in range(len(images)):
            xref = images[img_index][0]  # 画像の参照番号を取得
            base_image = document.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            if image_ext == 'png':  # QRコード画像と想定されるPNG画像のみを抽出
                qr_code_count += 1
                if qr_code_count == 5:
                    qr_code_image = image_bytes
                    break
        if qr_code_image:
            break

    return qr_code_image

def add_qr_and_text_to_image(base_image_path, qr_code_image, name, seat, position=None):
    """
    画像にQRコードとテキストを追加する関数
    """
    base_image = Image.open(base_image_path)
    qr_code = Image.open(io.BytesIO(qr_code_image))

    # QRコードを反転（白黒を逆に）
    qr_code = ImageOps.invert(qr_code.convert("RGB"))

    # QRコードを1.5倍に拡大
    qr_code = qr_code.resize((int(qr_code.width * 1.5), int(qr_code.height * 1.5)))

    if position is None:
        # 位置が指定されていない場合、右側の中央より少し上に設定
        position = (base_image.width - qr_code.width - 110, (base_image.height // 2) - qr_code.height // 2)

    base_image.paste(qr_code, position)

    draw = ImageDraw.Draw(base_image)
    font_size = 75  # ここでフォントサイズを指定
    font = ImageFont.truetype(FONT_PATH, font_size)  # フォントファイルとサイズを指定

    # 名前を描画
    name_position = (550, position[1] + qr_code.height + 80)  # QRコードの下にテキストを配置
    draw.text(name_position, name, font=font, fill="white")

    # 座席番号を描画
    seat_position = (position[0] - 40, position[1] + qr_code.height + 80)  # QRコードの下にテキストを配置
    draw.text(seat_position, seat, font=font, fill="black")

    output = io.BytesIO()
    base_image.save(output, format="PNG")
    output.seek(0)

    return output

def convert_image_to_pdf(image_stream):
    """
    画像ストリームをPDFに変換する関数
    """
    image = Image.open(image_stream)
    pdf_bytes = io.BytesIO()
    image.convert('RGB').save(pdf_bytes, format="PDF")
    pdf_bytes.seek(0)
    return pdf_bytes

def parse_filename(filename):
    """
    ファイル名から名前と座席情報を抽出する関数
    """
    name_match = re.search(r'_(.*?)_', filename)
    seat_match = re.search(r'\((.*?)\)', filename)
    
    if name_match and seat_match:
        name = name_match.group(1)
        seat = seat_match.group(1).replace('列', '-')
        seat = f"1階-{seat}"
        return name, seat
    return None, None

def process_pdf(filename, pdf_stream):
    """
    抽出したQRコード画像を使用して画像を生成し、PDFに変換する関数
    """
    name, seat = parse_filename(filename)
    if not name or not seat:
        return None

    qr_code_image = extract_fifth_qr(pdf_stream)
    if not qr_code_image:
        return None

    image_stream = add_qr_and_text_to_image(BASE_IMAGE_PATH, qr_code_image, name, seat)
    pdf_stream = convert_image_to_pdf(image_stream)

    return pdf_stream

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    """
    PDFファイルをアップロードして5個目のQRコードを抽出し、PDFを生成して返すルート
    """
    if request.method == 'POST':
        if 'files[]' not in request.files:
            return redirect(request.url)  # ファイルがない場合はリダイレクト
        files = request.files.getlist('files[]')
        if not files or all(file.filename == '' for file in files):
            return redirect(request.url)  # ファイル名が空の場合はリダイレクト

        zip_buffer = io.BytesIO()
        with ZipFile(zip_buffer, 'w') as zip_file:
            for file in files:
                if file:
                    pdf_stream = process_pdf(file.filename, file.stream.read())  # PDFを生成
                    if pdf_stream:
                        zip_file.writestr(f"{os.path.splitext(file.filename)[0]}.pdf", pdf_stream.read())

        zip_buffer.seek(0)
        return send_file(zip_buffer, as_attachment=True, download_name='converted_files.zip', mimetype='application/zip')

    return '''
    <!doctype html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <title>PDF変換</title>
        <style>
            body {
                font-size: 1.5em;
            }
            input[type="file"], input[type="submit"] {
                font-size: 1.5em;
            }
        </style>
    </head>
    <body>
        <h1>PDF変換</h1>
        <form method=post enctype=multipart/form-data>
            <input type=file name="files[]" multiple>
            <input type=submit value="変換ボタン">
        </form>
    </body>
    </html>
    '''

if __name__ == "__main__":
    app.run(debug=True)  # アプリケーションをデバッグモードで実行
