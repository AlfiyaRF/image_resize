import unittest
import logging
from psycopg2.extras import RealDictCursor
from PIL import Image
import app
import io
import requests
import json
import base64
from urllib.parse import urlparse, parse_qs
import os

logging.basicConfig(level=logging.DEBUG)

os.environ['PG_CONN_IM'] = os.environ['PG_CONN_IM_TEST']
app.SEND_TO_QUEUE = False

class TestAllowedExtensions(unittest.TestCase):

    def test_response(self):
        data = dict(width=100, height=200)
        data["file"] = (io.BytesIO(), 'birds.jpg')
        client = app.app.test_client()
        response = client.post('/images', data=data, content_type='multipart/form-data')
        logging.info(response.status_code)
        test_response = response.get_json()
        test_id = test_response["id"]
        self.assertIsInstance(test_id, int)
        self.assertEqual(response.status_code, 200)
        res2 = client.get('/status', json=dict(id=test_id))
        self.assertEqual(res2.get_json(), {'status': 'not_ready'})

    def test_save_to_db(self):
        file_name = 'birds.jpg'
        data = dict(width=100, height=200)
        data["file"] = (io.BytesIO(), file_name)
        client = app.app.test_client()
        response = client.post('/images', data=data, content_type='multipart/form-data')
        test_response = response.get_json()
        test_id = test_response["id"]
        conn = app._get_postgres_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM images WHERE id=%s", (test_id,))
        result = cur.fetchone()
        test_name = result['im_name']
        test_width = result['im_width']
        test_height = result['im_height']
        self.assertEqual(test_name, file_name)
        self.assertEqual(test_width, 100)
        self.assertEqual(test_height, 200)

    def test_resize(self):
        data = dict(width=10, height=20)
        data["file"] = (io.BytesIO(), 'demo.png')
        client = app.app.test_client()
        response = client.post('/images', data=data, content_type='multipart/form-data')
        test_response = response.get_json()
        test_id = test_response["id"]

        logging.info(test_response)
        app.resize_img(dict(
            Records=[dict(
                body=json.dumps(test_response)
            )]
        ), None)
        logging.info(test_response)
        client2 = app.app.test_client()
        res2 = client2.get('/status', json=test_response)
        self.assertEqual(res2.get_json(), {"status": "ready"})
        response2 = client2.post('/newimages', json=test_response, content_type='application/json')
        logging.info(response2)
        get_file = response2.data
        im_b = io.BytesIO(get_file)
        im = Image.open(im_b)
        size = im.size
        logging.info(size)

    def test_get_im(self):
        f = open('/Users/Alfiya/Study/cv/АппВелокс/image_resize/birds.jpg','rb')
        filedata = f.read()
        conn = app._get_postgres_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        test_file_name = 'test_file_name.jpg';
        im_mime = 'image/jpeg'
        tw = 100
        th = 100
        cur.execute("""
            INSERT INTO images (id, im_name, im_file, im_mime, im_width, im_height, status) 
            VALUES (DEFAULT, %s, %s, %s, %s, %s, 'ready') RETURNING id
            """, (test_file_name, filedata, im_mime, tw, th))
        result = cur.fetchone()
        conn.commit()
        f.close()
        client = app.app.test_client()
        res = client.post('/newimages', json=dict(id=result['id']))
        self.assertEqual(filedata, res.data)
        self.assertEqual(res.status_code, 200)

    def test_wrong_file(self):
        data = dict(width=100, height=200)
        data["file"] = (io.BytesIO(), 'test.pdf')
        client = app.app.test_client()
        response = client.post('/images', data=data, content_type='multipart/form-data')
        logging.info(response.status_code)
        self.assertEqual(response.status_code, 400)

    def test_not_size(self):
        data = dict()
        data["file"] = (io.BytesIO(), 'demo.png')
        client = app.app.test_client()
        response = client.post('/images', data=data, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 400)

        data2 = dict(width=10, height=0)
        data2["file"] = (io.BytesIO(), 'demo.png')
        client2 = app.app.test_client()
        response2 = client2.post('/images', data=data2, content_type='multipart/form-data')
        self.assertEqual(response2.status_code, 400)

        data3 = dict(width=100)
        data3["file"] = (io.BytesIO(), 'demo.png')
        client3 = app.app.test_client()
        response3 = client3.post('/images', data=data3, content_type='multipart/form-data')
        self.assertEqual(response3.status_code, 400)

if __name__ == '__main__':
    unittest.main()