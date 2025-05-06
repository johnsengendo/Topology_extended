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
    subprocess.run(['docker', 'exec', '-it', 'streaming_server', 'bash', '-c', 'cd /home && python3 video_streaming2.py'])

def start_client():
    subprocess.run(['docker', 'exec', '-it', 'streaming_client', 'bash', '-c', 'cd /home && python3 get_video_streamed2.py'])

def start_iperf_server(host):
    host.cmd('iperf -s -p 5001 -u &')

def start_iperf_client(host, target, port=5001, bandwidth='5M', duration=120):
    host.cmd(f'iperf -c {target} -p {port} -u -b {bandwidth} -t {duration} &')

def stop_iperf_client(host):
    host.cmd('pkill iperf')

def start_file_transfer(host, target, size_mb):
    host.cmd(f'iperf -c {target} -n {size_mb}M -t 10 &')

def change_link_properties(link, bw, delay, jitter=0, loss=0):
    info(f'*** Changing link properties: BW={bw} Mbps, Delay={delay} ms, Jitter={jitter} ms, Loss={loss}%\n')
    link.intf1.config(bw=bw, delay=f'{delay}ms', jitter=f'{jitter}ms', loss=loss)
    link.intf2.config(bw=bw, delay=f'{delay}ms', jitter=f'{jitter}ms', loss=loss)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Video streaming application with dynamic bandwidth and delay.')
    parser.add_argument('--autotest', dest='autotest', action='store_const', const=True, default=False,
                        help='Enables automatic testing of the topology and closes the streaming application.')
    args = parser.parse_args()

    # Predefined values for dynamic link changes
    bw_delay_pairs = [(30, 60), (35, 70)]
    jitter_values = [0, 5]
    loss_values = [0, 0.1]

    autotest = args.autotest

    # Shared directory for pcap files and other shared data
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

    # Existing hosts
    h1 = net.addHost('h1', ip='10.0.0.3')  # ping test
    h2 = net.addHost('h2', ip='10.0.0.4')
    h3 = net.addHost('h3', ip='10.0.0.5')  # medium iperf client
    h6 = net.addHost('h6', ip='10.0.0.6')  # medium iperf server
    h4 = net.addHost('h4', ip='10.0.0.7')  # large iperf client
    h5 = net.addHost('h5', ip='10.0.0.8')  # large iperf server

    # New web hosts
    h7 = net.addHost('h7', ip='10.0.0.9')  # web server
    h8 = net.addHost('h8', ip='10.0.0.10')  # web client

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
    # Links for web hosts
    net.addLink(switch1, h7)
    net.addLink(switch2, h8)

    info('\n*** Starting network\n')
    net.start()

    # Basic connectivity test
    info("*** Client host pings the server: \n")
    print(client.cmd("ping -c 5 10.0.0.1"))

    # Setup web server on h7
    html = '<html><body><h1>Hello from Web Server (h7)</h1></body></html>'
    h7.cmd(f'echo "{html}" > /tmp/index.html')
    h7.cmd('python3 -m http.server 80 --directory /tmp &')

    # Web client thread: periodically fetch page
    def web_fetch():
        while True:
            out = h8.cmd('curl -s http://10.0.0.9:80')
            info(f"*** h8 fetched webpage: {out}\n")
            time.sleep(60)

    web_thread = threading.Thread(target=web_fetch)
    web_thread.daemon = True
    web_thread.start()

    # Start tcpdump on middle link
    capture_interface = middle_link.intf1.name
    capture_file = os.path.join(shared_directory, 'middle_link_capture.pcap')
    info(f'*** Starting tcpdump on {capture_interface}, saving to {capture_file}\n')
    tcpdump_proc = subprocess.Popen(['sudo', 'tcpdump', '-i', capture_interface, '-w', capture_file])

    # Add streaming containers
    streaming_server = add_streaming_container(mgr, 'streaming_server', 'server', 'streaming_server_image', shared_directory)
    streaming_client = add_streaming_container(mgr, 'streaming_client', 'client', 'streaming_client_image', shared_directory)

    # Start streaming threads
    server_thread = threading.Thread(target=start_server)
    client_thread = threading.Thread(target=start_client)
    server_thread.start()
    client_thread.start()

    # Iperf servers
    start_iperf_server(h6)
    start_iperf_server(h5)

    # Dynamic link properties updater
    def update_link_properties():
        while True:
            bw, delay = random.choice(bw_delay_pairs)
            jitter = random.choice(jitter_values)
            loss = random.choice(loss_values)
            change_link_properties(middle_link, bw, delay, jitter, loss)
            time.sleep(120)

    dynamic_thread = threading.Thread(target=update_link_properties)
    dynamic_thread.daemon = True
    dynamic_thread.start()

    # Initial iperf tests
    def start_iperf_after_delay():
        time.sleep(2)
        start_iperf_client(h3, '10.0.0.6')
        start_iperf_client(h4, '10.0.0.8')
        time.sleep(20)
        stop_iperf_client(h3)
        stop_iperf_client(h4)

    iperf_thread = threading.Thread(target=start_iperf_after_delay)
    iperf_thread.start()

    # Continuous file transfers
    def continuous_transfer(host, target, size, interval):
        while True:
            start_file_transfer(host, target, size)
            time.sleep(interval)

    med = threading.Thread(target=continuous_transfer, args=(h3, '10.0.0.6', 50, 30))
    med.daemon = True; med.start()
    lg = threading.Thread(target=continuous_transfer, args=(h4, '10.0.0.8', 200, 60))
    lg.daemon = True; lg.start()

    # Wait for main threads
    server_thread.join(); client_thread.join(); iperf_thread.join()

    if not autotest:
        CLI(net)

    # Cleanup
    info('*** Terminating tcpdump\n')
    tcpdump_proc.terminate(); tcpdump_proc.wait()
    mgr.removeContainer('streaming_server'); mgr.removeContainer('streaming_client')
    net.stop(); mgr.stop()
