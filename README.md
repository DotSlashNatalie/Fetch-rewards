# Fetch Rewards

## Author

Natalie Adams

## Need to do

Develop an automation program that takes a YAML configuration file as input and deploys a Linux AWS EC2 instance with two volumes and two users.

Here are some guidelines to follow:

- Create a YAML file based on the configuration provided below for consumption by your application
- You may modify the configuration, but do not do so to the extent that you fundamentally change the exercise
- Include the YAML config file in your repo
- Use Python and Boto3
- Do not use configuration management, provisioning, or IaC tools such as Ansible, CloudFormation, Terraform, etc.

## Requirements

We must be able to:

1. Run your program
2. Deploy the virtual machine
3. SSH into the instance as user1 and user2
4. Read from and write to each of two volumes

## Assumptions

- You have Python 3 installed
  - Windows: https://www.python.org/downloads/
    - If you are on Windows that you have Python/pip in the %Path% environment variable
  - Linux
    - Should be installed by default on most distros
    - Debian
      - May need to install an extra package: apt-get install python3-venv
- You have an SSH client that can be ran via the command ssh
  - Windows
    - https://www.howtogeek.com/336775/how-to-enable-and-use-windows-10s-built-in-ssh-commands/
    - https://mobaxterm.mobatek.net/
  - Linux
    - Should be installed by default on most distros
- You have git installed (to get the repo)
- You have an AWS account setup. To get your keys Login to your AWS account
  - Click on your username in the upper right
  - Click on My security credentials
  - Click on "Access keys"
  - Click on "Create New Access Key"

## Pre-setup

- Debian 10 container
  - apt install git python3-venv

## Setup

### Linux

- python3 -m venv env
- source env/bin/activate
- pip install -r requirements.txt
- export AWS_ACCESS_KEY_ID=<yourid>
- export AWS_SECRET_ACCESS_KEY=<yourkey>

### Windows

- python3 -m venv env
- .\env\Scripts\activate
- pip install -r requirements.txt
- set AWS_ACCESS_KEY_ID=<yourid>
- set AWS_SECRET_ACCESS_KEY=<yourkey>

## Running

- python3 deploy.py
- chmod 400 fetch-root.pem
- chmod 400 user1.pem
- chmod 400 user2.pem

After running the script you should see some output similar to:

```
Attempting to create instance
Waiting for instance to be created...
Instace created....
Instance created successfully!
Public IP => <ip>
SSH instructions:
ssh -i fetch-root.pem ec2-user@<ip>
ssh -i user1.pem user1@<ip>
ssh -i user2.pem user2@<ip>
```

I did create a group called `datagrp` and gave it write permissions to `/data`. The requirements specified that you would need to read/write from the 2 volumes but it didn't specify which user you would be trying it as.

## Comments

- I'm assuming that if this program were to be used in a production environment that the SSH keys would be provided. For security's sake I will generate SSH keys on the fly rather than providing them via the repo.
- I modified the yaml to include the following keys:
  - region_name
    - This is to specify the region that you would like the instances in - the instructions did not specify but I figured it would be important to deploy to a region closet to you
  - key_name
    - This is used for the root SSH key (or ec2-user). If you do not specify one then one will be created in AWS with the name of fetch-root.pem
  - ami_owner
    - I used this to specify the owner of the AMI. It probably doesn't matter - but it's just another way to make it more flexible
- The instruction did not specify who required SSH access so I assumed it would be the person running the script - so I leveraged https://checkip.amazonaws.com to get the users external IP. This might be better as an option in the yaml file but it seemed outside of the scope of the test. I did NOT want to use 0.0.0.0/0 because that is extremely insecure. A specific IP or subnet should always be specified for any sort of remote access. HTTP/HTTPS can of course be more open but the requirements did not ask to open those ports.
- I created the Python script to leverage the provided yaml as a base (ie config_base.yaml) and populate the necessary information (such as the users SSH keys)
- The instructions did not specify features to terminate the instance so that was omitted
- I did not go into details of how to configure a system with Python 3 and ssh as I felt that was outside of the scope of this test. Creating instructions for that can encompass an entire week.

