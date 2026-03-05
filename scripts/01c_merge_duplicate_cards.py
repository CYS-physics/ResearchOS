import os
import json
import re
from collections import defaultdict

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CARDS_DIR = os.path.join(BASE_DIR, "02_cards/quick")
VAULT_DIRS = [
    os.path.join(BASE_DIR, "02_cards"),
    os.path.join(BASE_DIR, "03_deep"),
    os.path.join(BASE_DIR, "04_researchers"),
    os.path.join(BASE_DIR, "05_keywords"),
    os.path.join(BASE_DIR, "brain")
]

def load_card_content(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return ""

def extract_title(content):
    # Extract the title from the first H1 tag
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""

def update_links_in_vault(old_citekey, new_citekey):
    # E.g. replace [[old_citekey]] or [[old_citekey|Text]] with [[new_citekey]] and [[new_citekey|Text]]
    
    pattern1 = re.compile(r'\[\[' + re.escape(old_citekey) + r'\]\]')
    pattern2 = re.compile(r'\[\[' + re.escape(old_citekey) + r'\|(.*?)\]\]')
    
    # Optional deep link forms: 02_cards/quick/old_citekey
    pattern3 = re.compile(r'\[\[(?:02_cards/)?(?:quick/)?' + re.escape(old_citekey) + r'\]\]')
    pattern4 = re.compile(r'\[\[(?:02_cards/)?(?:quick/)?' + re.escape(old_citekey) + r'\|(.*?)\]\]')

    replaced_files = []
    
    for directory in VAULT_DIRS:
        if not os.path.exists(directory):
            continue
            
        for root, dirs, files in os.walk(directory):
            for file in files:
                if not file.endswith(".md"):
                    continue
                    
                filepath = os.path.join(root, file)
                
                # Skip the replacement target file itself to avoid self-modification issues during rename
                if file == f"{new_citekey}.md" or file == f"{new_citekey}_deep.md":
                     continue
                
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    new_content = pattern1.sub(f"[[{new_citekey}]]", content)
                    new_content = pattern2.sub(rf"[[{new_citekey}|\1]]", new_content)
                    
                    # More generic sub for full paths
                    # For simplicity, strip the path and just point to new_citekey
                    new_content = pattern3.sub(f"[[{new_citekey}]]", new_content)
                    new_content = pattern4.sub(rf"[[{new_citekey}|\1]]", new_content)

                    if new_content != content:
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        replaced_files.append(filepath)
                except Exception as e:
                    print(f"Error updating links in {filepath}: {e}")
                    
    return replaced_files

def main():
    if not os.path.exists(CARDS_DIR):
        print(f"Directory {CARDS_DIR} not found.")
        return

    # Group cards by normalized title
    title_to_cards = defaultdict(list)
    
    for filename in os.listdir(CARDS_DIR):
        if not filename.endswith(".md"):
            continue
            
        filepath = os.path.join(CARDS_DIR, filename)
        content = load_card_content(filepath)
        title = extract_title(content)
        
        if title:
            # Normalize title for better matching (lowercase, no punctuation except spaces)
            safe_title = "".join(c for c in title.lower() if c.isalnum() or c == ' ').strip()
            # Collapse multiple spaces
            safe_title = re.sub(r'\s+', ' ', safe_title)
            
            citekey = filename.replace(".md", "")
            title_to_cards[safe_title].append({
                "citekey": citekey,
                "filepath": filepath,
                "content": content
            })

    # Process duplicates
    merged_count = 0
    
    for safe_title, cards in title_to_cards.items():
        if len(cards) < 2:
            continue
            
        print(f"\nFound duplicate papers for title: '{safe_title}'")
        
        # Sort by length of content to tend to keep the more detailed one as primary
        cards.sort(key=lambda x: len(x["content"]), reverse=True)
        
        primary = cards[0]
        duplicates = cards[1:]
        
        print(f"  Primary: {primary['citekey']}")
        
        for dup in duplicates:
            print(f"  Merging: {dup['citekey']} -> {primary['citekey']}")
            
            # Read primary again in case it was modified in a previous loop iteration
            primary_content = load_card_content(primary["filepath"])
            dup_content = dup["content"]
            
            # 1. Add alias to primary
            # We look for the frontmatter aliases line
            aliases_match = re.search(r'^aliases:\s*\[(.*?)\]', primary_content, re.MULTILINE)
            if aliases_match:
                current_aliases_str = aliases_match.group(1)
                
                # Parse existing aliases ignoring quotes and spaces
                current_aliases = [a.strip().strip('"').strip("'") for a in current_aliases_str.split(',') if a.strip()]
                
                if dup['citekey'] not in current_aliases:
                    current_aliases.append(dup['citekey'])
                    
                    # Also include any aliases the duplicate might have had
                    dup_aliases_match = re.search(r'^aliases:\s*\[(.*?)\]', dup_content, re.MULTILINE)
                    if dup_aliases_match:
                        dup_aliases_str = dup_aliases_match.group(1)
                        dup_aliases = [a.strip().strip('"').strip("'") for a in dup_aliases_str.split(',') if a.strip()]
                        for a in dup_aliases:
                            if a not in current_aliases and a != primary['citekey']:
                                current_aliases.append(a)
                    
                    new_aliases_str = ", ".join(f'"{a}"' for a in current_aliases)
                    primary_content = re.sub(
                        r'^aliases:\s*\[.*?\]', 
                        f'aliases: [{new_aliases_str}]', 
                        primary_content, 
                        flags=re.MULTILINE
                    )
            else:
                # Add aliases line if it doesn't exist
                # This depends on the specific frontmatter structure. Assuming standard '---' boundaries
                primary_content = re.sub(
                    r'^---\n', 
                    f'---\naliases: ["{dup["citekey"]}"]\n', 
                    primary_content, 
                    count=1
                )
                
            # 2. Append content if different
            # For simplicity, we just check if the duplicate has a significantly different abstract or notes.
            # A simple heuristic: if the sizes are different by > 100 chars, or simple string matching fails.
            
            # Extract just the body (excluding frontmatter and standard footers)
            def extract_body(md):
                # Remove YAML
                body = re.sub(r'^---.*?---\n', '', md, flags=re.DOTALL)
                # Remove common footer
                body = re.sub(r'---\n\*Created by ResearchOS Quick Card Generator\*.*', '', body, flags=re.DOTALL).strip()
                return body
                
            primary_body = extract_body(primary_content)
            dup_body = extract_body(dup_content)
            
            if abs(len(primary_body) - len(dup_body)) > 50 or primary_body not in dup_body and dup_body not in primary_body:
                # Content is genuinely different, let's append it
                print(f"    Content differs. Appending duplicate content.")
                if "## Merged Content" not in primary_content:
                     primary_content += f"\n\n## Merged Content\n\n### From {dup['citekey']}\n{dup_body}\n"
                else:
                     primary_content += f"\n### From {dup['citekey']}\n{dup_body}\n"
            else:
                print(f"    Content is identical. Discarding duplicate.")
                
            # Write updated primary
            with open(primary["filepath"], "w", encoding="utf-8") as f:
                f.write(primary_content)
                
            # 3. Update links in vault
            updated_files = update_links_in_vault(dup['citekey'], primary['citekey'])
            if updated_files:
                print(f"    Updated {len(updated_files)} links in the vault.")
                
            # 4. Delete the duplicate file
            try:
                os.remove(dup["filepath"])
                print(f"    Deleted duplicate file: {dup['filepath']}")
                merged_count += 1
            except Exception as e:
                print(f"    Failed to delete duplicate file: {e}")

    print(f"\nDeduplication complete. Merged {merged_count} cards.")

if __name__ == "__main__":
    main()
