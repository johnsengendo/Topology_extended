#!/bin/env python3
# -*- coding: utf-8 -*-

# Importing necessary modules
import subprocess
import os
import signal
import time

# Function to start traffic capture using tcpdump
def start_capture():
    # Constructing the tcpdump command and starting the tcpdump process and get its PID
    proc = subprocess.Popen(["tcpdump", "-U", "-s0", "-i", "client-eth0", "src", "port", "1935", "-w", "pcap/client.pcap"])
    return proc.pid

# Function to stop traffic capture using the process ID
def stop_capture(pid):
    try:
        # Sending the SIGINT signal to the process
        os.kill(pid, signal.SIGINT)
        print("Capture stopped successfully.")
    except OSError as e:
        print(f"Error stopping capture: {e}")

# Function to get the video stream from the remote server
def get_video_stream():
    out_file = "stream_output.flv"
    total_duration = 20 * 60  # 20 periods of 120 seconds each
    capture_traffic = True

    # Starting traffic capture if the flag is True
    if capture_traffic:
        pid = start_capture()
        time.sleep(2)
    # Constructing the FFmpeg command
    ffmpeg_command = [
        "ffmpeg", "-loglevel", "info", "-stats", "-i", "rtmp://10.0.0.1:1935/live/video.flv",
        "-t", str(total_duration), "-probesize", "80000", "-analyzeduration", "15", "-c:a", "copy", "-c:v", "copy", out_file
    ]

    # Executing the FFmpeg command
    subprocess.run(ffmpeg_command)

    # Stopping traffic capture if the flag is True
    if capture_traffic:
        stop_capture(pid)

# Checking if the script is being run as the main program
if __name__ == "__main__":
    get_video_stream()
