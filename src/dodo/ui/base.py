"""UI protocol for swappable menu implementations."""

from typing import Protocol


class MenuUI(Protocol):
    """Protocol for swappable menu implementations."""

    def select(self, options: list[str], title: str = "") -> int | None:
        """Show selection menu, return index or None if cancelled."""
        ...

    def multi_select(self, options: list[str], selected: list[bool], title: str = "") -> list[int]:
        """Checkboxes, return selected indices."""
        ...

    def confirm(self, message: str) -> bool:
        """Yes/no prompt."""
        ...

    def input(self, prompt: str) -> str | None:
        """Text input, None if cancelled."""
        ...
