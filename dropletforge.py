import argparse
import os
import requests
import subprocess
import time
from colorama import init, Fore, Style
from tabulate import tabulate
from pydo import Client

banner = r'''
    .___                    .__          __      _____                           
  __| _/______  ____ ______ |  |   _____/  |_  _/ ____\___________  ____   ____  
 / __ |\_  __ \/  _ \\____ \|  | _/ __ \   __\ \   __\/  _ \_  __ \/ ___\_/ __ \ 
/ /_/ | |  | \(  <_> )  |_> >  |_\  ___/|  |    |  | (  <_> )  | \/ /_/  >  ___/ 
\____ | |__|   \____/|   __/|____/\___  >__|    |__|  \____/|__|  \___  / \___  >
     \/              |__|             \/                         /_____/      \/ 
'''

client = Client(token=os.getenv("DO_API_KEY"))

# List all droplets - https://docs.digitalocean.com/reference/pydo/reference/droplets/list/
def list_droplets():
    resp = client.droplets.list()
    data = []
    # Access the list containing all of the droplets
    droplets = resp["droplets"]
    for droplet in droplets:
        id = droplet["id"]
        name = droplet["name"]
        status = droplet["status"]

        if status == "active":
            status = f"{Fore.GREEN}{status}{Style.RESET_ALL}"
        elif status == "off":
            status = f"{Fore.RED}{status}{Style.RESET_ALL}"
        else:
            status = f"{Fore.YELLOW}{status}{Style.RESET_ALL}"
        
        for net in droplet["networks"]["v4"]:
            if net["type"] == "public":
                public_ip = net["ip_address"]
                break

        data.append([id, name, status, public_ip])
    
    headers = ["ID", "Name", "Status", "Public IP"]
    print(tabulate(data, headers=headers, tablefmt="grid"))

def get_allowed_ip(override_ip=None):
    if override_ip:
        print(f" [+] Using provided IP: {override_ip}")
        return override_ip.strip()

    # Detect users public IP
    for url in ["https://ifconfig.me", "https://api.ipify.org", "https://ifconfig.co"]:
        try:
            ip = requests.get(url, timeout=5).text.strip()
            print(f" [+] Detected your networks public IP: {ip}")
            return ip
        except:
            continue

    print(" [-] Failed to detect IP!")
    fallback = input("     Enter IP manually (or 'all' for 0.0.0.0/0): ").strip()
    return fallback or "0.0.0.0/0"

def create_firewall(droplet_id, droplet_name, allowed_ip):
    if not allowed_ip or allowed_ip is False:
        print(f"{Fore.YELLOW} [-] No valid IP - skipping firewall{Style.RESET_ALL}")
        return
    
    print(f" [+] Creating firewall: DropletForge-{droplet_name}")
    
    # Create firewall
    req = {
        "name": f"DropletForge-{droplet_name}",
        "inbound_rules": [
            {
                "protocol": "tcp",
                "ports": "22",                    
                "sources": {
                    "addresses": [f"{allowed_ip}"]    
                }
            }
        ],
        "outbound_rules": [
            {
                "protocol": "tcp",
                "ports": "0",
                "destinations": {
                    "addresses": ["0.0.0.0/0", "::/0"]
                }
            },
            {
                "protocol": "udp",
                "ports": "0",
                "destinations": {
                    "addresses": ["0.0.0.0/0", "::/0"]
                }
            },
            {
                "protocol": "icmp",
                "destinations": {
                    "addresses": ["0.0.0.0/0", "::/0"]
                }
            }
        ],
        "droplet_ids": [droplet_id]
    }

    try:
        resp = client.firewalls.create(body=req)
        print(" [+] Firewall created successfully!")
        print(f"     Allowed IP: {Fore.CYAN}{allowed_ip}{Style.RESET_ALL}")
    except Exception as e:
        error = str(e)
        if "duplicate name" in error:
            print(f"{Fore.YELLOW} [+] A firewall with the name 'DropletForge-{droplet_name}' already exists — skipping{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW} [+] An error occurred - no firewall was created")

            
# Generate an SSH key and upload to DO
def generate_ssh(key_name):
    key_path = os.path.expanduser(f"~/.ssh/{key_name}")
    subprocess.run([
        "ssh-keygen", "-t", "ed25519", "-f", key_path, "-q", "-N", ""
    ], check=True)

    print(f" [+] SSH key created: {key_path}.pub")

    # Return the pub key to later be uploaded to DO
    with open(f"{key_path}.pub") as f:
        public_key = f.read().strip()
    
    # Upload the key to DO
    req = {
        "public_key": f"{public_key}",
        "name": f"{key_name}"
    }

    resp = client.ssh_keys.create(body=req)
    print(f' [+] SSH key uploaded to Digital Ocean with ID: {resp["ssh_key"]["id"]}')

    # Return the id of the ssh key that will be used when we create a droplet
    return resp["ssh_key"]["id"]


# Create droplets - https://docs.digitalocean.com/reference/pydo/reference/droplets/create/
def create_droplet(droplet_name, region, size, image):
    # Generate ssh key pair
    ssh_id = generate_ssh(droplet_name)

    req = {
        "name": droplet_name,
        "region": region,
        "size": size,
        "image": image,
        "ssh_keys": [ssh_id]
    }

    try:
        resp = client.droplets.create(body=req)
        droplet_id = resp["droplet"]["id"]

        print(f" [+] Droplet '{droplet_name}' created! (ID: {droplet_id})")
        print("\nWaiting for droplet to become active...", end="")
    except Exception as e:
        print(f"\n{Fore.RED}Unexpected error: {str(e)}{Style.RESET_ALL}")
        return None

    # Poll until active w/ public IP
    while True:
        time.sleep(1) 
        print(".", end="", flush=True)

        details = client.droplets.get(droplet_id)
        droplet = details["droplet"]
        status = droplet["status"]

        if status != "active":
            continue

        public_ip = None
        for net in droplet["networks"]["v4"]:
            if net["type"] == "public":
                public_ip = net["ip_address"]
                break

        if public_ip:
            print(f"\n\n{Fore.GREEN} Droplet is ready!{Style.RESET_ALL}")
            print(f" Public IP: {Fore.CYAN}{public_ip}{Style.RESET_ALL}\n")
            break

    return droplet_id, public_ip

# This function provides the SSH command to access droplet
def get_ssh_cmd(droplet_id):
    try:
        resp = client.droplets.get(droplet_id)
        droplet = resp["droplet"]
        for net in droplet["networks"]["v4"]:
            if net["type"] == "public":
                public_ip = net["ip_address"]
        
        name = droplet["name"]

        print(f"\nSSH into your droplet:\n")
        print(f"  ssh -i ~/.ssh/{name} root@{public_ip}\n")
    except Exception as e:
        print(f"\n{Fore.RED}Unexpected error: {str(e)}{Style.RESET_ALL}")

def destroy_droplet(droplet_id):
    print(f"{Fore.RED}WARNING: This will permanently delete droplet ID {args.destroy}!{Style.RESET_ALL}")
    confirm = input("Type 'yes' to confirm: ")
    if confirm == "yes":
        try:
            resp = client.droplets.destroy(droplet_id=droplet_id)
            # Response will be "None" if droplet was successfully destroyed
            print(f"\n{Fore.GREEN}Droplet '{args.destroy}' destroyed successfully{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"\n{Fore.RED}Unexpected error: {str(e)}{Style.RESET_ALL}")

    else:
        print(f"\n{Fore.YELLOW}Aborted.{Style.RESET_ALL}")

def shutdown_droplet(droplet_id):
    req = {
            "type": "shutdown"
        }
    
    try:
        client.droplet_actions.post(droplet_id=droplet_id, body=req)
        print(f"{Fore.YELLOW}Sent shutdown command to droplet {droplet_id}{Style.RESET_ALL}")
        print(" Waiting for shutdown...", end="")
        
        while True:
            time.sleep(1)
            print(".", end="", flush=True)
            details = client.droplets.get(droplet_id)
            status = details["droplet"]["status"]
            if status == "off":
                print(f"\n{Fore.RED}Droplet is now OFF{Style.RESET_ALL}")
                break
    except Exception as e:
        print(f"\n{Fore.RED}Failed to shutdown: {str(e)}{Style.RESET_ALL}")

def power_on_droplet(droplet_id):
    req = {
        "type": "power_on"
    }

    try:
        client.droplet_actions.post(droplet_id=droplet_id, body=req)
        print(f"{Fore.YELLOW}Sent power on command to droplet {droplet_id}{Style.RESET_ALL}")
        print(" Waiting for power on...", end="")
        
        while True:
            time.sleep(1)
            print(".", end="", flush=True)
            details = client.droplets.get(droplet_id)
            status = details["droplet"]["status"]
            if status == "active":
                print(f"\n{Fore.GREEN}Droplet is now ON{Style.RESET_ALL}")
                break

        get_ssh_cmd(droplet_id)

    except Exception as e:
        print(f"\n{Fore.RED}Failed to power on: {str(e)}{Style.RESET_ALL}")

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="""
    DropletForge — Instantly deploy and manage secure droplets

    Examples:
      python3 dropletforge.py --create --name phishing-infra
      python3 dropletforge.py -c -n test-server --allow-ip 203.0.113.42
      python3 dropletforge.py --list
      python3 dropletforge.py --destroy 123456789
      python3 dropletforge.py --on 123456789
      python3 dropletforge.py --off 123456789
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Happy forging!"
    )

    parser.add_argument("-l", "--list", action="store_true", help="List all droplets to include their ID, Name, Status, and Public IP")
    parser.add_argument("-c", "--create", action="store_true", help="Create a new droplet")
    parser.add_argument("-n", "--name", type=str, help="Name of the droplet (required with --create)")
    parser.add_argument("--allow-ip", type=str, help="IP to allow access to droplet (default: auto-detect your current public IP)")
    parser.add_argument("--no-fw", action="store_true", help="Skip firewall creation (not recommended)")
    parser.add_argument("-d", "--destroy", type=str, metavar="DROPLET_ID", help="Permanently destroy a droplet [find its ID first by using --list]")
    parser.add_argument("--region", default="nyc1", help="Region")
    parser.add_argument("--size", default="s-1vcpu-1gb", help="Droplet size")
    parser.add_argument("--image", default="ubuntu-24-04-x64", help="Image")
    parser.add_argument("--off", type=int, metavar="DROPLET_ID", help="Shutdown a droplet")
    parser.add_argument("--on", type=int, metavar="DROPLET_ID", help="Power on a droplet")


    args = parser.parse_args()
    return args

if __name__ == "__main__":
    print(banner)
    args = parse_arguments()

    if args.list:
        list_droplets()

    elif args.destroy:
        destroy_droplet(args.destroy)

    elif args.off:
        shutdown_droplet(args.off)

    elif args.on:
        power_on_droplet(args.on)

    elif args.create and not args.name:
        print(f"{Fore.YELLOW}--create requires --name to be specified{Style.RESET_ALL}")
    
    # Create the droplet
    else:
        droplet = create_droplet(args.name, args.region, args.size, args.image)
        
        # Handle failed droplet creation
        if droplet is None:
            print(f"\n{Fore.RED}[-] Droplet creation failed — aborting{Style.RESET_ALL}")
            exit(1)
        
        droplet_id = droplet[0]
        public_ip = droplet[1]

        if args.no_fw:
            print(f"{Fore.RED} [-] WARNING: your droplet is not behind a firewall because you used '--no-fw'{Style.RESET_ALL}")
        else:
            allowed_ip = get_allowed_ip(args.allow_ip)
            create_firewall(droplet_id, args.name, allowed_ip)

        print(f"\n SSH into your droplet:\n")
        print(f"   ssh -i ~/.ssh/{args.name} root@{public_ip}\n")
