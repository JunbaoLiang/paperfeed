"""Materialize queued external reads (spec v1.2). Runs daily AFTER embed.py so
the feature snapshot carries real similarity features, not cold-start
fallbacks. Imports the single materialization implementation from the API
package rather than duplicating it.
"""

import sys
from datetime import UTC, datetime

from sqlalchemy import select

from packages.core.db import session_scope
from packages.core.logging import get_logger, log_event
from packages.core.models import ExternalRead, Paper

logger = get_logger("pipelines.external_reads")


def main() -> int:
    from services.api.app.recsys.external import already_recorded, materialize_external_read

    now = datetime.now(UTC)
    processed = waiting = 0
    with session_scope() as session:
        pending = session.execute(
            select(ExternalRead, Paper)
            .join(Paper, Paper.arxiv_id == ExternalRead.arxiv_id)
            .where(ExternalRead.processed_at.is_(None))
        ).all()
        for row, paper in pending:
            if paper.embedding is None:  # embed failed/skipped today; retry tomorrow
                waiting += 1
                continue
            if not already_recorded(session, paper.arxiv_id):
                materialize_external_read(session, paper, now)
            row.processed_at = now
            processed += 1
    log_event(logger, "external_reads_done", processed=processed, still_waiting=waiting)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("external_reads_failed")
        sys.exit(1)
