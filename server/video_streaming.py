#!/bin/env python3
# -*- coding: utf-8 -*-

# Importing necessary libraries
import subprocess
import os
import time
import signal 

def start_capture():
    """
    Starting packet capturing on server-eth0 interface using tcpdump. Captures all packets
    on source port 1935 and writing them to a pcap file. This is used to
    capture network traffic associated with the video streaming.
    """
    proc = subprocess.Popen(["tcpdump", "-U", "-s0", "-i", "server-eth0", "src", "port", "1935", "-w", "pcap/server.pcap"])
    #proc = subprocess.Popen(["tcpdump", "-U", "-s0", "-i", "h6-eth0", "src", "port", "1935", "-w", "pcap/server.pcap", "-A"])

    return proc.pid

def start_capture_h6():
    """
    Start packet capturing on h6-eth0 interface using tcpdump.
    Appends captured packets to the server.pcap file.
    """
    proc = subprocess.Popen(["tcpdump", "-U", "-s0", "-i", "h6-eth0", "src", "port", "1935", "-w", "pcap/server.pcap", "-A"])
    return proc.pid

def stop_capture(pid_list):
    """
    Stoping the tcpdump process that was started by start_capture. Searches through
    the process list, identifies the tcpdump process, and sends a SIGINT signal to
    terminate it.
    """
    for pid in pid_list:
        try:
            os.kill(pid, signal.SIGINT)
        except OSError as e:
            print(f"Error stopping capture: {e}")    

def main():
    """
    Main function to handle video streaming with optional packet capture.
    """
    input_file = "video/Deadpool.mp4"
    loops_number = -1  # Stream the video once, without looping
    capture_traffic = True

    pids = []

    if capture_traffic:
        pids.append(start_capture())
        #pids.append(start_capture_h6())
        #pid = start_capture()  # Begining packet capturing
        time.sleep(2)   # Short delay to ensure capturing starts before streaming

    ffmpeg_command = [
        "ffmpeg", "-loglevel", "info", "-stats", "-re", "-stream_loop", str(loops_number), "-i", input_file,
        "-t", "600", "-c:v", "copy", "-c:a", "aac", "-ar", "44100", "-ac", "1",
        "-f", "flv", "rtmp://localhost:1935/live/video.flv"
    ]
    subprocess.run(ffmpeg_command)  # Running ffmpeg command to stream video

    if capture_traffic:
        stop_capture(pids)  # Stopping packet capturing after streaming is done

if __name__ == "__main__":
    main()
