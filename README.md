# 💧What is Droplet Forge?

Droplet Forge gives you the ability to quickly spin up and manage Digital Ocean Droplets (virtual private servers) via the command line in a secure way. No more logging into your account with a browser just because you forgot what your droplets public IP was. One command will spin up your droplet, generate an SSH key that you can use for authentication, and even create a firewall rule that will only allow access from your public IP over SSH.

## Features

- Auto-generates a unique SSH key for each droplet you create
- Automatically places your droplet behind a firewall that will only allow SSH traffic from your networks public IP (this can be overridden with `--allow-ip`)
- List all of your droplets along with their statuses and public IPs
- Shutdown / power on / destroy a droplet all from the command line

## Prerequisites

- Python 3.x
- Linux
- [Digital Ocean](https://www.digitalocean.com) account (no, I’m not an affiliate 😂)

**DISCLAIMER:** Using this tool can create resources that cost money. I’ve set the defaults to create droplets that will run $6/mo, but it is your responsibility to make sure you’re keeping track of what you’re doing. 

## Install
### Grab an API Key

To use this tool, you need a Digital Ocean API key. It’s super simple to grab one. 

Navigate to https://cloud.digitalocean.com/account/api/tokens and then click `Generate New Token` 

Give your token a name, set the expiration to something you’re comfortable with, give it `Full Access` under “Scopes” and click “Generate Token”.

<center><img width="400" height="400" alt="image" src="https://github.com/user-attachments/assets/b43fd197-0353-4b60-8357-2fa3a6709469" /></center>

<img width="1000" height="524" alt="image" src="https://github.com/user-attachments/assets/e9af5460-8448-4a7f-8108-c8a46f66dfb5" />


<br>Make sure you copy this token and then add this as an environment variable on the Linux machine you’ll be running this script from.

**NOTE:** You must use the env var name `DO_API_KEY` otherwise the script won’t recognize it.

```python
export DO_API_KEY=dop_v1_rest_of_token_here
```

Now run the following commands:

```python
git clone https://github.com/boxalarm/dropletforge

# Create a virtual env
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

# ⌨️ Usage
### **Create a Droplet**
<img width="600" height="894" alt="image" src="https://github.com/user-attachments/assets/1f3d5edf-dc48-472a-be29-327cd845f880" />

By default a Droplet will be created with the following settings:

- Size: `s-1vcpu-1gb`
- Region: `nyc1`
- Image: `ubuntu-24-04-x64`

```python
python3 dropletforge.py --create --name phishing-infra
python3 dropletforge.py -c -n phishing-infra
```

An SSH key pair will automatically be generated and stored in `~/.ssh`. The name of the private and public key file will be the name of the droplet itself (whatever was provided to the `--name` parameter).

Additionally, the droplet will be placed behind a firewall with the name `DropletForge-{droplet_name}`. By default, a rule will be created that only allows TCP traffic to port 22 (SSH) from the public IP of the network you’re connected to (e.g. your home network).

<br>You can also specify the `--size`, `--region`, and `--image` for the droplet you’re creating:

```python
python3 dropletforge.py -c -n jenkins-server --size s-2vcpu-4gb --region lon1 --image jenkins
```

To view a full list of options (and to see pricing), visit: [https://slugs.do-api.dev](https://slugs.do-api.dev/) 

<br>You can specify an IP to override the default setting if you’d like using the `--allow-ip` parameter:

```python
python3 dropletforge.py -c -n phishing-infra --allow-ip 8.8.8.8 
```

<br>While it’s not recommended, if you want to spin up a new droplet without a firewall, you can use `--no-fw`:

```python
python3 dropletforge.py -c -n phishing-infra --no-fw
```

You can always add a firewall later by logging into the Digital Ocean dashboard (and I may add that functionality to this tool in the future).

<br>Once the script finishes, it will provide you with the command to SSH into your new droplet. Just copy and paste that to your terminal and you’ll be logged in!

<img width="400" height="118" alt="image" src="https://github.com/user-attachments/assets/bb217df0-f11a-4178-bad6-9370926ec111" />


### List Droplets

To get a list of all your droplets, including their status and public IP:

```python
python3 dropletforge.py --list
python3 dropletforge.py -l
```

<img width="600" height="674" alt="image" src="https://github.com/user-attachments/assets/6379619f-128d-4ec0-bdd1-da265a9eee10" />

### On / Off / Destroy

You can also turn a droplet off, turn it back on, and even destroy it:

```python
python3 dropletforge.py --off [droplet_id]
python3 dropletforge.py --on [droplet_id]
python3 dropletforge.py --destroy [droplet_id]
```

To get the `droplet_id` needed for these commands, just run `--list` first.
