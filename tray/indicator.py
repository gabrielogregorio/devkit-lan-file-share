"""The icon on the top bar. Imports GTK and AyatanaAppIndicator3 from apt."""

import signal
import subprocess
import warnings
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402
from gi.repository import GLib, Gtk  # noqa: E402

from server.config_store import load_config, save_config  # noqa: E402
from server.settings import APP_SLUG, SETTINGS  # noqa: E402
from tray.app_info import ICONS_DIR, LOG_PATH, NAME, OFF_ICON, ON_ICON, REPO_ROOT, SERVER_COMMAND  # noqa: E402
from tray.i18n import tr  # noqa: E402
from tray.icons import write_icons  # noqa: E402
from tray.panel import Panel, load_panel_style  # noqa: E402
from tray.panel_data import failure_note, lan_ip, last_log_line, short_path, status_text  # noqa: E402
from tray.process import belongs_to_app, notify, pids_on_port, signal_group, stop_process  # noqa: E402

TICK_MILLISECONDS = 2000
REFRESH_AFTER_TOGGLE_MILLISECONDS = 600
STOP_TIMEOUT_SECONDS = 5
EXPECTED_EXIT_CODES = (0, -signal.SIGTERM, -signal.SIGKILL)


class Tray:
    def __init__(self) -> None:
        write_icons(ICONS_DIR)
        self.server_process: subprocess.Popen[bytes] | None = None
        self.on_air = False
        self.updating_menu = False
        self.open_panel_when_on_air = False
        self.panel: Panel | None = None
        self.indicator = AppIndicator.Indicator.new(
            f"{APP_SLUG}-tray", OFF_ICON, AppIndicator.IndicatorCategory.APPLICATION_STATUS)
        self.indicator.set_icon_theme_path(str(ICONS_DIR))
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.indicator.set_title(NAME)
        self._build_menu()
        self.refresh()
        GLib.timeout_add(TICK_MILLISECONDS, self._on_tick)

    def _on_tick(self) -> bool:
        self.refresh()

        return True

    def _add_menu_item(self, menu: Gtk.Menu, text: str, action: Any) -> None:
        item = Gtk.MenuItem(label=text)
        item.connect("activate", action)
        menu.append(item)

    def _add_info_item(self, menu: Gtk.Menu) -> Gtk.MenuItem:
        item = Gtk.MenuItem(label="")
        item.set_sensitive(False)
        menu.append(item)

        return item

    def _build_menu(self) -> None:
        menu = Gtk.Menu()
        self.status_item = self._add_info_item(menu)
        self.on_item = Gtk.CheckMenuItem(label=tr("On"))
        self.on_item.connect("toggled", self._on_item_toggled)
        menu.append(self.on_item)
        self.address_item = self._add_info_item(menu)
        self._add_menu_item(menu, tr("Open panel"), self.show_panel)
        self.folder_item = self._add_info_item(menu)
        self._add_menu_item(menu, tr("Open folder"), self.open_folder)
        self._add_menu_item(menu, tr("Choose folder…"), self.choose_folder)
        self._add_menu_item(menu, tr("Change password…"), self.change_password)
        self._add_menu_item(menu, tr("View log"), self._view_log)
        menu.show_all()
        self.indicator.set_menu(menu)
        self.indicator.set_secondary_activate_target(self.on_item)  # middle click

    def _folder(self) -> str:
        return str(load_config(SETTINGS.config_dir).target_folder)

    def is_switched_on(self) -> bool:
        return bool(self.on_item.get_active())

    def open_folder(self, *_: Any) -> None:
        folder = load_config(SETTINGS.config_dir).target_folder
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["xdg-open", str(folder)])

    # the server reads the config on every request, so both changes apply without a restart
    def choose_folder(self, *_: Any) -> None:
        dialog = Gtk.FileChooserDialog(title=tr("Choose folder…"), action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons(tr("Cancel"), Gtk.ResponseType.CANCEL, tr("Choose"), Gtk.ResponseType.OK)
        load_config(SETTINGS.config_dir).target_folder.mkdir(parents=True, exist_ok=True)
        dialog.set_current_folder(self._folder())
        if dialog.run() == Gtk.ResponseType.OK:
            save_config(SETTINGS.config_dir, folder=dialog.get_filename())
        dialog.destroy()
        self.refresh()

    def change_password(self, *_: Any) -> None:
        dialog = Gtk.Dialog(title=tr("Change password…"))
        dialog.add_buttons(tr("Cancel"), Gtk.ResponseType.CANCEL, tr("Save"), Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_border_width(12)
        content.set_spacing(8)
        content.add(Gtk.Label(label=tr("New password (type the same one in the phone app):")))
        entry = Gtk.Entry()
        entry.set_activates_default(True)
        content.add(entry)
        dialog.show_all()
        if dialog.run() == Gtk.ResponseType.OK and entry.get_text():
            save_config(SETTINGS.config_dir, password=entry.get_text())
        dialog.destroy()

    def _view_log(self, *_: Any) -> None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOG_PATH.touch()
        subprocess.Popen(["xdg-open", str(LOG_PATH)])

    def _app_pids(self) -> list[int]:
        return [pid for pid in pids_on_port(SETTINGS.port) if belongs_to_app(pid)]

    def _report_early_exit(self) -> None:
        process = self.server_process
        if process is None or process.poll() is None:
            return

        exit_code = process.returncode
        self.server_process = None
        if exit_code not in EXPECTED_EXIT_CODES and not self.on_air:
            notify(tr("{name} did not start", name=NAME), failure_note(exit_code, last_log_line()))

    def _server_is_running(self) -> bool:
        return self.server_process is not None and self.server_process.poll() is None

    def refresh(self) -> None:
        self._report_early_exit()
        running = self._server_is_running()
        self.on_air = bool(self._app_pids())
        starting = running and not self.on_air
        text = status_text(self.on_air, starting)
        self.status_item.set_label(text)
        self.indicator.set_icon_full(ON_ICON if self.on_air else OFF_ICON, text)
        self.indicator.set_title(text)
        self.updating_menu = True  # set_active fires "toggled"
        self.on_item.set_active(self.on_air or starting)
        self.updating_menu = False
        self.folder_item.set_label(tr("Folder: {folder}", folder=short_path(self._folder())))
        address_text = "On the phone: {ip}:{port}" if self.on_air else "Address: {ip}:{port}"
        self.address_item.set_label(tr(address_text, ip=lan_ip(), port=SETTINGS.port))
        if self.on_air and self.open_panel_when_on_air:
            self.open_panel_when_on_air = False
            self.show_panel()
        elif self.panel:
            self.panel.update()
        if not running and not self.on_air:
            self.open_panel_when_on_air = False

    def show_panel(self, *_: Any) -> None:
        if self.panel:
            self.panel.update()
            self.panel.present()

            return

        self.panel = Panel(self)
        self.panel.connect("destroy", self._forget_panel)

    def _forget_panel(self, *_: Any) -> None:
        self.panel = None

    def set_on(self, turned_on: bool) -> None:
        if turned_on:
            self.start()
        else:
            self.stop()
        GLib.timeout_add(REFRESH_AFTER_TOGGLE_MILLISECONDS, self._refresh_once)

    def _refresh_once(self) -> bool:
        self.refresh()

        return False

    def _on_item_toggled(self, item: Gtk.CheckMenuItem) -> None:
        if not self.updating_menu:
            self.set_on(item.get_active())

    def start(self) -> None:
        if self.on_air or self._server_is_running():
            return

        SETTINGS.cache_dir.mkdir(parents=True, exist_ok=True)
        self.open_panel_when_on_air = True
        with open(LOG_PATH, "w", encoding="utf-8") as log_file:
            self.server_process = subprocess.Popen(
                SERVER_COMMAND, cwd=REPO_ROOT, stdin=subprocess.DEVNULL, stdout=log_file,
                stderr=subprocess.STDOUT, start_new_session=True)  # own group: stopping it takes the children

    def stop(self) -> None:
        self.open_panel_when_on_air = False
        process = self.server_process
        if process is not None and process.poll() is None:
            signal_group(process.pid)
            try:
                process.wait(STOP_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                signal_group(process.pid, signal.SIGKILL)
            self.server_process = None
        for pid in self._app_pids():  # started from a terminal: bring down whoever listens on the port
            stop_process(pid)

    def quit(self) -> bool:
        if self._server_is_running():
            self.stop()
        Gtk.main_quit()

        return False


def run_icon(open_panel: bool) -> None:
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    load_panel_style()
    tray = Tray()
    if open_panel:
        GLib.idle_add(tray.show_panel)
    for signal_number in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal_number, tray.quit)
    Gtk.main()
