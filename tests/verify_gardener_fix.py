
import sys
import os
import logging
from unittest.mock import MagicMock

# Setup path to import local modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from workers.gardener import Gardener

def test_is_similar():
    # Mock dependencies
    gm = MagicMock()
    llm = MagicMock()
    llm.compare_entities.return_value = True # Default to True for tests that reach LLM
    
    gardener = Gardener(gm, llm)
    
    test_cases = [
        # Technical IDs (Should NOT be similar even with shared prefix)
        ("item_bCDNqLZfmGII0iWrPMBkXX0f0Oe4uLCsySpA1ignZ6CQ1Ce1Ur3XGNrzoskqE24H", 
         "item_hlvfLnUPoldzhL1TGcscDOuqvoQ9zKj8dLBUHCxfmfpPy2fqOmmEiab0LMLCb1h1", False),
        
        # Exact Match (Should be similar)
        ("Python", "Python", True),
        
        # Different small strings (Should NOT be similar)
        ("Cat", "Dog", False),
        
        # Natural Language Substring (Should reach LLM)
        ("Python", "Python 3", True),
        
        # Shared small prefix but different words (Should NOT be similar)
        ("Cate", "Category", False)
    ]
    
    passed = 0
    for a, b, expected in test_cases:
        # Reset mock
        llm.compare_entities.reset_mock()
        llm.compare_entities.return_value = expected
        
        result = gardener._is_similar(a, b)
        if result == expected:
            print(f"✅ PASS: '{a}' vs '{b}' -> {result}")
            passed += 1
        else:
            print(f"❌ FAIL: '{a}' vs '{b}' -> Got {result}, Expected {expected}")
            
    print(f"\nSummary: {passed}/{len(test_cases)} passed.")
    
if __name__ == "__main__":
    test_is_similar()
