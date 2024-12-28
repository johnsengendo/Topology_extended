#!/bin/env python3
# -*- coding: utf-8 -*-

# Importing necessary libraries
import requests
import subprocess
import time
import os

def start_tcpdump():
    """
    Starting capturing packets using tcpdump.
    Returns:
        subprocess.Popen: The tcpdump process object.
    """
    return subprocess.Popen(['tcpdump', '-i', 'any', '-w', 'pcap/client_capture.pcap', 'tcp and port 8000 and host 10.0.0.1'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def stop_tcpdump(process):
    """
    Stopping the tcpdump process.
    Args:
        process (subprocess.Popen): The tcpdump process object.
    """
    # Terminating the tcpdump process and waiting for it to finish
    process.terminate()
    process.wait()

def fetch_web_page():
    """Fetching the web page."""
    try:
        # Sending a GET request to fetch the web page at http://10.0.0.1:8000
        response = requests.get("http://10.0.0.1:8000")
        # Printing the response status code and text
        print(f"Response from server: {response.status_code}\n{response.text}")
    except requests.exceptions.ConnectionError:
        # Raising an exception if there's a connection error (e.g., server shut down)
        print("Server shut down.")
        raise

if __name__ == "__main__":
    # Starting the tcpdump process
    tcpdump_proc = start_tcpdump()
    # Waiting for 1 second to give tcpdump a moment to start
    time.sleep(1)

    try:
        # Continuously fetching the web page until the server shuts down
        while True:
            try:
                fetch_web_page()  # Fetching the web page
            except requests.exceptions.ConnectionError:
                print("Server shut down.")
                break  # Exiting the loop if the server shuts down
            # Waiting for 1 second before fetching the web page again
            time.sleep(1)
    finally:
        # Stopping the tcpdump process
        stop_tcpdump(tcpdump_proc)
