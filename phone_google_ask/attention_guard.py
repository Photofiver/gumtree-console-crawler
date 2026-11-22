"""External, pretrained-transformer attention for prioritising review context.

This is an actual scaled dot-product attention computation over pretrained
sentence embeddings, NOT an alteration to ChatGPT model weights or layers.
All requirements remain mandatory regardless of their attention weights.
"""
import hashlib
import json
import math
import os
from pathlib import Path

MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MAX_CHECKS = 64


def context_hash(question, requirements):
    payload = json.dumps([question, requirements], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def scaled_dot_product_attention(query, keys):
    """Return softmax(QK^T/sqrt(d)) and its weighted V (V=K).

    The encoder supplies *trained* representations; no randomly initialised
    trainable projection is presented as a useful attention mechanism.
    """
    # numpy.ndarray / torch.Tensor refuse boolean truth testing for multi-value
    # arrays. Validate lengths explicitly rather than using `if not keys`.
    if query is None or keys is None or len(query) == 0 or len(keys) == 0:
        raise ValueError("Attention requires a query and at least one key")
    d = len(query)
    if any(len(key) != d for key in keys):
        raise ValueError("Inconsistent embedding dimensions")
    numbers = [float(v) for v in query] + [float(v) for key in keys for v in key]
    if not all(math.isfinite(x) for x in numbers):
        raise ValueError("Non-finite embedding")
    scores = [sum(float(a)*float(b) for a,b in zip(query,key))/math.sqrt(d) for key in keys]
    largest = max(scores)
    exp = [math.exp(s-largest) for s in scores]
    total = sum(exp)
    weights = [v/total for v in exp]
    attended = [sum(w*float(key[j]) for w,key in zip(weights,keys)) for j in range(d)]
    return weights, attended


def build_focus(data, encoder):
    question = data.get("question")
    checks = data.get("checks")
    if not isinstance(question, str) or not question.strip() or not isinstance(checks, list):
        raise ValueError("Missing main task or checks")
    if not 1 <= len(checks) <= MAX_CHECKS:
        raise ValueError("Number of requirements outside supported range")
    requirements = [c["requirement"] for c in checks]
    if not all(isinstance(r, str) and r.strip() for r in requirements):
        raise ValueError("Invalid requirement")
    # The multilingual pretrained transformer itself uses self-attention;
    # these final trained representations feed a separate cross-item attention.
    embeddings = encoder.encode([question[:4000]] + [r[:1000] for r in requirements],
                                convert_to_numpy=True, normalize_embeddings=False,
                                show_progress_bar=False)
    weights, vector = scaled_dot_product_attention(embeddings[0], embeddings[1:])
    order = sorted(range(len(weights)), key=lambda i: (-weights[i], i))
    return {"status":"active", "type":"pretrained-transformer+scaled-dot-product",
            "model":MODEL_ID, "context_sha256":context_hash(question, requirements),
            "ranked_indices":order, "attention_weights":[round(w, 8) for w in weights],
            "embedding_dimensions":len(vector), "requirements_total":len(requirements),
            "note":"Ranking only; every check remains mandatory and source verification is unchanged."}


def focus_hint(data, max_bytes=340):
    report = data.get("attention") or {}
    if not isinstance(report, dict) or report.get("status") != "active":
        return ""
    try:
        question = data["question"]
        requirements = [c["requirement"] for c in data["checks"]]
        if report["context_sha256"] != context_hash(question, requirements):
            return ""
        order = report["ranked_indices"]
        if len(order) != len(requirements) or sorted(order) != list(range(len(requirements))):
            return ""
    except (KeyError, ValueError, TypeError):
        return ""
    # The model's weights rank attention for reminder purposes only.
    prefix = "Main task: " + question[:110] + ". Keep ALL requirements; attention highlights: "
    for i in order[:3]:
        candidate = prefix + requirements[i][:110] + "; "
        if len(candidate.encode("utf-8")) > max_bytes - 2:
            break
        prefix = candidate
    return (prefix.rstrip("; ") + ".\n") if len(prefix.encode("utf-8")) <= max_bytes else ""


def main():
    issue = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())["issue"]
    output = Path("attention-report.json")
    try:
        data = json.loads(issue["body"])
        from sentence_transformers import SentenceTransformer
        # This pretrained encoder has its own actual multi-head self-attention.
        model = SentenceTransformer(MODEL_ID, trust_remote_code=False)
        result = build_focus(data, model)
    except Exception as exc:
        result = {"status":"unavailable", "reason":type(exc).__name__,
                  "error_detail":str(exc)[:200],
                  "note":"No attention ranking was used; no heuristic substitute."}
    output.write_text(json.dumps(result, ensure_ascii=False))
    print(json.dumps({k:result[k] for k in ("status","model","reason") if k in result}))


if __name__ == "__main__":
    main()
