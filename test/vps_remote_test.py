import paramiko
import os
import sys
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def run_vps_test():
    host = "121.36.42.119"
    user = "root"
    pw = "Qweedc213!"
    
    print(f"Connecting to {host}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(host, username=user, password=pw)
        print("Connected!")
        
        sftp = ssh.open_sftp()
        
        files = [
            ("SayuStock/utils/image.py", "/root/gsuid_core/gsuid_core/plugins/SayuStock/SayuStock/utils/image.py"),
            ("SayuStock/stock_cloudmap/get_cloudmap.py", "/root/gsuid_core/gsuid_core/plugins/SayuStock/SayuStock/stock_cloudmap/get_cloudmap.py"),
            ("SayuStock/stock_info/draw_info.py", "/root/gsuid_core/gsuid_core/plugins/SayuStock/SayuStock/stock_info/draw_info.py"),
            ("SayuStock/stock_info/draw_future.py", "/root/gsuid_core/gsuid_core/plugins/SayuStock/SayuStock/stock_info/draw_future.py"),
            ("test/vps_test.py", "/root/test_promax_vps.py"),
            ("test/vps_sanity.py", "/root/vps_sanity.py")
        ]
        
        for local, remote in files:
            sftp.put(local, remote)
            
        print("Running Sanity Check...")
        stdin, stdout, stderr = ssh.exec_command("cd /root/gsuid_core && /root/.local/bin/uv run python3 /root/vps_sanity.py")
        print(stdout.read().decode('utf-8'))
        print(stderr.read().decode('utf-8'))
            
        print("Running Full Dashboard Test...")
        cmd = "cd /root/gsuid_core && /root/.local/bin/uv run python3 /root/test_promax_vps.py"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        
        output = stdout.read().decode('utf-8')
        errors = stderr.read().decode('utf-8')
        
        print("--- STDOUT ---")
        print(output)
        print("--- STDERR ---")
        print(errors)
        
        if "SUCCESS" in output:
            print("VPS Test PASSED!")
            local_path = "test/all_weather_VPS_VERIFIED.png"
            sftp.get("/root/all_weather_VPS_TEST.png", local_path)
            print(f"Image saved to {local_path}")
        else:
            print("VPS Test FAILED.")
            
        sftp.close()
    finally:
        ssh.close()

if __name__ == "__main__":
    run_vps_test()
