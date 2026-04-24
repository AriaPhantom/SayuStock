import paramiko
import os

def final_deploy():
    host = "121.36.42.119"
    user = "root"
    pw = "Qweedc213!"
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(host, username=user, password=pw)
        print("Connected for Final Deploy...")
        
        # 1. Restart Service
        print("Restarting gsuid.service...")
        ssh.exec_command("systemctl restart gsuid")
        
        # 2. Verify Status
        import time
        time.sleep(2)
        stdin, stdout, stderr = ssh.exec_command("systemctl status gsuid --no-pager")
        status = stdout.read().decode('utf-8')
        print(f"Service Status:\n{status}")
        
        if "active (running)" in status:
            print("DEPLOYS SUCCESSFUL!")
        
        # 3. Cleanup Test Files
        print("Cleaning up test files on VPS...")
        ssh.exec_command("rm /root/test_promax_vps.py /root/vps_sanity.py /root/all_weather_VPS_TEST.png /root/test_out.log")
        
        print("VPS Finalized.")
        
    finally:
        ssh.close()

if __name__ == "__main__":
    final_deploy()
