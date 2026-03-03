import os
import re

PEOPLE_DRAFT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../04_researchers/drafts"))
PEOPLE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../04_researchers"))
KEYWORDS_DRAFT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../05_keywords/drafts"))
KEYWORDS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../05_keywords"))

DEEP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../03_deep"))
BRIEF_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards"))
QUICK_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards/quick"))

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

def update_all_links():
    search_dirs = [PEOPLE_DRAFT_DIR, PEOPLE_DIR, KEYWORDS_DRAFT_DIR, KEYWORDS_DIR]
    
    updated_count = 0

    for directory in search_dirs:
        if not os.path.exists(directory):
            continue

        updates_dir = os.path.join(directory, "_updates")

        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            
            if not filename.endswith(".md") or filename.endswith(".update.md"):
                continue

            if not filename.endswith(".md"):
                continue
                
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # Find all list items starting with - [[citekey...
            # The structure we are looking for is: - [[link_target]] : Old Title or Stars
            # We want to replace the entire line so we capture the line context
            def link_replacer(match):
                full_link = match.group(1)
                old_rest_of_line = match.group(2)
                
                # Extract base citekey
                link_target = full_link.split("|")[0]
                base_citekey = link_target.split("/")[-1].replace("_deep", "").replace(".md", "")
                
                # Determine new link target
                new_link = full_link
                if os.path.exists(os.path.join(DEEP_DIR, f"{base_citekey}_deep.md")):
                    new_link = f"{base_citekey}_deep"
                elif os.path.exists(os.path.join(BRIEF_DIR, f"{base_citekey}.md")):
                    new_link = f"02_cards/{base_citekey}|{base_citekey}"
                elif os.path.exists(os.path.join(QUICK_DIR, f"{base_citekey}.md")):
                    new_link = f"02_cards/quick/{base_citekey}|{base_citekey}"
                    
                # Clean up old rest of line to find just the title (remove old stars, old [DEEP] tags)
                clean_title = old_rest_of_line.strip()
                clean_title = re.sub(r'⭐+\s*', '', clean_title)
                clean_title = re.sub(r'\s*\[DEEP\]\s*', '', clean_title)
                
                # Format with new metadata
                formatted_title = get_card_metadata(base_citekey).format(title=clean_title)
                
                return f"- [[{new_link}]] : {formatted_title}"

            # Matching "- [[link]] : rest of line"
            new_content = re.sub(r'-\s+\[\[(.*?)\]\]\s*:\s*(.*)', link_replacer, content)

            # 2. Update forward links in main profile to .update.md
            base_name = filename.replace(".md", "")
            update_file = os.path.join(updates_dir, f"{base_name}.update.md")
            if os.path.exists(update_file) and "**Update History:**" not in new_content:
                parts = new_content.rsplit("\n---\n", 1)
                if len(parts) == 2:
                    new_content = parts[0] + f"\n---\n**Update History:** [[{base_name}.update|View Logs]]\n\n" + parts[1].lstrip()

            if new_content != content:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                updated_count += 1
                print(f"  Fixed links in {filename}")

    # Process backlinks in _updates folder
    for directory in search_dirs:
        updates_dir = os.path.join(directory, "_updates")
        if not os.path.exists(updates_dir):
            continue
            
        for filename in os.listdir(updates_dir):
            if not filename.endswith(".update.md"):
                continue
                
            filepath = os.path.join(updates_dir, filename)
            base_name = filename.replace(".update.md", "")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            if "**Main Profile:**" not in content:
                new_content = f"**Main Profile:** [[{base_name}]]\n\n" + content
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                updated_count += 1
                print(f"  Added backlink to {filename}")

    print(f"\n✅ Successfully updated links and metadata in {updated_count} cards.")

if __name__ == "__main__":
    update_all_links()
