from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# Stored timestamps are always UTC. Some databases (SQLite) hand them back without a zone, which a
# browser would then read as local time, so responses always carry an explicit offset.
UTCDateTime = Annotated[datetime, AfterValidator(_as_utc)]
