"""Ch3.2 激活示例 —— 3 个接口端到端。
用法：python examples/ch03_activation.py [新密码]
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from isapi.activation import Activator

HOST = os.environ.get("ISAPI_HOST", "192.168.18.84")

if __name__ == "__main__":
    act = Activator(HOST)
    # ① GET /SDK/activateStatus（免认证）
    activated = act.is_activated()
    print("已激活?" , activated)
    # ②③ 若未激活则执行激活
    if not activated:
        pwd = sys.argv[1] if len(sys.argv) > 1 else "Abc12345"
        print(act.activate(pwd))
