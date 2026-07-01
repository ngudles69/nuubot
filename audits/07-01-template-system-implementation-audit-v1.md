# Template System Implementation Audit V1

Status: PASS after fixes.

Initial status: FAIL before fixes.

Adversarial review found four material issues:

- High: `nuubot/webgui/sweeps/create.py` still pointed at deleted `workspace/templates/ema-1h-fast.toml`.
- High: sweep runtime accepted generated configs with multiple signalers but executed only `signalers[0]`.
- Medium: `wiki/templates-bots.md` said signalers could be absent, while `BotrunConfig` required at least one.
- Medium: `wiki/templates-sweeps.md` described generated `[sweeprun]`, while code stores generated windows under `botrun.backtest`.

Disposition:

- Fixed WebGUI default template path to `workspace/templates/sweeps/emacross-tradebot-2025-halves.toml`.
- Fixed runtime guard to fail loud unless a generated sweeprun has exactly one `emacross` signaler and a `tradebot` executor.
- Fixed docs to match current runnable config requirements and generated `meta + botrun.backtest` storage.
- Kept current one-signaler runtime by design. Multi-signaler composition is a later strategy/runtime feature, not part of this proof.

Proof from adversarial review:

- `workspace/db/sweep_26.db` had `sweep.status=complete`.
- 36 generated sweepruns existed.
- 36 generated sweepruns completed.
- 0 generated sweepruns failed.
- First generated run was BTCUSDT, 1h, first half 2025, fast 5, slow 20.
- Last generated run was SOLUSDT, 1h, second half 2025, fast 11, slow 50.

Recheck:

- WebGUI default points to the active sweep template.
- Runtime fails loud unless a generated sweeprun has exactly one `emacross`
  signaler and one `tradebot` executor.
- Bot template docs match the current model requiring at least one runnable
  signaler.
- Sweep template docs describe generated `meta + botrun.backtest`.
- Sweep 26 remained complete with 36 complete sweepruns and 0 failed.
