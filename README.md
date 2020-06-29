## Resize image

For sending image:
* method = 'POST'
* content-type = 'multipart/form-data'
* url = "https://a2qtfu6dtd.execute-api.us-east-1.amazonaws.com/dev/images"
* data = {'width': '10', 'height': '100'}
* data['file'] = open('path/to/your/file.jpg', 'rb')

You will get the response like {'id': N}, where N is integer
***
For geting status of sent image:
* method = 'POST'
* content-type = 'application/json'
* url = "https://a2qtfu6dtd.execute-api.us-east-1.amazonaws.com/dev/status"
* data = {"id": N} N - from response of sending image

You will get the response {'status': 'not_ready'}, if image is not resized  
And the response {'status': 'ready'}, if image is resized
***
For getting resize image:
* method = 'POST'
* content-type = 'application/json'
* url = "https://a2qtfu6dtd.execute-api.us-east-1.amazonaws.com/dev/newimages"
* data = {"id": N} N - from response of sending image

You will get the image if it's resized and message 'Repeat request later, image is not resized' if not
***
