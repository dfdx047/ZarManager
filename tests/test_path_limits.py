"""The Windows path limit is checked before anything is written.

A stage that writes a tree cannot know in advance what the engine will write
inside it; what it can guarantee is that the prefix the app builds leaves enough
room. These tests cover that calculation, the error that translates it, and the
moment the stage raises it.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import locales
from core import paths
from core.errors import PathTooLong
from core.formats import Fmt
from core.stages.base import Artifact, StageContext
from core.stages.xiso import XisoExtract


class PathBudgetTest(unittest.TestCase):
    def test_the_room_left_for_the_internal_names(self) -> None:
        prefix = (
            r"C:\Roms\.zarmanager-work\20261103-161759"
            r"\Dark_Messiah_-_Might_and_Magic_-_Elements_USA_Europe_En_Fr_E"
            r"\Dark Messiah - Might and Magic - Elements (USA, Europe) (En,Fr,Es,It)_xiso"
        )
        # The real case: the prefix the app builds leaves 84 characters and the
        # deepest internal path in the ISO takes 92, so it does not fit.
        self.assertEqual(paths.name_depth(prefix), 84)
        self.assertGreater(len(prefix), paths.MAX_PATH - paths.MIN_NAME_DEPTH)
        self.assertFalse(paths.fits(prefix, depth=92, windows=True))
        self.assertTrue(paths.fits(prefix, depth=60, windows=True))
        self.assertFalse(paths.fits(prefix, depth=paths.MIN_NAME_DEPTH, windows=True))
        # Outside Windows the limit does not exist: the same path is acceptable.
        self.assertTrue(paths.fits(prefix, depth=paths.MIN_NAME_DEPTH, windows=False))

    def test_the_error_names_the_path_and_whats_missing(self) -> None:
        long = "z" * 200
        with self.assertRaises(PathTooLong) as caught:
            paths.ensure_fits(long, depth=100, windows=True)

        error = caught.exception
        self.assertEqual(error.key, "err_path_too_long")
        self.assertEqual(error.args_dict["path"], long)
        self.assertEqual(error.args_dict["depth"], 100)
        self.assertEqual(error.args_dict["limit"], paths.MAX_PATH)
        self.assertEqual(error.args_dict["left"], paths.MAX_PATH - len(long))

    def test_the_stage_checks_before_creating_anything(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="zar-limit-"))
        ctx = StageContext(base_name="game", work_dir=base, target_dir=base,
                           runner=None, resolver=None)
        stage = XisoExtract()
        artifact = Artifact(base / "game.iso", Fmt.XISO)

        calls: list[Path] = []

        def fake(path, depth=None, *, windows=None):
            calls.append(Path(str(path)))
            raise PathTooLong(
                str(path),
                depth=depth or paths.MIN_NAME_DEPTH,
                limit=paths.MAX_PATH,
                left=paths.name_depth(path),
            )

        with patch.object(paths, "ensure_fits", fake):
            with self.assertRaises(PathTooLong):
                stage.prepare_output(artifact, ctx)

        self.assertEqual(calls, [ctx.temp_path("_xiso")])
        self.assertFalse((base / "game_xiso").exists())      # nothing was created

    def test_the_key_exists_in_every_table(self) -> None:
        for language, table in locales.TRANSLATIONS.items():
            self.assertIn("err_path_too_long", table)


if __name__ == "__main__":
    unittest.main()
