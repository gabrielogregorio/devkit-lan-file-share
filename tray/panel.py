"""The panel window: status, on/off switch, pairing QR code, received files and keys. Imports GTK."""

import io
import subprocess
from typing import Any, Protocol

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, Gtk, Pango  # noqa: E402

from server.config_store import load_config  # noqa: E402
from server.keys import KeyRecord, KeyStore  # noqa: E402
from server.settings import SETTINGS  # noqa: E402
from tray.app_info import ICONS_DIR, NAME, OFF_ICON, ON_ICON  # noqa: E402
from tray.i18n import tr  # noqa: E402
from tray.panel_data import (  # noqa: E402
    RecentFile,
    format_moment,
    human_size,
    key_rows,
    kind_label,
    lan_ip,
    pair_url,
    recent_files,
    short_path,
)

PANEL_WIDTH = 640
PAIRING_CARD_WIDTH = 270
LOGO_SIZE = 44
KEYS_SHOWN = 6
QR_SCALE = 6
QR_BORDER = 3

PANEL_CSS = b"""
.panel { background: #0b1220; color: #eaf0f8; }
.panel label { color: #eaf0f8; }
.panel .title { font-size: 20px; font-weight: bold; }
.panel .heading { font-size: 14px; font-weight: bold; }
.panel .muted { color: #8a99af; font-size: 12px; }
.panel .card { background: #141d2e; border: 1px solid #233048; border-radius: 16px; padding: 14px; }
.panel .kind { background: #1c2a42; color: #5aa2f5; border-radius: 8px; padding: 8px 6px; font-size: 10px;
               font-weight: bold; min-width: 30px; }
.panel list { background: transparent; }
.panel list row { background: transparent; border-radius: 10px; padding: 4px; }
.panel list row:hover { background: #1c2a42; }
.panel button { background: #141d2e; background-image: none; color: #eaf0f8; border: 1px solid #233048;
                border-radius: 10px; box-shadow: none; text-shadow: none; padding: 6px 12px; }
.panel button label { color: #eaf0f8; }
.panel button:hover { background: #1c2a42; }
.panel button.primary { background-image: linear-gradient(90deg, #2f80ed, #14b8a6); border: none; }
.panel button.primary label { font-weight: bold; color: #ffffff; }
.panel .key-current { background: #123f3a; color: #5eead4; border-radius: 8px; padding: 2px 8px; font-size: 11px; }
.panel .key-old { background: #1c2a42; color: #8ab8f5; border-radius: 8px; padding: 2px 8px; font-size: 11px; }
.panel .key-revoked { background: #3a1c22; color: #f8a0a0; border-radius: 8px; padding: 2px 8px; font-size: 11px; }
.panel switch { border-radius: 14px; background-image: none; background-color: #233048; }
.panel switch:checked { background-image: linear-gradient(90deg, #2f80ed, #14b8a6); }
"""


class TrayControls(Protocol):
    on_air: bool

    def is_switched_on(self) -> bool: ...
    def set_on(self, turned_on: bool) -> None: ...
    def open_folder(self, *_: Any) -> None: ...
    def choose_folder(self, *_: Any) -> None: ...
    def change_password(self, *_: Any) -> None: ...


def load_panel_style() -> None:
    style = Gtk.CssProvider()
    style.load_from_data(PANEL_CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), style, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def make_label(text: str = "", css_class: str | None = None, wrap: bool = False) -> Gtk.Label:
    widget = Gtk.Label(label=text, xalign=0)
    widget.set_line_wrap(wrap)
    if css_class:
        widget.get_style_context().add_class(css_class)

    return widget


def make_button(text: str, action: Any, css_class: str | None = None) -> Gtk.Button:
    widget = Gtk.Button(label=text)
    widget.connect("clicked", action)
    if css_class:
        widget.get_style_context().add_class(css_class)

    return widget


def make_card(spacing: int) -> Gtk.Box:
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    card.get_style_context().add_class("card")

    return card


class Panel(Gtk.Window):
    def __init__(self, tray: TrayControls) -> None:
        super().__init__(title=NAME)
        self.tray = tray
        self.keys = KeyStore(SETTINGS.config_dir)
        self.syncing_switch = False
        self.shown_qr_url: str | None = None
        self.shown_files: list[RecentFile] | None = None
        self.shown_keys: list[KeyRecord] | None = None
        self.get_style_context().add_class("panel")
        self.set_default_size(PANEL_WIDTH, -1)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)
        self.set_icon_from_file(str(ICONS_DIR / f"{ON_ICON}.svg"))

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_border_width(20)
        self.add(root)
        root.pack_start(self._build_header(), False, False, 0)
        body = Gtk.Box(spacing=16)
        root.pack_start(body, True, True, 0)
        body.pack_start(self._build_pairing_card(), False, False, 0)
        body.pack_start(self._build_received_card(), True, True, 0)
        root.pack_start(self._build_keys_card(), False, False, 0)
        root.pack_start(self._build_actions(), False, False, 0)
        self.update()
        self.show_all()
        self.set_keep_above(True)  # GNOME opens a new window behind the focused one
        self.connect("focus-out-event", self._release_keep_above)
        self.present()

    def _release_keep_above(self, *_: Any) -> bool:
        self.set_keep_above(False)

        return False

    def _build_header(self) -> Gtk.Box:
        header = Gtk.Box(spacing=12)
        self.logo = Gtk.Image()
        header.pack_start(self.logo, False, False, 0)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        text.pack_start(make_label(NAME, "title"), False, False, 0)
        self.state_label = make_label(css_class="muted")
        text.pack_start(self.state_label, False, False, 0)
        header.pack_start(text, True, True, 0)
        self.switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.switch.connect("notify::active", self._on_switch_changed)
        header.pack_end(self.switch, False, False, 0)

        return header

    def _build_pairing_card(self) -> Gtk.Box:
        card = make_card(spacing=10)
        card.set_size_request(PAIRING_CARD_WIDTH, -1)
        self.qr_image = Gtk.Image()
        card.pack_start(self.qr_image, False, False, 0)
        self.qr_note = make_label(css_class="muted", wrap=True)
        self.qr_note.set_max_width_chars(30)
        card.pack_start(self.qr_note, False, False, 0)

        return card

    def _build_received_card(self) -> Gtk.Box:
        card = make_card(spacing=8)
        card.pack_start(make_label(tr("Received"), "heading"), False, False, 0)
        self.file_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, activate_on_single_click=True)
        self.file_rows.connect("row-activated", self._open_received_file)
        card.pack_start(self.file_rows, True, True, 0)

        return card

    def _build_keys_card(self) -> Gtk.Box:
        card = make_card(spacing=6)
        card.pack_start(make_label(tr("Keys"), "heading"), False, False, 0)
        hint = tr("Pairing makes a new key; old ones keep working until you revoke them.")
        card.pack_start(make_label(hint, "muted"), False, False, 0)
        self.key_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.pack_start(self.key_list, False, False, 0)

        return card

    def _build_actions(self) -> Gtk.Box:
        actions = Gtk.Box(spacing=8)
        self.folder_label = make_label(css_class="muted")
        self.folder_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        actions.pack_start(self.folder_label, True, True, 0)
        actions.pack_start(make_button(tr("Open folder"), self.tray.open_folder, "primary"), False, False, 0)
        actions.pack_start(make_button(tr("Change folder"), self.tray.choose_folder), False, False, 0)
        actions.pack_start(make_button(tr("Change password"), self.tray.change_password), False, False, 0)

        return actions

    def _open_received_file(self, _list_box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        subprocess.Popen(["xdg-open", row.path])

    def _on_switch_changed(self, *_: Any) -> None:
        if not self.syncing_switch:
            self.tray.set_on(self.switch.get_active())

    def _revoke(self, key_id: str) -> None:
        self.keys.revoke(key_id)
        self.update()

    def _update_keys(self, records: list[KeyRecord]) -> None:
        if records == self.shown_keys:
            return

        self.shown_keys = records
        for child in self.key_list.get_children():
            self.key_list.remove(child)
        for key_row in key_rows(records)[:KEYS_SHOWN]:
            line = Gtk.Box(spacing=10)
            badge = make_label(tr(key_row["state"]), f"key-{key_row['state']}")
            badge.set_valign(Gtk.Align.CENTER)
            line.pack_start(badge, False, False, 0)
            detail = tr("{label} · created {created} · last used {used}", label=key_row["label"],
                        created=format_moment(key_row["created"]), used=format_moment(key_row["last_used"]))
            text = make_label(f"{key_row['id']}  {detail}", "muted")
            text.set_ellipsize(Pango.EllipsizeMode.END)
            line.pack_start(text, True, True, 0)
            if key_row["state"] != "revoked":
                revoke_button = make_button(tr("Revoke"), self._revoke_action(key_row["id"]))
                line.pack_end(revoke_button, False, False, 0)
            self.key_list.pack_start(line, False, False, 0)
        self.key_list.show_all()

    def _revoke_action(self, key_id: str) -> Any:
        def revoke(_button: Gtk.Button) -> None:
            self._revoke(key_id)

        return revoke

    def _update_qr(self, url: str | None) -> None:
        if url is not None and url == self.shown_qr_url:
            return

        self.shown_qr_url = url
        if url is None:
            self.qr_image.clear()
            self.qr_image.hide()
            self.qr_note.set_text(tr("Turn it on to pair the phone"))

            return

        try:
            import segno  # python3-segno from apt, only needed here
        except ImportError:
            self.qr_note.set_text(tr("Install python3-segno to show the QR code."))

            return

        png_buffer = io.BytesIO()  # in memory: this image holds a key
        segno.make(url, error="m").save(png_buffer, kind="png", scale=QR_SCALE, border=QR_BORDER)
        loader = GdkPixbuf.PixbufLoader.new_with_type("png")
        loader.write(png_buffer.getvalue())
        loader.close()
        self.qr_image.set_from_pixbuf(loader.get_pixbuf())
        self.qr_image.show()
        self.qr_note.set_text(tr(
            "Phone not paired yet? Scan this in the app, or just open it: it finds this PC on the Wi-Fi."))

    def _build_file_row(self, recent_file: RecentFile) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.path = recent_file["path"]
        line = Gtk.Box(spacing=10)
        line.pack_start(make_label(kind_label(recent_file["name"]), "kind"), False, False, 0)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        name = make_label(recent_file["name"])
        name.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        name.set_max_width_chars(28)
        text.pack_start(name, False, False, 0)
        details = f"{human_size(recent_file['size'])} · {format_moment(recent_file['time'])}"
        text.pack_start(make_label(details, "muted"), False, False, 0)
        line.pack_start(text, True, True, 0)
        row.add(line)

        return row

    def _update_files(self, files: list[RecentFile]) -> None:
        if files == self.shown_files:
            return

        self.shown_files = files
        for row in self.file_rows.get_children():
            self.file_rows.remove(row)
        for recent_file in files:
            self.file_rows.add(self._build_file_row(recent_file))
        if not files:
            empty_row = Gtk.ListBoxRow(activatable=False, selectable=False)
            hint = tr("Nothing received yet. On the phone, tap Share and pick LAN File Share.")
            empty_row.add(make_label(hint, "muted", wrap=True))
            self.file_rows.add(empty_row)
        self.file_rows.show_all()

    def update(self) -> None:
        tray = self.tray
        self.syncing_switch = True
        self.switch.set_active(tray.is_switched_on())
        self.syncing_switch = False
        if tray.on_air:
            self.state_label.set_text(tr("On the phone: {ip}:{port}", ip=lan_ip(), port=SETTINGS.port))
        else:
            self.state_label.set_text(tr("{name}: off", name=NAME))
        icon_file = ICONS_DIR / f"{ON_ICON if tray.on_air else OFF_ICON}.svg"
        self.logo.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_size(str(icon_file), LOGO_SIZE, LOGO_SIZE))
        folder = str(load_config(SETTINGS.config_dir).target_folder)
        self.folder_label.set_text(tr("Folder: {folder}", folder=short_path(folder)))
        self._update_qr(pair_url(lan_ip()) if tray.on_air else None)
        self._update_files(recent_files(folder))
        self._update_keys(self.keys.all())
