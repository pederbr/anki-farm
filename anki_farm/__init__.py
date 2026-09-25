"""Anki Farm: earn seeds by reviewing, merge them into bigger crops."""

from __future__ import annotations

from aqt import gui_hooks, mw
from aqt.qt import QAction, QKeySequence, QMenu, qconnect

from . import deck_panel, farm_dialog, rewards


def _add_toolbar_link(links: list[str], toolbar) -> None:
    links.append(
        toolbar.create_link(
            "anki_farm", "Farm", farm_dialog.open_farm, tip="Open Anki Farm", id="anki_farm"
        )
    )


def _add_menu() -> None:
    """An "Anki Farm" menu in the menu bar (the macOS top bar), before Help."""
    menu = QMenu("Anki Farm", mw)
    items = [
        ("Open Farm", lambda: farm_dialog.open_farm(), "Ctrl+Shift+F"),
        (None, None, None),
        ("Almanac", lambda: farm_dialog.open_window("almanac"), None),
        ("Settings…", lambda: farm_dialog.open_window("settings"), None),
        ("How to Play", lambda: farm_dialog.open_window("howto"), None),
    ]
    for label, callback, shortcut in items:
        if label is None:
            menu.addSeparator()
            continue
        action = QAction(label, mw)
        # stop macOS moving "Settings…" into the Anki application menu
        action.setMenuRole(QAction.MenuRole.NoRole)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        qconnect(action.triggered, callback)
        menu.addAction(action)
    mw.form.menubar.insertMenu(mw.form.menuHelp.menuAction(), menu)


def _setup() -> None:
    mw.addonManager.setWebExports(__name__, r"web/.*\.(js|css|png|ttf)")

    _add_menu()

    gui_hooks.reviewer_did_answer_card.append(rewards.on_answer)
    gui_hooks.state_did_undo.append(rewards.on_undo)
    # reviews done on a phone arrive through sync
    gui_hooks.profile_did_open.append(rewards.catch_up)
    gui_hooks.sync_did_finish.append(rewards.catch_up)
    gui_hooks.deck_browser_will_render_content.append(deck_panel.render)
    gui_hooks.webview_did_receive_js_message.append(deck_panel.on_js_message)
    gui_hooks.top_toolbar_did_init_links.append(_add_toolbar_link)
    gui_hooks.profile_will_close.append(farm_dialog.close_if_open)


_setup()
