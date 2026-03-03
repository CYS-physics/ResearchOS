import os
import subprocess
import time

# Create a dummy paper in the library json for testing
LIBRARY_JSON = "/Users/siksik/내 드라이브/obsidian/ResearchOS/01_zotero_export/library.json"
TEST_PAPER_ID = "test_incremental_paper_2026"
TEST_RESEARCHER = "Test Researcher Incremental"
TEST_KEYWORD = "test_incremental_keyword"

print("Test setup: Incremental Updates")

# 1. Run quick generator to create base state
print("\n--- Running Quick Card Generator ---")
subprocess.run(["python3", "/Users/siksik/내 드라이브/obsidian/ResearchOS/scripts/01_quick_card_generator.py"])

# 2. Run researcher generator to create drafts
print("\n--- Running Researcher Generator (Drafts) ---")
subprocess.run(["python3", "/Users/siksik/내 드라이브/obsidian/ResearchOS/scripts/11_researcher_card_generator.py"])

# 3. Modify a researcher draft to pretend it's a deep card (for testing the quick generator flag)
# We need an existing deep card that links to our test paper, or we just manually create one
test_deep_card_path = f"/Users/siksik/내 드라이브/obsidian/ResearchOS/04_researchers/{TEST_RESEARCHER}.md"
print(f"\n--- Creating dummy deep card at {test_deep_card_path} ---")

# Ensure dir exists
os.makedirs(os.path.dirname(test_deep_card_path), exist_ok=True)

with open(test_deep_card_path, "w", encoding="utf-8") as f:
    f.write(f"""---
aliases: ["{TEST_RESEARCHER}"]
tags: ["researcher", "key_researchers"]
status: deep_processed
paper_count: 1
---
# {TEST_RESEARCHER}

## Papers in Library
- [[{TEST_PAPER_ID}]] [PROCESSED] : Title Here

---
## 1. Core Keywords
#test

## 2. Key Research Questions & Focus
Testing.

## 3. Update Summary
Initial profile.
""")

print("Created dummy deep card with status: deep_processed.")

# 4. Now modify the quick card generator to trigger the update
# We don't actually need to modify the json, the flag_affected_profiles_as_modified function just looks for the citekey.
print(f"\n--- Testing flag_affected_profiles_as_modified for {TEST_PAPER_ID} ---")
import sys
sys.path.append("/Users/siksik/내 드라이브/obsidian/ResearchOS/scripts")
from importlib import import_module
quick_script = import_module("01_quick_card_generator")

quick_script.flag_affected_profiles_as_modified(TEST_PAPER_ID)

# 5. Check if the status changed
with open(test_deep_card_path, "r", encoding="utf-8") as f:
    content = f.read()
    if "status: modified" in content:
        print("✅ SUCCESS: Profile status changed to 'modified'!")
    else:
        print("❌ FAILED: Profile status did not change.")

# 6. Now let's test the deep researcher generator observing the PROCESSED tag and updating it
# But first we need a new unseen paper to trigger the update
with open(test_deep_card_path, "w", encoding="utf-8") as f:
    f.write(f"""---
aliases: ["{TEST_RESEARCHER}"]
tags: ["researcher", "key_researchers"]
status: modified
paper_count: 2
---
# {TEST_RESEARCHER}

## Papers in Library
- [[{TEST_PAPER_ID}]] [PROCESSED] : Old Paper
- [[new_unprocessed_paper_2026]] : New Paper

---
## 1. Core Keywords
#test

## 2. Key Research Questions & Focus
Testing.

## 3. Update Summary
Initial profile.
""")

print("\n--- Running Deep Researcher Generator on 'modified' card ---")
subprocess.run(["python3", "/Users/siksik/내 드라이브/obsidian/ResearchOS/scripts/12_deep_researcher_card_generator.py"])

# 7. Check if the PROCESSED tag was added and status reverted to deep_processed
with open(test_deep_card_path, "r", encoding="utf-8") as f:
    content = f.read()
    
    if "status: deep_processed" in content:
        print("✅ SUCCESS: Profile status changed back to 'deep_processed'!")
    else:
        print("❌ FAILED: Profile status is not 'deep_processed'.")
        
    if "[[new_unprocessed_paper_2026]] [PROCESSED]" in content or "[[new_unprocessed_paper_2026]]  [PROCESSED]" in content:
        print("✅ SUCCESS: [PROCESSED] tag appended to new paper!")
    else:
        print("❌ FAILED: [PROCESSED] tag not appended correctly.")
        print("Content lines around paper:")
        for line in content.splitlines():
            if "new_unprocessed_paper" in line:
                print(f"  {line}")

print("\nCleaning up test files...")
os.remove(test_deep_card_path)
update_path = f"/Users/siksik/내 드라이브/obsidian/ResearchOS/04_researchers/_updates/{TEST_RESEARCHER}.update.md"
if os.path.exists(update_path):
    os.remove(update_path)
print("Done.")
