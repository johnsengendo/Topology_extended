#!/bin/env python3
# -*- coding: utf-8 -*-

# Importing necessary libraries
import http.server
import socketserver

# Setting the port number and maximum number of requests to serve
PORT = 8000
MAX_REQUESTS = 10

"""
The global variable request_count keeps track of the number of requests served by the server.
It is initialized to 0 and increments each time a request is handled.
"""
request_count = 0

# Defining a custom TCP server that allows address reuse
class LimitedRequestHTTPServer(socketserver.TCPServer):
    # This flag will allow the server to shut down after handling a certain number of requests
    allow_reuse_address = True

"""
LimitedRequestHandler is a custom HTTP request handler that serves a maximum number of requests
and subsequently shuts down the server.
It inherits from the http.server.SimpleHTTPRequestHandler class and overrides the do_GET method.
The do_GET method is invoked whenever a GET request is received.
"""
class LimitedRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global request_count
        request_count += 1
        if request_count >= MAX_REQUESTS:
            # Printting a message and shut down the server if the maximum number of requests has been reached
            print("Reached maximum number of requests, shutting down.")
            self.server.shutdown()
            return

        # Sending a response with a 200 status code and an HTML web page
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"<html><head><title>Sample Web Page</title></head>")
        self.wfile.write(b"<body><h1>Hello, this is a simple web server!</h1></body></html>")
        print("Hello, this is a simple web server!")

# Creating the HTTP server and bind it to the specified port
httpd = LimitedRequestHTTPServer(("", PORT), LimitedRequestHandler)

# Printing a message indicating that the server is running
print(f"Serving HTTP on 0.0.0.0 port {PORT} ...")

# Handling requests until the maximum number of requests has been reached
while request_count < MAX_REQUESTS:
    httpd.handle_request()

# Shutting down the server and printing a message indicating that it has been shut down
httpd.server_close()
print("Server shut down.")
