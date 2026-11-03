"""Smoke test da UI sem Qt instalado.

Importa todos os módulos e constrói todas as telas contra o stub em
`tests/qt_stub`. Não valida aparência -- valida que o código corre.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUB = ROOT / "tests" / "qt_stub"

try:
    import PySide6  # noqa: F401

    USING_STUB = False
except ImportError:
    sys.path.insert(0, str(STUB))
    USING_STUB = True

sys.path.insert(0, str(ROOT))

MODULES = [
    "app", "config", "locales",
    "core", "core.formats", "core.engines", "core.runner", "core.planner",
    "core.job", "core.workspace", "core.events", "core.errors", "core.stages",
    "services.paths", "services.logging_service", "services.file_service",
    "services.sound", "services.updater_service", "services.versioning",
    "ui.i18n", "ui.dialogs", "ui.worker", "ui.update_dialog", "ui.main_window",
    "ui.theme", "ui.theme.tokens", "ui.theme.qss", "ui.theme.manager",
    "ui.widgets", "ui.widgets.card", "ui.widgets.item_list", "ui.widgets.pill_nav",
    "ui.views", "ui.views.welcome_view", "ui.views.workspace_view",
    "ui.views.settings_view", "ui.views.about_view", "ui.views.troubleshoot_view",
]


class ImportTest(unittest.TestCase):
    def test_todos_os_modulos_importam(self):
        import importlib

        for name in MODULES:
            with self.subTest(module=name):
                importlib.import_module(name)

    def test_core_nao_importa_qt(self):
        """O core tem de continuar testável sem interface.

        Corre num subprocesso limpo: importar o pacote core inteiro não pode
        deixar nenhum módulo do PySide6 carregado.
        """
        import subprocess
        import textwrap

        script = textwrap.dedent(
            """
            import sys
            sys.path.insert(0, %r)
            import core, core.job, core.planner, core.stages, core.runner
            qt = [m for m in sys.modules if m.startswith("PySide6")]
            print(",".join(qt))
            """
        ) % str(ROOT)

        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "", "o core puxou Qt")


@unittest.skipUnless(USING_STUB or True, "")
class WidgetBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        from config import ConfigManager
        from services.sound import SoundManager
        from ui.i18n import Translator
        from ui.theme import ThemeManager

        cls.cfg = ConfigManager(directory=tempfile.mkdtemp())
        cls.app = QApplication.instance() or QApplication([])
        cls.t = Translator(cls.cfg)
        cls.theme = ThemeManager(cls.app, cls.cfg)
        cls.theme.apply("Preto")
        cls.sound = SoundManager(cls.cfg, directory=ROOT / "assets" / "sfx")

    def test_constroi_todas_as_telas(self):
        from ui.main_window import MainWindow
        from ui.views.about_view import AboutView
        from ui.views.settings_view import SettingsView
        from ui.views.troubleshoot_view import TroubleshootView
        from ui.views.welcome_view import WelcomeView
        from ui.views.workspace_view import WorkspaceView

        factories = {
            "workspace": lambda: WorkspaceView(self.cfg, self.t, self.sound),
            "settings": lambda: SettingsView(self.cfg, self.t, self.sound),
            "about": lambda: AboutView(self.cfg, self.t),
            "troubleshoot": lambda: TroubleshootView(self.cfg, self.t),
            "welcome": lambda: WelcomeView(self.cfg, self.t, self.theme),
            "main": lambda: MainWindow(self.cfg, self.theme, self.sound),
        }
        for name, factory in factories.items():
            with self.subTest(view=name):
                self.assertIsNotNone(factory())

    def test_todos_os_temas_aplicam(self):
        from ui.theme import available_themes

        for name in available_themes():
            with self.subTest(theme=name):
                self.assertIsNotNone(self.theme.apply(name))

    def test_troca_de_modo_e_de_idioma(self):
        from core.planner import Mode
        from ui.main_window import MainWindow

        window = MainWindow(self.cfg, self.theme, self.sound)
        for index in range(len(Mode)):
            window._on_mode_changed(index)
        for language in ("en", "pt-br"):
            self.cfg.set("language", language)
            window.retranslate()

    def test_sinais_do_job_atualizam_a_lista(self):
        from core.events import Event, ItemState, ItemStatus, JobResult, Level, Progress
        from ui.views.workspace_view import WorkspaceView

        view = WorkspaceView(self.cfg, self.t, self.sound)
        view._on_event(Event("ev_item_done", {"name": "X.zip", "output": "X.zar"}, Level.SUCCESS))
        view._on_progress(Progress(1, 4, 0.25))
        view._on_item(ItemStatus("X.zip", ItemState.RUNNING, "zar", 0.5, "compressing 50%"))
        view._on_item(ItemStatus("X.zip", ItemState.DONE))
        view._on_finished(JobResult(completed=1, total=1))

    @unittest.skipIf(USING_STUB, "the Qt stub does not simulate widget state")
    def test_pilula_repetida_volta_ao_workspace(self):
        """Opening Settings does not move the marked pill, so clicking it again has
        to go back to the mode screen.

        An exclusive QButtonGroup does not emit `toggled` when the already checked
        pill is clicked: the bar stays the same and the caller never hears about
        it. That is why ISO -> Settings -> ISO left the view stuck on Settings.
        """
        from ui.main_window import MainWindow, PAGE_SETTINGS, PAGE_WORKSPACE

        window = MainWindow(self.cfg, self.theme, self.sound)
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()

        pill_iso = window.nav._buttons[2]
        pill_iso.click()
        self.assertEqual(window.stack.currentIndex(), PAGE_WORKSPACE)

        window.btn_settings.click()
        self.assertEqual(window.stack.currentIndex(), PAGE_SETTINGS)

        # The ISO pill is still the checked one: the click is the only signal.
        self.assertEqual(window.nav.current_index(), 2)
        pill_iso.click()
        self.app.processEvents()

        self.assertEqual(
            window.stack.currentIndex(), PAGE_WORKSPACE,
            "clicking the active pill has to return to the workspace",
        )

        # And the mode is not lost on the way.
        from core.planner import Mode
        self.assertEqual(window.workspace.mode, Mode.EXTRACT_ISO)

    @unittest.skipIf(USING_STUB, "o stub Qt não simula estado dos widgets")
    def test_selecionar_todos_marca_os_checkboxes(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtTest import QTest
        from ui.views.workspace_view import WorkspaceView

        sfx_enabled = self.cfg.get_bool("sfx_enabled")
        self.addCleanup(self.cfg.set, "sfx_enabled", sfx_enabled)
        self.cfg.set("sfx_enabled", False)

        view = WorkspaceView(self.cfg, self.t, self.sound)
        view.show()
        self.app.processEvents()
        view.items.populate([Path("one.zip"), Path("two.zip")])
        self.assertEqual(view.items.checked_count(), 0)

        row = view.items.visualItemRect(view.items.item(0))
        box = view.items.delegate.check_rect(row.adjusted(4, 3, -4, -3))
        QTest.mouseClick(view.items.viewport(), Qt.MouseButton.LeftButton, pos=box.center())
        self.app.processEvents()
        self.assertEqual(view.items.checked_count(), 1)

        def checkbox_pixel(item_index):
            image = QImage(view.items.viewport().size(), QImage.Format.Format_ARGB32)
            painter = QPainter(image)
            view.items.viewport().render(painter, QPoint())
            painter.end()
            item_rect = view.items.visualItemRect(view.items.item(item_index))
            item_box = view.items.delegate.check_rect(item_rect.adjusted(4, 3, -4, -3))
            return image.pixelColor(item_box.center().x(), item_box.top() + 6).name()

        accent = view.items.delegate.tokens.accent.lower()
        self.assertEqual(checkbox_pixel(0), accent)

        view.btn_select_all.click()
        self.app.processEvents()

        self.assertEqual(view.items.checked_count(), 2)
        self.assertTrue(all(
            view.items.item(index).checkState() == Qt.CheckState.Checked
            for index in range(view.items.count())
        ))
        self.assertEqual(checkbox_pixel(0), accent)
        self.assertEqual(checkbox_pixel(1), accent)

        view.btn_select_all.click()
        self.app.processEvents()
        self.assertEqual(view.items.checked_count(), 0)
        self.assertTrue(all(
            view.items.item(index).checkState() == Qt.CheckState.Unchecked
            for index in range(view.items.count())
        ))


class LocaleTest(unittest.TestCase):
    def test_nenhuma_chave_em_falta(self):
        import locales

        for language, missing in locales.missing_keys().items():
            with self.subTest(language=language):
                self.assertEqual(missing, [], f"chaves em falta em {language}")

    def test_chaves_usadas_existem(self):
        """Cada self.t("chave") no código tem de existir no locales."""
        import re

        import locales

        pattern = re.compile(r'self\.t\(\s*["\']([a-z0-9_]+)["\']')
        known = set(locales.TRANSLATIONS["pt-br"])
        dynamic = {"stage_", "ts_", "collision_", "fmt_", "state_"}
        missing = set()

        for path in (ROOT / "ui").rglob("*.py"):
            for key in pattern.findall(path.read_text(encoding="utf-8")):
                if key not in known and not any(key.startswith(p) for p in dynamic):
                    missing.add(key)

        self.assertEqual(sorted(missing), [], "chaves usadas mas não traduzidas")


if __name__ == "__main__":
    unittest.main(verbosity=2)
