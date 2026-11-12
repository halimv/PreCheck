"""Repair backends for the benchmark.

CountingOllamaBackend is the pipeline's Ollama backend plus per-call token and time counts.
RuleBackend (baseline B1) applies the translator's own suggested fix with no model, which
measures how far the lab-concept diagnostics get on their own.
"""

import json
import re
import urllib.request
from typing import Any, Dict, List

from pipeline.self_heal import EDIT_SCHEMA, OllamaBackend


class CountingOllamaBackend(OllamaBackend):
    def __init__(self, model: str = "qwen2.5-coder:7b", temperature: float = 0.0, num_ctx: int = 32768):
        super().__init__(model=model, num_ctx=num_ctx)
        self.temperature = temperature
        self.calls: List[Dict[str, Any]] = []

    def propose_edits(self, system: str, prompt: str, schema: Dict[str, Any] = EDIT_SCHEMA) -> Dict[str, Any]:
        body = {
            "model": self.model,
            "stream": False,
            "format": schema,
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }
        req = urllib.request.Request(
            f"{self.host}/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=900) as resp:
            reply = json.loads(resp.read())
        self.calls.append({
            "prompt_tokens": reply.get("prompt_eval_count", 0),
            "output_tokens": reply.get("eval_count", 0),
            "seconds": reply.get("total_duration", 0) / 1e9,
        })
        return json.loads(reply["message"]["content"])


SET_VOLUME = re.compile(r'\{"op": "set_initial_volume", "labware": "([^"]+)", "volume_ul": ([\d.]+)\}')
SPLIT = re.compile(r"Replace step (\d+) with \d+ steps of the same action, each using a single channel")


class RuleBackend:
    """Reads the suggested fix out of the translated diagnostic in the prompt and applies it verbatim."""

    model = "rule-based"

    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def propose_edits(self, system: str, prompt: str, schema: Any = None) -> Dict[str, Any]:
        self.calls.append({"prompt_tokens": 0, "output_tokens": 0, "seconds": 0.0})
        m = SET_VOLUME.search(prompt)
        if m:
            lid, vol = m.group(1), float(m.group(2))
            return {
                "reasoning": f"Rule: INSUFFICIENT_LIQUID, not enough liquid in {lid}; load {vol:g} uL.",
                "edits": [{"op": "set_initial_volume", "labware": lid, "volume_ul": vol}],
            }
        m = SPLIT.search(prompt)
        if m:
            n = int(m.group(1))
            step = next(
                json.loads(line) for line in prompt.splitlines()
                if line.startswith("{") and json.loads(line).get("step") == n
            )
            new_steps = [
                {**{k: v for k, v in step.items() if k != "step"}, "channels": [ch],
                 "description": f"{step['action']} on channel {ch} only"}
                for ch in step["channels"]
            ]
            return {
                "reasoning": f"Rule: CHANNEL_SPACING, channels do not fit in {step['labware']}; "
                             "split into single channel steps.",
                "edits": [{"op": "replace_step", "step": n, "new_steps": new_steps}],
            }
        return {"reasoning": "Rule: no suggested fix found in the diagnostic.", "edits": []}
