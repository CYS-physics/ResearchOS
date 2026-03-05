#!/usr/bin/env python3
import os
import subprocess
import time

def run_script(script_name):
    script_path = os.path.join(os.path.dirname(__file__), script_name)
    if not os.path.exists(script_path):
        print(f"❌ Error: Could not find {script_name} at {script_path}")
        return False
        
    print(f"\n" + "="*50)
    print(f"🚀 Running: {script_name}")
    print("="*50)
    
    start_time = time.time()
    try:
        # We use subprocess to run the python file so it executes in its own fresh environment
        result = subprocess.run(["python3", script_path], check=True, text=True)
        elapsed = time.time() - start_time
        print(f"✅ Finished {script_name} in {elapsed:.2f}s")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error executing {script_name}:")
        print(e)
        return False

def main():
    print("Starting Routine Sync Sequence...")
    print("This will process new Zotero exports, update aliases, and rebuild base drafts.")
    print("NOTE: This will NOT trigger AI (Deep) generation.\n")
    
    scripts_to_run = [
        "01_quick_card_generator.py",
        "01c_merge_duplicate_cards.py",
        "find_duplicates.py",
        "clean_aliases.py",
        "31b_update_alias_links.py",
        "11_researcher_card_generator.py",
        "21_keyword_card_generator.py",
        "32_update_all_links.py",
        "33_generate_preprint_index.py"
    ]
    
    for script in scripts_to_run:
        success = run_script(script)
        if not success:
            print("\n⚠️ Sync sequence halted due to an error.")
            return
            
    print("\n" + "="*50)
    print("✨ Routine Sync Complete!")
    print("Your quick cards are updated, aliases are merged, and links are synced.")
    print("A Preprint Index was generated.")
    print("Any profiles affected by new papers have been flagged as 'modified'.")
    print("When you have API quota available, you can manually run 12_ and 22_ deep generators.")
    print("="*50)

if __name__ == "__main__":
    main()
