# ComfyUI Workflow Executor

一个用于自动化执行ComfyUI工作流的工具，支持动态参数配置、随机值生成和批量任务处理，适用于图像生成等场景的自动化工作流管理。

## 功能特点

- **灵活的配置系统**：通过JSON/YAML配置文件定义工作流参数，支持固定值和随机值
- **工作流动态修改**：执行前可通过回调函数动态调整工作流参数
- **批量任务处理**：支持队列式执行多个工作流任务
- **自动化前后处理**：可自定义前处理（资源检查、清理）和后处理（结果保存、分析）逻辑
- **种子自动随机化**：自动识别并随机化工作流中的种子节点，避免生成重复内容
- **生产/开发模式切换**：生产模式精简日志输出，提升性能；开发模式保留详细调试信息

## 目录结构

```
comfyui_workflow_exec/
├── config/                 # 配置文件目录
│   ├── config.yaml         # YAML格式配置示例
│   ├── config.json         # JSON格式配置示例
│   └── workflow_template.json  # 工作流模板
├── workflows/              # 工作流模板目录
│   └── workflow_template.json  # 工作流模板
├── workflow_manager/       # 工作流管理核心模块
│   ├── __init__.py
│   ├── workflow_manager.py # 工作流解析与修改
│   ├── workflow_run.py     # 工作流执行逻辑
│   └── constant.py         # 常量定义
├── comfyui_client/         # ComfyUI客户端模块
│   ├── __init__.py
│   ├── comfyui_webscoket.py # WebSocket通信实现
│   └── message_config.py   # 消息类型定义
├── main.py                 # 主程序入口
└── .gitignore              # Git忽略文件
```

## 快速开始

### 前提条件

- Python 3.8+
- 已安装并运行ComfyUI服务
- 安装依赖：`pip install pyyaml requests websocket-client`

### 基本使用

1. 配置工作流模板（参考 `config/workflow_template.json`）
2. 创建配置文件（支持JSON或YAML格式）
3. 运行主程序：

```bash
python main.py
```

## 配置文件说明

配置文件用于定义工作流路径和需要修改的节点参数，支持两种格式：

### JSON格式示例

```json
{
  "workflow_path": "./workflow_template.json",
  "nodes": [
    {
      "class_type": "Class1",
      "parameter_name": "param1",
      "value": 42,
      "node_index": 1
    },
    {
      "class_type": "Class2",
      "parameter_name": "param2",
      "value": {
        "type": "random_range",
        "min": 0.0,
        "max": 100.0
      },
      "node_index": 2
    },
    {
      "class_type": "Class3",
      "parameter_name": "param3",
      "value": {
        "type": "random_choice",
        "choices": ["option1", "option2", "option3"]
      },
      "node_index": 3
    }
  ]
}
```

### YAML格式示例

```yaml
Workflow_path: "./workflow_template.json"
nodes: 
  - class_type: "Class1"
    parameter_name: "param1"
    value: 42
    node_index: 1
  - class_type: "Class2"
    parameter_name: "param2"
    value:
      type: "random_range"
      min: 0.0
      max: 100.0
    node_index: 2
  - class_type: "Class3"
    parameter_name: "param3"
    value:
      type: "random_choice"
      choices: ["option1", "option2", "option3"]
    node_index: 3
```

### 配置参数说明

- `workflow_path`: 工作流模板文件路径（支持相对路径和绝对路径）
- `nodes`: 节点配置列表，每个节点包含：
  - `class_type`: 节点类型（需与工作流中定义的一致）
  - `parameter_name`: 要修改的参数名
  - `value`: 参数值，支持：
    - 固定值（数字、字符串、布尔值等）
    - 随机范围：`{"type": "random_range", "min": 最小值, "max": 最大值}`
    - 随机选择：`{"type": "random_choice", "choices": [选项列表]}`
  - `node_index`: 同类型节点的索引（从1开始）

## 高级用法

### 自定义回调函数

可以通过自定义回调函数扩展功能：

1. **前处理回调**：在工作流执行前执行（资源检查、清理等）
2. **后处理回调**：在工作流执行后处理结果（保存图片、分析数据等）
3. **工作流修改回调**：动态修改工作流参数

示例：

```python
def my_preprocess_callback():
    """自定义前处理逻辑"""
    print("执行自定义前处理...")

def my_postprocess_callback(output_images):
    """自定义后处理逻辑"""
    print(f"处理 {len(output_images)} 个节点的输出...")
    # 自定义保存逻辑...
    return processed_results

# 绑定回调函数
runner.set_preprocess_callback(my_preprocess_callback)
runner.set_postprocess_callback(my_postprocess_callback)
```

### 批量执行任务

在 `main.py`中定义任务队列，支持批量执行多个工作流：

```python
workflow_tasks = [
    {"config_file": "config/task1.json"},
    {"config_file": "config/task2.json"},
    {"config_file": "config/task3.json"},
]

# 循环执行队列中的任务
with ComfyUIWebSocketClient(server_address="127.0.0.1:8188") as client:
    for task in workflow_tasks:
        run_workflow(config_file=task["config_file"], comfyui_client=client)
```

## 扩展随机值类型

可以通过修改 `workflow_manager/workflow_manager.py`扩展更多随机值类型：

1. 在 `ValueType`枚举中添加新类型
2. 实现对应的处理方法
3. 在 `_VALUE_HANDLERS`中注册新类型和处理方法

示例：

```python
class ValueType(str, Enum):
    RANDOM_RANGE = "random_range"
    RANDOM_CHOICE = "random_choice"
    RANDOM_INT = "random_int"  # 新增类型

def _handle_random_int(self, config: dict) -> int:
    min_v = config.get("min", 0)
    max_v = config.get("max", 100)
    return random.randint(min_v, max_v)

_VALUE_HANDLERS = {
    ValueType.RANDOM_RANGE: _handle_random_range,
    ValueType.RANDOM_CHOICE: _handle_random_choice,
    ValueType.RANDOM_INT: _handle_random_int,  # 注册新类型
}
```

## 注意事项

- 确保ComfyUI服务已启动并在配置的地址（默认 `127.0.0.1:8188`）可用
- 工作流模板中的节点ID和类型需与配置文件中的保持一致
- 生产环境中建议开启 `production_mode`以减少日志输出
- 大批量任务执行时，可调整 `wait_for_queue_empty`中的 `min_queue_num`参数控制并发量

## 许可证

[MIT](LICENSE)
