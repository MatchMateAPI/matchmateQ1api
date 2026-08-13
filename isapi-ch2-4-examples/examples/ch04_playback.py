"""Ch4.4 录像回放 —— 月历查询 -> 检索 playbackURI -> RTSP 回放。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from isapi.client import from_env
from isapi.rtsp import DigestRTSP

TRACK = 101   # 通道1主码流

if __name__ == "__main__":
    client = from_env()
    # ①（可选）月历查询：POST .../record/tracks/<ID>/dailyDistribution
    cal = client.post(f"/ISAPI/ContentMgmt/record/tracks/{TRACK}/dailyDistribution",
        '<?xml version="1.0" encoding="utf-8"?>'
        '<trackDailyParam><year>2021</year><monthOfYear>08</monthOfYear></trackDailyParam>',
        content_type='application/xml; charset="UTF-8"')
    print("月历:", cal[:200], "...")

    # ② 录像检索：POST /ISAPI/ContentMgmt/search，解析 playbackURI
    result = client.post("/ISAPI/ContentMgmt/search",
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<CMSearchDescription><searchID>88C2CD4D-D3FA-4AD4-BD80-555C18205DCC</searchID>'
        '<trackList><trackID>101</trackID></trackList>'
        '<timeSpanList><timeSpan><startTime>2021-08-16T00:00:00Z</startTime>'
        '<endTime>2021-08-18T23:59:59Z</endTime></timeSpan></timeSpanList>'
        '<maxResults>100</maxResults><searchResultPostion>0</searchResultPostion>'
        '<metadataList><metadataDescriptor>//recordType.meta.std-cgi.com</metadataDescriptor>'
        '</metadataList></CMSearchDescription>',
        content_type='application/xml; charset="UTF-8"')
    print("检索结果:", result[:300], "...")
    # 从结果中取 playbackURI 后，用 DigestRTSP 回放（同 4.3 流程，支持 PAUSE / PLAY+Scale）
