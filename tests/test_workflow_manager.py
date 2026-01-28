import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import json

from workflow_manager.workflow_manager import WorkflowManager, RootConfig, WorkflowNodeConfig

class TestWorkflowManager(unittest.TestCase):
    def setUp(self):
        self.manager = WorkflowManager()
        self.maxDiff = None

    @patch("workflow_manager.workflow_manager.load_file_content")
    def test_get_workflow_random_init(self, mock_load_file):
        # Mock config file content
        config_content = {
            "workflow_path": "dummy_workflow.json",
            "nodes": [
                {
                    "class_type": "TestNode",
                    "item_name": "param1",
                    "value": {
                        "type": "random_range",
                        "min": 10,
                        "max": 20
                    }
                }
            ]
        }
        
        # Mock workflow template content
        workflow_content = {
            "1": {
                "class_type": "TestNode",
                "inputs": {
                    "param1": 0
                }
            }
        }

        # Setup mock side effects
        def side_effect(path):
            if str(path).endswith("config.json"):
                return config_content
            else:
                return workflow_content.copy() # Return copy to allow modification

        mock_load_file.side_effect = side_effect

        # Run method
        result = self.manager.get_workflow(Path("config.json"), random_init=True, remove_previews=False)

        # Assertions
        node_input = result["1"]["inputs"]["param1"]
        self.assertTrue(10 <= node_input <= 20, f"Value {node_input} not in range [10, 20]")

    @patch("workflow_manager.workflow_manager.load_file_content")
    def test_get_workflow_no_random_init(self, mock_load_file):
        # Mock config with random config
        config_content = {
            "workflow_path": "dummy_workflow.json",
            "nodes": [
                {
                    "class_type": "TestNode",
                    "item_name": "param1",
                    "value": 100
                }
            ]
        }
        
        workflow_content = {
            "1": {
                "class_type": "TestNode",
                "inputs": {
                    "param1": 0
                }
            }
        }

        mock_load_file.side_effect = lambda p: config_content if str(p).endswith("config.json") else workflow_content.copy()

        # Run with random_init=False
        result = self.manager.get_workflow(Path("config.json"), random_init=False, remove_previews=False)

        # Should NOT modify inputs based on config if random_init=False?
        # Wait, looking at code:
        # if not random_init or not config.nodes: return workflow_data
        # Yes, it returns early.
        
        self.assertEqual(result["1"]["inputs"]["param1"], 0)

if __name__ == "__main__":
    unittest.main()
