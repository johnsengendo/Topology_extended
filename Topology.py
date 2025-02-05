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

def add_streaming_container(manager, name, role, image, shared_dir):
    return manager.addContainer(
        name, role, image, '', docker_args={
            'volumes': {
                shared_dir: {'bind': '/home/pcap/', 'mode': 'rw'}
            }
        }
    )

def start_server():
    subprocess.run(['docker', 'exec', '-it', 'streaming_server', 'bash', '-c', 'cd /home && python3 video_streaming.py'])

def start_client():
    subprocess.run(['docker', 'exec', '-it', 'streaming_client', 'bash', '-c', 'cd /home && python3 get_video_streamed.py'])

def start_iperf_server(host):
    host.cmd('iperf -s -p 5001 -u &')

def start_iperf_client(host):
    host.cmd('iperf -c 10.0.0.6 -p 5001 -u -b 5M -t 120 &')

def start_iperf_client2(host):
    host.cmd('iperf -c 10.0.0.8 -p 5001 -u -b 5M -t 120 &')

def stop_iperf_client(host):
    host.cmd('pkill iperf')

def change_link_properties(link, bw, delay, jitter=0, loss=0):
    info(f'*** Changing link properties: BW={bw} Mbps, Delay={delay} ms, Jitter={jitter} ms, Loss={loss}%\n')
    link.intf1.config(bw=bw, delay=f'{delay}ms', jitter=f'{jitter}ms', loss=loss)
    link.intf2.config(bw=bw, delay=f'{delay}ms', jitter=f'{jitter}ms', loss=loss)

def start_tcpdump(switch, interface, output_file):
    switch.cmd(f'tcpdump -i {interface} -w {output_file} &')

def stop_tcpdump(switch):
    switch.cmd('pkill tcpdump')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Video streaming application with dynamic bandwidth and delay.')
    parser.add_argument('--autotest', dest='autotest', action='store_const', const=True, default=False,
                        help='Enables automatic testing of the topology and closes the streaming application.')
    args = parser.parse_args()

    bw_delay_pairs = [
        (30, 60), (35, 70), (40, 80), (45, 90), (50, 100)
    ]
    jitter_values = [0, 5, 10, 20]
    loss_values = [0, 0.1, 0.5, 1]

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
    server = net.addDockerHost(
        'server', dimage='dev_test', ip='10.0.0.1', docker_args={'hostname': 'server'}
    )
    client = net.addDockerHost(
        'client', dimage='dev_test', ip='10.0.0.2', docker_args={'hostname': 'client'}
    )

    h1 = net.addHost('h1', ip='10.0.0.3')
    h2 = net.addHost('h2', ip='10.0.0.4')
    h3 = net.addHost('h3', ip='10.0.0.5')
    h6 = net.addHost('h6', ip='10.0.0.6')
    h4 = net.addHost('h4', ip='10.0.0.7')
    h5 = net.addHost('h5', ip='10.0.0.8')

    info('*** Adding switches and links\n')
    switch1 = net.addSwitch('s1')
    switch2 = net.addSwitch('s2')

    net.addLink(switch1, server)
    net.addLink(switch1, h1)
    middle_link = net.addLink(switch1, switch2, bw=10, delay='10ms')
    net.addLink(switch2, client)
    net.addLink(switch2, h2)
    net.addLink(switch1, h3)
    net.addLink(switch2, h6)
    net.addLink(switch1, h4)
    net.addLink(switch2, h5)

    info('\n*** Starting network\n')
    net.start()

    info("*** Client host pings the server to test for connectivity: \n")
    reply = client.cmd("ping -c 5 10.0.0.1")
    print(reply)

    info("*** Starting tcpdump on switch 2 interface s2-eth1\n")
    start_tcpdump(switch2, 's2-eth1', os.path.join(shared_directory, 'switch2_capture.pcap'))

    streaming_server = add_streaming_container(mgr, 'streaming_server', 'server', 'streaming_server_image', shared_directory)
    streaming_client = add_streaming_container(mgr, 'streaming_client', 'client', 'streaming_client_image', shared_directory)

    server_thread = threading.Thread(target=start_server)
    client_thread = threading.Thread(target=start_client)

    server_thread.start()
    client_thread.start()

    start_iperf_server(h6)
    start_iperf_server(h5)

    def update_link_properties():
        while True:
            bw, delay = random.choice(bw_delay_pairs)
            jitter = random.choice(jitter_values)
            loss = random.choice(loss_values)

            change_link_properties(middle_link, bw, delay, jitter, loss)

            # Wait for 2 minutes (120 seconds) before changing the properties again
            time.sleep(120)

    dynamic_link_thread = threading.Thread(target=update_link_properties)
    dynamic_link_thread.start()

    def start_iperf_after_delay():
        time.sleep(2)
        start_iperf_client(h3)
        start_iperf_client2(h4)
        time.sleep(20)
        stop_iperf_client(h3)
        stop_iperf_client(h4)

    iperf_thread = threading.Thread(target=start_iperf_after_delay)
    iperf_thread.start()

    server_thread.join()
    client_thread.join()
    iperf_thread.join()

    if not autotest:
        CLI(net)

    stop_tcpdump(switch2)
    mgr.removeContainer('streaming_server')
    mgr.removeContainer('streaming_client')
    net.stop()
    mgr.stop()
