"""数学工具函数模块"""

import math
import random

__all__ = [
    "select_random_elements",
    "round_to_nearest_ten",
    "normalize_angle",
    "calculate_angle_difference",
    "generate_random_angle_offset",
    "apply_angle_transformation",
    "calculate_bounding_box_area",
    "calculate_bounding_box_center",
    "calculate_iou",
    "is_overlapping",
    "calculate_distance",
    "randomize_value",
    "clamp_value",
    "generate_random_padding",
    "lerp",
    "format_number_with_padding",
]


def select_random_elements(total_count: int, select_count: int) -> list[int]:
    """
    随机选择指定数量的元素

    Args:
        total_count: 总元素数量
        select_count: 选择数量

    Returns:
        选中的索引列表
    """
    if select_count >= total_count:
        indices = list(range(total_count))
        indices.sort()
        return indices

    indices = list(range(total_count))
    selected_indices = random.sample(indices, select_count)
    selected_indices.sort()
    return selected_indices


def round_to_nearest_ten(number: int) -> int:
    """
    将数字四舍五入到最近的十位数

    Args:
        number: 输入数字

    Returns:
        四舍五入后的数字
    """
    ones_digit = number % 10
    tens_multiple = number - ones_digit

    if ones_digit >= 5:
        tens_multiple += 10

    return tens_multiple


def normalize_angle(angle: int, max_angle: int = 360) -> int:
    """
    标准化角度到指定范围内

    Args:
        angle: 角度值
        max_angle: 最大角度（默认360）

    Returns:
        标准化后的角度
    """
    angle = angle % max_angle
    if angle == 0:
        angle = max_angle
    return angle


def calculate_angle_difference(angle1: int, angle2: int, max_angle: int = 360) -> int:
    """
    计算两个角度之间的最小差值

    Args:
        angle1: 第一个角度
        angle2: 第二个角度
        max_angle: 最大角度（默认360）

    Returns:
        角度差值
    """
    diff = abs(angle1 - angle2) % max_angle
    return min(diff, max_angle - diff)


def generate_random_angle_offset(min_offset: int, max_offset: int) -> int:
    """
    生成随机角度偏移

    Args:
        min_offset: 最小偏移
        max_offset: 最大偏移

    Returns:
        随机偏移值
    """
    return random.randint(min_offset, max_offset)


def apply_angle_transformation(angle: int, offset: int, max_angle: int = 360) -> int:
    """
    应用角度变换

    Args:
        angle: 原始角度
        offset: 偏移量
        max_angle: 最大角度（默认360）

    Returns:
        变换后的角度
    """
    return normalize_angle(angle + offset, max_angle)


def calculate_bounding_box_area(xmin: int, ymin: int, xmax: int, ymax: int) -> int:
    """
    计算边界框面积

    Args:
        xmin, ymin, xmax, ymax: 边界框坐标

    Returns:
        面积
    """
    return max(0, xmax - xmin) * max(0, ymax - ymin)


def calculate_bounding_box_center(xmin: int, ymin: int, xmax: int, ymax: int) -> tuple[float, float]:
    """
    计算边界框中心点

    Args:
        xmin, ymin, xmax, ymax: 边界框坐标

    Returns:
        (x_center, y_center) 元组
    """
    return (xmin + xmax) / 2.0, (ymin + ymax) / 2.0


def calculate_iou(box1: tuple[int, int, int, int], box2: tuple[int, int, int, int]) -> float:
    """
    计算两个边界框的IoU（Intersection over Union）

    Args:
        box1: 第一个边界框 (xmin, ymin, xmax, ymax)
        box2: 第二个边界框 (xmin, ymin, xmax, ymax)

    Returns:
        IoU值 (0.0 - 1.0)
    """
    xmin1, ymin1, xmax1, ymax1 = box1
    xmin2, ymin2, xmax2, ymax2 = box2

    # 计算交集区域
    intersection_xmin = max(xmin1, xmin2)
    intersection_ymin = max(ymin1, ymin2)
    intersection_xmax = min(xmax1, xmax2)
    intersection_ymax = min(ymax1, ymax2)

    # 检查是否有交集
    if intersection_xmax <= intersection_xmin or intersection_ymax <= intersection_ymin:
        return 0.0

    # 计算交集面积
    intersection_area = (intersection_xmax - intersection_xmin) * (intersection_ymax - intersection_ymin)

    # 计算并集面积
    area1 = (xmax1 - xmin1) * (ymax1 - ymin1)
    area2 = (xmax2 - xmin2) * (ymax2 - ymin2)
    union_area = area1 + area2 - intersection_area

    # 计算IoU
    return intersection_area / union_area if union_area > 0 else 0.0


def is_overlapping(
    box1: tuple[int, int, int, int],
    box2: tuple[int, int, int, int],
    threshold: float = 0.0,
) -> bool:
    """
    检查两个边界框是否重叠

    Args:
        box1: 第一个边界框
        box2: 第二个边界框
        threshold: 重叠阈值

    Returns:
        是否重叠
    """
    iou = calculate_iou(box1, box2)
    return iou > threshold


def calculate_distance(point1: tuple[float, float], point2: tuple[float, float]) -> float:
    """
    计算两点之间的距离

    Args:
        point1: 第一个点 (x, y)
        point2: 第二个点 (x, y)

    Returns:
        距离
    """
    x1, y1 = point1
    x2, y2 = point2
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def randomize_value(base_value: int | float, variation_percentage: float = 0.1) -> int | float:
    """
    在基准值基础上随机化

    Args:
        base_value: 基准值
        variation_percentage: 变化百分比

    Returns:
        随机化后的值
    """
    if isinstance(base_value, int):
        variation = int(base_value * variation_percentage)
        return base_value + random.randint(-variation, variation)
    else:
        variation = base_value * variation_percentage
        return base_value + random.uniform(-variation, variation)


def clamp_value(
    value: int | float,
    min_value: int | float,
    max_value: int | float,
) -> int | float:
    """
    将值限制在指定范围内

    Args:
        value: 要限制的值
        min_value: 最小值
        max_value: 最大值

    Returns:
        限制后的值
    """
    return max(min_value, min(value, max_value))


def generate_random_padding(min_padding: float = 0.1, max_padding: float = 1.5) -> float:
    """
    生成随机内边距

    Args:
        min_padding: 最小内边距
        max_padding: 最大内边距

    Returns:
        随机内边距
    """
    return random.uniform(min_padding, max_padding)


def lerp(start: float, end: float, factor: float) -> float:
    """
    线性插值

    Args:
        start: 起始值
        end: 结束值
        factor: 插值因子 (0.0 - 1.0)

    Returns:
        插值结果
    """
    return start + factor * (end - start)


def format_number_with_padding(number: int, padding: int = 5) -> str:
    """
    格式化数字为带填充的字符串

    Args:
        number: 数字
        padding: 填充位数

    Returns:
        格式化后的字符串
    """
    return f"{number:0{padding}d}"
