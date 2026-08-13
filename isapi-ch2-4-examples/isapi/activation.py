"""
3.2 设备激活 —— 三个接口 + 完整密码学实现。

接口总览（定义/类型/调用方式详见各方法 docstring）：
  ① GET  /SDK/activateStatus        免认证查询激活状态
  ② POST /ISAPI/Security/challenge  提交 RSA 公钥模数，换取加密随机串
  ③ PUT  /ISAPI/System/activate     下发 AES128-ECB 加密的初始密码

文档约定的两个基础运算：
  bytesToHexstring : N 字节 -> 2N 字符十六进制
  hexStringToBytes : 逆运算
"""
from __future__ import annotations
import base64
import requests
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5


def bytes_to_hexstring(b: bytes) -> str:
    """文档 3.2 定义：127,10,23 -> '7f0a17'."""
    return b.hex()


def hexstring_to_bytes(s: str) -> bytes:
    """文档 3.2 定义：'7f0a17' -> b'\x7f\x0a\x17'."""
    return bytes.fromhex(s)


class Activator:
    """激活流程封装。

    用例：
        >>> act = Activator("192.168.18.84")
        >>> if not act.is_activated():
        ...     act.activate("Abc12345")
    """

    def __init__(self, host: str, port: int = 80, timeout: int = 10):
        self.base = f"http://{host}:{port}"
        self.timeout = timeout

    # ① GET /SDK/activateStatus
    def is_activated(self) -> bool:
        """查询激活状态。**定义**：激活前唯一可用的探测接口，**免认证**。
        返回 True 表示已激活。"""
        r = requests.get(f"{self.base}/SDK/activateStatus", timeout=self.timeout)
        r.raise_for_status()
        # XML/JSON 均可能出现，做宽松判断
        text = r.text
        return "true" in text.lower()

    # ② POST /ISAPI/Security/challenge
    def challenge(self, pubkey_b64: str) -> str:
        """提交 Base64 编码的公钥模数字符串，返回设备给出的加密随机串（Base64）。

        调用方式（文档 3.2 步骤 1-4）：
          1. 生成 1024bit 密钥对，取公钥模数（128 字节，超长去前导 0）
          2. bytesToHexstring -> 256 字符 -> Base64 -> XML 提交
          3. 设备用模数 + 指数 010001 构造公钥
          4. 设备加密 32 字节随机串返回
        """
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Challenge xmlns="http://www.isapi.org/ver20/XMLSchema" version="2.0">'
            f"<key>{pubkey_b64}</key>"
            "</Challenge>"
        )
        r = requests.post(f"{self.base}/ISAPI/Security/challenge",
                          data=body.encode("utf-8"),
                          headers={"Content-Type": 'application/xml; charset="UTF-8"'},
                          timeout=self.timeout)
        r.raise_for_status()
        # 从 XML 中取出加密随机串（字段名以设备实际返回为准，常见为 <key>）
        import re
        m = re.search(r"<key>([^<]+)</key>", r.text)
        return m.group(1) if m else r.text

    # ③ PUT /ISAPI/System/activate
    def activate(self, password: str) -> str:
        """完整激活流程（含 challenge），返回设备响应。

        密码学（文档 3.2 步骤 5-7）：
          1. 私钥 RSA 解密设备返回的随机串
          2. 随机串 hex->bytes 取前 16 字节作 AES 密钥
          3. AES128-ECB(zeropadding) 加密 [随机串前16字节 + 真实密码]
          4. hex -> Base64 -> XML 提交；设备校验后返回激活结果
        """
        # --- 生成密钥对并提交 challenge ---
        key = RSA.generate(1024)
        modulus = key.n.to_bytes((key.n.bit_length() + 7) // 8, "big")
        modulus = modulus[-128:]                       # 128 字节，超长截前导 0
        pub_hex = bytes_to_hexstring(modulus)          # 256 字符
        pub_b64 = base64.b64encode(pub_hex.encode()).decode()
        enc_random_b64 = self.challenge(pub_b64)

        # --- 私钥解密随机串 ---
        enc_random = base64.b64decode(enc_random_b64)
        enc_random = hexstring_to_bytes(enc_random.decode())  # hex 字符串 -> 密文
        cipher = PKCS1_v1_5.new(key)
        rand_hex = cipher.decrypt(enc_random, None)           # 32 字节 hex 字符
        if rand_hex is None:
            raise RuntimeError("RSA 解密随机串失败")
        rand_bytes = hexstring_to_bytes(rand_hex.decode())
        aes_key = rand_bytes[:16]                             # 前 16 字节 = AES 密钥

        # --- AES128-ECB(zeropadding) 加密 [随机串前16字节 + 密码] ---
        plaintext = rand_hex[:16] + password.encode()         # 文档示例：aaaabbbbccccdddd + Abc12345
        pad = (-len(plaintext)) % AES.block_size
        ciphertext = AES.new(aes_key, AES.MODE_ECB).encrypt(plaintext + b"\x00" * pad)
        ct_hex = bytes_to_hexstring(ciphertext)
        ct_b64 = base64.b64encode(ct_hex.encode()).decode()

        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<ActivateInfo xmlns="http://www.isapi.org/ver20/XMLSchema" version="2.0">'
            f"<password>{ct_b64}</password>"
            "</ActivateInfo>"
        )
        r = requests.put(f"{self.base}/ISAPI/System/activate",
                         data=body.encode("utf-8"),
                         headers={"Content-Type": 'application/xml; charset="UTF-8"'},
                         timeout=self.timeout)
        r.raise_for_status()
        return r.text
