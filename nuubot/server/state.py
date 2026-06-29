from __future__ import annotations

import ray

from nuubot import nuubot_setup, sweepmgr_setup
from nuubot.sweep import ensure_ray


def start_server_state(app) -> None:
    ensure_server_state(app)
    ensure_ray()


def ensure_server_state(app) -> None:
    if getattr(app.state, "sweepmgr", None) is not None:
        return
    nuubot = nuubot_setup()
    app.state.nuubot = nuubot
    app.state.sweepmgr = sweepmgr_setup(nuubot)


def stop_server_state(app) -> None:
    nuubot = getattr(app.state, "nuubot", None)
    if nuubot is not None:
        nuubot.stop()
    if ray.is_initialized():
        print("INFO:     Ray shutdown in progress.", flush=True)
        ray.shutdown()
        print("INFO:     Ray shutdown complete.", flush=True)
