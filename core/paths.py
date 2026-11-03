"""Path limits that matter when writing to disk.

The 260-character limit is a Windows one (MAX_PATH). The engines the app launches
-- extract-xiso, chdman, 7-Zip, PkgTool -- are binaries that do not declare
`longPathAware` in their manifest, so the `LongPathsEnabled` registry key does
not help them: even when it is 1, they still fail above 260.

The app cannot know in advance how much the internal structure of a package will
take: that is decided by whoever packed it and can only be seen by reading it --
which is exactly what the core leaves to the engines. What it does control is the
prefix it builds itself, so the check is on that prefix: if it does not leave the
minimum room to write inside, the stage stops before it starts, instead of writing
half of an 8 GB image and failing with a loose engine code.

Changing `MIN_NAME_DEPTH`, choosing a shorter root, or warning instead of failing
is a one-line change here.
"""

from __future__ import annotations

import os

from core.errors import PathTooLong

MAX_PATH = 260

# Minimum room needed for the internal names. An XDVDFS directory record accepts
# names up to 424 bytes; in real Scene dumps the deepest internal path is usually
# around 90, so 100 is the room a stage can work with without surprises.
MIN_NAME_DEPTH = 100


def name_depth(path) -> int:
    """How much room is left for what the engine will write inside `path`."""
    return MAX_PATH - len(str(path))


def fits(path, depth: int | None = None, *, windows: bool | None = None) -> bool:
    """Whether `path` plus the internal structure fits the Windows limit.

    `windows` can be forced in the tests; by default it only applies where the
    limit really exists.
    """
    limit_on = (os.name == "nt") if windows is None else windows
    if not limit_on:
        return True
    needed = depth if depth is not None else MIN_NAME_DEPTH
    return len(str(path)) + needed <= MAX_PATH


def ensure_fits(path, depth: int | None = None, *, windows: bool | None = None) -> None:
    """Raise `PathTooLong` when the path does not fit."""
    if not fits(path, depth, windows=windows):
        raise PathTooLong(
            str(path),
            depth=depth if depth is not None else MIN_NAME_DEPTH,
            limit=MAX_PATH,
            left=name_depth(path),
        )
