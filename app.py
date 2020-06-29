import os
from flask import Flask, request, send_file
from werkzeug.utils import secure_filename
import psycopg2
from psycopg2.extras import RealDictCursor
from PIL import Image
import logging
import io
import json
import boto3

logging.getLogger('boto').setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
ALLOWED_MIME = {'image/jpeg', 'image/png'}
RESULT_PATH = os.path.dirname(os.path.abspath(__file__)) + '/im/'

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

SEND_TO_QUEUE = True

def _get_postgres_conn():
    conn_uri = os.environ['PG_CONN_IM']
    return psycopg2.connect(conn_uri)

def allowed_ext(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_mime(filemime):
    return filemime in ALLOWED_MIME

@app.route('/images', methods=['POST'])
def index():
    logging.info(request)
    logging.info(request.form)

    if 'file' not in request.files:
        return 'No file part', 400
    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400
    if not file or not allowed_ext(file.filename) or not allowed_mime(file.mimetype):
        return 'Not allowed', 400
    if 'width' not in request.form or 'height' not in request.form:
        return 'No size part', 400
    filewidth = request.form['width']
    fileheight = request.form['height']
    if int(filewidth) not in range(1, 9999) or int(fileheight) not in range(1, 9999):
        return 'Not allowed size', 400
    logging.info(file)
    logging.info(file.mimetype)
    filename = secure_filename(file.filename)
    f = open(filename,'rb')
    filedata = f.read()
    filemime = file.mimetype
    conn = _get_postgres_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        INSERT INTO images (id, im_name, im_file, im_mime, im_width, im_height, status) 
        VALUES (DEFAULT, %s, %s, %s, %s, %s, 'not_ready') RETURNING id
        """, (filename, filedata, filemime, filewidth, fileheight))
    result = cur.fetchone()
    conn.commit()
    msg_body = json.dumps(dict(id=result['id']))
    if SEND_TO_QUEUE is False:
        return result

    sqs = boto3.resource('sqs')
    queue = sqs.get_queue_by_name(QueueName='images_queue.fifo')
    response = queue.send_message(MessageBody=msg_body, MessageGroupId='resize-group')

    if response['ResponseMetadata']['HTTPStatusCode'] != 200:
        logging.error('Cannot send to queue: %s', response)
        return json.dumps(dict(error="Cannot add to queue"))

    return result

import time
def resize_img(event, context):
    body = event['Records'][0]["body"]
    time.sleep(15)
    try:
        json_data = json.loads(body)
    except ValueError as e:
        logging.error("Error decoding data: %s %s", body, e)
        return False
    im_id = json_data['id']
    conn = _get_postgres_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM images WHERE id=%s", (im_id,))
    result = cur.fetchone()
    im_file = result['im_file']
    im_name = result['im_name']
    im_mime = result['im_mime']
    im_width = result['im_width']
    im_height = result['im_height']
    im_b = io.BytesIO(im_file.tobytes())
    im = Image.open(im_b)
    res_im = im.resize((im_width, im_height))
    buffer = io.BytesIO()
    if im_mime == 'image/jpeg':
        res_im.save(buffer, format='JPEG')
    if im_mime == 'image/png':
        res_im.save(buffer, format='PNG')
    new_im_file = buffer.getvalue()
    w = str(im_width)
    h = str(im_height)
    new_im_name = '_'.join([w, h, im_name])
    conn = _get_postgres_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        UPDATE images SET im_name = %s, im_file = %s, status = 'ready' 
        WHERE id=%s
        """, (new_im_name, new_im_file, im_id))
    conn.commit()

@app.route('/newimages', methods=['GET', 'POST'])
def get_im():
    data = request.get_json()
    if 'id' not in data:
        return "No id part", 400
    im_id = data['id']
    logging.info(im_id)
    logging.info(not im_id)
    if not im_id:
        return 'Invalid request', 400
    conn = _get_postgres_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM images WHERE id=%s", (im_id, ))
    result = cur.fetchone()
    if result is None:
        return 'Not found', 404
    img_status = result['status']
    if img_status == 'not_ready':
        return 'Repeat request later, image is not resized', 404
    img_file = result['im_file']
    img_mime = result['im_mime']
    return send_file(io.BytesIO(img_file.tobytes()), mimetype=img_mime)

@app.route('/status', methods=['GET', 'POST'])
def get_status():
    data = request.get_json()
    if not data or 'id' not in data:
        return "No id part", 400
    im_id = data['id']
    if not im_id:
        return 'Invalid request', 400
    conn = _get_postgres_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT status FROM images WHERE id=%s", (im_id, ))
    result = cur.fetchone()
    if result:
        return dict(status=result['status'])
    else: 
        return "Not found", 404
