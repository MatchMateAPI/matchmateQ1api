"""Ch4.3 实时预览 —— RTSP channels/<ID> 六步流程。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from isapi.rtsp import DigestRTSP, live_url

HOST = os.environ.get("ISAPI_HOST", "10.21.84.147")
USER = os.environ.get("ISAPI_USER", "admin")
PWD  = os.environ.get("ISAPI_PASS", "admin12345")

if __name__ == "__main__":
    path = "/ISAPI/Streaming/channels/101"     # 通道1主码流
    c = DigestRTSP(HOST, USER, PWD)
    print("SDP:\n", c.describe(path))          # 步骤1-2：DESCRIBE(401重发)+SDP
    c.setup("trackID=1", path); c.setup("trackID=2", path)  # 步骤3：两次 SETUP
    c.play(path)                                # 步骤4：PLAY
    pkts = c.recv_rtp(10)                       # 步骤5：收 10 个 RTP 包(分包重组)
    print("收到 RTP 包:", [len(p) for p in pkts])
    c.teardown(path); c.close()                 # 步骤6：TEARDOWN
