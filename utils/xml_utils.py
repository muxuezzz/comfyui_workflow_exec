"""XML工具类"""

import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple


class XMLUtils:
    """XML工具类"""
    
    @staticmethod
    def parse_xml(xml_path: str) -> Tuple[List[Tuple[int, int, int, int]], List[str]]:
        """
        解析XML文件，获取边界框和标签
        
        Args:
            xml_path: XML文件路径
            
        Returns:
            (边界框列表, 标签列表) 元组
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
        except Exception as e:
            raise ValueError(f"Failed to parse XML file {xml_path}: {e}")
        
        boxes = []
        labels = []
        
        for obj in root.findall("object"):
            label = obj.find("name")
            if label is None:
                continue
                
            label_text = label.text
            if not label_text:
                continue
            
            bbox = obj.find("bndbox")
            if bbox is None:
                continue
            
            # 获取边界框坐标
            xmin_elem = bbox.find("xmin")
            ymin_elem = bbox.find("ymin")
            xmax_elem = bbox.find("xmax")
            ymax_elem = bbox.find("ymax")
            
            if None in [xmin_elem, ymin_elem, xmax_elem, ymax_elem]:
                continue
            
            try:
                x_min = int(xmin_elem.text)
                y_min = int(ymin_elem.text)
                x_max = int(xmax_elem.text)
                y_max = int(ymax_elem.text)
                
                boxes.append((x_min, y_min, x_max, y_max))
                labels.append(label_text)
            except (ValueError, TypeError):
                continue
        
        return boxes, labels
    
    @staticmethod
    def get_xml_image_extension(xml_path: str) -> str:
        """
        获取XML文件对应的图像文件扩展名
        
        Args:
            xml_path: XML文件路径
            
        Returns:
            图像文件扩展名（如 '.png'）
        """
        
        if os.path.exists(xml_path[:-4] + ".jpg"):
            img_suffix = ".jpg"
        else:
            img_suffix = ".png"
        
        return img_suffix
    
    @staticmethod
    def parse_label(label: str) -> Tuple[str, int, int]:
        """
        解析标签字符串，格式为 "category_angle1_angle2"
        
        Args:
            label: 标签字符串
            
        Returns:
            (类别, 角度1, 角度2) 元组
        """
        parts = label.split("_")
        if len(parts) != 3:
            raise ValueError(f"Invalid label format: {label}")
        
        category = parts[0]
        try:
            angle1 = int(parts[1])
            angle2 = int(parts[2])
        except ValueError as e:
            raise ValueError(f"Invalid angle values in label {label}: {e}")
        
        return category, angle1, angle2
    
    @staticmethod
    def get_xml_info(xml_path: str) -> Dict[str, Any]:
        """
        获取XML文件的详细信息
        
        Args:
            xml_path: XML文件路径
            
        Returns:
            XML文件信息字典
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
        except Exception as e:
            return {"error": f"Failed to parse XML: {e}"}
        
        info = {
            "filename": None,
            "objects": [],
            "total_objects": 0
        }
        
        # 获取文件名
        filename_elem = root.find("filename")
        if filename_elem is not None:
            info["filename"] = filename_elem.text
        
        # 获取对象信息
        for obj in root.findall("object"):
            obj_info = {}
            
            # 获取对象名称
            name_elem = obj.find("name")
            if name_elem is not None:
                obj_info["name"] = name_elem.text
            
            # 获取边界框
            bbox_elem = obj.find("bndbox")
            if bbox_elem is not None:
                bbox = {}
                for coord in ["xmin", "ymin", "xmax", "ymax"]:
                    coord_elem = bbox_elem.find(coord)
                    if coord_elem is not None and coord_elem.text:
                        try:
                            bbox[coord] = int(coord_elem.text)
                        except ValueError:
                            continue
                obj_info["bbox"] = bbox
            
            if obj_info:
                info["objects"].append(obj_info)
        
        info["total_objects"] = len(info["objects"])
        return info
    
    @staticmethod
    def validate_xml_structure(xml_path: str) -> Dict[str, Any]:
        """
        验证XML文件结构
        
        Args:
            xml_path: XML文件路径
            
        Returns:
            验证结果字典
        """
        validation_result = {
            "valid": False,
            "errors": [],
            "warnings": []
        }
        
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
        except Exception as e:
            validation_result["errors"].append(f"Failed to parse XML: {e}")
            return validation_result
        
        # 检查必要的元素
        if root.tag != "annotation":
            validation_result["warnings"].append("Root element should be 'annotation'")
        
        required_elements = ["filename"]
        for elem_name in required_elements:
            elem = root.find(elem_name)
            if elem is None:
                validation_result["errors"].append(f"Missing required element: {elem_name}")
            elif not elem.text:
                validation_result["errors"].append(f"Empty element: {elem_name}")
        
        # 检查对象
        objects = root.findall("object")
        if not objects:
            validation_result["warnings"].append("No objects found in XML")
        
        for i, obj in enumerate(objects):
            obj_name = obj.find("name")
            if obj_name is None or not obj_name.text:
                validation_result["errors"].append(f"Object {i+1} missing name")
            
            bbox = obj.find("bndbox")
            if bbox is None:
                validation_result["errors"].append(f"Object {i+1} missing bounding box")
                continue
            
            # 检查边界框坐标
            coords = ["xmin", "ymin", "xmax", "ymax"]
            for coord in coords:
                coord_elem = bbox.find(coord)
                if coord_elem is None or not coord_elem.text:
                    validation_result["errors"].append(f"Object {i+1} missing {coord}")
                    continue
                
                try:
                    value = int(coord_elem.text)
                    if value < 0:
                        validation_result["warnings"].append(f"Object {i+1} has negative {coord}: {value}")
                except ValueError:
                    validation_result["errors"].append(f"Object {i+1} has invalid {coord}: {coord_elem.text}")
            
            # 检查坐标逻辑
            try:
                xmin = int(bbox.find("xmin").text) if bbox.find("xmin") is not None else 0
                ymin = int(bbox.find("ymin").text) if bbox.find("ymin") is not None else 0
                xmax = int(bbox.find("xmax").text) if bbox.find("xmax") is not None else 0
                ymax = int(bbox.find("ymax").text) if bbox.find("ymax") is not None else 0
                
                if xmin >= xmax:
                    validation_result["errors"].append(f"Object {i+1} has invalid x range: xmin={xmin}, xmax={xmax}")
                if ymin >= ymax:
                    validation_result["errors"].append(f"Object {i+1} has invalid y range: ymin={ymin}, ymax={ymax}")
            except (ValueError, TypeError):
                validation_result["errors"].append(f"Object {i+1} has invalid coordinate values")
        
        validation_result["valid"] = len(validation_result["errors"]) == 0
        return validation_result
    
    @staticmethod
    def filter_objects_by_conditions(boxes: List[Tuple[int, int, int, int]], 
                                   labels: List[str],
                                   conditions: Optional[Dict[str, Any]] = None) -> Tuple[List[int], List[Tuple[int, int, int, int]], List[str]]:
        """
        根据条件过滤对象
        
        Args:
            boxes: 边界框列表
            labels: 标签列表
            conditions: 过滤条件字典
            
        Returns:
            (索引列表, 过滤后的边界框, 过滤后的标签) 元组
        """
        if conditions is None:
            return list(range(len(boxes))), boxes, labels
        
        filtered_indices = []
        filtered_boxes = []
        filtered_labels = []
        
        for i, (box, label) in enumerate(zip(boxes, labels)):
            include = True
            
            # 过滤条件示例
            if "categories" in conditions:
                category, _, _ = XMLUtils.parse_label(label)
                if category not in conditions["categories"]:
                    include = False
            
            if "min_area" in conditions:
                xmin, ymin, xmax, ymax = box
                area = (xmax - xmin) * (ymax - ymin)
                if area < conditions["min_area"]:
                    include = False
            
            if "max_area" in conditions:
                xmin, ymin, xmax, ymax = box
                area = (xmax - xmin) * (ymax - ymin)
                if area > conditions["max_area"]:
                    include = False
            
            if include:
                filtered_indices.append(i)
                filtered_boxes.append(box)
                filtered_labels.append(label)
        
        return filtered_indices, filtered_boxes, filtered_labels