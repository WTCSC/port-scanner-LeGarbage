from sys import argv
import subprocess
import socket
import re
from rich.table import Table
from rich.live import Live
from rich import box


def parse_args():
    iter_argv = iter(argv[1:])
    args = {"force":False}
    for arg in iter_argv:
        if arg == "-p":
            port = [i for i in next(iter_argv, "").split(",") if i]
            for port_range in [i for i in port if "-" in i]:
                port.remove(port_range)
                port_range = [int(i) for i in port_range.split("-")]
                print(port_range)
                port.extend(range(port_range[0], port_range[1] + 1))
            if port:
                args["port"] = sorted([int(i) for i in port])
        elif arg == "-f":
            args["force"] = True
        else:
            args["ip"] = arg
    return args
        

# Gets the first ip and the number of ips in a subnet
def get_range(ip):
    # Split the address into the ip part and the cidr subnet mask
    ip = ip.split("/")
    # Get the cidr subnet mask
    cidr = int(ip[1])
    # Split the ip into its parts to be converted into binary
    ip = ip[0].split(".")
    # Converts each byte of the ip into binary, making sure that each byte has 8 characters by adding leading zeros
    bip = [bin(int(i)).removeprefix("0b").zfill(8) for i in ip]
    # Put the ip back into a single string
    bin_ip = "".join(bip)
    # Use the cidr address to get the network address, which is the first n digits of the binary ip
    subnet = bin_ip[:cidr]
    # Get the first host address in the range by filling the host address portion with zeros and a one
    bin_ip = subnet + "0" * (31 - cidr) + "1"
    # Convert the single string back into a list to go back to decimal
    bin_ip = [bin_ip[:8], bin_ip[8:16], bin_ip[16:24], bin_ip[24:]]
    # Convert the ip address back into decimal
    first_ip = [int(i, 2) for i in bin_ip]
    # Get the number of host addresses from the subnet mask
    ip_range = (2 ** (32 - cidr)) - 2
    return first_ip, ip_range

# Lists all of the ips starting from [ip] and ending [ip_range] ips from the start
def list_ips(ip, ip_range):
    ip_list = []
    for _ in range(ip_range):
        # Add the formatted ip to the return list
        ip_list.append(format_ip(ip))
        # Add one to the least signigicant byte
        ip[-1] += 1
        # Iterate from the back of the ip to the front
        for i in range(-1, -5, -1):
            # Checks if the byte is overflowing
            if ip[i] > 255:
                # Carry the overflow
                ip[i] = 0
                ip[i - 1] += 1
    return ip_list

def format_ip(ip):
    # Convert the ip from a list of ints to a str (xxx.xxx.xxx.xxx)
    return ".".join([str(i) for i in ip])

# Ping an ip and get a response
def ping_ip(ip):
    try:
        # Ping the address
        output = subprocess.run(["ping", "-c", "1", ip], timeout=.5, capture_output=True)
        # Checks if the response has content
        if output.stdout:
            # Convert the response from bytes to a string
            output.stdout = output.stdout.decode()
            # If there was a response, then the host is up
            status = "UP"
    except subprocess.TimeoutExpired:
        # If the ping timed out, show an error
        status = "DOWN"
    return status

# Tries to connect to a port to see if it's open
def check_port(ip, port):
    # Make  a new socket using IPv4 and TCP
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Make it time out after 5 seconds
    sock.settimeout(.5)
    # Connect to the port
    result = sock.connect_ex((ip, port))
    sock.close()
    # Check if it was successful
    if result == 0:
        status = True
    else:
        status = False
    return status

args = parse_args()

# Get the range of the address
first_ip, ip_range = get_range(args["ip"])
# Create a table to display the results
table = Table("IP/Port", "Status", box=box.ASCII_DOUBLE_HEAD)

# Update the table live
with Live(table, auto_refresh=False) as live:
    try:
        # Ping each ip in the subnet
        for ip in list_ips(first_ip, ip_range):
            # Get a response from pinging the ip
            response = ping_ip(ip)
            # Add the response to the table
            table.add_row(ip, response)
            # Update the table
            live.refresh()

            if (response == "UP" or args["force"]) and "port" in args:
                for port in args["port"]:
                    status = check_port(ip, port)
                    if status:
                        table.add_row(f"  - {port}", "OPEN")
                        live.refresh()
    except KeyboardInterrupt:
        # Stop uptating the table on ^c, also prevents the ugly error message
        live.stop()