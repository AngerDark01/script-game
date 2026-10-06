"""Deterministic, no-side-effect adapter implementations for replay tests."""

from __future__ import annotations


class StaticWindow:
    def __init__(self, foreground: bool = True) -> None:
        self.foreground = bool(foreground)

    def is_game_foreground(self) -> bool:
        return self.foreground


class StaticMemory:
    def __init__(self, positions=()) -> None:
        self.positions = tuple(positions)
        self.read_count = 0

    def read_player_positions(self):
        self.read_count += 1
        return self.positions


class RecordingGamepad:
    def __init__(self) -> None:
        self.controllers: list[int] = []
        self.commands: list[tuple[int, object]] = []

    def acquire(self, controller: int):
        self.controllers.append(int(controller))
        return self

    def submit(self, controller: int, command: object) -> None:
        self.commands.append((int(controller), command))
