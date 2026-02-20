
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from butler.llm import MockLLM, OllamaLLM, OpenAILLM

def test_signatures():
    print("Testing LLM Provider signatures...")
    
    providers = [
        MockLLM(),
        OllamaLLM(base_url="http://localhost:11434", model="mistral"),
        OpenAILLM(api_key="sk-test", model="gpt-4o-mini")
    ]
    
    for p in providers:
        print(f"Testing {p.__class__.__name__}...")
        try:
            # Should not raise TypeError
            p.generate_response("User input", "Proactive", "Impact", "Semantic")
            print(f"✅ {p.__class__.__name__} is OK.")
        except TypeError as e:
            print(f"❌ {p.__class__.__name__} failed: {e}")
            sys.exit(1)
        except Exception as e:
            # We expect exceptions like OpenAI API key errors, but NOT TypeError on signature
            if "TypeError" in str(type(e)):
                 print(f"❌ {p.__class__.__name__} failed with TypeError: {e}")
                 sys.exit(1)
            print(f"ℹ️ {p.__class__.__name__} signature is OK (but failed execution: {e})")

if __name__ == "__main__":
    test_signatures()
