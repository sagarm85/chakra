# Checkpoint / Resume Design

**Date:** 2026-04-28
**Feature:** Phase checkpointing so a failed run resumes from the last successful phase rather than restarting from scratch.

---

## Problem

Every run of `orchestrator.py` starts from the planning phase. If planning succeeds but coding (or testing) fails, the next run re-plans, re-assigns a new story ID, and re-prompts for human approval — wasting time and LLM tokens.

---

## Scope

Full-chain checkpointing: planning → coding → testing. Each phase's output is persisted on success so the next run can resume from the failure point.

---

## Architecture

**New file:** `tools/checkpoint_tool.py`
- `save(path, data)` — writes/overwrites `<story_path>.chakra.json`
- `load(path)` — returns parsed checkpoint dict, or `None` if absent/corrupt
- `clear(path)` — deletes the checkpoint file

**Modified file:** `orchestrator.py`
- On startup: compute story hash, load checkpoint, decide resume phase
- After each phase: call `save()`
- On `Done`: call `clear()`

No other files change.

---

## Checkpoint File

Location: `<story_path>.chakra.json` (e.g., `story.txt` → `story.chakra.json`)

```json
{
  "story_id": "CHAKRA-001",
  "story_hash": "<sha256 of story content>",
  "phase_reached": "coding",
  "tasks": [{"task": "...", "description": "..."}],
  "code_files": {"path/file.py": "# content"},
  "test_files": {"tests/test_file.py": "# content"}
}
```

- `story_hash`: SHA-256 of story text. Mismatch → discard checkpoint, re-plan.
- `phase_reached`: one of `"planning"` | `"coding"` | `"testing"`.
- `code_files` / `test_files`: only present once the respective phase succeeds.

---

## Resume Logic

| `phase_reached` | Skip | Restore |
|---|---|---|
| `"planning"` | planning + approval loop | `story_id`, `tasks` |
| `"coding"` | planning + coding | `story_id`, `tasks`, `code_files` |
| `"testing"` | planning + coding + testing | `story_id`, `tasks`, `code_files`, `test_files` |

On startup:
1. Hash story content.
2. Load checkpoint.
3. If hash mismatch → warn, delete, start fresh.
4. If valid → log `"Resuming from <phase>"`, restore state, skip phases.

---

## Error Handling

- Malformed/corrupt checkpoint JSON → treat as no checkpoint, start fresh.
- Story content changed (hash mismatch) → warn user, delete checkpoint, start fresh.
- Successful completion (`Done`) → checkpoint deleted automatically.

---

## README Update

Add a "Checkpoint & Resume" section documenting:
- What the `.chakra.json` file is
- That it is auto-created and auto-deleted
- How to force a fresh run (delete the file manually)
- That changing `story.txt` between runs discards the checkpoint
