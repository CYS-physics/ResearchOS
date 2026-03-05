# ResearchOS

## Brain Context Loader + Context Vault Update Package

This project uses a lightweight, editable **research context vault** (the `brain/` folder) that can be loaded and injected into LLM prompts when generating cards (Quick / Brief / Deep). The goal is to keep high-signal personal research context in Markdown so you can:

- auto-tag new literature (keyword extraction)
- ground generation with your current interests, taxonomy, and running questions
- keep “deep cards” navigable inside Obsidian

This README merges:
- the **Context vault update package** README (generated **2026-03-04**)
- the **Brain Context Loader** README (how `brain_utils.py` is used for keyword/context loading)

## Directory layout

- `brain/`
  - `00_My_Research_Context.md` — updated core interests / questions (high signal)
  - `01_Keyword_Taxonomy.md` — expanded tag taxonomy (grouped)
  - `02_Recent_Reviews_and_Influences.md` — what changed + links to deep cards
- `03_deep/journal_club/`
  - `*_deep.md` — deep cards (1 per slide deck / review topic)
  - `_Index.md` — navigation index (entry point)

## Quick start (Obsidian)

1. Copy the folders into the root of your Obsidian vault (**merge** if folders already exist).
2. Put the original PDFs into your vault at:
   - `00_Attachments/<same file name>.pdf`
   - (or edit the `source_pdf` field inside each deep card)
3. Open `03_deep/journal_club/_Index.md` and start from there.

### Notes

- These are **drafts** meant to be edited.
- The `## ✍️ Manual Notes` section in each deep card is meant for your own additions.

## Brain loading rules

### 1) Keyword extraction (Quick Cards)

The Quick Card generator (`01_quick_card_generator.py`) can automatically extract keywords from your `brain/` folder to tag new Zotero papers. It scans for:

- **YAML frontmatter**: `keywords: [ai, machine learning]` or `tags: [concept]`
- **Keyword sections**: bulleted lists under the exact heading `## 3. Important Keywords`
- **Inline hashtags**: any hashtag like `#active_matter` used anywhere in the document

### 2) LLM context generation (Brief + Deep Cards)

The Brief and Deep card generators inject the `brain/` context into their prompts to personalize outputs.

You can control exactly what is sent to the model:

- **Exclude files entirely**
  - Add `include_in_llm: false` to a file's frontmatter.

- **Send only a specific snippet**
  - Put the desired excerpt under the heading `## LLM Context`, **or**
  - Wrap it with HTML comments:
    - `<!-- LLM_CONTEXT_START --> ... <!-- LLM_CONTEXT_END -->`

### 3) Token budgeting

To prevent API quota exhaustion on large vaults, you can set maximum character limits in your `.env` file:

```env
BRAIN_CONTEXT_MAX_CHARS=18000
BRAIN_CONTEXT_MAX_CHARS_PER_FILE=4000
```

## Using brain context with `antigravity` (API calls)

When you load and use the API via `antigravity`, you generally want your **brain context** to be present in every call.

Because the exact `antigravity` interface can vary by project, the key idea is:

- **Build the brain context once** (from `brain/`) using `brain_utils.py`
- **Inject it** into each request (typically as a *system message*), **or** wrap your client so it is injected automatically

### Pattern A — Per-request injection (simple & explicit)

1. Build context once at startup.
2. Prepend as a **system** message (or pass as your client's `context=` / `system_prompt=` argument).

```python
import os
import antigravity
from brain_utils import load_brain_context

brain_context = load_brain_context(
    brain_dir="brain",
    max_chars=int(os.getenv("BRAIN_CONTEXT_MAX_CHARS", "18000")),
    max_chars_per_file=int(os.getenv("BRAIN_CONTEXT_MAX_CHARS_PER_FILE", "4000")),
)

system_prompt = (
    "You are ResearchOS assistant. "
    "Use the following personal research context when it is relevant.\n\n"
    + brain_context
)

client = antigravity.load_api()  # (example) reads API key/model from env

resp = client.chat(
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Draft a deep card for this paper..."},
    ]
)
```

### Pattern B — Context-aware client wrapper (set once, reuse)

If you want to “load API + context” once and reuse across scripts, wrap the antigravity client so it always prepends the brain context.

```python
import antigravity
from brain_utils import load_brain_context

class ContextClient:
    def __init__(self, *args, **kwargs):
        self._client = antigravity.load_api(*args, **kwargs)
        self._brain_context = load_brain_context("brain")

    def chat(self, messages, **kwargs):
        messages = [{"role": "system", "content": self._brain_context}] + list(messages)
        return self._client.chat(messages=messages, **kwargs)

client = ContextClient()
resp = client.chat([{"role": "user", "content": "Summarize this PDF..."}])
```

### Recommended conventions (so context stays useful)

- Keep stable, high-signal constraints in `brain/00_My_Research_Context.md`.
- Use `include_in_llm: false` for long notes, scratchpads, or anything you do **not** want sent to the API.
- For long documents, prefer `## LLM Context` (or `LLM_CONTEXT_START/END`) snippets so you don't waste tokens.
- If your scripts run long, consider **caching** the built context and rebuilding only when files in `brain/` change.
