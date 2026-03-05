import os
import re

def parse_frontmatter(content):
    """
    Parses YAML-like frontmatter from markdown content.
    Returns a dictionary of frontmatter and the rest of the text.
    """
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}, content
        
    fm_text = match.group(1)
    text = content[match.end():]
    fm_dict = {}
    
    for line in fm_text.split('\n'):
        if ':' in line:
            key, val = line.split(':', 1)
            key = key.strip()
            val = val.strip()
            
            # Simple list parsing [a, b, c]
            if val.startswith('[') and val.endswith(']'):
                items = [x.strip().strip('"\'') for x in val[1:-1].split(',')]
                fm_dict[key] = [x for x in items if x]
            elif val.lower() == 'true':
                fm_dict[key] = True
            elif val.lower() == 'false':
                fm_dict[key] = False
            else:
                fm_dict[key] = val.strip('"\'')
                
    return fm_dict, text

def load_brain_keywords(brain_dir) -> list:
    """
    Recursively scan brain_dir for keywords from:
    1) Frontmatter keywords/tags arrays
    2) "## 3. Important Keywords" section
    3) Anywhere hashtags are used
    """
    keywords = set()
    if not os.path.exists(brain_dir):
        print(f"Warning: Brain directory not found at {brain_dir}")
        return list(keywords)
        
    system_tags = {'deepcard', 'briefcard', 'quickcard', 'noabstract'}
        
    for root, dirs, files in os.walk(brain_dir):
        for file in files:
            if not file.endswith('.md'):
                continue
                
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                fm, text = parse_frontmatter(content)
                
                # 1. Frontmatter keywords/tags
                if 'keywords' in fm and isinstance(fm['keywords'], list):
                    for kw in fm['keywords']:
                        keywords.add(kw)
                if 'tags' in fm and isinstance(fm['tags'], list):
                    for tag in fm['tags']:
                        keywords.add(tag)
                        
                # 2. "## 3. Important Keywords"
                match = re.search(r'## 3\. Important Keywords\s*(.*?)(?=\n## |$)', text, re.DOTALL)
                if match:
                    kw_section = match.group(1)
                    for word in kw_section.split():
                        if word.startswith('#'):
                            kw = word.strip('#, \n')
                            if kw:
                                keywords.add(kw)
                                
                # 3. Hashtags in text (e.g., #active_matter)
                # Matches #word but ignores headings like "# Heading"
                hashtags = re.findall(r'(?<!\w)#([a-zA-Z0-9_\-]+)', text)
                for tag in hashtags:
                    if tag.lower() not in system_tags:
                        keywords.add(tag)
                        
            except Exception as e:
                print(f"Error reading brain file {filepath}: {e}")
                
    return sorted(list(keywords))

def load_brain_context(brain_dir) -> str:
    """
    Recursively scan brain_dir for LLM context.
    Respects include_in_llm: false frontmatter.
    Extracts only ## LLM Context or <!-- LLM_CONTEXT_START --> blocks if present.
    Applies optional token budgeting via environment variables.
    """
    if not os.path.exists(brain_dir):
        print(f"Warning: Brain directory not found at {brain_dir}")
        return "No specific user context provided."
        
    try:
        max_total = int(os.getenv('BRAIN_CONTEXT_MAX_CHARS', '0'))
        max_per_file = int(os.getenv('BRAIN_CONTEXT_MAX_CHARS_PER_FILE', '0'))
    except ValueError:
        max_total = 0
        max_per_file = 0
        
    context_parts = []
    
    for root, dirs, files in os.walk(brain_dir):
        for file in files:
            if not file.endswith('.md'):
                continue
                
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                fm, text = parse_frontmatter(content)
                
                # Exclude if explicitly marked false
                if fm.get('include_in_llm') is False:
                    continue
                    
                snippet = None
                
                # Try finding <!-- LLM_CONTEXT_START -->
                html_match = re.search(r'<!--\s*LLM_CONTEXT_START\s*-->(.*?)<!--\s*LLM_CONTEXT_END\s*-->', content, re.DOTALL)
                if html_match:
                    snippet = html_match.group(1).strip()
                else:
                    # Try finding ## LLM Context
                    h2_match = re.search(r'## LLM Context\s*(.*?)(?=\n## |$)', text, re.DOTALL | re.IGNORECASE)
                    if h2_match:
                        snippet = h2_match.group(1).strip()
                        
                # Fallback to entire text if no explicit section
                if snippet is None:
                    snippet = text.strip()
                    
                if not snippet:
                    continue
                    
                if max_per_file > 0 and len(snippet) > max_per_file:
                    snippet = snippet[:max_per_file] + "\n... (truncated for limits)"
                    
                rel_path = os.path.relpath(filepath, brain_dir)
                context_parts.append(f"--- Context from {rel_path} ---\n{snippet}\n")
                
            except Exception as e:
                print(f"Error reading brain file {filepath} for context: {e}")
                
    if not context_parts:
        return "No specific user context provided."
        
    combined = "\n".join(context_parts)
    
    if max_total > 0 and len(combined) > max_total:
        combined = combined[:max_total] + "\n... (Total context truncated for limits)"
        
    return combined
