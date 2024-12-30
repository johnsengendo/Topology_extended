#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import subprocess
import sys
import time
import threading

# Importing necessary functionalities from ComNetsEmu and Mininet
from comnetsemu.cli import CLI, spawnXtermDocker
from comnetsemu.net import Containernet, VNFManager
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.node import Controller

# Function to add streaming container
def add_streaming_container(manager, name, role, image, shared_dir):
    return manager.addContainer(
        name, role, image, '', docker_args={
            'volumes': {
                shared_dir: {'bind': '/home/pcap/', 'mode': 'rw'}
            }
        }
    )

# Function to start server
def start_server():
    subprocess.run(['docker', 'exec', '-it', 'streaming_server', 'bash', '-c', 'cd /home && python3 video_streaming.py'])

# Function to start client
def start_client():
    subprocess.run(['docker', 'exec', '-it', 'streaming_client', 'bash', '-c', 'cd /home && python3 video_client.py'])

# changing the link parameters
def change_link_properties(link, bw, delay):
    info(f'*** Changing bandwidth to {bw} Mbps and delay to {delay} ms\n')
    link.intf1.config(bw=bw, delay=f'{delay}ms')
    link.intf2.config(bw=bw, delay=f'{delay}ms')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Video streaming application with dynamic bandwidth and delay.')
    parser.add_argument('--autotest', dest='autotest', action='store_true', default=False,
                        help='Enables automatic testing of the topology and closes the streaming application.')
    args = parser.parse_args()

    # Defining 15 bandwidth-delay pairs for the link
    bw_delay_pairs = [
        (5, 10), (10, 20), (15, 30), (20, 40), (25, 50),
        (30, 60), (35, 70), (40, 80), (45, 90), (50, 100),
        (55, 110), (60, 120), (65, 130), (70, 140), (75, 150),
        (80, 160), (85, 170), (90, 180), (95, 190), (100, 200)]
    
    autotest = args.autotest

    script_directory = os.path.abspath(os.path.dirname(__file__))
    shared_directory = os.path.join(script_directory, 'pcap')

    if not os.path.exists(shared_directory):
        os.makedirs(shared_directory)

    setLogLevel('info')

    net = Containernet(controller=Controller, link=TCLink, xterms=False)
    mgr = VNFManager(net)

    info('*** Add controller\n')
    net.addController('c0')

    info('*** Creating hosts\n')
    server = net.addDockerHost('server', dimage='dev_test', ip='10.0.0.1', docker_args={'hostname': 'server'})
    client = net.addDockerHost('client', dimage='dev_test', ip='10.0.0.2', docker_args={'hostname': 'client'})

    info('*** Adding switches and links\n')
    switch1 = net.addSwitch('s1')
    switch2 = net.addSwitch('s2')
    net.addLink(switch1, server)
    middle_link = net.addLink(switch1, switch2, bw=bw_delay_pairs[0][0], delay=f'{bw_delay_pairs[0][1]}ms')
    net.addLink(switch2, client)

    info('\n*** Starting network\n')
    net.start()

    info("*** Client host pings the server to test for connectivity: \n")
    reply = client.cmd("ping -c 5 10.0.0.1")
    print(reply)
    # Adding containers
    streaming_server = add_streaming_container(mgr, 'streaming_server', 'server', 'streaming_server_image', shared_directory)
    streaming_client = add_streaming_container(mgr, 'streaming_client', 'client', 'streaming_client_image', shared_directory)

    server_thread = threading.Thread(target=start_server)
    client_thread = threading.Thread(target=start_client)

    server_thread.start()
    time.sleep(2)  # Giving the server time to start
    client_thread.start()

    # Changing link properties every 120 seconds
    for bw, delay in bw_delay_pairs:
        change_link_properties(middle_link, bw, delay)
        time.sleep(60)

    # Waiting for threads to finish
    server_thread.join()
    client_thread.join()

    if not autotest:
        CLI(net)

    mgr.removeContainer('streaming_server')
    mgr.removeContainer('streaming_client')
    net.stop()
    mgr.stop()
