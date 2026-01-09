"""Rich + simple-term-menu implementation."""

from collections.abc import Callable
from typing import Any, Generic, TypeVar

import readchar
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from simple_term_menu import TerminalMenu

T = TypeVar("T")

# UI Constants
LIVE_REFRESH_RATE = 20
DEFAULT_PANEL_WIDTH = 80
DEFAULT_TERMINAL_HEIGHT = 24


class InteractiveList:
    """Reusable interactive list with customizable keybindings.

    Example:
        items = ["Apple", "Banana", "Cherry"]
        list_view = InteractiveList(
            items=items,
            title="Fruits",
            keybindings={
                "d": lambda ctx: ctx.items.pop(ctx.cursor),  # delete
                " ": lambda ctx: print(f"Selected: {ctx.current}"),  # action
            },
        )
        result = list_view.show()  # returns final cursor position or None if quit
    """

    def __init__(
        self,
        items: list[T],
        title: str = "",
        render_item: Callable[[T, bool], str] | None = None,
        keybindings: dict[str, Callable[["ListContext[T]"], Any]] | None = None,
        footer: str | None = None,
        width: int = DEFAULT_PANEL_WIDTH,
    ):
        """Initialize interactive list.

        Args:
            items: List of items to display.
            title: Panel title.
            render_item: Function(item, is_selected) -> str. Default shows str(item).
            keybindings: Dict mapping key chars to callbacks. Callback receives ListContext.
                         Return "quit" from callback to exit, "refresh" to update display.
            footer: Custom footer text. Default shows navigation hints.
            width: Panel width.
        """
        self.items = items
        self.title = title
        self.render_item = render_item or (lambda item, sel: f"{'>' if sel else ' '} {item}")
        self.keybindings = keybindings or {}
        self.footer = footer
        self.width = width
        self.cursor = 0
        self.scroll_offset = 0
        self.status_msg: str | None = None
        self._console = Console()

    def show(self) -> int | None:
        """Display the interactive list. Returns cursor position or None if quit."""
        term_width = self._console.width or DEFAULT_PANEL_WIDTH
        width = min(self.width, term_width - 4)  # adapt to terminal width
        height = self._console.height or DEFAULT_TERMINAL_HEIGHT
        # Panel height = height (full terminal), interior = height - 2
        # Reserve: footer+gap(2) + scroll indicators(2) + status(1) = 5
        max_items = height - 6

        def build_panel() -> Panel:
            lines: list[str] = []
            lines.append("")  # blank line before items

            if not self.items:
                lines.append("[dim]No items[/dim]")
            else:
                # Keep cursor in bounds
                self.cursor = max(0, min(self.cursor, len(self.items) - 1))
                if self.cursor < self.scroll_offset:
                    self.scroll_offset = self.cursor
                elif self.cursor >= self.scroll_offset + max_items:
                    self.scroll_offset = self.cursor - max_items + 1
                self.scroll_offset = max(0, min(self.scroll_offset, len(self.items) - 1))

                visible_end = min(self.scroll_offset + max_items, len(self.items))

                if self.scroll_offset > 0:
                    lines.append(f"[dim]  ↑ {self.scroll_offset} more[/dim]")

                for i in range(self.scroll_offset, visible_end):
                    selected = i == self.cursor
                    rendered = self.render_item(self.items[i], selected)
                    lines.append(rendered)

                if visible_end < len(self.items):
                    lines.append(f"[dim]  ↓ {len(self.items) - visible_end} more[/dim]")

            # Status line (with left margin)
            status_line = f"  {self.status_msg}" if self.status_msg else ""
            footer = self.footer or "[dim]  ↑↓/jk nav · q quit[/dim]"

            # Calculate panel height: content + blank + status + footer + borders
            min_panel_height = len(lines) + 5
            panel_height = min(min_panel_height, height)

            # Pad to fill panel if using full height
            target_lines = panel_height - 2  # interior
            while len(lines) < target_lines - 3:  # -3 for blank + status + footer
                lines.append("")

            lines.append("")  # blank line before status
            lines.append(status_line)
            lines.append(footer)
            content = "\n".join(lines)

            return Panel(
                content,
                title=f"[bold]{self.title}[/bold]" if self.title else None,
                border_style="blue",
                width=width + 4,
                height=panel_height,
            )

        self._console.clear()
        with Live(
            build_panel(), console=self._console, refresh_per_second=LIVE_REFRESH_RATE
        ) as live:
            while True:
                try:
                    key = readchar.readkey()
                except KeyboardInterrupt:
                    return None

                # Built-in navigation
                if key in (readchar.key.UP, "k"):
                    self.cursor = max(0, self.cursor - 1)
                elif key in (readchar.key.DOWN, "j"):
                    self.cursor = min(len(self.items) - 1, self.cursor + 1) if self.items else 0
                elif key == "q":
                    return None
                elif key in self.keybindings:
                    ctx = ListContext(self)
                    result = self.keybindings[key](ctx)
                    if result == "quit":
                        return self.cursor
                    self.status_msg = ctx.status_msg

                live.update(build_panel())

        return self.cursor


class ListContext(Generic[T]):
    """Context passed to keybinding callbacks."""

    def __init__(self, list_view: InteractiveList[T]):
        self._list = list_view
        self.status_msg: str | None = None

    @property
    def items(self) -> list[T]:
        return self._list.items

    @property
    def cursor(self) -> int:
        return self._list.cursor

    @cursor.setter
    def cursor(self, value: int) -> None:
        self._list.cursor = value

    @property
    def current(self) -> T | None:
        if self._list.items and 0 <= self._list.cursor < len(self._list.items):
            return self._list.items[self._list.cursor]
        return None


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
