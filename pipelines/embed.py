"""SPECTER2 embedding (spec §6.3). The ONLY module that touches torch/adapters.

Embeds papers with embedding IS NULL: input `title + [SEP] + abstract`,
allenai/specter2_base + proximity adapter, CPU, batch 32, L2-normalized.
"""

import sys

from sqlalchemy import select

from packages.core.db import session_scope
from packages.core.logging import get_logger, log_event
from packages.core.models import Paper

BASE_MODEL = "allenai/specter2_base"
ADAPTER = "allenai/specter2"
# SPEC-GAP: spec wants 'specter2@<adapter_rev>'; the adapters lib doesn't expose
# the hub revision cleanly, so we tag with the adapter name instead.
EMBEDDING_MODEL_TAG = "specter2@proximity"
BATCH_SIZE = 32
MAX_TOKENS = 512

logger = get_logger("pipelines.embed")


def load_model():
    """Heavy imports kept local so the module is importable without torch."""
    from adapters import AutoAdapterModel
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoAdapterModel.from_pretrained(BASE_MODEL)
    model.load_adapter(ADAPTER, source="hf", load_as="proximity", set_active=True)
    # Redundant with set_active=True, but explicit. (The load-time warning
    # "no adapters activated for the forward pass" is a benign library
    # artifact — verified: forward passes run with Stack[proximity] active.)
    model.set_active_adapters("proximity")
    model.eval()
    return tokenizer, model


def embed_texts(tokenizer, model, texts: list[str]):
    import torch

    with torch.no_grad():
        inputs = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=MAX_TOKENS,
            return_tensors="pt",
        )
        output = model(**inputs)
        cls = output.last_hidden_state[:, 0, :]
        cls = torch.nn.functional.normalize(cls, p=2, dim=1)
        return cls.numpy()


def main() -> int:
    with session_scope() as session:
        pending = session.execute(
            select(Paper.arxiv_id, Paper.title, Paper.abstract).where(Paper.embedding.is_(None))
        ).all()
    log_event(logger, "embed_start", pending=len(pending))
    if not pending:
        return 0

    tokenizer, model = load_model()
    sep = tokenizer.sep_token or "[SEP]"
    done = 0
    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i : i + BATCH_SIZE]
        texts = [f"{title}{sep}{abstract}" for _, title, abstract in batch]
        vectors = embed_texts(tokenizer, model, texts)
        with session_scope() as session:
            for (arxiv_id, _, _), vec in zip(batch, vectors, strict=True):
                paper = session.get(Paper, arxiv_id)
                if paper is not None:
                    paper.embedding = vec.tolist()
                    paper.embedding_model = EMBEDDING_MODEL_TAG
        done += len(batch)
        log_event(logger, "embed_progress", done=done, total=len(pending))

    log_event(logger, "embed_done", embedded=done)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("embed_failed")
        sys.exit(1)
