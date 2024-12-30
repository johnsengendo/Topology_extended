#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# Importing required modules
import argparse
import os
import subprocess
import sys
import time
import threading
import random


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
    subprocess.run(['docker', 'exec', '-it', 'streaming_client', 'bash', '-c', 'cd /home && python3 get_video_streamed.py'])

# Function to start iperf server on h6
def start_iperf_server(host):
    host.cmd('iperf -s -p 5001 -u &')  # Use UDP for more disruptive traffic

# Function to start iperf client on h3
def start_iperf_client(host):
    host.cmd('iperf -c 10.0.0.6 -p 5001 -u -b 0M -t 120 &')  # Use UDP with high bandwidth
# Function to start iperf client on h4
def start_iperf_client2(host):
    host.cmd('iperf -c 10.0.0.8 -p 5001 -u -b 0M -t 120 &')  # Use UDP with high bandwidth
# Function to stop iperf client on h3
def stop_iperf_client(host):
    host.cmd('pkill iperf')

def change_link_properties(link, bw, delay, jitter=0, loss=0):
    """
    Dynamically change link properties: bandwidth, delay, jitter, and packet loss.
    """
    info(f'*** Changing link properties: BW={bw} Mbps, Delay={delay} ms, Jitter={jitter} ms, Loss={loss}%\n')
    link.intf1.config(bw=bw, delay=f'{delay}ms', jitter=f'{jitter}ms', loss=loss)
    link.intf2.config(bw=bw, delay=f'{delay}ms', jitter=f'{jitter}ms', loss=loss)
# Main execution starts here
if __name__ == '__main__':
    # Setting up command-line argument parsing
    parser = argparse.ArgumentParser(description='video streaming application.')
    parser.add_argument('--autotest', dest='autotest', action='store_const', const=True, default=False,
                        help='Enables automatic testing of the topology and closes the streaming application.')
    args = parser.parse_args()

    bw_delay_pairs = [
        (5, 10), (10, 20), (15, 30), (20, 40), (25, 50),
        (30, 60), (35, 70), (40, 80), (45, 90), (50, 100),
        (55, 110), (60, 120), (65, 130), (70, 140), (75, 150),
        (80, 160), (85, 170), (90, 180), (95, 190), (100, 200)
    ]

    # Adding jitter and packet loss settings for variation
    jitter_values = [0, 5, 10, 20]  # Random jitter in ms
    loss_values = [0, 0.1, 0.5, 1]  # Random packet loss in percentage

    autotest = args.autotest

    # Preparing a shared folder to store the pcap files
    script_directory = os.path.abspath(os.path.dirname(__file__))
    shared_directory = os.path.join(script_directory, 'pcap')

    # Creating the shared directory if it doesn't exist
    if not os.path.exists(shared_directory):
        os.makedirs(shared_directory)

    # Configuring the logging level
    setLogLevel('info')

    # Creating a network with Containernet (a Docker-compatible Mininet fork) and a virtual network function manager
    net = Containernet(controller=Controller, link=TCLink, xterms=False)
    mgr = VNFManager(net)

    # Adding a controller to the network
    info('*** Add controller\n')
    net.addController('c0')

    # Setting up Docker hosts as network nodes
    info('*** Creating hosts\n')
    server = net.addDockerHost(
        'server', dimage='dev_test', ip='10.0.0.1', docker_args={'hostname': 'server'}
    )
    client = net.addDockerHost(
        'client', dimage='dev_test', ip='10.0.0.2', docker_args={'hostname': 'client'}
    )

    # Adding normal hosts
    h1 = net.addHost('h1', ip='10.0.0.3')
    h2 = net.addHost('h2', ip='10.0.0.4')
    h3 = net.addHost('h3', ip='10.0.0.5')
    h6 = net.addHost('h6', ip='10.0.0.6')
    h4 = net.addHost('h4', ip='10.0.0.7')
    h5 = net.addHost('h5', ip='10.0.0.8')

    # Adding switches and links to the network
    info('*** Adding switches and links\n')
    switch1 = net.addSwitch('s1')
    switch2 = net.addSwitch('s2')

    net.addLink(switch1, server)
    net.addLink(switch1, h1)
    middle_link = net.addLink(switch1, switch2, bw=bw_delay_pairs[0][0], delay=f'{bw_delay_pairs[0][1]}ms')
    net.addLink(switch2, client)
    net.addLink(switch2, h2)
    net.addLink(switch1, h3)
    net.addLink(switch2, h6)
    net.addLink(switch1, h4)
    net.addLink(switch2, h5)

    # Starting the network
    info('\n*** Starting network\n')
    net.start()

    # Testing connectivity by pinging server from client
    info("*** Client host pings the server to test for connectivity: \n")
    reply = client.cmd("ping -c 5 10.0.0.1")
    print(reply)

    # Adding containers
    streaming_server = add_streaming_container(mgr, 'streaming_server', 'server', 'streaming_server_image', shared_directory)
    streaming_client = add_streaming_container(mgr, 'streaming_client', 'client', 'streaming_client_image', shared_directory)

    # Creating threads to run the server and client
    server_thread = threading.Thread(target=start_server)
    client_thread = threading.Thread(target=start_client)

    # Starting the threads
    server_thread.start()
    client_thread.start()

    # Start iperf server on h6
    start_iperf_server(h6)
    start_iperf_server(h5)

    # Use a timer to start iperf communication between h3 and h6 after 2 seconds
    def start_iperf_after_delay():
        time.sleep(2)
        start_iperf_client(h3)
        start_iperf_client2(h4)
        time.sleep(20)
        stop_iperf_client(h3)
        stop_iperf_client(h4)

    iperf_thread = threading.Thread(target=start_iperf_after_delay)
    iperf_thread.start()
# Changing link properties every 120 seconds
    for i in range(20):
        bw, delay = random.choice(bw_delay_pairs)
        jitter = random.choice(jitter_values)
        loss = random.choice(loss_values)
        change_link_properties(middle_link, bw, delay, jitter, loss)
        time.sleep(60)
    # Waiting for the server and client threads to finish
    server_thread.join()
    client_thread.join()

    # Wait for the iperf thread to finish
    iperf_thread.join()

    # If not in autotest mode, start an interactive CLI
    if not autotest:
        CLI(net)

    # Cleanup: removing containers and stopping the network and VNF manager
    mgr.removeContainer('streaming_server')
    mgr.removeContainer('streaming_client')
    net.stop()
    mgr.stop()
