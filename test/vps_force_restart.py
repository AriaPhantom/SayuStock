import paramiko
import time

def force_restart():
    host = "121.36.42.119"
    user = "root"
    pw = "Qweedc213!"
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(host, username=user, password=pw)
        print("Forcing Clean Restart...")
        
        # Follow the cleanup steps in GSUID.md
        cmds = [
            "systemctl stop gsuid || true",
            "pkill -f '/root/.local/bin/uv run core' || true",
            "pkill -f '/root/gsuid_core/.venv/bin/core' || true",
            "systemctl reset-failed gsuid",
            "systemctl start gsuid"
        ]
        
        for cmd in cmds:
            print(f"Running: {cmd}")
            ssh.exec_command(cmd)
            time.sleep(1)
            
        # Verify
        time.sleep(3)
        stdin, stdout, stderr = ssh.exec_command("systemctl is-active gsuid")
        status = stdout.read().decode().strip()
        print(f"Final Status: {status}")
        
    finally:
        ssh.close()

if __name__ == "__main__":
    force_restart()
