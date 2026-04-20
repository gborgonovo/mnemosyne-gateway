import re

def normalize_node_name(name: str) -> str:
    """
    Standardizes a node name for use as a primary key in databases.
    Ensures case-insensitivity and uniform formatting.
    """
    if not name:
        return "unnamed"
    
    # 1. To lowercase
    normalized = name.lower().strip()
    
    # 2. Standardize separators (replace spaces and dashes with underscores)
    normalized = re.sub(r'[\s\-]+', '_', normalized)
    
    # 3. Remove any non-alphanumeric characters (except underscores)
    normalized = re.sub(r'[^\w]', '', normalized)
    
    # 4. Collapse multiple underscores
    normalized = re.sub(r'_{2,}', '_', normalized)
    
    return normalized.strip('_')
