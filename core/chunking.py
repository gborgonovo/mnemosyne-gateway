import re
from typing import List

class HeuristicChunker:
    """
    Splits text into semantic chunks without using an LLM.
    Uses structural cues (paragraphs, double newlines) and size limits.
    """
    def __init__(self, max_chars_per_chunk: int = 2000, overlap_chars: int = 200):
        self.max_chars = max_chars_per_chunk
        self.overlap = overlap_chars

    def chunk_text(self, text: str) -> List[str]:
        """
        Splits a text into a list of chunks based on paragraphs,
        respecting the maximum character limit.
        """
        if not text:
            return []

        # 1. Normalize line endings and split by double newline (paragraphs)
        text = text.replace('\r\n', '\n')
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]

        chunks = []
        current_chunk = ""

        # 2. Iterate through paragraphs and build chunks
        for p in paragraphs:
            # If a single paragraph is larger than max_chars, we must hard-split it
            if len(p) > self.max_chars:
                # If we have an existing chunk, save it first
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # Hard split the giant paragraph
                sub_chunks = self._hard_split(p)
                chunks.extend(sub_chunks[:-1]) # add all but the last
                current_chunk = sub_chunks[-1] # keep the last one to build upon (or just append it)
                continue

            # If adding the paragraph exceeds the limit, save current chunk
            if len(current_chunk) + len(p) + 2 > self.max_chars: # +2 for double newline
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # Start new chunk, incorporating overlap if possible
                current_chunk = self._get_overlap_prefix(chunks[-1] if chunks else "") + p
            else:
                # Add to current chunk
                if current_chunk:
                    current_chunk += "\n\n" + p
                else:
                    current_chunk = p

        # Add the final chunk
        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _hard_split(self, text: str) -> List[str]:
        """Splits a very long string into chunks of max_chars, trying to break at sentences."""
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.max_chars, text_len)
            
            # If we're not at the end of the text, try to find a natural break point
            if end < text_len:
                # Look for sentence boundaries (. ! ?) going backwards from 'end'
                match = re.search(r'[.!?] ', text[start:end][::-1])
                if match:
                    # Adjust end to exactly after the sentence boundary
                    boundary_idx = end - match.start()
                    # Only accept the boundary if it doesn't make the chunk too small (e.g., > 50% max)
                    if boundary_idx - start > self.max_chars * 0.5:
                        end = boundary_idx
                else:
                    # Look for spaces if no sentence boundary is found
                    last_space = text.rfind(' ', start, end)
                    if last_space > start + self.max_chars * 0.5:
                        end = last_space + 1

            chunks.append(text[start:end].strip())
            
            # Move start to the end, minus overlap
            new_start = end - self.overlap
            if new_start <= start: # prevent infinite loops if overlap is too large
                 start = end
            else:
                 start = new_start

        return chunks

    def _get_overlap_prefix(self, prev_chunk: str) -> str:
        """Extracts the last 'overlap' characters from the previous chunk, ideally starting at a sentence."""
        if not prev_chunk or self.overlap <= 0:
            return ""
        
        prefix_candidate = prev_chunk[-self.overlap:]
        
        # Try to find a clean sentence start in the candidate
        match = re.search(r'[.!?]\s+([A-Z])', prefix_candidate)
        if match:
            # Return from the start of the new sentence
            return prefix_candidate[match.start() + 1:].strip() + " "
            
        return prefix_candidate.strip() + " "
