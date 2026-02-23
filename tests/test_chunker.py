import sys
import os

# Add parent dir to path to import core
sys.path.append(os.getcwd())

from core.chunking import HeuristicChunker

def test_chunker():
    text = """
Mnemosyne is a Cognitive Partner.
It is designed to remember things for a long time.

Here is a semantic chunk. It's separated by a double newline.
By default, the chunker groups these paragraphs together as long as they fit in the limit.

But what if we have a very long paragraph?
""" + "A" * 2500 + """ This is the end of the very long paragraph.

And finally, another short paragraph to close it out.
"""
    
    chunker = HeuristicChunker(max_chars_per_chunk=1000, overlap_chars=50)
    chunks = chunker.chunk_text(text)
    
    print(f"Total chunks: {len(chunks)}")
    for i, c in enumerate(chunks):
        print(f"--- Chunk {i} ({len(c)} chars) ---")
        # Print first 100 and last 100 chars
        if len(c) > 200:
            print(f"{c[:100]}...\n...{c[-100:]}")
        else:
            print(c)
        print("-" * 40)

if __name__ == "__main__":
    test_chunker()
