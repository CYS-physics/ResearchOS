import json
import os
import re
import time
from dotenv import load_dotenv
import openai
from google import genai

env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.env"))
load_dotenv(dotenv_path=env_path)

# Initialize API clients
gemini_keys = [v for k, v in os.environ.items() if k.startswith("GEMINI_API_KEY") and v.strip()]
gemini_clients = [genai.Client(api_key=key) for key in gemini_keys]
current_gemini_index = 0

openai_api_key = os.getenv("OPENAI_API_KEY")
openai_client = openai.OpenAI(api_key=openai_api_key) if openai_api_key else None

INPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards/quick"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards"))
BRAIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../brain"))

def run_llm_prompt(prompt: str) -> str:
    global current_gemini_index
    
    # Try Gemini clients first, rotating if we hit a 429 quota exhaustion
    while current_gemini_index < len(gemini_clients):
        client = gemini_clients[current_gemini_index]
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            error_str = str(e)
            if "429" in error_str and "RESOURCE_EXHAUSTED" in error_str:
                print(f"  Gemini API Key {current_gemini_index + 1} exhausted (429). Rotating to next key...")
                current_gemini_index += 1
                continue # Try the next key in the loop
            else:
                print(f"  Gemini API failed: {e}. Falling back to OpenAI...")
                break # Non-quota error, jump to OpenAI fallback
                
    if current_gemini_index >= len(gemini_clients) and gemini_clients:
        print("  All Gemini API keys exhausted.")
            
    if openai_client:
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                timeout=30.0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"  OpenAI API failed: {e}")
            if "429" in str(e):
                raise Exception("RATE_LIMIT")
            
    return ""

def run_llm_prompt_with_retry(prompt: str, max_retries: int = 3) -> str:
    base_delay = 10
    for attempt in range(max_retries):
        try:
            result = run_llm_prompt(prompt)
            if result:
                return result
            # Only retries if RATE_LIMIT exception was raised, empty string means normal auth/eval failure
            break
        except Exception as e:
            if "RATE_LIMIT" in str(e):
                delay = base_delay * (2 ** attempt)
                if attempt < max_retries - 1:
                    print(f"  [Rate Limit Hit] Sleeping for {delay} seconds before retry {attempt + 1}/{max_retries}...")
                    time.sleep(delay)
                else:
                    print(f"  [Rate Limit] Max retries reached.")
                    return ""
            else:
                return ""
    return ""

import brain_utils

def load_research_context() -> str:
    return brain_utils.load_brain_context(BRAIN_DIR)

def generate_brief_cards():
    research_context = load_research_context()

    if not os.path.exists(INPUT_DIR):
        print("No quick cards found.")
        return

    processed_count = 0

    for filename in os.listdir(INPUT_DIR):
        if not filename.endswith(".md"):
            continue
            
        filepath_in = os.path.join(INPUT_DIR, filename)
        filepath_out = os.path.join(OUTPUT_DIR, filename)
        with open(filepath_in, "r", encoding="utf-8") as f:
            content = f.read()

        if "status: brief\n" not in content and "status: brief\r" not in content and "status: brief" not in content.splitlines():
            continue

        citekey = filename.replace(".md", "")
        print(f"\nProcessing Brief Card: {citekey}...")

        # Extract abstract
        abstract_match = re.search(r'## Abstract \(Preview\)\n(.*?)(\n---|\Z)', content, re.DOTALL)
        abstract = abstract_match.group(1).strip() if abstract_match else "(No Abstract)"

        prompt = f'''You are an expert academic research assistant. I need you to create a "Brief Card" analysis for the following paper abstract.
You must analyze it based strictly on my personal research context.

### My Research Context:
{research_context}

### Paper Abstract:
{abstract}

### Task:
Output valid Markdown format. Do not wrap it in ```markdown codeblocks. Provide exactly these sections to append to the card:

## Relevance Rating
(Provide a rating from 1 to 5 stars, using ⭐ emojis, based on how closely this paper aligns with my core interests and key questions. E.g., ⭐⭐⭐⭐. Add a 1-sentence justification for the score.)

## Brainstorming & Connections
(1 paragraph analyzing exactly how this paper conceptually connects to my 'Key Questions' or relates to my 'Core Interests'. Be highly specific and technical.)

## Questions to Think About
(Generate 2-3 interesting or provocative questions about this paper's findings that I should keep in mind if I decide to read the full PDF. Format as a bulleted list. keep it short 2-3 sentences each)

## Recommended Keywords
(Provide 3-5 specific keywords or tags relevant to this paper and my research context. Format them as hashtags separated by spaces, e.g., #active_matter #machine_learning #phase_separation)
'''
        
        print(f"  Sending to LLM API...")
        ai_response = run_llm_prompt_with_retry(prompt)
        
        if not ai_response:
            print(f"  Failed to get a response for {citekey}. Skipping.")
            continue

        # Extract manual notes if any
        manual_notes = "\n\n## ✍️ Manual Notes\n*(Add your manual notes here - this section will not be overwritten by AI)*\n"
        if os.path.exists(filepath_out):
            with open(filepath_out, "r", encoding="utf-8") as existing_f:
                existing_content = existing_f.read()
                if "## ✍️ Manual Notes" in existing_content:
                    manual_notes = "\n\n## ✍️ Manual Notes" + existing_content.split("## ✍️ Manual Notes", 1)[1]
        elif "## ✍️ Manual Notes" in content:
            manual_notes = "\n\n## ✍️ Manual Notes" + content.split("## ✍️ Manual Notes", 1)[1]

        # Append to content and replace status
        new_content = re.sub(r'\bstatus:\s*brief\b', 'status: brief_processed', content)
        new_content = re.sub(r'-\s*status:\s*brief\b', '- status: brief_processed', new_content)
        if "## ✍️ Manual Notes" in new_content:
            new_content = new_content.split("## ✍️ Manual Notes", 1)[0].strip()
        
        backlink = f"**Previous Version:** [[02_cards/quick/{citekey}|Quick Card]]\n\n"
        
        # Insert before the horizontal rule if it exists, otherwise at the end
        if len(new_content.split("Abstract")) > 1 and "---" in new_content.split("Abstract")[1]: # rough check
            parts = new_content.rsplit("\n---", 1)
            final_content = parts[0] + "\n\n" + manual_notes.strip() + "\n\n" + backlink + ai_response + "\n\n---" + parts[1]
        else:
            final_content = new_content + "\n\n" + manual_notes.strip() + "\n\n" + backlink + ai_response

        with open(filepath_out, "w", encoding="utf-8") as f:
            f.write(final_content)

        # Update the original input file status so it's not processed again
        with open(filepath_in, "w", encoding="utf-8") as f:
            f.write(final_content)

        print(f"  ✅ Updated {citekey}.md with Brief analysis.")
        processed_count += 1
        
    if processed_count == 0:
        print("No cards found with 'status: brief'.")
    else:
        print(f"\nFinished processing {processed_count} brief cards.")

if __name__ == "__main__":
    generate_brief_cards()
