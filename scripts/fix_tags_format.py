import os
import re

def standardize_tags_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the frontmatter block
    frontmatter_match = re.search(r'^---\n(.*?)\n---((\n|\Z).*)?', content, re.DOTALL)
    if not frontmatter_match:
        return False
        
    frontmatter = frontmatter_match.group(1)
    rest_of_file = frontmatter_match.group(2) or ""
    
    # check if 'tags:' exists in frontmatter
    tags_match = re.search(r'^tags:\s*(.*?)$', frontmatter, re.MULTILINE)
    if not tags_match:
        return False
        
    tags_value = tags_match.group(1).strip()
    
    # Check if it's already a list, or some other format.
    # We are specifically looking for `tags: [tag1, tag2]` or `tags: ["tag1", "tag2"]`
    if tags_value.startswith('['):
        # Extract items
        items_str = tags_value.strip('[] \t')
        # Split by comma, handling potential quotes
        items = []
        if items_str:
            # Simple split by comma, then strip quotes and spaces
            raw_items = [item.strip() for item in items_str.split(',')]
            for item in raw_items:
                clean_item = item.strip('"\'')
                if clean_item:
                    items.append(clean_item)
                    
        if items:
            new_tags_yaml = "tags:\n" + "\n".join([f"  - {item}" for item in items])
            new_frontmatter = frontmatter[:tags_match.start()] + new_tags_yaml + frontmatter[tags_match.end():]
            new_content = "---\n" + new_frontmatter + "\n---" + rest_of_file
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        elif not items_str:
            # empty brackets case: tags: [] -> tags:
             new_tags_yaml = "tags:"
             new_frontmatter = frontmatter[:tags_match.start()] + new_tags_yaml + frontmatter[tags_match.end():]
             new_content = "---\n" + new_frontmatter + "\n---" + rest_of_file
             
             with open(filepath, 'w', encoding='utf-8') as f:
                 f.write(new_content)
             return True
            
    return False

def standardize_all_tags(base_dirs):
    processed_count = 0
    modified_count = 0
    for base_dir in base_dirs:
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                if file.endswith('.md'):
                    filepath = os.path.join(root, file)
                    processed_count += 1
                    if standardize_tags_in_file(filepath):
                        print(f"Standardized tags in: {filepath}")
                        modified_count += 1
    print(f"Processed {processed_count} markdown files. Modified tags in {modified_count} files.")

if __name__ == "__main__":
    base_dirs = [
        "/Users/siksik/내 드라이브/obsidian/ResearchOS/02_cards",
        "/Users/siksik/내 드라이브/obsidian/ResearchOS/03_deep",
        "/Users/siksik/내 드라이브/obsidian/ResearchOS/04_researchers",
        "/Users/siksik/내 드라이브/obsidian/ResearchOS/05_keywords",
    ]
    standardize_all_tags(base_dirs)
