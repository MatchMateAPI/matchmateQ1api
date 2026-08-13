"""
ISAPI HTTP client with Digest authentication (RFC 7616) and unified error handling.

章节映射：
- 3.3.1 认证   —— 所有请求必须摘要认证
- 4.2.6 出错处理 —— HTTP 状态码 != 200 时解析 ISAPI 错误码结构
"""
from __future__ import annotations
import os
import requests
from requests.auth import HTTPDigestAuth


class ISAPIError(RuntimeError):
    """封装 4.2.6 的错误结构：
    {requestURL, statusCode, statusString, subStatusCode, errorCode, errorMsg}
    """

    def __init__(self, http_status: int, payload: dict | str):
        self.http_status = http_status
        self.payload = payload
        if isinstance(payload, dict):
            msg = (f"HTTP {http_status} ISAPI statusCode={payload.get('statusCode')} "
                   f"statusString={payload.get('statusString')} "
                   f"subStatusCode={payload.get('subStatusCode')} "
                   f"errorCode={payload.get('errorCode')} errorMsg={payload.get('errorMsg')}")
        else:
            msg = f"HTTP {http_status}: {payload[:200]}"
        super().__init__(msg)


class ISAPIClient:
    """最小 ISAPI 客户端。

    用法（用例）：
        >>> client = ISAPIClient("192.168.18.84", "admin", "admin12345")
        >>> xml = client.get("/ISAPI/System/deviceInfo")
    """

    def __init__(self, host: str, username: str, password: str,
                 port: int = 80, scheme: str = "http", timeout: int = 10):
        self.host, self.port, self.scheme = host, port, scheme
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = HTTPDigestAuth(username, password)   # 3.3.1 / 4.1 Digest
        self.base = f"{scheme}://{host}:{port}"

    # ---- 核心请求 ----
    def request(self, method: str, path: str, *, fmt: str | None = None,
                data: bytes | str | None = None, content_type: str | None = None,
                stream: bool = False, params: dict | None = None, **kw) -> requests.Response:
        """统一请求入口。

        - fmt="json" 时在 URL 追加 ?format=json（4.2.1.2 规则）
        - HTTP != 200 时抛出 ISAPIError（4.2.6）
        """
        url = self.base + path
        params = dict(params or {})
        if fmt == "json":
            params["format"] = "json"
        headers = kw.pop("headers", {})
        if content_type:
            headers["Content-Type"] = content_type
        resp = self.session.request(method, url, params=params, data=data,
                                    headers=headers, timeout=self.timeout,
                                    stream=stream, **kw)
        if resp.status_code != 200:
            try:
                payload = resp.json()
            except Exception:
                payload = resp.text
            raise ISAPIError(resp.status_code, payload)
        return resp

    # ---- 便捷方法（定义/类型/调用方式见各章节注释） ----
    def get(self, path: str, **kw) -> str:
        return self.request("GET", path, **kw).text

    def get_json(self, path: str, **kw) -> dict:
        return self.request("GET", path, fmt="json", **kw).json()

    def put(self, path: str, body: str | bytes, **kw) -> str:
        return self.request("PUT", path, data=body, **kw).text

    def post(self, path: str, body: str | bytes, **kw) -> str:
        return self.request("POST", path, data=body, **kw).text

    # ---- 4.1 示范接口：验证认证调通 ----
    def device_info(self) -> str:
        """GET /ISAPI/System/deviceInfo —— 4.1 认证示例接口。"""
        return self.get("/ISAPI/System/deviceInfo")


def from_env() -> "ISAPIClient":
    """按环境变量构造客户端：ISAPI_HOST / ISAPI_USER / ISAPI_PASS。"""
    host = os.environ.get("ISAPI_HOST", "192.168.18.84")
    user = os.environ.get("ISAPI_USER", "admin")
    pwd = os.environ.get("ISAPI_PASS", "admin12345")
    return ISAPIClient(host, user, pwd)
