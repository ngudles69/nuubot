from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

from nuubot import nuubot_setup, sweepmgr_setup
from nuubot.sweep import MAX_SWEEP_WORKERS, init_sweep_worker


def start_server_state(app) -> None:
    ensure_server_state(app)


def ensure_server_state(app) -> None:
    if getattr(app.state, "sweepmgr", None) is not None:
        return
    nuubot = nuubot_setup()
    sweep_pool = ProcessPoolExecutor(max_workers=MAX_SWEEP_WORKERS, initializer=init_sweep_worker)
    app.state.nuubot = nuubot
    app.state.sweep_pool = sweep_pool
    app.state.sweepmgr = sweepmgr_setup(nuubot, sweep_pool)


def stop_server_state(app) -> None:
    sweepmgr = getattr(app.state, "sweepmgr", None)
    if sweepmgr is not None:
        sweepmgr.shutdown()
    sweep_pool = getattr(app.state, "sweep_pool", None)
    if sweep_pool is not None:
        sweep_pool.shutdown(wait=True, cancel_futures=False)
    nuubot = getattr(app.state, "nuubot", None)
    if nuubot is not None:
        nuubot.stop()
