#!/usr/bin/python3

# SPDX-FileCopyrightText: 2025 Jeff Epler
# SPDX-FileCopyrightText: 2021 Will McGugan
#
# SPDX-License-Identifier: MIT

from textual.app import ComposeResult, RenderResult
from textual.widgets._progress_bar import ProgressBar, Bar
from rich.text import Text


class OneCellBar(Bar):
    """The bar portion of the tiny progress bar."""

    BARS = "▁▂▃▄▅▆▇"
    SHADES = "█▓▒░▒▓"

    DEFAULT_CSS = """
    OneCellBar {
        width: 1;
        height: 1;

        &> .bar--bar {
            color: $primary;
            background: $surface;
        }
        &> .bar--indeterminate {
            color: $error;
            background: $surface;
        }
        &> .bar--complete {
            color: $success;
            background: $surface;
        }
    }
    """

    def render(self) -> RenderResult:
        if self.percentage is None:
            return self.render_indeterminate()
        else:
            return self.render_determinate(self.percentage)

    def render_determinate(self, percentage: float) -> RenderResult:
        bar_style = (
            self.get_component_rich_style("bar--bar")
            if percentage < 1
            else self.get_component_rich_style("bar--complete")
        )
        i = self.percentage_to_index(percentage)
        return Text(self.BARS[i], style=bar_style)

    def watch_percentage(self, percentage: float | None) -> None:
        """Manage the timer that enables the indeterminate bar animation."""
        if percentage is not None:
            self.auto_refresh = None
        else:
            self.auto_refresh = 1  # every second

    def render_indeterminate(self) -> RenderResult:
        bar_style = self.get_component_rich_style("bar--indeterminate")
        phase = round(self._clock.time) % len(self.SHADES)
        i = self.SHADES[phase]
        return Text(i, style=bar_style)

    def percentage_to_index(self, percentage: float) -> int:
        p = max(0, min(1, percentage))
        i = round(p * (len(self.BARS) - 1))
        return i

    def _validate_percentage(self, percentage: float | None) -> float | None:
        if percentage is None:
            return None
        return self.percentage_to_index(percentage) / (len(self.BARS) - 1)


class TinyProgress(ProgressBar):
    def compose(self) -> ComposeResult:
        if self.show_bar:
            yield (
                OneCellBar(id="bar", clock=self._clock)
                .data_bind(ProgressBar.percentage)
                .data_bind(ProgressBar.gradient)
            )
