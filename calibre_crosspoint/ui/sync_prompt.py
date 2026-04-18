"""Thread-safe sync-prompt dialog for use from Calibre's device thread."""

import threading

from qt.core import QObject, pyqtSignal, pyqtSlot, Qt, QApplication

_prompter = None
_prompter_lock = threading.Lock()


class _SyncPrompter(QObject):
    _request = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._event = threading.Event()
        self._result = False
        app = QApplication.instance()
        if app is not None:
            self.moveToThread(app.thread())
        self._request.connect(self._on_request, Qt.ConnectionType.QueuedConnection)

    @pyqtSlot()
    def _on_request(self):
        from calibre.gui2 import question_dialog
        from calibre.gui2.ui import get_gui
        gui = get_gui()
        self._result = bool(gui and question_dialog(
            gui,
            'Sync Reading Progress',
            '<p>Reading progress was found on the SD card.</p>'
            '<p>Sync it to your Calibre library now?</p>',
        ))
        self._event.set()

    def prompt(self):
        self._event.clear()
        self._result = False
        self._request.emit()
        self._event.wait()
        return self._result


def ask_sync_prompt():
    """Show sync dialog; safe to call from any thread. Returns True if user chose Yes."""
    from calibre.gui2.ui import get_gui
    if get_gui() is None:
        return False  # headless / test environment

    global _prompter
    with _prompter_lock:
        if _prompter is None:
            _prompter = _SyncPrompter()
    return _prompter.prompt()
