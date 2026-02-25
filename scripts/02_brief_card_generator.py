import json
import os
import re
import time
from dotenv import load_dotenv
import openai
from google import genai

env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.env"))
load_dotenv(dotenv_path=env_path)

gemini_api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None

openai_api_key = os.getenv("OPENAI_API_KEY")
openai_client = openai.OpenAI(api_key=openai_api_key) if openai_api_key else None

INPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards/quick"))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../02_cards"))
BRAIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../brain"))

def run_llm_prompt(prompt: str) -> str:
    if client:
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            print(f"  Gemini API failed: {e}. Falling back to OpenAI...")
            
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

def load_research_context() -> str:
    if not os.path.exists(BRAIN_DIR):
        print(f"Warning: Brain directory not found at {BRAIN_DIR}")
        return "No specific user context provided."
        
    context_parts = []
    for filename in os.listdir(BRAIN_DIR):
        if not filename.endswith(".md"):
            continue
            
        filepath = os.path.join(BRAIN_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                context_parts.append(f"--- Context from {filename} ---\n{content}\n")
        except Exception as e:
            print(f"Error reading brain file {filename}: {e}")
            
    if not context_parts:
        return "No specific user context provided."
        
    return "\n".join(context_parts)

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

        # Append to content and replace status
        new_content = content.replace("status: brief", "status: brief_processed")
        new_content = new_content.replace("- status: brief", "- status: brief_processed")
        
        backlink = f"**Previous Version:** [[02_cards/quick/{citekey}|Quick Card]]\n\n"
        
        # Insert before the horizontal rule if it exists, otherwise at the end
        if "---" in new_content.split("Abstract")[1]: # rough check
            parts = new_content.rsplit("\n---", 1)
            final_content = parts[0] + "\n\n" + backlink + ai_response + "\n\n---" + parts[1]
        else:
            final_content = new_content + "\n\n" + backlink + ai_response

        with open(filepath_out, "w", encoding="utf-8") as f:
            f.write(final_content)

        print(f"  ✅ Updated {citekey}.md with Brief analysis.")
        processed_count += 1
        
    if processed_count == 0:
        print("No cards found with 'status: brief'.")
    else:
        print(f"\nFinished processing {processed_count} brief cards.")

if __name__ == "__main__":
    generate_brief_cards()
