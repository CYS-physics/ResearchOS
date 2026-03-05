#!/usr/bin/env python3
import os
import json
import re

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ALIASES_PATH = os.path.join(BASE_DIR, "01_zotero_export/aliases.json")

VAULT_DIRS = [
    os.path.join(BASE_DIR, "02_cards"),
    os.path.join(BASE_DIR, "03_deep"),
    os.path.join(BASE_DIR, "04_researchers"),
    os.path.join(BASE_DIR, "05_keywords"),
    os.path.join(BASE_DIR, "brain")
]

def main():
    if not os.path.exists(ALIASES_PATH):
        print(f"Aliases file not found at {ALIASES_PATH}.")
        return

    try:
        with open(ALIASES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading aliases file: {e}")
        return

    researcher_aliases = data.get("researchers", {})
    keyword_aliases = data.get("keywords", {})
    
    # Precompile regex replacements
    # We want to replace [[variant]] with [[primary]]
    # and [[variant|text]] with [[primary|text]]
    
    replacements = []
    
    # Combine both dicts
    all_aliases = {}
    all_aliases.update(researcher_aliases)
    all_aliases.update(keyword_aliases)
    
    for variant, primary in all_aliases.items():
        if variant == primary:
            continue
            
        # We need to match [[variant]] and [[variant|...]]
        # We also need to be careful of safe names vs full names. 
        # Sometimes the quick card has [[Safe Name|Full Name]].
        
        safe_variant = "".join(c for c in variant if c.isalnum() or c in ('-', '_', ' ')).strip()
        safe_primary = "".join(c for c in primary if c.isalnum() or c in ('-', '_', ' ')).strip()
        
        # Replace exactly [[variant]]
        pattern1 = re.compile(r'\[\[' + re.escape(variant) + r'\]\]')
        # Replace exactly [[variant|something]]
        pattern2 = re.compile(r'\[\[' + re.escape(variant) + r'\|(.*?)\]\]')
        
        # Sometimes links are made using the safe string, so let's also look for that.
        pattern3 = re.compile(r'\[\[' + re.escape(safe_variant) + r'\]\]')
        pattern4 = re.compile(r'\[\[' + re.escape(safe_variant) + r'\|(.*?)\]\]')
        
        replacements.append((pattern1, r'[[' + safe_primary + r']]', variant, primary))
        replacements.append((pattern2, r'[[' + safe_primary + r'|\1]]', variant, primary))
        replacements.append((pattern3, r'[[' + safe_primary + r']]', safe_variant, primary))
        replacements.append((pattern4, r'[[' + safe_primary + r'|\1]]', safe_variant, primary))


    if not replacements:
        print("No aliases to process.")
        return

    updated_count = 0
    
    for directory in VAULT_DIRS:
        if not os.path.exists(directory):
            continue
            
        for root, dirs, files in os.walk(directory):
            for file in files:
                if not file.endswith(".md"):
                    continue
                    
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                    new_content = content
                    for pattern, replacement_str, var, prim in replacements:
                        new_content = pattern.sub(replacement_str, new_content)
                        
                    if new_content != content:
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        updated_count += 1
                        print(f"  Fixed alias links in {file}")
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")
                    
    print(f"\n✅ Successfully updated alias links in {updated_count} files.")

if __name__ == "__main__":
    main()
