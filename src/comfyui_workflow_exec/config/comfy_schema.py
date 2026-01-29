import json
from typing import Annotated, Any, Literal, NamedTuple
from urllib.parse import urljoin

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator

EXTRA: Literal["allow", "ignore", "forbid"] | None = "allow"

APINodeID = Annotated[str, Field(alias="node_id", description="工作流中节点的ID。")]
PromptID = Annotated[
    str,
    Field(
        alias="prompt_id",
        description="提示的ID（将api工作流提交到服务器执行）。提交时可以自行选择此ID。",
    ),
]
ClientID = Annotated[str, Field(alias="client_id")]
OutputName = Annotated[
    str,
    Field(
        alias="output_name",
        description="节点中输出的名称，在 /history/、/history/{prompt_id} 端点中使用。",
    ),
]
# 这是 BOOLEAN、INT 等类型
OutputType = Annotated[
    str,
    Field(
        alias="output_type",
        description="节点命名输出的类型，在 /object_info 端点中，也可以在 {节点,自定义节点} 的实现中查看/找到。",
    ),
]

# 这是 BOOLEAN、INT 等类型
NamedInputType = Annotated[
    str,
    Field(
        alias="input_type",
        description="节点命名输入的类型，在 /object_info 端点中，也可以在 {节点,自定义节点} 的实现中查看/找到。",
    ),
]
# 这是组合框输入的有效*值*列表。
ComboInputType = Annotated[list[Any], Field(alias="combo_input_class")]
ComfyFolderType = Literal["input", "output", "temp"]
VALID_FOLDER_TYPES: list[ComfyFolderType] = ["input", "output", "temp"]


################################################################################
class APIWorkflowInConnection(NamedTuple):
    """表示工作流中两个节点之间的连接。这用于节点的输入中。"""

    output_node_id: APINodeID
    output_index: int


class APIWorkflowNodeMeta(BaseModel):
    """节点允许有一个 `_meta` 字段。

    元字段是在 https://github.com/comfyanonymous/ComfyUI/pull/2380 中添加的，用于存储诸如节点标题等信息。
    """

    model_config = ConfigDict(extra=EXTRA)
    title: str | None = None


class APIWorkflowNodeInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra=EXTRA)
    """populate_by_name: 这允许通过 `_meta` 或 `meta` 填充 `meta` 字段。"""

    inputs: dict[str, str | int | float | bool | APIWorkflowInConnection | dict]
    class_type: str
    meta: APIWorkflowNodeMeta | None = Field(None, alias="_meta")


class APIWorkflow(RootModel[dict[APINodeID, APIWorkflowNodeInfo]]):
    """这是 API 格式，您可以从 UI 中的 `Save (API Format)` 获取它。

    请查看 test_data/sdxlturbo_example_api.json 以获取此格式的 json 示例。
    """

    root: dict[APINodeID, APIWorkflowNodeInfo]


################################################################################
class APISystemStatsSystem(BaseModel):
    model_config = ConfigDict(extra=EXTRA)

    os: str | None = None
    python_version: str | None = None
    embedded_python: bool | None = None


class APISystemStatsDevice(BaseModel):
    model_config = ConfigDict(extra=EXTRA)

    name: str | None = None
    type: str | None = None
    index: int | None = None
    vram_total: int | None = None
    vram_free: int | None = None
    torch_vram_total: int | None = None
    torch_vram_free: int | None = None


class APISystemStats(BaseModel):
    """从 /system_stats 端点返回。"""

    model_config = ConfigDict(extra=EXTRA)

    system: APISystemStatsSystem | None = None
    devices: list[APISystemStatsDevice] | None = None


################################################################################
class APIPromptInfo(BaseModel):
    """从 /prompt 端点返回。"""

    class ExecInfo(BaseModel):
        queue_remaining: int | None

    exec_info: ExecInfo | None


################################################################################
class APIQueueInfoEntry(NamedTuple):
    number: int
    prompt_id: PromptID
    prompt: APIWorkflow
    extra_data: dict
    outputs_to_execute: list[APINodeID]


class APIQueueInfo(BaseModel):
    """从 /queue 端点返回。"""

    model_config = ConfigDict(extra=EXTRA)

    queue_pending: list[APIQueueInfoEntry]
    queue_running: list[APIQueueInfoEntry]


################################################################################
class NodeErrorInfo(BaseModel):
    model_config = ConfigDict(extra=EXTRA)

    details: str
    extra_info: dict
    message: str
    type: str


class NodeErrors(BaseModel):
    model_config = ConfigDict(extra=EXTRA)

    class_type: str
    dependent_outputs: list[APINodeID]
    errors: list[NodeErrorInfo]


class APIWorkflowTicket(BaseModel):
    """从 post /prompt 端点返回。"""

    model_config = ConfigDict(extra=EXTRA)

    node_errors: dict[APINodeID, NodeErrors] | None = None
    number: int | None = None
    prompt_id: PromptID | None = None
    error: NodeErrorInfo | str | None = None


################################################################################


class APIOutputUI(RootModel[dict[OutputName, list[Any]]]):
    root: dict[OutputName, list[Any]]


class APIHistoryEntryStatusNote(NamedTuple):
    name: str
    data: Any


class APIHistoryEntryStatus(BaseModel):
    """

    示例:
      "status": {
        "status_str": "success",
        "completed": true,
        "messages": [
          [
            "execution_start",
            { "prompt_id": "b1b64df6-9b2c-4a09-bd0e-b6c294702085" }
          ],
          [
            "execution_cached",
            { "nodes": [], "prompt_id": "b1b64df6-9b2c-4a09-bd0e-b6c294702085" }
          ]
        ]
      }
    """

    model_config = ConfigDict(extra=EXTRA)

    status_str: str | None = None
    completed: bool | None = None
    messages: list[APIHistoryEntryStatusNote] | None = None


class APIHistoryEntry(BaseModel):
    model_config = ConfigDict(extra=EXTRA)

    outputs: dict[APINodeID, APIOutputUI] | None = None
    prompt: APIQueueInfoEntry | None = None
    status: APIHistoryEntryStatus | None = None


class APIHistory(RootModel[dict[PromptID, APIHistoryEntry]]):
    """如果调用 /history 和 /history/{prompt_id} 端点则返回。

    TODO: 显示示例。
    """

    root: dict[PromptID, APIHistoryEntry]


################################################################################

APIObjectKey = Annotated[str, Field(alias="object_key")]
"""
  示例:

  KSampler:
    input:
      required:
        model:
        - MODEL
    ...

  这里 'KSampler' 就是 APIObjectKey。

"""


class APIObjectInputInfo(BaseModel):
    """
    示例:

    seed:
    - INT
    - default: 0
      min: 0
      max: 18446744073709551615
    """

    model_config = ConfigDict(extra=EXTRA)
    """这是 pydantic 的配置，用于配置模型，它不是可访问的字段。

  extra: 这只是为了未来验证模式，以便在添加额外字段时不会破坏。它们将被动态存储。

  我在这里允许 extra 是因为我不知道键是什么，而且它们似乎变化很大。
  """
    default: Any | None = None
    min: Any | None = None
    max: Any | None = None
    step: Any | None = None
    round: Any | None = None
    # 注意：其他所有内容都将存储在 extra 字典中。通过 `extra` 属性访问它。


class APIObjectInputTuple(NamedTuple):
    """
    示例:

    seed:
    - INT
    - default: 0
      min: 0
      max: 18446744073709551615

      列表/元组中的第一项是类型，第二项是可选的 info。
    """

    type: NamedInputType | ComboInputType
    # 出于某种原因，当 type=='*' 时，这是一个空字符串。
    info: APIObjectInputInfo | str | None = None


class APIObjectInput(BaseModel):
    """
    input:
        required:
          model:
          - MODEL
          seed:
          - INT
          - default: 0
            min: 0
            max: 18446744073709551615
          ...
    """

    model_config = ConfigDict(extra=EXTRA)

    required: dict[str, APIObjectInputTuple | NamedInputType] | None = None
    """
  出于某种原因，当 type=='*' 时，它只显示类型而没有 `[type, {... limits}]` 元组，所以我允许了 NamedInputType。
  """

    optional: dict[str, APIObjectInputTuple | NamedInputType] | None = None
    hidden: dict[str, APIObjectInputTuple | NamedInputType] | None = None


class APIObjectInfoEntry(BaseModel):
    """

    示例的 yaml 版本:

    input:
        required:
          model:
          - MODEL
          seed:
          - INT
          - default: 0
            min: 0
            max: 18446744073709551615
          ...
      output:
      - LATENT
      output_is_list:
      - false
      output_name:
      - LATENT
      name: KSampler
      display_name: KSampler
      description: ''
      category: sampling
      output_node: false
    """

    model_config = ConfigDict(extra=EXTRA)

    input: APIObjectInput
    output: OutputType | list[OutputType | list[OutputType]]
    output_is_list: list[bool]
    output_name: OutputName | list[OutputName]
    name: str
    display_name: str
    description: str
    category: str
    output_node: bool


class APIObjectInfo(RootModel[dict[APIObjectKey, APIObjectInfoEntry]]):
    """从 /object_info 端点返回。

    请查看 test_data/object_info.yml 以获取此格式的 yaml 示例。

    来自 test_data/object_info.yml 的 APIObjectInfo 键和值示例：
    KSampler:
      input:
        required:
          model:
          - MODEL
          seed:
          - INT
          - default: 0
            min: 0
            max: 18446744073709551615
          steps:
          - INT
          - default: 20
            min: 1
            max: 10000
          cfg:
          - FLOAT
          - default: 8.0
            min: 0.0
            max: 100.0
            step: 0.1
            round: 0.01
          sampler_name:
          - - euler
            - euler_ancestral
            - heun
            - heunpp2
            - dpm_2
            - dpm_2_ancestral
            - lms
            - dpm_fast
            - dpm_adaptive
            - dpmpp_2s_ancestral
            - dpmpp_sde
            - dpmpp_sde_gpu
            - dpmpp_2m
            - dpmpp_2m_sde
            - dpmpp_2m_sde_gpu
            - dpmpp_3m_sde
            - dpmpp_3m_sde_gpu
            - ddpm
            - lcm
            - ddim
            - uni_pc
            - uni_pc_bh2
          scheduler:
          - - normal
            - karras
            - exponential
            - sgm_uniform
            - simple
            - ddim_uniform
          positive:
          - CONDITIONING
          negative:
          - CONDITIONING
          latent_image:
          - LATENT
          denoise:
          - FLOAT
          - default: 1.0
            min: 0.0
            max: 1.0
            step: 0.01
      output:
      - LATENT
      output_is_list:
      - false
      output_name:
      - LATENT
      name: KSampler
      display_name: KSampler
      description: ''
      category: sampling
      output_node: false
    """

    # model_config = ConfigDict(extra=EXTRA)

    root: dict[APIObjectKey, APIObjectInfoEntry]


################################################################################
class APIUploadImageResp(BaseModel):
    name: str
    subfolder: str
    type: ComfyFolderType


################################################################################
class WSExecutingData(BaseModel):
    """Websocket "executing" 消息。
    参见:

    * https://github.com/comfyanonymous/ComfyUI/blob/61b3f15f8f2bc0822cb98eac48742fb32f6af396/server.py#L115
    * https://github.com/comfyanonymous/ComfyUI/blob/c782144433e41c21ae2dfd75d0bc28255d2e966d/main.py#L113
    * https://github.com/comfyanonymous/ComfyUI/blob/c782144433e41c21ae2dfd75d0bc28255d2e966d/execution.py#L146
    * https://github.com/comfyanonymous/ComfyUI/blob/e478b1794e91977c50dc6eea6228ef1248044507/script_examples/websockets_api_example.py#L36


    """

    model_config = ConfigDict(extra=EXTRA)

    node: str | None = None
    prompt_id: PromptID | None = None


class WSMessage(BaseModel):
    """来自 websocket 的消息，如果它是非二进制的。"""

    model_config = ConfigDict(extra=EXTRA)

    type: str
    data: dict


################################################################################


class ComfyUIPathTriplet(BaseModel):
    """
    表示一个 folder_type/subfolder/filename 三元组，ComfyUI API 和一些节点将其用作文件路径。
    """

    model_config = ConfigDict(frozen=True)

    type: ComfyFolderType
    subfolder: str
    filename: str

    @field_validator("type")
    @classmethod
    def validate_folder_type(cls, v: str):
        if v not in VALID_FOLDER_TYPES:
            raise ValueError(f"folder_type {json.dumps(v)} 不是 {VALID_FOLDER_TYPES} 之一")
        return v

    @field_validator("subfolder")
    @classmethod
    def validate_subfolder(cls, v: str):
        if v.startswith("/"):
            raise ValueError(f"subfolder {json.dumps(v)} 不能以斜杠开头")
        return v

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str):
        if "/" in v:
            raise ValueError(f"filename {json.dumps(v)} 不能包含斜杠")
        if v == "":
            raise ValueError(f"filename {json.dumps(v)} 不能为空")
        return v

    def ToLocalPathStr(self, *, include_folder_type: bool) -> str:
        """将此三元组转换为类似 `input/subfolder/filename` 的字符串。"""
        subfolder = self.subfolder
        if subfolder == "":
            subfolder = "."
        if not subfolder.endswith("/"):
            subfolder += "/"

        local_path = urljoin(subfolder, self.filename)
        if include_folder_type:
            local_path = urljoin(f"{self.type}/", local_path)
        return local_path
