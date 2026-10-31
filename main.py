"""
main.py - start the app.

    python main.py                 -> open the player
    python main.py "C:\\movie.mkv"  -> open the player and play the file
                                     (this is what Windows "Open with" does)
"""

import ctypes
import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

import app_info


def make_mpv_dll_findable():
    """python-mpv searches the Windows PATH for libmpv-2.dll / mpv-2.dll / mpv-1.dll.
    Put our own folder (and a 'mpv' subfolder) at the front of PATH, so a DLL
    placed next to main.py is found."""
    here = app_info.app_folder()
    extra = [here, os.path.join(here, "mpv"), os.path.dirname(sys.executable)]
    os.environ["PATH"] = os.pathsep.join(extra) + os.pathsep + os.environ.get("PATH", "")
    # Python 3.8+ does not use PATH for DLLs that other DLLs load, so register the folders too.
    for folder in extra:
        if os.path.isdir(folder):
            os.add_dll_directory(folder)


_running_marker = None   # kept for the whole run; Windows removes it when the app exits


def main():
    global _running_marker
    # Give the app its own taskbar identity, so Windows shows our icon
    # instead of the Python icon when running from source.
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"TamimRijan.{app_info.EXE_NAME}")
        # A named "mutex" tells the uninstaller/installer that the player is running,
        # so it can close it first instead of failing to delete files that are in use.
        _running_marker = ctypes.windll.kernel32.CreateMutexW(None, False, app_info.MUTEX_NAME)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName(app_info.APP_NAME)
    app.setApplicationVersion(app_info.VERSION)
    app.setWindowIcon(QIcon(app_info.LOGO_PATH))

    make_mpv_dll_findable()
    try:
        import mpv  # noqa: F401  (only checking that libmpv can be loaded)
    except OSError:
        QMessageBox.critical(
            None, "libmpv not found",
            "The mpv library (libmpv-2.dll) could not be found.\n\n"
            "1. Download 'mpv-dev-x86_64-...7z' from\n"
            "   https://github.com/shinchiro/mpv-winbuild-cmake/releases\n"
            "2. Extract libmpv-2.dll from it.\n"
            f"3. Put it in this folder:\n   {app_info.app_folder()}\n\n"
            "See README.md for details.")
        return 1

    # Import the UI only now, because it imports mpv.
    import theme
    from settings import load_settings
    from ui import MainWindow

    settings = load_settings()
    theme.load_fonts()
    theme.apply(app, settings.theme)
    window = MainWindow(settings)
    # "System" theme: follow Windows when the user switches light/dark there.
    app.styleHints().colorSchemeChanged.connect(
        lambda _: settings.theme == "system" and window.set_theme("system"))
    window.show()

    # "Open with" from Windows passes the file path as the first argument.
    if len(sys.argv) > 1:
        window.open_file(sys.argv[1])

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
