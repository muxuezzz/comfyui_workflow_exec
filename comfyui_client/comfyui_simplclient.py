"""ComfyUI客户端，处理与ComfyUI服务的通信"""

import json
import time
from typing import Any, Dict

import requests


class ComfyUISimpleClient:
    """ComfyUI客户端类"""

    def __init__(
        self,
        server_address: str = "127.0.0.1:8188",
        timeout: int = 30,
    ):
        self.server_address = server_address
        self.timeout = timeout
        # 创建 requests 会话，启用连接池
        self.base_url = f"http://{self.server_address}"

    def queue_prompt(self, prompt_workflow: Dict[str, Any]) -> str:
        """
        将工作流加入队列

        Args:
            prompt_workflow: 工作流配置字典

        Returns:
            响应内容
        """
        p = {"prompt": prompt_workflow}
        data = json.dumps(p).encode("utf-8")

        try:
            response = requests.post(
                f"{self.base_url}/prompt",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.content.decode("utf-8")
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to queue prompt: {e}")

    def get_prompt_status(self) -> Dict[str, Any]:
        """
        获取提示状态

        Returns:
            状态信息字典
        """
        try:
            response = requests.get(f"{self.base_url}/prompt")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to get prompt status: {e}")

    def get_queue_status(self) -> Dict[str, Any]:
        """
        获取队列状态

        Returns:
            队列状态信息字典
        """
        try:
            response = requests.get(f"{self.base_url}/queue")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to get queue status: {e}")

    def wait_for_completion(self, timeout: int = 300, check_interval: int = 1) -> bool:
        """
        等待工作流执行完成

        Args:
            timeout: 超时时间（秒）
            check_interval: 检查间隔（秒）

        Returns:
            是否成功完成
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            queue_status = self.get_queue_status()

            # 检查队列是否为空
            if not queue_status.get("queue_running") and not queue_status.get(
                "queue_pending"
            ):
                return True

            time.sleep(check_interval)

        raise TimeoutError(f"Workflow did not complete within {timeout} seconds")

    def test_connection(self) -> bool:
        """
        测试与ComfyUI的连接

        Returns:
            连接是否成功
        """
        try:
            self.get_queue_status()
            return True
        except ConnectionError:
            return False

    def get_system_info(self) -> Dict[str, Any]:
        """
        获取系统信息

        Returns:
            系统信息字典
        """
        try:
            prompt_status = self.get_prompt_status()
            queue_status = self.get_queue_status()

            return {
                "prompt_status": prompt_status,
                "queue_status": queue_status,
                "connection_healthy": True,
            }
        except ConnectionError as e:
            return {"connection_healthy": False, "error": str(e)}
