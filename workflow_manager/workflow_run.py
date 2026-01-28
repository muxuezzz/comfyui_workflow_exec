from collections.abc import Callable
from pathlib import Path
from typing import Any

from comfyui_client.comfyui_client import ComfyUISimpleClient
from comfyui_client.comfyui_websocket import ComfyUIWebSocketClient
from utils.logger import setup_logger

from .exceptions import ConfigValidationError, WorkflowConnectionError
from .workflow_manager import WorkflowManager

logger = setup_logger(__name__)


class WorkflowRunner:
    def __init__(
        self,
        config_path: str,
        comfyui_client: ComfyUIWebSocketClient | ComfyUISimpleClient | None,
    ):
        self.config_path = Path(config_path)
        self.workflow_manager = WorkflowManager()
        self.client = (
            comfyui_client if comfyui_client else ComfyUIWebSocketClient(server_address="http://localhost:8188")
        )

        # 回调函数
        self.preprocess_callback: Callable | None = None
        self.postprocess_callback: Callable | None = None
        self.workflow_modify_callback: Callable[[dict], dict] | None = None

    def set_preprocess_callback(self, callback: Callable):
        """设置前处理回调函数"""
        self.preprocess_callback = callback

    def set_postprocess_callback(self, callback: Callable[[dict[str, list[bytes]]], Any]):
        """设置后处理回调函数"""
        self.postprocess_callback = callback

    def set_workflow_modify_callback(self, callback: Callable[[dict], dict]):
        """设置工作流修改回调函数"""
        self.workflow_modify_callback = callback

    def run(self, random_init: bool = True, remove_previews: bool = True) -> Any:
        """执行工作流的完整流程"""
        try:
            # 1. 前处理
            logger.info("开始前处理...")
            if self.preprocess_callback:
                self.preprocess_callback()

            # 2. 初始化工作流（读取配置，生成随机值）
            logger.info("初始化工作流...")
            workflow_data = self.workflow_manager.get_workflow(
                self.config_path,
                random_init=random_init,
                remove_previews=remove_previews,
            )

            # 3. 检查是否有工作流修改的回调
            if self.workflow_modify_callback:
                logger.info("应用工作流修改回调...")
                workflow_data = self.workflow_modify_callback(workflow_data)

            # 4. 工作流执行
            logger.info("连接到ComfyUI服务器并执行工作流...")
            output_images = None
            prompt_id = None

            if isinstance(self.client, ComfyUIWebSocketClient):
                output_images = self.client.execute_workflow(workflow_data)
            elif isinstance(self.client, ComfyUISimpleClient):
                prompt_id = self.client.queue_prompt(workflow_data)

            # 5. 后处理
            logger.info("开始后处理...")
            if self.postprocess_callback:
                if output_images:
                    self.postprocess_callback(output_images)
                else:
                    logger.warning("没有输出图片，跳过后处理回调")
            return output_images if output_images else prompt_id

        except Exception as e:
            logger.error(f"工作流执行失败: {str(e)}", exc_info=True)
            raise


def execute_workflow_task(
    config_file: str,
    comfyui_client: ComfyUIWebSocketClient | ComfyUISimpleClient,
    random_init: bool = True,
    remove_previews: bool = True,
    preprocess_callback: Callable | None = None,
    postprocess_callback: Callable | None = None,
    workflow_modify_callback: Callable | None = None,
) -> Any | None:
    """
    可复用的工作流执行函数

    参数说明：
    - config_file: 工作流配置文件路径
    - comfyui_client: ComfyUI 客户端实例
    - random_init: 是否启用随机值初始化工作流
    - remove_previews: 是否移除预览节点以提升执行效率
    - preprocess_callback: 前处理回调
    - postprocess_callback: 后处理回调
    - workflow_modify_callback: 工作流修改回调

    返回值：
    - 执行结果，执行失败返回None
    """
    try:
        # 初始化工作流运行器
        runner = WorkflowRunner(config_path=config_file, comfyui_client=comfyui_client)

        # 绑定回调函数
        if preprocess_callback:
            runner.set_preprocess_callback(preprocess_callback)
        if postprocess_callback:
            runner.set_postprocess_callback(postprocess_callback)
        if workflow_modify_callback:
            runner.set_workflow_modify_callback(workflow_modify_callback)

        # 执行工作流核心逻辑
        logger.info(f"开始执行工作流，配置文件：{config_file}")
        results = runner.run(random_init=random_init, remove_previews=remove_previews)

        logger.info(f"工作流执行完成，配置文件：{config_file}")
        return results

    except (ConfigValidationError, WorkflowConnectionError) as e:
        logger.error(f"工作流执行失败（配置文件：{config_file}）: {str(e)}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"工作流执行遇到未知错误: {str(e)}", exc_info=True)
        return None
