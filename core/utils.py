import re
import yaml


def strip_leading_frontmatter(body: str) -> str:
    """Remove any frontmatter block(s) accidentally embedded at the start of a body.

    Guards against a caller passing raw file content (frontmatter included) as
    the new body, which would otherwise nest a second frontmatter block on the
    next write. Loops so repeated nesting is collapsed in one pass. Only strips
    a leading block that parses as a non-empty YAML mapping, so a stray '---'
    horizontal rule at the top of real content is left untouched.
    """
    if not body:
        return body
    changed = False
    while True:
        candidate = body.lstrip()
        m = re.match(r'^---\n(.*?)\n---\n?(.*)', candidate, re.DOTALL)
        if not m:
            break
        try:
            parsed = yaml.safe_load(m.group(1))
        except yaml.YAMLError:
            break
        if not isinstance(parsed, dict) or not parsed:
            break
        body = m.group(2)
        changed = True
    return body.lstrip("\n") if changed else body


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
