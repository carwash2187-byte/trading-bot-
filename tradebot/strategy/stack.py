"""Run several strategies side by side under one cycle.

Presents a group of strategies to the trading cycle as if it were a single
strategy, so nothing about the cycle, risk layer or journal has to change.

The important detail is position ownership. Each strategy sees *only* the
positions it opened, matched through the order comment stamped at entry. Get
that wrong and one strategy will happily trail, bank or close another's trade
-- and the report cards would then be measuring the wrong thing, which quietly
corrupts every benching decision the manager makes.

Positions with no owner tag are shown to nobody. A manually opened trade is not
the bot's to manage.
"""

from __future__ import annotations

import dataclasses
import logging

from .base import Action, Strategy, StrategyContext

log = logging.getLogger("tradebot.stack")


class StrategyStack(Strategy):
    """Fan one cycle out across the active strategies of a portfolio."""

    name = "stack"

    def __init__(self, manager) -> None:
        self.manager = manager
        members = list(manager.roster.values())
        if not members:
            raise ValueError("a stack needs at least one strategy")

        timeframes = {s.timeframe for s in members}
        if len(timeframes) > 1:
            # One cycle fetches one candle series. Mixed timeframes would mean
            # silently feeding a strategy bars it was never designed for, so
            # refuse rather than guess which one wins.
            raise ValueError(
                "all strategies in a stack must share a timeframe, got: "
                + ", ".join(sorted(timeframes))
            )
        self.timeframe = timeframes.pop()
        self.lookback = max(s.lookback for s in members)

    def evaluate(self, context: StrategyContext) -> list[Action]:
        actions: list[Action] = []
        for strategy in self.manager.active_strategies():
            mine = [p for p in context.open_positions if p.comment == strategy.name]
            scoped = dataclasses.replace(context, open_positions=mine)
            try:
                actions.extend(strategy.evaluate(scoped) or [])
            except Exception as err:  # noqa: BLE001 - one bad member must not
                # take the others down with it; the cycle's guard would abort
                # the whole symbol.
                log.error("strategy %s raised %s: %s", strategy.name,
                          type(err).__name__, err)
        return actions
