from __future__ import annotations

from nuubot import nuubot_setup, sweepmgr_setup


def start_server_state(app) -> None:
    ensure_server_state(app)


def ensure_server_state(app) -> None:
    if getattr(app.state, "sweepmgr", None) is not None:
        return
    nuubot = nuubot_setup()
    app.state.nuubot = nuubot
    app.state.sweepmgr = sweepmgr_setup(nuubot)


def stop_server_state(app) -> None:
    sweepmgr = getattr(app.state, "sweepmgr", None)
    if sweepmgr is not None:
        for finalizer in sweepmgr.finalizers.values():
            finalizer.join()
    nuubot = getattr(app.state, "nuubot", None)
    if nuubot is not None:
        nuubot.stop()
