from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_PROMPT = """You are a static-analysis summarizer.
Summarize the given code in exactly 4 bullet lines.
Each line must start with "- ".
Use this fixed schema:
- Purpose:
- Source/Input:
- Key data/control flow:
- Risky operations/APIs:

Rules:
- Use exactly those 4 labels in that order.
- Keep summaries neutral and descriptive (no final security verdict).
- Do not claim CWE IDs or definitive vulnerability conclusions.
- Mention concrete function/API/variable names from the code.
- Preserve key branch conditions and source-to-sink/data-flow relations when visible.
- Call out error paths, early returns, and cleanup (e.g. resource release) when they affect safety.
- If information is missing, say "Unknown from visible snippet." and do not hallucinate.
- Keep each bullet to one concise sentence (two short clauses max if needed for accuracy).
- Do not include <think> or hidden reasoning.
- Output only the 4 bullets, nothing else.
"""


def _post_ollama(
    host: str,
    model: str,
    prompt: str,
    timeout_s: int = 240,
    num_predict: int = 180,
    temperature: float = 0.0,
    num_ctx: int | None = None,
) -> dict[str, str]:
    url = host.rstrip("/") + "/api/generate"
    options: dict[str, float | int] = {
        "temperature": temperature,
        "num_predict": num_predict,
    }
    if num_ctx is not None and num_ctx > 0:
        options["num_ctx"] = num_ctx
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": options,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    obj = json.loads(body)
    return {
        "response": str(obj.get("response", "")).strip(),
        "thinking": str(obj.get("thinking", "")).strip(),
        "done_reason": str(obj.get("done_reason", "")).strip(),
    }


def _load_completed_ids(output_path: Path) -> set[str]:
    done: set[str] = set()
    if not output_path.exists():
        return done
    with output_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            sid = str(row.get("sample_id", "")).strip()
            if not sid:
                sid = str(row.get("id", "")).strip()
            if sid:
                done.add(sid)
    return done


def _clip_text(s: str, max_chars: int) -> str:
    s = s.strip()
    if len(s) <= max_chars:
        return s
    return s[:max_chars]


KEY_LABELS = [
    "Purpose",
    "Source/Input",
    "Key data/control flow",
    "Risky operations/APIs",
    # "Vulnerability hypothesis",
]


RETRY_SUFFIX = """Rewrite the summary with higher factual precision.
Additional constraints:
- Use only evidence visible in the code snippet.
- Keep the same 4 labels in the same order.
- Avoid generic placeholders unless evidence is truly absent.
- Keep each bullet one concise sentence.
"""


def _cleanup_summary_text(s: str) -> str:
    text = (s or "").strip()
    if not text:
        return ""
    # Remove chain-of-thought blocks if model emits them.
    text = re.sub(r"(?is)<think>.*?</think>", "", text).strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Keep only bullet-like or label-like lines.
    kept: list[str] = []
    for ln in lines:
        l = ln.lstrip("- ").strip()
        if any(l.lower().startswith(k.lower() + ":") for k in KEY_LABELS):
            kept.append("- " + l)
        elif ln.startswith("- "):
            kept.append(ln)
    # If model returned paragraph text, try line-splitting by label.
    if not kept:
        flat = " ".join(lines)
        for k in KEY_LABELS:
            m = re.search(rf"(?i){re.escape(k)}\s*:\s*(.*?)(?=(Purpose:|Source/Input:|Key data/control flow:|Risky operations/APIs:|Vulnerability hypothesis:|$))", flat)
            if m:
                kept.append(f"- {k}: {m.group(1).strip()}")

    # Normalize to exactly 5 schema lines.
    out: list[str] = []
    for k in KEY_LABELS:
        val = ""
        for ln in kept:
            l = ln.lstrip("- ").strip()
            if l.lower().startswith(k.lower() + ":"):
                val = l[len(k) + 1 :].strip()
                break
        if not val:
            val = "Unknown from visible snippet."
        out.append(f"- {k}: {val}")
    return "\n".join(out)


def _has_all_key_labels(s: str) -> bool:
    low = (s or "").lower()
    return all((f"- {k}:").lower() in low for k in KEY_LABELS)


def _unknown_field_count(s: str) -> int:
    text = s or ""
    return text.count("Unknown from visible snippet.")


def _field_values(summary: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for ln in (summary or "").splitlines():
        l = ln.lstrip("- ").strip()
        for k in KEY_LABELS:
            pref = f"{k}:"
            if l.lower().startswith(pref.lower()):
                out[k] = l[len(pref) :].strip()
                break
    return out


def _concrete_cue_count(summary: str) -> int:
    # Heuristic: function-call patterns and common security-relevant API tokens.
    text = summary or ""
    call_like = len(re.findall(r"\b[A-Za-z_]\w*\s*\(", text))
    token_like = len(
        re.findall(
            r"\b(memcpy|memmove|strcpy|strncpy|malloc|free|read|write|open|recv|send|socket|GetNodeAttr|TF_RETURN_IF_ERROR|OP_REQUIRES)\b",
            text,
            flags=re.IGNORECASE,
        )
    )
    return call_like + token_like


def _needs_quality_retry(summary: str, done_reason: str) -> bool:
    if not summary.strip():
        return True
    fields = _field_values(summary)
    first3 = KEY_LABELS[:3]
    unknown_first3 = sum(fields.get(k, "") == "Unknown from visible snippet." for k in first3)
    short_first3 = sum(len(fields.get(k, "")) < 24 for k in first3)
    if unknown_first3 >= 1:
        return True
    if short_first3 >= 2:
        return True
    if done_reason == "length" and _concrete_cue_count(summary) < 2:
        return True
    return False


def _quality_score(summary: str, done_reason: str) -> tuple[int, int, int, int]:
    fields = _field_values(summary)
    first3 = KEY_LABELS[:3]
    unknown_first3 = sum(fields.get(k, "") == "Unknown from visible snippet." for k in first3)
    unknown_total = _unknown_field_count(summary)
    length_stop = int(done_reason == "length")
    # Lower tuple is better; negate cue count so more cues improves score.
    cue_penalty = -_concrete_cue_count(summary)
    return (unknown_first3, unknown_total, length_stop, cue_penalty)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate LLM summaries via local Ollama and append to JSONL.")
    ap.add_argument("--input", required=True, help="Input JSONL with sample_id and source text field.")
    ap.add_argument("--output", required=True, help="Output JSONL path.")
    ap.add_argument("--model", default="gpt-oss:20b", help="Ollama model name.")
    ap.add_argument("--host", default="http://127.0.0.1:11434", help="Ollama host URL.")
    ap.add_argument(
        "--id-field",
        default="sample_id",
        help="Row key for sample id (e.g. sample_id or id). Output always sets sample_id for resume compatibility.",
    )
    ap.add_argument("--input-field", default="code", help="Field used as summary source text.")
    ap.add_argument("--summary-field", default="llm_summary_text", help="Output field name for summary text.")
    ap.add_argument("--error-field", default="llm_summary_error", help="Output field name for errors.")
    ap.add_argument("--max-chars", type=int, default=7000, help="Max input chars sent to model per sample.")
    ap.add_argument("--limit", type=int, default=0, help="Optional max number of new rows to process.")
    ap.add_argument("--sleep-ms", type=int, default=0, help="Optional delay between requests.")
    ap.add_argument("--timeout-s", type=int, default=240, help="Request timeout seconds.")
    ap.add_argument("--num-predict", type=int, default=180, help="Generation token cap.")
    ap.add_argument(
        "--num-ctx",
        type=int,
        default=0,
        help="If >0, pass num_ctx to Ollama (wider context for long prompts; uses more VRAM).",
    )
    ap.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature.")
    ap.add_argument("--prompt-file", default="", help="Optional prompt file; defaults to built-in summary schema.")
    ap.add_argument(
        "--retry-poor-summary",
        action="store_true",
        help="Retry once with shorter input and larger output budget when summary looks truncated/low-information.",
    )
    ap.add_argument(
        "--use-thinking-fallback",
        action="store_true",
        help="If response is empty, fallback to Ollama `thinking` field.",
    )
    args = ap.parse_args()

    in_p = Path(args.input)
    out_p = Path(args.output)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    base_prompt = DEFAULT_PROMPT
    if args.prompt_file:
        base_prompt = Path(args.prompt_file).read_text(encoding="utf-8")

    done_ids = _load_completed_ids(out_p)
    n_total = 0
    n_skip_done = 0
    n_processed = 0
    n_error = 0

    with in_p.open("r", encoding="utf-8") as fin, out_p.open("a", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            n_total += 1
            row = json.loads(line)
            sid = str(row.get(args.id_field, "") or "").strip()
            if not sid:
                sid = str(row.get("sample_id", "") or row.get("id", "") or "").strip()
            if sid in done_ids:
                n_skip_done += 1
                continue
            if args.limit and n_processed >= args.limit:
                break

            src = str(row.get(args.input_field, "") or "")
            src = _clip_text(src, args.max_chars)

            # Keep prompt lean: retain sample_id for mapping, omit extra metadata.
            prompt = (
                f"{base_prompt}\n"
                f"Sample ID: {sid}\n"
                f"{src}\n"
            )

            summary = ""
            err = ""
            done_reason = ""
            num_ctx_opt = args.num_ctx if args.num_ctx > 0 else None
            try:
                out_obj = _post_ollama(
                    host=args.host,
                    model=args.model,
                    prompt=prompt,
                    timeout_s=args.timeout_s,
                    num_predict=args.num_predict,
                    temperature=args.temperature,
                    num_ctx=num_ctx_opt,
                )
                summary = out_obj.get("response", "")
                done_reason = out_obj.get("done_reason", "")
                if not summary and args.use_thinking_fallback:
                    summary = out_obj.get("thinking", "")
                summary = _cleanup_summary_text(summary)

                # Optional quality retry for truncated or low-information summaries.
                if args.retry_poor_summary:
                    looks_weak = _needs_quality_retry(summary, done_reason)
                    if looks_weak:
                        retry_src = _clip_text(src, max(800, int(args.max_chars * 0.75)))
                        retry_prompt = (
                            f"{base_prompt}\n"
                            f"{RETRY_SUFFIX}\n"
                            "Previous summary draft:\n"
                            f"{summary}\n"
                            f"Sample ID: {sid}\n"
                            f"{retry_src}\n"
                        )
                        retry_obj = _post_ollama(
                            host=args.host,
                            model=args.model,
                            prompt=retry_prompt,
                            timeout_s=max(args.timeout_s, 900),
                            num_predict=max(args.num_predict, 700),
                            temperature=args.temperature,
                            num_ctx=num_ctx_opt,
                        )
                        retry_summary = retry_obj.get("response", "")
                        retry_done_reason = retry_obj.get("done_reason", "")
                        if not retry_summary and args.use_thinking_fallback:
                            retry_summary = retry_obj.get("thinking", "")
                        retry_summary = _cleanup_summary_text(retry_summary)
                        improved = retry_summary and (
                            _quality_score(retry_summary, retry_done_reason)
                            < _quality_score(summary, done_reason)
                        )
                        if improved:
                            summary = retry_summary
                            done_reason = retry_done_reason

                if not summary and not err:
                    err = f"empty_response_done_reason:{done_reason or 'unknown'}"
                elif not _has_all_key_labels(summary) and not err:
                    err = "summary_missing_key_fields"
            except urllib.error.URLError as e:
                err = f"url_error:{e}"
            except Exception as e:  # noqa: BLE001
                err = f"generation_error:{e}"

            out = dict(row)
            if not str(out.get("sample_id", "") or "").strip():
                out["sample_id"] = sid
            # Drop raw source text from JSONL to keep outputs small; join on sample_id/id if needed.
            out.pop(args.input_field, None)
            out["representation"] = "llm_summary"
            out[args.summary_field] = summary
            out[args.error_field] = err
            out["llm_summary_model"] = args.model
            out["llm_summary_input_field"] = args.input_field
            out["llm_summary_done_reason"] = done_reason
            fout.write(json.dumps(out, ensure_ascii=False) + "\n")
            fout.flush()

            n_processed += 1
            if err:
                n_error += 1
            if args.sleep_ms > 0:
                time.sleep(args.sleep_ms / 1000.0)

            if n_processed % 10 == 0:
                print(f"processed={n_processed} errors={n_error}")

    print(
        f"done total_seen={n_total} skipped_done={n_skip_done} "
        f"new_processed={n_processed} errors={n_error} output={out_p}"
    )


if __name__ == "__main__":
    main()
