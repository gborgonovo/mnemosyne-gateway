
import sys
import os
sys.path.append(os.getcwd())
import unittest
from unittest.mock import MagicMock, patch

# Mock pydantic since it might not be in the environment or we want to avoid dependency issues
sys.modules['pydantic'] = MagicMock()

# Mock the Filter class structure
class MockValves:
    def __init__(self):
        self.mnemosyne_url = "http://localhost:4001"
        self.api_key = "test_key"
        self.project_context = "TestProject"
        self.enable_search = True
        self.search_context_limit = 2000
        self.enable_continuous_learning = True
        self.incognito_command = "/incognito"

class TestOpenWebUIFunction(unittest.TestCase):
    @patch('requests.get')
    def test_inlet_semantic_search(self, mock_get):
        # Setup
        from integrations.open_webui.mnemosyne_function import Filter
        f = Filter()
        f.valves = MockValves()
        
        # Mock responses
        mock_briefing = MagicMock()
        mock_briefing.status_code = 200
        mock_briefing.json.return_value = {"hot_topics": ["test"], "butler_log": "log"}
        
        mock_search = MagicMock()
        mock_search.status_code = 200
        mock_search.json.return_value = {
            "name": "FoundConcept",
            "properties": {"summary": "Concept summary"},
            "related": [{"name": "Rel1"}, {"name": "Rel2"}]
        }
        
        mock_get.side_effect = [mock_briefing, mock_search]
        
        body = {
            "messages": [
                {"role": "user", "content": "Tell me about Mnemosyne"}
            ]
        }
        
        # Execute
        result = f.inlet(body)
        
        # Verify
        self.assertEqual(mock_get.call_count, 2)
        
        # Check briefing call
        briefing_call = mock_get.call_args_list[0]
        self.assertEqual(briefing_call[0][0], "http://localhost:4001/briefing")
        self.assertEqual(briefing_call[1]['headers']['X-API-Key'], "test_key")
        
        # Check search call
        search_call = mock_get.call_args_list[1]
        self.assertEqual(search_call[0][0], "http://localhost:4001/search")
        self.assertEqual(search_call[1]['params']['q'], "[TestProject] Tell me about Mnemosyne")
        self.assertEqual(search_call[1]['headers']['X-API-Key'], "test_key")
        
        # Check injected message
        messages = result['messages']
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]['role'], 'system')
        self.assertIn("FoundConcept", messages[0]['content'])

if __name__ == '__main__':
    unittest.main()
