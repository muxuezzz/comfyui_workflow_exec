import os
from pathlib import Path

# 导入核心库
from comfyui_workflow_exec import ComfyUIWebSocketClient, execute_workflow_task
from comfyui_workflow_exec.utils.logger import setup_logger

# 设置日志
logger = setup_logger(__name__)

def main():
    # 示例配置路径
    current_dir = Path(__file__).parent
    config_path = current_dir / "config" / "my_config.json"
    
    # 确保配置文件存在（这里仅作演示，实际使用时请确保文件存在）
    if not config_path.exists():
        logger.error(f"配置文件不存在: {config_path}")
        logger.info("请先参照 examples/config/config.json.example 创建配置文件")
        return

    # ComfyUI 服务器地址
    server_address = os.getenv("COMFYUI_BACKED_URL", "http://localhost:8188")

    logger.info("=== 开始简单示例 ===")
    
    # 初始化客户端
    # production_mode=True 会减少日志输出，适合批量任务
    with ComfyUIWebSocketClient(server_address=server_address, production_mode=False) as client:
        
        # 检查连接
        if not client.test_connection():
            logger.error(f"无法连接到 ComfyUI 服务器: {server_address}")
            return

        # 执行工作流任务
        # execute_workflow_task 是一个高层封装函数，处理了配置加载、随机化、执行、结果获取等全流程
        result = execute_workflow_task(
            config_file=str(config_path),
            comfyui_client=client,
            random_init=True,       # 启用随机值初始化
            remove_previews=True    # 移除预览节点以提高性能
        )

        if result:
            logger.info("任务执行成功！")
            # result 是一个字典，key是节点ID，value是生成的图片二进制数据列表
            logger.info(f"生成了 {len(result)} 个节点的输出")
        else:
            logger.error("任务执行失败")

if __name__ == "__main__":
    main()
