"""Team-draft interleaving (spec §7 step 3, §9.3 online comparison).

Merges the production and challenger rankings; each pick is attributed to its
arm so clicks can be credited during the online judgment.
"""

import random
from dataclasses import dataclass

ARM_PROD = "prod"
ARM_CHALLENGER = "challenger"


@dataclass
class InterleavedItem:
    key: str
    arm: str  # 'prod'|'challenger'


def team_draft(
    prod_ranking: list[str],
    challenger_ranking: list[str],
    k: int,
    rng: random.Random | None = None,
) -> list[InterleavedItem]:
    """Classic team-draft: per round a coin flip decides which team drafts
    first; each team drafts its best not-yet-picked item."""
    rng = rng or random.Random()
    picked: set[str] = set()
    out: list[InterleavedItem] = []
    idx = {ARM_PROD: 0, ARM_CHALLENGER: 0}
    rankings = {ARM_PROD: prod_ranking, ARM_CHALLENGER: challenger_ranking}

    def draft(arm: str) -> None:
        ranking = rankings[arm]
        while idx[arm] < len(ranking) and ranking[idx[arm]] in picked:
            idx[arm] += 1
        if idx[arm] < len(ranking) and len(out) < k:
            key = ranking[idx[arm]]
            picked.add(key)
            out.append(InterleavedItem(key=key, arm=arm))

    while len(out) < k:
        exhausted = all(
            idx[a] >= len(rankings[a]) or all(x in picked for x in rankings[a][idx[a] :])
            for a in (ARM_PROD, ARM_CHALLENGER)
        )
        if exhausted:
            break
        first = ARM_PROD if rng.random() < 0.5 else ARM_CHALLENGER
        second = ARM_CHALLENGER if first == ARM_PROD else ARM_PROD
        draft(first)
        draft(second)
    return out
