# ComfyUI Workflow Executor

![Python](https://img.shields.io/badge/Python-%3E%3D3.10-blue?logo=python) ![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi)

一个用于自动化执行 ComfyUI 工作流的 Python 库，支持动态参数配置、随机值生成、批量任务处理以及灵活的回调机制。

## ✨ 功能特点

- **作为库使用**：封装良好的 Python 包，易于集成到其他项目中
- **灵活的配置**：通过 JSON/YAML 配置文件定义工作流参数，支持固定值和随机值
- **动态修改**：支持在执行前通过回调函数动态调整工作流结构和参数
- **批量处理**：支持队列式执行多个工作流任务
- **自动化流**：可自定义前处理（资源检查）和后处理（结果保存、分析）逻辑
- **智能随机**：自动识别并随机化工作流中的种子节点，避免生成重复内容

## 📦 安装

### 源码安装（推荐）

```bash
# 进入项目根目录
pip install .

# 或者安装为编辑模式（开发用）
pip install -e .
```

## 🚀 快速开始

### 1. 准备工作流配置

你需要一个 ComfyUI 的 API 格式工作流文件（通常通过 ComfyUI 界面 "Save (API Format)" 导出）和一个任务配置文件。

示例配置文件 (`config.json`):
```json
{
  "workflow_path": "./workflow_api.json",
  "nodes": [
    {
      "class_type": "KSampler",
      "item_name": "seed",
      "value": {"type": "random_range", "min": 0, "max": 100000},
      "node_index": 1
    }
  ]
}
```

### 2. Python 代码调用

```python
from comfyui_workflow_exec import ComfyUIWebSocketClient, execute_workflow_task

# ComfyUI 服务器地址
SERVER_URL = "http://localhost:8188"

# 使用上下文管理器自动处理连接
with ComfyUIWebSocketClient(server_address=SERVER_URL) as client:
    
    # 执行任务
    result = execute_workflow_task(
        config_file="path/to/config.json",
        comfyui_client=client,
        random_init=True  # 启用随机值生成
    )
    
    if result:
        print(f"任务成功，生成了 {len(result)} 个节点的输出")
        # result 格式: { "node_id": [image_bytes, ...] }
```

更多示例请参考 [examples/](examples/) 目录：
- `examples/simple_usage.py`: 基础用法演示
- `examples/advanced_usage.py`: 包含回调函数的高级用法

## 📂 目录结构

```
comfyui_workflow_exec/
├── src/
│   └── comfyui_workflow_exec/   # 核心库代码
│       ├── client/              # ComfyUI 客户端 (HTTP/WebSocket)
│       ├── workflow/            # 工作流管理与执行逻辑
│       ├── utils/               # 工具函数
│       └── config/              # 配置 Schema 定义
├── examples/                    # 示例代码和配置
│   ├── simple_usage.py          # 简单示例
│   ├── advanced_usage.py        # 高级示例
│   ├── config/                  # 示例配置文件
│   └── workflows/               # 示例工作流文件
├── tests/                       # 测试用例
├── main.py                      # 命令行入口示例
└── pyproject.toml               # 项目构建配置
```

## ⚙️ 配置文件说明

配置文件用于定义工作流路径和需要动态修改的节点参数。

### 参数说明

- `workflow_path`: 工作流模板文件路径（支持相对路径和绝对路径）
- `nodes`: 节点修改规则列表
  - `class_type`: 节点类型（需与 ComfyUI 节点名一致，如 `KSampler`）
  - `item_name` (或 `parameter_name`): 要修改的参数名
  - `value`: 参数值，支持：
    - **固定值**: 直接填写数字、字符串等
    - **随机范围**: `{"type": "random_range", "min": 0, "max": 100}`
    - **随机选择**: `{"type": "random_choice", "choices": ["A", "B", "C"]}`
  - `node_index`: 同类型节点的索引（从 1 开始，用于区分同一个流程中多个相同类型的节点）

## 🔧 高级用法

### 自定义回调

通过回调函数可以介入工作流执行的各个阶段：

```python
def my_postprocess(output_images):
    # 自定义结果处理逻辑，例如保存到特定目录或上传
    for node_id, images in output_images.items():
        save_images(images)

execute_workflow_task(
    ...,
    postprocess_callback=my_postprocess
)
```

### 扩展随机类型

如果内置的随机类型（范围、选择）不满足需求，可以修改 `src/comfyui_workflow_exec/workflow/workflow_manager.py` 中的 `_VALUE_HANDLERS` 来扩展更多类型。

## 📝 许可证

[MIT](LICENSE)
