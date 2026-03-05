import os
import re
from collections import defaultdict

CARD_DIRS = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards/quick")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../03_deep")),
]
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../05_keywords/drafts"))
DEEP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../03_deep"))
BRIEF_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards"))
QUICK_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards/quick"))
ALIASES_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../01_zotero_export/aliases.json"))
IGNORE_TAGS = {"quickcard", "briefcard", "deepcard", "paper", "unread", "processed", "researcher", "key_researchers"}

def get_card_metadata(citekey: str) -> str:
    rating = ""
    is_deep = False
    
    deep_path = os.path.join(DEEP_DIR, f"{citekey}_deep.md")
    brief_path = os.path.join(BRIEF_DIR, f"{citekey}.md")
    
    if os.path.exists(deep_path):
        is_deep = True
        
    if os.path.exists(brief_path):
        try:
            with open(brief_path, "r", encoding="utf-8") as f:
                content = f.read()
            match = re.search(r'(⭐+)', content)
            if match:
                rating = f"{match.group(1)} "
        except Exception:
            pass
            
    deep_tag = " [DEEP]" if is_deep else ""
    return f"{rating}{{title}}{deep_tag}"

def get_title_from_content(content, filename):
    # Try to find the first H1 header for title
    match = re.search(r'^#\s+(.*?)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return filename.replace('.md', '').replace('_deep', '')

def generate_keyword_cards():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Load aliases
    import json
    aliases = {}
    if os.path.exists(ALIASES_PATH):
        try:
            with open(ALIASES_PATH, "r", encoding="utf-8") as f:
                alias_data = json.load(f)
                aliases = alias_data.get("keywords", {})
        except Exception as e:
            print(f"Warning: Could not read aliases.json: {e}")
            
    keyword_papers = defaultdict(list)
    processed_citekeys = set() # Avoid double counting if a paper exists in multiple folders

    # Parse all cards
    for directory in CARD_DIRS:
        if not os.path.exists(directory):
            continue
            
        for filename in os.listdir(directory):
            if not filename.endswith(".md"):
                continue
                
            citekey = filename.replace('.md', '').replace('_deep', '')
            if citekey in processed_citekeys:
                continue # We've already processed a more advanced/different version of this paper
                
            filepath = os.path.join(directory, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            title = get_title_from_content(content, filename)
            found_keywords = set()

            # 1. Extract from frontmatter tags: ["a", "b"]
            fm_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
            if fm_match:
                frontmatter = fm_match.group(1)
                tags_match = re.search(r'tags:\n((?:\s+-\s+.*\n?)+)|tags:\s*\[(.*?)\]', frontmatter)
                if tags_match:
                    if tags_match.group(1): # List format
                        tags = re.findall(r'-\s+(.*)', tags_match.group(1))
                        for t in tags:
                            t = t.strip().strip('"\'')
                            if t and t.lower() not in IGNORE_TAGS:
                                kw_lower = t.lower()
                                mapped_kw = aliases.get(kw_lower, kw_lower)
                                found_keywords.add(mapped_kw)
                    elif tags_match.group(2): # Array format
                        tags = [t.strip().strip('"\'') for t in tags_match.group(2).split(',')]
                        for t in tags:
                            if t and t.lower() not in IGNORE_TAGS:
                                kw_lower = t.lower()
                                mapped_kw = aliases.get(kw_lower, kw_lower)
                                found_keywords.add(mapped_kw)

            # 2. Extract inline hashtags #keyword
            # \B ensures we don't start in the middle of a word, (?<!#) prevents matching ##
            hashtags = re.findall(r'\B#([a-zA-Z0-9_]+)', content)
            for ht in hashtags:
                ht_lower = ht.lower()
                if ht_lower not in IGNORE_TAGS:
                    mapped_ht = aliases.get(ht_lower, ht_lower)
                    found_keywords.add(mapped_ht)

            if found_keywords:
                processed_citekeys.add(citekey)
                
                # Determine best link target
                link_target = citekey
                if filename.endswith("_deep.md"):
                    link_target = f"{citekey}_deep"
                elif directory.endswith("02_cards"):
                    link_target = f"02_cards/{citekey}|{citekey}"
                elif directory.endswith("quick"):
                    link_target = f"02_cards/quick/{citekey}|{citekey}"
                    
                for kw in found_keywords:
                    keyword_papers[kw].append({
                        "citekey": citekey,
                        "link_target": link_target,
                        "title": title
                    })

    print(f"Found {len(keyword_papers)} unique keywords across {len(processed_citekeys)} papers.")

    # Generate cards
    for keyword, papers in keyword_papers.items():
        safe_name = "".join(c for c in keyword if c.isalnum() or c in ('-', '_')).strip()
        if not safe_name:
            continue
            
        filepath = os.path.join(OUTPUT_DIR, f"{safe_name}.md")
        
        # Check overwrite
        should_write = True
        existing_profile = ""
        existing_processed_tags = set()
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            if "status: unread" not in content:
                should_write = False
            else:
                parts = content.split("---")
                if len(parts) >= 3:
                    main_body = "---".join(parts[2:])
                    sub_parts = main_body.split("---")
                    if len(sub_parts) > 1:
                        existing_profile = "---".join(sub_parts[1:]).strip()
                        
                # Extract existing processed tags
                for line in content.splitlines():
                    match = re.search(r'-\s+\[\[(.*?)\]\]\s*\[PROCESSED\]', line)
                    if match:
                        link_target = match.group(1).split("|")[0]
                        base_citekey = link_target.split("/")[-1].replace("_deep", "").replace(".md", "")
                        existing_processed_tags.add(base_citekey)

        if not should_write:
            continue

        links = []
        for p in papers:
            formatted_title = get_card_metadata(p['citekey']).format(title=p['title'])
            
            processed_marker = " [PROCESSED]" if p['citekey'] in existing_processed_tags else ""
            links.append(f"- [[{p['link_target']}]]{processed_marker} : {formatted_title}")
        links_list = "\n".join(links)

        final_md = f"""---
aliases: ["{keyword}"]
tags: ["keyword"]
status: unread
paper_count: {len(papers)}
---
# {keyword.replace('_', ' ').title()}

## Papers
{links_list}

---
{existing_profile}
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(final_md)

        for p in papers:
            original_filepath = os.path.join(CARD_DIRS[0], f"{p['citekey']}.md")
            if not os.path.exists(original_filepath):
                original_filepath = os.path.join(CARD_DIRS[1], f"{p['citekey']}.md")
            if not os.path.exists(original_filepath):
                original_filepath = os.path.join(CARD_DIRS[2], f"{p['citekey']}.md")
            
        print(f"  ✅ Saved {safe_name}.md ({len(papers)} papers)")

if __name__ == "__main__":
    generate_keyword_cards()
