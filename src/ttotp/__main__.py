#!/usr/bin/python3

# SPDX-FileCopyrightText: 2023 Jeff Epler
#
# SPDX-License-Identifier: MIT

from dataclasses import dataclass, field

import time
import hashlib
import pathlib
import subprocess
from urllib.parse import parse_qsl, unquote, urlparse
import re
from typing import TYPE_CHECKING, Any, Sequence, cast

import rich.text
from textual.fuzzy import Matcher
from textual.app import App, ComposeResult
from textual.events import Key, MouseDown, MouseUp, MouseScrollDown, MouseScrollUp
from textual.widget import Widget
from textual.widgets import Label, Footer, ProgressBar, Button, Input
from textual.binding import Binding
from textual.containers import VerticalScroll, Horizontal
from textual.css.query import DOMQuery
from textual.timer import Timer

import click
import pyotp
import platformdirs
import tomllib

from typing import TypeGuard  # use `typing_extensions` for Python 3.9 and below

# workaround for pyperclip being un-typed
if TYPE_CHECKING:

    def pyperclip_paste() -> str:
        ...

    def pyperclip_copy(data: str) -> None:
        ...
else:
    from pyperclip import paste as pyperclip_paste
    from pyperclip import copy as pyperclip_copy


def is_str_list(val: Any) -> TypeGuard[list[str]]:
    """Determines whether all objects in the list are strings"""
    if not isinstance(val, list):
        return False
    return all(isinstance(x, str) for x in val)


# Copied from pyotp with the issuer mismatch check removed and HTOP support removed
def parse_uri(uri: str) -> pyotp.TOTP:
    """
    Parses the provisioning URI for the TOTP

    See also:
        https://github.com/google/google-authenticator/wiki/Key-Uri-Format

    :param uri: the hotp/totp URI to parse
    :returns: OTP object
    """

    # Secret (to be filled in later)
    secret = None

    # Data we'll parse to the correct constructor
    otp_data: dict[str, Any] = {}

    # Parse with URLlib
    parsed_uri = urlparse(unquote(uri))

    if parsed_uri.scheme != "otpauth":
        raise ValueError("Not an otpauth URI")

    # Parse issuer/accountname info
    accountinfo_parts = re.split(":|%3A", parsed_uri.path[1:], maxsplit=1)
    if len(accountinfo_parts) == 1:
        otp_data["name"] = accountinfo_parts[0]
    else:
        otp_data["issuer"] = accountinfo_parts[0]
        otp_data["name"] = accountinfo_parts[1]

    # Parse values
    for key, value in parse_qsl(parsed_uri.query):
        if key == "secret":
            secret = value
        elif key == "issuer":
            otp_data["issuer"] = value
        elif key == "algorithm":
            if value == "SHA1":
                otp_data["digest"] = hashlib.sha1
            elif value == "SHA256":
                otp_data["digest"] = hashlib.sha256
            elif value == "SHA512":
                otp_data["digest"] = hashlib.sha512
            else:
                raise ValueError(
                    "Invalid value for algorithm, must be SHA1, SHA256 or SHA512"
                )
        elif key == "digits":
            digits = int(value)
            if digits not in [6, 7, 8]:
                raise ValueError("Digits may only be 6, 7, or 8")
            otp_data["digits"] = digits
        elif key == "period":
            otp_data["interval"] = int(value)
        elif key == "counter":
            otp_data["initial_count"] = int(value)
        elif key != "image":
            raise ValueError("{} is not a valid parameter".format(key))

    if not secret:
        raise ValueError("No secret found in URI")

    # Create objects
    if parsed_uri.netloc == "totp":
        return pyotp.TOTP(secret, **otp_data)

    raise ValueError(f"Not a supported OTP type: {parsed_uri.netloc}")


default_conffile = platformdirs.user_config_path("ttotp") / "settings.toml"


class TOTPLabel(Label, can_focus=True, inherit_bindings=True):
    otp: "TOTPData"

    BINDINGS = [
        Binding("c", "app.copy", "Copy code", show=True),
        Binding("s", "app.show", "Show code", show=True),
        Binding("up", "app.focus_previous", show=False),
        Binding("down", "app.focus_next", show=False),
        Binding("k", "app.focus_previous", show=False),
        Binding("j", "app.focus_next", show=False),
    ]

    def __init__(self, otp: "TOTPData") -> None:
        self.otp = otp
        super().__init__(
            rich.text.Text(otp.name),
            classes=f"otp-name otp-name-{otp.id} otp-{otp.id}",
            expand=True,
        )

    @property
    def css_class(self) -> str:
        for c in self.classes:
            if re.match("otp-[0-9]", c):
                return c
        raise RuntimeError("Class not found")

    @property
    def related(self, arg: str = "") -> DOMQuery[Widget]:
        return self.screen.query(f".{self.css_class}{arg}")

    def related_remove_class(self, cls: str) -> None:
        for widget in self.related:
            widget.remove_class(cls)

    def related_add_class(self, cls: str) -> None:
        for widget in self.related:
            widget.add_class(cls)

    def on_blur(self) -> None:
        self.related_remove_class("otp-focused")
        self.otp.value_widget.update("*" * self.otp.totp.digits)
        self.shown = False


class SearchInput(Input, can_focus=False):
    BINDINGS = [
        Binding("up", "app.focus_previous", show=False),
        Binding("down", "app.focus_next", show=False),
        Binding("ctrl+a", "clear_search", "Show all", show=True),
        Binding("escape", "clear_search", show=True),
    ]

    def on_focus(self) -> None:
        self.placeholder = "Enter search expression"

    def on_blur(self) -> None:
        self.placeholder = "Type / to search"
        self.can_focus = False
        self.remove_class("error")


class TOTPButton(Button, can_focus=False):
    def __init__(self, otp: "TOTPData", label: str, classes: str):
        self.otp = otp
        super().__init__(label=label, classes=classes)


@dataclass
class TOTPData:
    totp: pyotp.TOTP
    generation = None
    name: str = field(init=False)
    name_widget: Label = field(init=False)
    value_widget: Label = field(init=False)
    progress_widget: ProgressBar = field(init=False)
    copy_widget: TOTPButton = field(init=False)
    show_widget: TOTPButton = field(init=False)

    @property
    def id(self) -> int:
        return id(self)

    def __post_init__(self) -> None:
        self.name = f"{self.totp.name} / {self.totp.issuer}"
        self.name_widget = TOTPLabel(self)
        self.copy_widget = TOTPButton(
            self, "🗐 ", classes=f"otp-copy otp-copy-{self.id} otp-{self.id}"
        )
        self.show_widget = TOTPButton(
            self, "👀", classes=f"otp-show otp-show-{self.id} otp-{self.id}"
        )
        self.value_widget = Label(
            "*" * self.totp.digits,
            classes=f"otp-value otp-value-{self.id} otp-{self.id}",
            expand=True,
        )
        self.progress_widget = ProgressBar(
            classes=f"otp-progress otp-progress-{self.id} otp-{self.id}",
            show_percentage=False,
            show_eta=False,
        )
        self.progress_widget.total = self.totp.interval

    def tick(self, now: float) -> None:
        generation, progress = divmod(now, self.totp.interval)
        if generation != self.generation:
            self.generation = generation
            self.value_widget.update("*" * self.totp.digits)
        self.progress_widget.progress = self.totp.interval - progress

    @property
    def widgets(self) -> Sequence[Widget]:
        return (
            self.value_widget,
            self.name_widget,
            self.progress_widget,
            self.show_widget,
            self.copy_widget,
        )


def search_preprocess(s: str) -> str:
    def replace_escape_sequence(m: re.Match[str]) -> str:
        s = m.group(0)
        if s == "\\ ":
            return " "
        if s == " ":
            return r".*\s+.*"
        return s

    return re.sub(r"\\.| |[^\\ ]+", replace_escape_sequence, s)


class TTOTP(App[None]):
    CSS = """
    VerticalScroll { min-height: 1; }
    .otp-progress { width: 12; }
    .otp-value { width: 9; }
    .otp-hidden { display: none; }
    .otp-name { text-wrap: nowrap; text-overflow: ellipsis; }
    .otp-name:focus { background: red; }
    TOTPLabel { width: 1fr; height: 1; padding: 0 1; }
    Horizontal:focus-within { background: $primary-background; }
    Bar > .bar--bar { color: $success; }
    Bar { width: 1fr; }
    Button { border: none; height: 1; width: 3; min-width: 4 }
    Horizontal { height: 1; }
    Input { border: none; height: 1; width: 1fr; }
    Input.error { background: $error; }
    """

    BINDINGS = [
        Binding("/", "search"),
        Binding("ctrl+a", "clear_search", "Show all", show=True),
    ]

    def __init__(
        self, tokens: Sequence[pyotp.TOTP], timeout: int | float | None
    ) -> None:
        super().__init__()
        self.tokens = tokens
        self.otp_data: list[TOTPData] = []
        self.timer: Timer | None = None
        self.clear_clipboard_time: Timer | None = None
        self.exit_time: Timer | None = None
        self.warn_exit_time: Timer | None = None
        self.timeout: int | float | None = timeout
        self.copied = ""

    def on_mount(self) -> None:
        self.timer_func()
        self.timer = self.set_interval(1, self.timer_func)
        self.clear_clipboard_timer = self.set_timer(
            30, self.clear_clipboard_func, pause=True
        )
        if self.timeout:
            self.exit_time = self.set_timer(self.timeout, self.action_quit)
            warn_timeout = max(self.timeout / 2, self.timeout - 10)
            self.warn_exit_time = self.set_timer(warn_timeout, self.warn_quit)

    def reset_exit_timers(self) -> None:
        if self.exit_time:
            self.exit_time.reset()
        if self.warn_exit_time:
            self.warn_exit_time.reset()

    async def on_event(self, event: Any) -> None:
        if isinstance(event, (Key, MouseDown, MouseUp, MouseScrollDown, MouseScrollUp)):
            self.reset_exit_timers()
        await super().on_event(event)

    def warn_quit(self) -> None:
        self.notify("Will exit soon due to inactivity", title="Auto-exit")

    def clear_clipboard_func(self) -> None:
        if pyperclip_paste() == self.copied:
            self.notify("Clipboard cleared", title="")
            pyperclip_copy("")

    def timer_func(self) -> None:
        now = time.time()
        for otp in self.otp_data:
            otp.tick(now)

    def compose(self) -> ComposeResult:
        yield Footer()
        with VerticalScroll() as v:
            v.can_focus = False
            for otp in self.tokens:
                data = TOTPData(otp)
                self.otp_data.append(data)
                with Horizontal():
                    yield from data.widgets
        yield SearchInput(id="search", placeholder="Type / to search")

    def action_show(self) -> None:
        widget = self.focused
        if widget is not None:
            otp = cast(TOTPLabel, widget).otp
            otp.value_widget.update(otp.totp.now())

    def action_copy(self) -> None:
        widget = self.focused
        if widget is not None:
            otp = cast(TOTPLabel, widget).otp
            code = otp.totp.now()
            pyperclip_copy(code)
            self.copied = code
            self.clear_clipboard_timer.reset()
            self.clear_clipboard_timer.resume()

            self.notify("Code copied", title="")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = cast(TOTPButton, event.button)
        self.screen.set_focus(button.otp.name_widget)
        if "otp-show" in button.classes:
            self.action_show()
        else:
            self.action_copy()

    @property
    def search(self) -> Input:
        return self.query_one(Input)

    def action_search(self) -> None:
        self.search.can_focus = True
        self.search.focus()

    def action_clear_search(self) -> None:
        self.search.clear()
        if self.focused is self.search:
            self.screen.focus_next()

    def on_input_changed(self, event: Input.Changed) -> None:
        with self.batch_update():
            needle = event.value
            if not needle:
                for otp in self.otp_data:
                    name_widget = otp.name_widget
                    parent = name_widget.parent
                    assert parent is not None
                    parent.remove_class("otp-hidden")
                    name_widget.update(rich.text.Text(otp.name))
                return

            matcher = Matcher(needle)
            for otp in self.otp_data:
                name_widget = otp.name_widget
                parent = name_widget.parent
                assert parent is not None
                score = matcher.match(otp.name)
                if score > 0:
                    highlighted = matcher.highlight(otp.name)
                    name_widget.update(highlighted)
                    parent.remove_class("otp-hidden")
                else:
                    parent.add_class("otp-hidden")

    def on_input_submitted(self, event: Input.Changed) -> None:
        self.screen.focus_next()


@click.command
@click.option(
    "--config",
    type=pathlib.Path,
    default=default_conffile,
    help="Configuration file to use",
)
@click.option(
    "--profile",
    type=str,
    default=None,
    help="Profile to use within the configuration file",
)
def main(config: pathlib.Path, profile: str) -> None:
    def config_hint(extra: str) -> None:
        config.parent.mkdir(parents=True, exist_ok=True)
        print(
            f"""\
You need to create the configuration file:
    {config}

It's a toml file which specifies a command to run to retrieve the list of OTPs.
One way to do this is with the `pass` program (https://www.passwordstore.org/)
`pass` keeps your secrets safe using GPG. Typical contents:

    otp-command = ['pass', 'totp-tokens']

By default, the otp-command in the global section is used. You can have
multiple profiles as configuration file sections, and select one with
`ttotp --profile profile-name`:

    [work]
    otp-command = ['pass', 'totp-tokens-work']

{extra}"""
        )
        raise SystemExit(2)

    if not config.exists():
        config_hint(f"The configuration file {config} does not exist.")

    with open(config, "rb") as f:
        config_data = tomllib.load(f)

    if profile:
        profile_data = config_data.get(profile, None)
        if profile_data is None:
            config_hint(f"The profile {profile!r} file does not exist.")
        config_data.update(profile_data)

    otp_command = config_data.get("otp-command")
    if otp_command is None:
        config_hint("The otp-command value is missing.")

    if isinstance(otp_command, str) or is_str_list(otp_command):
        c = subprocess.check_output(
            otp_command, shell=isinstance(otp_command, str), text=True
        )
    else:
        config_hint("The otp-command value must be a string or list of strings.")

    timeout = config_data.get("auto-exit", None)
    if timeout is not None:
        if not isinstance(timeout, (float, int)):
            config_hint("If specified, the auto-exit value must be a number.")

    tokens: list[pyotp.TOTP] = []
    for row in c.strip().split("\n"):
        if row.startswith("otpauth://"):
            tokens.append(parse_uri(row))

    if not tokens:
        config_hint("No tokens were found when running the given command.")

    TTOTP(tokens, timeout).run()


if __name__ == "__main__":
    main()
