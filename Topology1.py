import argparse
import os
import subprocess
import sys
import time
import threading
import random
from comnetsemu.cli import CLI, spawnXtermDocker
from comnetsemu.net import Containernet, VNFManager
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.node import Controller

# Utility functions omitted for brevity; assume same as before

def add_streaming_container(manager, name, role, image, shared_dir): ...
def start_server(): ...
def start_client(): ...
def start_iperf_server(host): ...
def start_iperf_client(host, target, port=5001, bandwidth='5M', duration=120): ...
def stop_iperf_client(host): ...
def start_file_transfer(host, target, size_mb): ...
def change_link_properties(link, bw, delay, jitter=0, loss=0): ...

if __name__ == '__main__':
    # (Argument parsing, setup, and host/link creation same as before)
    # ...

    net.start()

    # Setup web server on h7
    h7.cmd('echo "<html><body><h1>Hello from Web Server (h7)</h1></body></html>" > /tmp/index.html')
    h7.cmd('python3 -m http.server 80 --directory /tmp &')

    # Start tcpdump captures
    interface = middle_link.intf1.name
    iperf_dump = subprocess.Popen(['sudo', 'tcpdump', '-i', interface, 'udp port 5001', '-w', os.path.join(shared_directory, 'file_traffic.pcap')])
    web_dump = subprocess.Popen(['sudo', 'tcpdump', '-i', interface, 'tcp port 80', '-w', os.path.join(shared_directory, 'web_traffic.pcap')])

    # Threads for all services
    threads = []

    # Video streaming
    threads.append(threading.Thread(target=start_server, daemon=True))
    threads.append(threading.Thread(target=start_client, daemon=True))

    # Iperf servers and initial tests
    start_iperf_server(h6)
    start_iperf_server(h5)
    iperf_init = threading.Thread(target=lambda: (time.sleep(2), start_iperf_client(h3, '10.0.0.6'), start_iperf_client(h4, '10.0.0.8'), time.sleep(20), stop_iperf_client(h3), stop_iperf_client(h4)), daemon=True)
    threads.append(iperf_init)

    # Continuous file transfers
    threads.append(threading.Thread(target=lambda: continuous_transfer(h3, '10.0.0.6', 50, 30), daemon=True))
    threads.append(threading.Thread(target=lambda: continuous_transfer(h4, '10.0.0.8', 200, 60), daemon=True))

    # Web client fetch
    threads.append(threading.Thread(target=web_fetch, daemon=True))

    # Dynamic link updater
    threads.append(threading.Thread(target=update_link_properties, daemon=True))

    # Start all threads
    for t in threads:
        t.start()

    # Drop into CLI; all services run concurrently
    if not autotest:
        CLI(net)

    # Cleanup capture processes
    info('*** Terminating captures')
    iperf_dump.terminate(); web_dump.terminate();
    mgr.removeContainer('streaming_server'); mgr.removeContainer('streaming_client')
    net.stop(); mgr.stop()
