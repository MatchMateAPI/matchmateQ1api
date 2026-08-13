"""
4.2 报文解析 —— 四种格式 + 注释标注 + 能力集 + 时间/字符集。

格式速查（类型）：
  XML    application/xml; charset="UTF-8"   默认，命名空间 ver20/XMLSchema v2.0
  JSON   application/json                   URL 追加 ?format=json
  BINARY application/octet-stream           固件/配置
  FORM   multipart/form-data (RFC 1867)     一次请求携带多份数据
"""
from __future__ import annotations
import re
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass

NS = "http://www.isapi.org/ver20/XMLSchema"   # 4.2.1.1 统一命名空间


# ---------- 4.2.1.4 multipart/form-data ----------
@dataclass
class FormPart:
    name: str
    filename: str | None
    content_type: str | None
    body: bytes


def build_multipart(parts: list[FormPart], boundary: str | None = None):
    """构造 RFC 1867 表单。返回 (body_bytes, content_type_header)。

    用例（4.2.1.4 请求示例 /ISAPI/Intelligent/FDLib/pictureUpload）：
        xml_part  = FormPart("PictureUploadData", None, "application/xml", xml_bytes)
        img_part  = FormPart("face_picture", "face_picture.jpg", "image/jpeg", jpg_bytes)
        body, ctype = build_multipart([xml_part, img_part])
    """
    boundary = boundary or uuid.uuid4().hex
    buf = bytearray()
    for p in parts:
        buf += f"--{boundary}\r\n".encode()
        disp = f'Content-Disposition: form-data; name="{p.name}"'
        if p.filename:
            disp += f'; filename="{p.filename}"'
        buf += (disp + "\r\n").encode()
        if p.content_type:
            buf += f"Content-Type: {p.content_type}\r\n".encode()
        buf += f"Content-Length: {len(p.body)}\r\n\r\n".encode()
        buf += p.body + b"\r\n"
    buf += f"--{boundary}--\r\n".encode()
    return bytes(buf), f"multipart/form-data; boundary={boundary}"


def parse_multipart(body: bytes, boundary: str) -> list[FormPart]:
    """按 boundary 分割解析表单单元（解析 4.2.1.4 / 4.5 事件流的关键）。"""
    parts = []
    for seg in body.split(f"--{boundary}".encode()):
        seg = seg.strip(b"\r\n")
        if not seg or seg == b"--":
            continue
        head, _, payload = seg.partition(b"\r\n\r\n")
        name = re.search(rb'name="([^"]+)"', head)
        fname = re.search(rb'filename="([^"]+)"', head)
        ctype = re.search(rb"Content-Type:\s*([^\r\n]+)", head, re.I)
        # 去掉尾部 Content-Length 与实际负载之间可能的空白
        parts.append(FormPart(
            name=name.group(1).decode() if name else "",
            filename=fname.group(1).decode() if fname else None,
            content_type=ctype.group(1).decode().strip() if ctype else None,
            body=payload.rstrip(b"\r\n"),
        ))
    return parts


# ---------- 4.2.2 注释标注解析 ----------
_ANNOT = re.compile(r"<!--(.*?)-->|/\*(.*?)\*/", re.S)

def parse_annotation(comment: str) -> dict:
    """把 'ro, req, int, 节点序号, range:[1,32]' 解析为结构化字典。

    返回键：access(ro/wo), presence(req/opt/dep), type(object/list/string/int/float/bool/enum),
            desc, range, subType
    """
    toks = [t.strip() for t in comment.split(",") if t.strip()]
    out = {"raw": comment}
    for t in toks:
        if t in ("ro", "wo"):
            out["access"] = t
        elif t in ("req", "opt", "dep"):
            out["presence"] = t
        elif t in ("object", "list", "string", "int", "float", "bool", "enum"):
            out["type"] = t
        elif t.startswith("range:"):
            out["range"] = t[6:]
        elif t.startswith("subType:"):
            out["subType"] = t[8:]
        elif t.startswith("desc:"):
            out["desc"] = t[5:]
    return out


# ---------- 4.2.3 能力集 ----------
def is_supported(cap: dict, key: str) -> bool:
    """JSON 能力集中判断 isSupportXxx。用例：is_supported(sys_cap, 'isSupportSubscribeEvent')"""
    return bool(cap.get(key))


def capability_url(path: str, *, type_: str | None = None, fmt_json: bool = True) -> str:
    """能力集 URL 统一以 /capabilities 结尾，可带 ?format=json&type=xxx。"""
    url = path.rstrip("/") + "/capabilities"
    qs = []
    if fmt_json:
        qs.append("format=json")
    if type_:
        qs.append(f"type={type_}")
    return url + ("?" + "&".join(qs) if qs else "")


# ---------- 4.2.4 时间格式 ----------
ISO8601_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})$")

def parse_iso8601(ts: str):
    """同时兼容 TD 格式（本地+偏移，推荐）与 TZ 格式（UTC，...Z）。

    用例：parse_iso8601('2017-08-16T20:17:06.123+08:00')"""
    from datetime import datetime
    m = ISO8601_RE.match(ts)
    if not m:
        raise ValueError(f"非 ISO 8601: {ts}")
    fmt = "%Y-%m-%dT%H:%M:%S"
    frac = m.group(7) or ""
    tz = "+00:00" if m.group(8) == "Z" else m.group(8)
    return datetime.strptime(ts.split("+")[0].split("Z")[0].split(".")[0], fmt)         .replace(tzinfo=__import__("datetime").timezone(__import__("datetime").timedelta(
            hours=int(tz[1:3]) * (1 if tz[0] == "+" else -1),
            minutes=int(tz[4:6]))))


# ---------- 4.2.5 字符集 ----------
SPECIALS_ALL = list("()+,-.;=@[]_{} !#$%&'*<>?^'|~\":\\")  # 33 个特殊符号
def check_charset(s: str, kind: str = "default") -> bool:
    """按 4.2.5 校验：username(1-30) / password(1-33) / display(1-15+多字节) / default。"""
    limits = {"username": 30, "password": 33, "display": 15, "default": 15}
    n = limits.get(kind, 15)
    allowed = set(SPECIALS_ALL[:n])
    multi_ok = kind in ("display", "default")
    for ch in s:
        if ch.isalnum() and ch.isascii():
            continue
        if ch in allowed:
            continue
        if multi_ok and not ch.isascii():
            continue
        return False
    return True


# ---------- XML 辅助 ----------
def strip_ns(xml_text: str) -> ET.Element:
    """去掉命名空间后解析（ISAPI XML 统一命名空间 ver20/XMLSchema）。"""
    xml_text = xml_text.replace(f'xmlns="{NS}"', "")
    return ET.fromstring(xml_text)
