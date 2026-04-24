import sys
sys.path.insert(0, "/root/gsuid_core")
sys.path.insert(0, "/root/gsuid_core/gsuid_core")
sys.path.insert(0, "/root/gsuid_core/gsuid_core/plugins/SayuStock")

try:
    import SayuStock
    print(f"IMPORT SUCCESS: SayuStock version {getattr(SayuStock, '__version__', 'unknown')}")
except Exception as e:
    print(f"IMPORT FAILED: {e}")
    import traceback
    traceback.print_exc()
