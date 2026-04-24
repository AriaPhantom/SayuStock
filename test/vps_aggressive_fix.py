import paramiko
import time

def aggressive_fix():
    host = "121.36.42.119"
    user = "root"
    pw = "Qweedc213!"
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(host, username=user, password=pw)
        print("Aggressive Fix Started...")
        
        # 1. Stop service and kill everything
        ssh.exec_command("systemctl stop gsuid")
        ssh.exec_command("pkill -9 -f 'uv run core'")
        ssh.exec_command("pkill -9 -f 'gsuid_core'")
        time.sleep(2)
        
        # 2. Check if anything is still alive
        stdin, stdout, stderr = ssh.exec_command("ps aux | grep -E 'uv|gsuid' | grep -v grep")
        ps_out = stdout.read().decode()
        print(f"Remaining processes:\n{ps_out}")
        
        # 3. If something remains, kill by PID
        for line in ps_out.splitlines():
            parts = line.split()
            if len(parts) > 1:
                pid = parts[1]
                print(f"Killing PID {pid}")
                ssh.exec_command(f"kill -9 {pid}")
        
        time.sleep(1)
        
        # 4. Final start
        ssh.exec_command("systemctl reset-failed gsuid")
        ssh.exec_command("systemctl start gsuid")
        print("Service Started.")
        
        time.sleep(5)
        stdin, stdout, stderr = ssh.exec_command("systemctl is-active gsuid")
        print(f"Final Status: {stdout.read().decode().strip()}")
        
    finally:
        ssh.close()

if __name__ == "__main__":
    aggressive_fix()
