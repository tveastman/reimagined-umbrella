"""
Just print the headers and body of any request sent to it.

I needed this to work out what exactly authlib was sending upstream,
since the error messages from Twitter are completely unhelpful.
"""


from rich import print

import http.server

port = 8001

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        print(self.headers)
        print(self.path)

        self.send_response(200)
        self.send_header("x-hi", "hi")
        self.end_headers()
        self.wfile.write(b"Done, you can close this tab.")

    def do_POST(self):
        print(self.headers)
        print(self.path)
        length = int(self.headers['content-length'])
        field_data = self.rfile.read(length)
        print(field_data)
        self.send_response(200)
        self.send_header("x-hi", "hi")
        self.end_headers()
        self.wfile.write(b"You posted.\n")


server_address = ("127.0.0.1", port)
with http.server.HTTPServer(
        server_address=server_address,
        RequestHandlerClass=Handler,
) as httpd:
    httpd.serve_forever()
