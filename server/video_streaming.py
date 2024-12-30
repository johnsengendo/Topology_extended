#!/bin/env python3
# -*- coding: utf-8 -*-
# Importing necessary modules
import subprocess
import os
import time
import signal 

# Function to start traffic capture using tcpdump
def start_capture():
    # Constructing the tcpdump command
    proc = subprocess.Popen(["tcpdump", "-U", "-s0", "-i", "server-eth0", "src", "port", "1935", "-w", "pcap/server.pcap"])
    return proc.pid

# Function to stop traffic capture using the process ID
def stop_capture(pid):
    try:
        # Sending the SIGINT signal to the process
        os.kill(pid, signal.SIGINT)
        print("Capture stopped successfully.")
    except OSError as e:
        print(f"Error stopping capture: {e}")
        
# Main function to orchestrate the streaming and capturing processes
def main():
    # Setting the input video file, number of loops, total duration, and capture traffic flag
    input_file = "Video/Deadpool.mp4"
    loops_number = -1  # Streaming the video indefinitely
    total_duration = 20 * 60  # 15 periods of 120 seconds each
    capture_traffic = True

    # Starting traffic capture if the flag is True
    if capture_traffic:
        pid = start_capture()
        time.sleep(2)
        
    # Constructing the FFmpeg command
    ffmpeg_command = [
        "ffmpeg", "-loglevel", "info", "-stats", "-re", "-stream_loop", str(loops_number), "-i", input_file,
        "-t", str(total_duration), "-c:v", "copy", "-c:a", "aac", "-ar", "44100", "-ac", "1",
        "-f", "flv", "rtmp://localhost:1935/live/video.flv"
    ]

    # Executting the FFmpeg command
    subprocess.run(ffmpeg_command)

    # Stopping traffic capture if the flag is True
    if capture_traffic:
        stop_capture(pid)

# Checking if the script is being run as the main program
if __name__ == "__main__":
    main()
