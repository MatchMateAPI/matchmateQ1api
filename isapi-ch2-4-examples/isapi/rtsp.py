"""
RTSP 客户端 —— 覆盖 4.3 实时预览 与 4.4 录像回放。

URL 编址（3.4.1 / 4.3）：
  实时：rtsp://<host>[:port]/ISAPI/Streaming/channels/<ID>
  回放：rtsp://<host>/ISAPI/Streaming/tracks/<ID>/?starttime=...&endtime=...
  <ID> = 通道号 × 100 + 码流类型（1 主 / 2 子 / 3 三）
认证：与 ISAPI 相同的 Digest（MD5），见 4.3 步骤 1 / 4.4 注。

六步流程（4.3）：
  DESCRIBE(401->带Authorization重发) -> 解析SDP -> SETUP(trackID=1,2) ->
  PLAY -> 接收RTP(分包重组) -> TEARDOWN
"""
from __future__ import annotations
import base64
import hashlib
import re
import socket


def md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


class DigestRTSP:
    """最小 RTSP 客户端（TCP interleaved 传输）。

    用例：
        >>> c = DigestRTSP("10.21.84.147", "admin", "admin12345")
        >>> sdp = c.describe("/ISAPI/Streaming/channels/101")
        >>> c.setup(track="trackID=1"); c.setup(track="trackID=2")
        >>> c.play(); packets = c.recv_rtp(10); c.teardown()
    """

    def __init__(self, host: str, user: str, pwd: str, port: int = 554, timeout: int = 10):
        self.host, self.port, self.user, self.pwd = host, port, user, pwd
        self.timeout = timeout
        self.cseq = 0
        self.session = None
        self.realm = self.nonce = None
        self.sock = socket.create_connection((host, port), timeout=timeout)

    # ---- 内部：Digest 计算（与 ISAPI 一致，4.3 注） ----
    def _auth_header(self, method: str, uri: str) -> str:
        ha1 = md5(f"{self.user}:{self.realm}:{self.pwd}")
        ha2 = md5(f"{method}:{uri}")
        resp = md5(f"{ha1}:{self.nonce}:{ha2}")
        return (f'Digest username="{self.user}", realm="{self.realm}", nonce="{self.nonce}", '
                f'uri="{uri}", response="{resp}"')

    def _send(self, method: str, uri: str, extra: dict | None = None) -> str:
        self.cseq += 1
        lines = [f"{method} {uri} RTSP/1.0", f"CSeq: {self.cseq}"]
        if self.realm:  # 已认证后每条请求都带 Authorization
            lines.append(f"Authorization: {self._auth_header(method, uri)}")
        if self.session:
            lines.append(f"Session: {self.session}")
        for k, v in (extra or {}).items():
            lines.append(f"{k}: {v}")
        lines.append("User-Agent: isapi-ch2-4-examples")
        self.sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
        return self._read_response()

    def _read_response(self) -> str:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            data += chunk
        return data.decode(errors="replace")

    # ---- 步骤1-2：DESCRIBE + 401 Digest 重协商 ----
    def describe(self, path: str) -> str:
        """DESCRIBE 并处理 401。返回 SDP 文本。

        4.3.3 用例：设备返回 401 + WWW-Authenticate: Digest realm=..., nonce=...，
        客户端重发带 Authorization 的 DESCRIBE，得 200 + SDP。"""
        uri = f"rtsp://{self.host}:{self.port}{path}"
        resp = self._send("DESCRIBE", uri, {"Accept": "application/sdp"})
        if "401" in resp.splitlines()[0]:
            m = re.search(r'realm="([^"]+)",\s*nonce="([^"]+)"', resp)
            self.realm, self.nonce = m.group(1), m.group(2)
            resp = self._send("DESCRIBE", uri, {"Accept": "application/sdp"})
        # 返回 body（SDP）
        return resp.split("\r\n\r\n", 1)[-1]

    # ---- 步骤3：SETUP（按 trackID 分别建立，4.3 步骤3）----
    def setup(self, track: str, path: str) -> str:
        """track 例：'trackID=1'(视频) / 'trackID=2'(音频)。RTP/AVP/TCP interleaved。"""
        uri = f"rtsp://{self.host}:{self.port}{path}/{track}"
        ch = "0-1" if track.endswith("1") else "2-3"
        resp = self._send("SETUP", uri,
                          {"Transport": f"RTP/AVP/TCP;unicast;interleaved={ch};ssrc=0"})
        m = re.search(r"Session:\s*(\d+)", resp)
        if m:
            self.session = m.group(1)
        return resp

    # ---- 步骤4：PLAY ----
    def play(self, path: str, scale: float | None = None) -> str:
        """PLAY 开始推流。回放时可用 scale 做快放/慢放（4.4 注：Scale 头，RFC 7826 §12.34）。"""
        uri = f"rtsp://{self.host}:{self.port}{path}"
        extra = {"Range": "npt=0.000000-0.000000"}
        if scale:
            extra["Scale"] = str(scale)
        return self._send("PLAY", uri, extra)

    # ---- 步骤5：接收 RTP（TCP interleaved，需分包重组，4.3 步骤5）----
    def recv_rtp(self, count: int = 10) -> list[bytes]:
        """接收 count 个 RTP 包。TCP 交错帧以 '$' 开头：$ + channel + length(2B) + payload。"""
        pkts = []
        buf = b""
        while len(pkts) < count:
            chunk = self.sock.recv(65535)
            if not chunk:
                break
            buf += chunk
            while True:
                i = buf.find(b"$")
                if i < 0 or len(buf) < i + 4:
                    break
                length = int.from_bytes(buf[i + 2:i + 4], "big")
                if len(buf) < i + 4 + length:
                    break
                pkts.append(buf[i + 4:i + 4 + length])
                buf = buf[i + 4 + length:]
        return pkts

    # ---- 步骤6：TEARDOWN ----
    def teardown(self, path: str) -> str:
        uri = f"rtsp://{self.host}:{self.port}{path}"
        return self._send("TEARDOWN", uri)

    def close(self):
        self.sock.close()


# ---- URL 构造工具（3.4.1 / 4.3 / 4.4） ----
def live_url(host: str, channel: int, stream: int = 1, port: int = 554) -> str:
    """实时预览地址。用例：live_url('172.7.203.11', 17, 1) ->
    rtsp://172.7.203.11:554/ISAPI/Streaming/channels/1701"""
    return f"rtsp://{host}:{port}/ISAPI/Streaming/channels/{channel * 100 + stream}"


def playback_path(track_id: int, start: str, end: str, name: str, size: int) -> str:
    """回放地址（对应 4.4.3.2 playbackURI 的 path 部分）。"""
    return (f"/ISAPI/Streaming/tracks/{track_id}/?"
            f"starttime={start}&endtime={end}&name={name}&size={size}")
