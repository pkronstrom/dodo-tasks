"""Rich + simple-term-menu implementation."""

from rich.console import Console
from simple_term_menu import TerminalMenu


class RichTerminalMenu:
    """Rich + simple-term-menu implementation.

    Swap this out for your rich-live-menu library later.
    """

    def __init__(self):
        self.console = Console()

    def select(self, options: list[str], title: str = "") -> int | None:
        if not options:
            return None
        menu = TerminalMenu(options, title=title or None)
        result = menu.show()
        return result

    def multi_select(self, options: list[str], selected: list[bool], title: str = "") -> list[int]:
        if not options:
            return []
        preselected = [i for i, s in enumerate(selected) if s]
        menu = TerminalMenu(
            options,
            title=title or None,
            multi_select=True,
            preselected_entries=preselected,
            multi_select_select_on_accept=False,
        )
        result = menu.show()
        return list(result) if result else []

    def confirm(self, message: str) -> bool:
        menu = TerminalMenu(["Yes", "No"], title=message)
        return menu.show() == 0

    def input(self, prompt: str) -> str | None:
        try:
            return self.console.input(f"[bold]{prompt}[/bold] ")
        except (KeyboardInterrupt, EOFError):
            return None
