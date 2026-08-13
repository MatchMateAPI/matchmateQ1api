"""Ch3.3 / 4.1 认证示例 —— Digest 调通 deviceInfo。
对应 4.1 四语言示例的 Python 可运行版；另演示 4.2.6 错误处理。
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from isapi.client import ISAPIClient, ISAPIError, from_env

if __name__ == "__main__":
    client = from_env()
    try:
        print(client.device_info())           # GET /ISAPI/System/deviceInfo
    except ISAPIError as e:                    # 4.2.6 统一错误结构
        print("调用失败:", e)
