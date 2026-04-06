"""
FinBERT sentiment pipeline.

Uses ProsusAI/finbert (HuggingFace) for financial-domain sentiment.
Falls back to a keyword-based scorer if torch/transformers unavailable
or if the model cannot be downloaded (e.g., offline environment).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import NamedTuple

logger = logging.getLogger(__name__)

FINBERT_MODEL = "ProsusAI/finbert"
BATCH_SIZE = 32
MAX_LENGTH = 512


class SentimentResult(NamedTuple):
    positive: float
    negative: float
    neutral: float
    label: str          # dominant label
    confidence: float   # probability of dominant label


# ── FinBERT loader (cached at module level) ────────────────────────────────

@lru_cache(maxsize=1)
def _load_finbert():
    """Load FinBERT model and tokenizer. Raises ImportError if deps missing."""
    from transformers import pipeline as hf_pipeline  # noqa: PLC0415
    pipe = hf_pipeline(
        "text-classification",
        model=FINBERT_MODEL,
        tokenizer=FINBERT_MODEL,
        top_k=None,          # return all labels
        truncation=True,
        max_length=MAX_LENGTH,
        device=-1,           # CPU; change to 0 for CUDA
    )
    return pipe


# ── fallback keyword scorer ────────────────────────────────────────────────

_POS_WORDS = {
    "growth", "rally", "gain", "rise", "profit", "beat", "strong", "positive",
    "recovery", "bullish", "outperform", "record", "rebound", "improvement",
    "upgrade", "exceed", "surplus", "boom", "expand",
}
_NEG_WORDS = {
    "decline", "loss", "fall", "crash", "risk", "concern", "warning", "weak",
    "bearish", "underperform", "default", "bankruptcy", "crisis", "plunge",
    "slump", "recession", "inflation", "downgrade", "deficit", "debt",
}


def _keyword_sentiment(text: str) -> SentimentResult:
    words = set(text.lower().split())
    pos = len(words & _POS_WORDS)
    neg = len(words & _NEG_WORDS)
    total = pos + neg + 1  # avoid /0
    p = pos / total
    n = neg / total
    neu = 1.0 - p - n
    # normalise
    p, n, neu = p / (p + n + neu), n / (p + n + neu), neu / (p + n + neu)
    label = "positive" if p >= n and p >= neu else ("negative" if n >= p and n >= neu else "neutral")
    conf = max(p, n, neu)
    return SentimentResult(positive=round(p, 4), negative=round(n, 4),
                           neutral=round(neu, 4), label=label, confidence=round(conf, 4))


# ── public interface ───────────────────────────────────────────────────────

def score_text(text: str) -> SentimentResult:
    """Score a single text. Uses FinBERT; falls back to keyword scorer."""
    try:
        pipe = _load_finbert()
        raw: list[dict] = pipe(text[:MAX_LENGTH])[0]  # list of {label, score}
        scores = {d["label"].lower(): d["score"] for d in raw}
        pos = scores.get("positive", 0.0)
        neg = scores.get("negative", 0.0)
        neu = scores.get("neutral", 0.0)
        label = max(scores, key=scores.get)
        return SentimentResult(
            positive=round(pos, 4),
            negative=round(neg, 4),
            neutral=round(neu, 4),
            label=label,
            confidence=round(scores[label], 4),
        )
    except Exception as exc:
        logger.warning("FinBERT unavailable (%s); using keyword fallback.", exc)
        return _keyword_sentiment(text)


def score_batch(texts: list[str]) -> list[SentimentResult]:
    """Batch-score multiple texts efficiently using FinBERT."""
    if not texts:
        return []
    try:
        pipe = _load_finbert()
        truncated = [t[:MAX_LENGTH] for t in texts]
        raw_batch = pipe(truncated, batch_size=BATCH_SIZE)
        results = []
        for raw in raw_batch:
            scores = {d["label"].lower(): d["score"] for d in raw}
            pos = scores.get("positive", 0.0)
            neg = scores.get("negative", 0.0)
            neu = scores.get("neutral", 0.0)
            label = max(scores, key=scores.get)
            results.append(SentimentResult(
                positive=round(pos, 4),
                negative=round(neg, 4),
                neutral=round(neu, 4),
                label=label,
                confidence=round(scores[label], 4),
            ))
        return results
    except Exception as exc:
        logger.warning("FinBERT batch failed (%s); using keyword fallback.", exc)
        return [_keyword_sentiment(t) for t in texts]
