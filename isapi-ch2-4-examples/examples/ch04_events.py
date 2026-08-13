"""Ch4.5 事件上报 —— 三种接收方式演示。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from isapi.events import EventReceiver, HttpHosts, parse_incoming_alarm

HOST = os.environ.get("ISAPI_HOST", "192.168.18.84")
USER = os.environ.get("ISAPI_USER", "admin")
PWD  = os.environ.get("ISAPI_PASS", "admin12345")

def on_event(ctype, body):
    head = body[:120].decode(errors="replace") if isinstance(body, bytes) else str(body)[:120]
    print(f"[{ctype}] {head}")

if __name__ == "__main__":
    er = EventReceiver(HOST, USER, PWD)
    # 方式一：非订阅布防 GET /ISAPI/Event/notification/alertStream（收全部事件）
    # er.alert_stream(on_event, max_events=20)

    # 方式二：订阅布防（先探测能力）
    # if er.subscribe_capable():
    #     er.subscribe(["VMD", "ANPR"], on_event)

    # 方式三：监听 httpHosts（设备主动 POST 到平台）
    hh = HttpHosts(HOST, USER, PWD)
    print("支持监听主机?", hh.capable())
    # hh.set_host(1, "10.6.165.192", 8080, "/alarm")
    # hh.test(1)
    # 平台端收到后用 parse_incoming_alarm(body, content_type) 解析
