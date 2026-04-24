import paramiko
import sys

def fetch_logs():
    host = "121.36.42.119"
    user = "root"
    pw = "Qweedc213!"
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(host, username=user, password=pw)
        sftp = ssh.open_sftp()
        
        remote_log = "/root/gsuid_core/data/logs/2026-04-25.log"
        local_log = "test/vps_real_time.log"
        
        print(f"Fetching {remote_log}...")
        sftp.get(remote_log, local_log)
        sftp.close()
        
        with open(local_log, "r", encoding="utf-8", errors="replace") as f:
            log_content = f.read()
            
        print("Log fetched successfully.")
        
        # Look for the LAST traceback
        if "Traceback" in log_content:
            print("\n--- LAST TRACEBACK DETECTED ---")
            idx = log_content.rfind("Traceback")
            print(log_content[idx:idx+2000])
        else:
            print("No Traceback found in the last log.")
            # Print last 50 lines anyway
            lines = log_content.splitlines()
            print("\n--- LAST 50 LINES ---")
            print("\n".join(lines[-50:]))
                
    finally:
        ssh.close()

if __name__ == "__main__":
    fetch_logs()
