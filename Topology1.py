import argparse
import os
import subprocess
import sys
import time
import threading
import random
from comnetsemu.cli import CLI
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
    subprocess.Popen([
        'docker', 'exec', '-it', 'streaming_server',
        'bash', '-c', 'cd /home && python3 video_streaming2.py'
    ])

def start_client():
    subprocess.Popen([
        'docker', 'exec', '-it', 'streaming_client',
        'bash', '-c', 'cd /home && python3 get_video_streamed2.py'
    ])

def start_iperf_server(host):
    host.cmd('iperf -s -p 5001 -u &')

def start_iperf_client(host, target, port=5001, bandwidth='5M', duration=120):
    host.cmd(f'iperf -c {target} -p {port} -u -b {bandwidth} -t {duration} &')

def stop_iperf_client(host):
    host.cmd('pkill iperf')

def start_file_transfer(host, target, size_mb):
    host.cmd(f'iperf -c {target} -n {size_mb}M -t 10 &')

def change_link_properties(link, bw, delay, jitter=0, loss=0):
    info(f'*** Changing link: BW={bw}Mbps, delay={delay}ms, jitter={jitter}ms, loss={loss}%\n')
    link.intf1.config(bw=bw, delay=f'{delay}ms', jitter=f'{jitter}ms', loss=loss)
    link.intf2.config(bw=bw, delay=f'{delay}ms', jitter=f'{jitter}ms', loss=loss)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Combined streaming, iperf, file and web traffic topology')
    parser.add_argument('--autotest', action='store_true', help='Run without CLI and exit')
    args = parser.parse_args()

    # Setup shared directory
    base_dir = os.path.abspath(os.path.dirname(__file__))
    shared_dir = os.path.join(base_dir, 'pcap')
    os.makedirs(shared_dir, exist_ok=True)

    # Link property options
    bw_delay_pairs = [(30, 60), (35, 70)]
    jitter_vals = [0, 5]
    loss_vals = [0, 0.1]

    setLogLevel('info')
    net = Containernet(controller=Controller, link=TCLink)
    mgr = VNFManager(net)

    info('*** Adding controller\n')
    net.addController('c0')

    info('*** Adding hosts\n')
    server = net.addDockerHost('server', dimage='dev_test', ip='10.0.0.1')
    client = net.addDockerHost('client', dimage='dev_test', ip='10.0.0.2')
    h1 = net.addHost('h1', ip='10.0.0.3')
    h2 = net.addHost('h2', ip='10.0.0.4')
    h3 = net.addHost('h3', ip='10.0.0.5')
    h6 = net.addHost('h6', ip='10.0.0.6')
    h4 = net.addHost('h4', ip='10.0.0.7')
    h5 = net.addHost('h5', ip='10.0.0.8')
    h7 = net.addHost('h7', ip='10.0.0.9')  # web server
    h8 = net.addHost('h8', ip='10.0.0.10') # web client

    info('*** Adding switches and links\n')
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    net.addLink(s1, server)
    net.addLink(s1, h1)
    middle = net.addLink(s1, s2, bw=10, delay='10ms')
    net.addLink(s2, client)
    net.addLink(s2, h2)
    net.addLink(s1, h3)
    net.addLink(s2, h6)
    net.addLink(s1, h4)
    net.addLink(s2, h5)
    net.addLink(s1, h7)
    net.addLink(s2, h8)

    info('*** Starting network\n')
    net.start()

    # Launch web server
    h7.cmd('echo "<html><body><h1>Hello from h7</h1></body></html>" > /tmp/index.html')
    h7.cmd('python3 -m http.server 80 --directory /tmp &')

    # Start tcpdump captures
    iface = middle.intf1.name
    pcap_file1 = os.path.join(shared_dir, 'file_traffic.pcap')
    pcap_file2 = os.path.join(shared_dir, 'web_traffic.pcap')
    file_dump = subprocess.Popen(['sudo', 'tcpdump', '-i', iface, 'udp port 5001', '-w', pcap_file1])
    web_dump  = subprocess.Popen(['sudo', 'tcpdump', '-i', iface, 'tcp port 80', '-w', pcap_file2])

    # Define dynamic updater
    def update_link():
        while True:
            bw, dly = random.choice(bw_delay_pairs)
            jit = random.choice(jitter_vals)
            loss = random.choice(loss_vals)
            change_link_properties(middle, bw, dly, jit, loss)
            time.sleep(120)

    # Define web fetcher
    def web_fetch():
        while True:
            out = h8.cmd('curl -s http://10.0.0.9:80')
            info(f'*** h8 fetched: {out}\n')
            time.sleep(60)

    # Define continuous transfer
    def continuous(host, target, size, interval):
        while True:
            start_file_transfer(host, target, size)
            time.sleep(interval)

    # Start services concurrently
    threads = []
    # streaming
    threads += [threading.Thread(target=start_server, daemon=True),
                threading.Thread(target=start_client, daemon=True)]
    # iperf servers
    start_iperf_server(h6)
    start_iperf_server(h5)
    # initial iperf clients
    threads.append(threading.Thread(target=lambda: (time.sleep(2), start_iperf_client(h3, '10.0.0.6'),
                                                  start_iperf_client(h4, '10.0.0.8'), time.sleep(20),
                                                  stop_iperf_client(h3), stop_iperf_client(h4)), daemon=True))
    # continuous transfers
    threads += [
        threading.Thread(target=lambda: continuous(h3, '10.0.0.6', 50, 30), daemon=True),
        threading.Thread(target=lambda: continuous(h4, '10.0.0.8', 200, 60), daemon=True)
    ]
    # web fetch
    threads.append(threading.Thread(target=web_fetch, daemon=True))
    # dynamic link
    threads.append(threading.Thread(target=update_link, daemon=True))

    for t in threads:
        t.start()

    # CLI holds until exit
    if not args.autotest:
        CLI(net)

    # cleanup
    info('*** Terminating captures\n')
    file_dump.terminate(); web_dump.terminate()
    mgr.removeContainer('streaming_server'); mgr.removeContainer('streaming_client')
    net.stop(); mgr.stop()
