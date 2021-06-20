import yaml
import boto3
import logging
from Crypto.PublicKey import RSA
import urllib.request

logging.basicConfig(filename='%s.log' % ("deploy"), filemode='w', format='%(name)s - %(levelname)s - %(message)s')

setupUserScript = """#!/bin/bash
"""

createGroupPerms = """
groupadd datagrp
chgrp datagrp /data
chmod 775 /data
"""

def getExternalIP():
    with urllib.request.urlopen('https://checkip.amazonaws.com') as response:
        return response.read().decode("utf-8")

def setupUser(login, key):
    return """
adduser %(login)s
usermod -a -G datagrp %(login)s
su - %(login)s
mkdir /home/%(login)s/.ssh
chmod 700 /home/%(login)s/.ssh
touch /home/%(login)s/.ssh/authorized_keys
chmod 600 /home/%(login)s/.ssh/authorized_keys
echo "%(key)s" > /home/%(login)s/.ssh/authorized_keys
chown %(login)s:%(login)s /home/%(login)s/.ssh
chown %(login)s:%(login)s /home/%(login)s/.ssh/authorized_keys


    """ % {'login':login, 'key':key}

def setupMount(mount, dev, type):
    return """
mkfs.%(type)s %(dev)s
mkdir %(mount)s
mount -o rw %(dev)s %(mount)s
    """ % {'type': type, 'mount':mount, 'dev':dev}

def keygen():
    with open("config_base.yaml") as f:
        config_base = yaml.load(f, Loader=yaml.FullLoader)
        for i in range(0, 2):
            if config_base["server"]["users"][i]["ssh_key"] is None:
                key = RSA.generate(1024)
                with open("user%s.pem" % str(i+1), "wb") as f:
                    f.write(key.exportKey('PEM'))
                config_base["server"]["users"][i]["ssh_key"] = key.public_key().exportKey('OpenSSH').decode("utf-8")
    with open("config.yaml", "w") as f:
        f.write(yaml.dump(config_base))

def awsKeyGen(ec2):
    keypair = ec2.create_key_pair(KeyName="fetch-root")
    with open("fetch-root.pem", "w") as f:
        f.write(keypair.key_material)

def deploy():
    try:
        with open("config.yaml") as f:
            try:
                config = yaml.load(f, Loader=yaml.FullLoader)
            except Exception as e:
                logging.error("Error when loading yaml file - perhaps formatting issue?")
                logging.error(str(e))
                raise e

    except FileNotFoundError as e:
        logging.error("config.yaml file not found - please place it in the same directory as deploy.py")
        logging.error(str(e))
        raise e
    except Exception as e:
        logging.error("Something else went wrong - " + str(e))
        logging.error(str(e))
        raise e

    try:
        REGION_NAME = config['server']['region_name']
        AMI_NAME = config['server']['ami_type'] + '*'
        AMI_ARCH = config['server']['architecture']
        AMI_ROOT_DEVICE_TYPE = config['server']['root_device_type']
        AMI_OWNER = config['server']['ami_owner']
        AMI_VIRT_TYPE = config['server']['virtualization_type']
        VOLUMES = config['server']['volumes']
        USERS = config['server']['users']
        KEY_NAME = config['server']['key_name']

        INSTANCE_TYPE = config['server']['instance_type']
        MIN_COUNT = config['server']['min_count']
        MAX_COUNT = config['server']['max_count']

    except Exception as e:
        logging.error(str(e))
        raise e
    try:
        client = boto3.client('ec2',
                              region_name=REGION_NAME
                              )
        ec2 = boto3.resource('ec2', region_name=REGION_NAME)
    except Exception as e:
        logging.error("There seemed to be an issue setting up the AWS client - do you have the following ENV variables set?")
        logging.error("AWS_ACCESS_KEY_ID")
        logging.error("AWS_SECRET_ACCESS_KEY")
        logging.error(str(e))
        raise e

    response = client.describe_images(
        Owners=[AMI_OWNER],
        Filters=
        [
            {'Name': 'name', 'Values': [AMI_NAME]},
            {'Name': 'architecture', 'Values': [AMI_ARCH]},
            {'Name': 'root-device-type', 'Values': [AMI_ROOT_DEVICE_TYPE]},
            {'Name': 'virtualization-type', 'Values': [AMI_VIRT_TYPE]},
            {'Name': 'block-device-mapping.volume-size', 'Values': ['8']},
            {'Name': 'platform-details', 'Values': ['Linux/UNIX']},
        ]
    )

    amis = sorted(response['Images'],
                  key=lambda x: x['CreationDate'],
                  reverse=True)
    amiID = amis[0]["ImageId"]

    BlockDeviceMapping = []
    userScript = setupUserScript
    for vol in VOLUMES:
        userScript += setupMount(vol["mount"], vol["device"], vol["type"])
        BlockDeviceMapping.append({
            'DeviceName': vol['device'],
            'Ebs': {
                'VolumeSize': vol['size_gb']
            }
        })
    userScript += createGroupPerms
    for user in USERS:
        userScript += setupUser(user["login"], user["ssh_key"])


    if KEY_NAME is None:
        try:
            awsKeyGen(ec2)
        except Exception as e:
            pass
        KEY_NAME = "fetch-root"

    print("Attempting to create instance")
    instances = ec2.create_instances(
        KeyName=KEY_NAME,
        ImageId=amiID,
        InstanceType=INSTANCE_TYPE,
        MinCount=MIN_COUNT,
        MaxCount=MAX_COUNT,
        UserData=userScript,
        BlockDeviceMappings=BlockDeviceMapping
    )

    print("Waiting for instance to be created...")
    instanceCreated = instances[0]
    instanceId = [instanceCreated.id]
    waiter = ec2.meta.client.get_waiter('instance_running')
    waiter.wait(InstanceIds=instanceId)
    print("Instace created....")

    try:
        sgId = instanceCreated.security_groups[0]['GroupId']
        resp = client.authorize_security_group_ingress(
            GroupId=sgId,
            IpPermissions=[
                {'IpProtocol': 'tcp',
                 'FromPort': 22,
                 'ToPort': 22,
                 'IpRanges': [{'CidrIp': getExternalIP().strip() + "/32"}]}
            ])
    except Exception as e:
        if e.response["Error"]["Code"] == 'InvalidPermission.Duplicate':
            logging.info("Rule already exists")
        else:
            logging.error("Issue adding security group")
            logging.error(str(e))

    instance = client.describe_instances(
        InstanceIds=[
            instanceCreated.instance_id,
        ],
    )

    publicIP = instance['Reservations'][0]["Instances"][0]['PublicIpAddress']
    print("Instance created successfully!")
    print("Public IP => " + publicIP)
    print("SSH instructions:")
    print("ssh -i fetch-root.pem ec2-user@" + publicIP)
    print("ssh -i user1.pem user1@" + publicIP)
    print("ssh -i user2.pem user2@" + publicIP)


if __name__ == "__main__":
    keygen()
    deploy()
