"""
4.5 事件上报 —— 三种接收方式。

对比（定义）：
  非订阅布防  GET  alertStream        客户端长连接，收全部事件
  订阅布防    POST subscribeEvent     客户端长连接，只收订阅列表事件
  监听        设备主动 POST httpHosts  平台开端口，设备主动推送（无心跳）

通用限制（4.5.1）：HTTP 长连接单工——布防连接建立后客户端不能再发消息；
                  心跳超时未收到消息应主动断开重连。
"""
from __future__ import annotations
import json
import requests
from requests.auth import HTTPDigestAuth
from .parsing import parse_multipart


class EventReceiver:
    def __init__(self, host: str, user: str, pwd: str, port: int = 80):
        self.base = f"http://{host}:{port}"
        self.auth = HTTPDigestAuth(user, pwd)

    # ---------- 4.5.1.1 非订阅布防 ----------
    def alert_stream(self, on_event, max_events: int = 20):
        """GET /ISAPI/Event/notification/alertStream —— 收全部事件。

        调用方式：Connection: keep-alive；401 后带 Digest 重发；
        按 multipart/mixed 的 boundary 分割；部分报警为 JSON，按 Content-Type 区分。
        """
        with requests.get(f"{self.base}/ISAPI/Event/notification/alertStream",
                          auth=self.auth, stream=True,
                          headers={"Connection": "keep-alive"}, timeout=None) as r:
            r.raise_for_status()
            boundary = r.headers["Content-Type"].split("boundary=")[-1]
            buf = b""
            n = 0
            for chunk in r.iter_content(8192):
                buf += chunk
                while f"--{boundary}".encode() in buf[len(boundary) + 4:]:
                    # 简单按 boundary 切段
                    parts = parse_multipart(buf, boundary)
                    if len(parts) > 1:
                        for p in parts:
                            if p.body:
                                on_event(p.content_type, p.body)
                                n += 1
                        buf = b""
                    if n >= max_events:
                        return
                    break

    # ---------- 4.5.1.2 订阅布防 ----------
    def subscribe_capable(self) -> bool:
        """步骤1-2：GET /ISAPI/System/capabilities，判断 isSupportSubscribeEvent。"""
        r = requests.get(f"{self.base}/ISAPI/System/capabilities",
                         auth=self.auth, timeout=10)
        return "isSupportSubscribeEvent" in r.text and "true" in r.text.lower()

    def subscribe_event_cap(self) -> str:
        """步骤3：GET /ISAPI/Event/notification/subscribeEventCap 订阅能力。"""
        r = requests.get(f"{self.base}/ISAPI/Event/notification/subscribeEventCap",
                         auth=self.auth, timeout=10)
        return r.text

    def subscribe(self, event_types: list[str], on_event, max_events: int = 20):
        """步骤4：POST /ISAPI/Event/notification/subscribeEvent 建立订阅长连接。

        链路三类数据：SubscribeEventResponse / EventNotificationAlert(heartBeat) / 图片。
        设备不主动断链，无表单结束符。退订见 unsubscribe()。"""
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<SubscribeEvent xmlns="http://www.isapi.org/ver20/XMLSchema" version="2.0">'
            "<eventTypeList>" +
            "".join(f"<eventType>{t}</eventType>" for t in event_types) +
            "</eventTypeList></SubscribeEvent>"
        )
        with requests.post(f"{self.base}/ISAPI/Event/notification/subscribeEvent",
                           auth=self.auth, data=body.encode(),
                           headers={"Connection": "keep-alive",
                                    "Content-Type": 'application/xml; charset="UTF-8"'},
                           stream=True, timeout=None) as r:
            r.raise_for_status()
            boundary = r.headers["Content-Type"].split("boundary=")[-1]
            buf, n = b"", 0
            for chunk in r.iter_content(8192):
                buf += chunk
                parts = parse_multipart(buf, boundary)
                for p in parts:
                    if not p.body:
                        continue
                    on_event(p.content_type, p.body)
                    n += 1
                if n >= max_events:
                    return

    def unsubscribe(self, subscribe_event_id: str) -> str:
        """步骤7（可选）：PUT /ISAPI/Event/notification/unSubscribeEvent?ID=<id>。
        HTTP 直连设备时直接断开即可，可不调用。"""
        r = requests.put(f"{self.base}/ISAPI/Event/notification/unSubscribeEvent",
                         params={"ID": subscribe_event_id}, auth=self.auth, timeout=10)
        return r.text


# ---------- 4.5.2 监听（httpHosts） ----------
class HttpHosts:
    """监听主机配置（设备侧）+ 平台监听端解析。

    配置流程（4.5.2.1）：
      1. GET  httpHosts/capabilities —— 判断支持（返回 HttpHostNotificationCap）
      2. PUT  httpHosts[/<hostID>]?security=&iv= —— 配置推送地址
      3. 平台开启 TCP 监听（普通网络编程）
      4. POST httpHosts/<hostID>/test —— 连通测试
      5. 接收报警（application/xml|json 或 multipart/form-data）
      备注：超时等参数 httpHosts/<hostID>/uploadCtrl
    """

    def __init__(self, host: str, user: str, pwd: str, port: int = 80):
        self.base = f"http://{host}:{port}"
        self.auth = HTTPDigestAuth(user, pwd)

    def capable(self) -> bool:
        r = requests.get(f"{self.base}/ISAPI/Event/notification/httpHosts/capabilities",
                         auth=self.auth, timeout=10)
        return "HttpHostNotificationCap" in r.text

    def set_host(self, host_id: int, ip: str, port: int, uri: str = "/",
                 security: str = "0", iv: str = "") -> str:
        """PUT /ISAPI/Event/notification/httpHosts/<hostID>?security=<s>&iv=<iv>"""
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<HttpHostNotification xmlns="http://www.isapi.org/ver20/XMLSchema" version="2.0">'
            f"<id>{host_id}</id><url>{uri}</url>"
            f"<addressingFormatType>ipaddress</addressingFormatType>"
            f"<ipAddress>{ip}</ipAddress><portNo>{port}</portNo>"
            "<protocolType>HTTP</protocolType>"
            "</HttpHostNotification>"
        )
        r = requests.put(f"{self.base}/ISAPI/Event/notification/httpHosts/{host_id}",
                         params={"security": security, "iv": iv},
                         auth=self.auth, data=body.encode(),
                         headers={"Content-Type": 'application/xml; charset="UTF-8"'},
                         timeout=10)
        return r.text

    def test(self, host_id: int) -> str:
        """POST /ISAPI/Event/notification/httpHosts/<hostID>/test 连通测试。"""
        r = requests.post(f"{self.base}/ISAPI/Event/notification/httpHosts/{host_id}/test",
                          auth=self.auth, timeout=10)
        return r.text


def parse_incoming_alarm(body: bytes, content_type: str):
    """平台监听端解析（4.5.2.2）。

    - application/xml|json：直接为 <EventNotificationAlert/>
    - multipart/form-data：含报文单元(Event_Type)与图片单元(Picture_Name)
    返回 (event_dict_or_xml, [images])
    """
    if "multipart/form-data" in content_type:
        boundary = content_type.split("boundary=")[-1]
        parts = parse_multipart(body, boundary)
        event, images = None, []
        for p in parts:
            if p.content_type and "image" in p.content_type:
                images.append(p.body)
            elif p.body.strip().startswith((b"<", b"{")):
                event = p.body
        return event, images
    # 纯报文
    try:
        return json.loads(body), []
    except Exception:
        return body.decode(errors="replace"), []
