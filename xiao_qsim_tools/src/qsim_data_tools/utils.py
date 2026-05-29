import smtplib
import socket
import sys
import subprocess
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def run_shell(command, check_stderr=True, abort=True):
    print("run shell: ", command)
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, shell=True)
    if result.returncode != 0 or (check_stderr and len(result.stderr) != 0):
        print("run shell failed, code %s, stderr %s" % (result.returncode, result.stderr))
        if abort:
            raise Exception('run shell failed')
    print("run shell finish, stdout: ", result.stdout)
    return result.stdout


def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('www.baidu.com', 0))
        ip = s.getsockname()[0]
        s.close()
    except:
        ip = "127.0.0.1"
    return ip


def get_debug_and_ip():
    debug = False
    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        debug = True
    ipaddr = get_ip()
    if ipaddr == "127.0.0.1":
        debug = True
        ipaddr = "192.168.1.244"
    if debug:
        print("debug mode")
    print("ip:", ipaddr)
    return debug, ipaddr
