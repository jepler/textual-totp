#!/usr/bin/python3

# SPDX-FileCopyrightText: 2023 Jeff Epler
#
# SPDX-License-Identifier: MIT

from dataclasses import dataclass

import time
import hashlib
import pathlib
import subprocess
from urllib.parse import parse_qsl, unquote, urlparse
import re
from typing import TYPE_CHECKING, Dict, Any, Sequence, cast

from textual.app import App, ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Footer, ProgressBar
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.css.query import DOMQuery
from textual.timer import Timer

import click
import pyotp
import platformdirs
import tomllib

# workaround for pyperclip being un-typed
if TYPE_CHECKING:
    def pyperclip_paste() -> str: ...
    def pyperclip_copy(data: str) -> None: ...
else:
    from pyperclip import paste as pyperclip_paste
    from pyperclip import copy as pyperclip_copy

from typing import TypeGuard  # use `typing_extensions` for Python 3.9 and below

def is_str_list(val: Any) -> TypeGuard[list[str]]:
    """Determines whether all objects in the list are strings"""
    if not isinstance(val, list): return False
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
    otp_data = {}  # type: Dict[str, Any]

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

    raise ValueError("Not a supported OTP type")


default_conffile = platformdirs.user_config_path("ttotp") / "settings.toml"


class TOTPLabel(Label, can_focus=True):
    BINDINGS = [
        Binding("c", "copy", "Copy code", show=True),
        Binding("s", "show", "Show code", show=True),
        Binding("up", "focus_previous", show=False),
        Binding("down", "focus_next", show=False),
    ]

    @property
    def idx(self) -> int:
        return int(self.css_class.split("-")[1])

    @property
    def css_class(self) -> str:
        for c in self.classes:
            if re.match("otp-[0-9]", c):
                return c
        raise RuntimeError("Class not found")

    @property
    def related(self, arg:str="") -> DOMQuery[Widget]:
        return self.screen.query(f".{self.css_class}{arg}")

    def related_remove_class(self, cls: str) -> None:
        for widget in self.related:
            widget.remove_class(cls)

    def related_add_class(self, cls: str) -> None:
        for widget in self.related:
            widget.add_class(cls)

    def on_blur(self) -> None:
        self.related_remove_class("otp-focused")
        self.shown = False

    def on_focus(self) -> None:
        self.related_add_class("otp-focused")


@dataclass
class TOTPData:
    totp: pyotp.TOTP
    name_widget: Label
    value_widget: Label
    progress_widget: ProgressBar
    generation = None

    def tick(self, now: float) -> None:
        generation, progress = divmod(now, self.totp.interval)
        if generation != self.generation:
            self.generation = generation
            self.value_widget.update("*" * self.totp.digits)
        self.progress_widget.progress = self.totp.interval - progress


class TTOTP(App[None]):
    CSS = """
    VerticalScroll {
        layout: grid;
        grid-size: 2;
        grid-columns: 9 1fr;
        grid-rows: 1;
    }
    .otp-focused { background: $primary-background; }
    ProgressBar { column-span: 2; }
    Bar > .bar--bar { color: $success; }
    Bar { width: 1fr; }
    """

    def __init__(self, tokens: Sequence[pyotp.TOTP]) -> None:
        super().__init__()
        self.tokens = tokens
        self.otp_data: Dict[int | pyotp.TOTP, TOTPData] = {}
        self.timer: Timer | None = None
        self.clear_clipboard_time: Timer | None = None
        self.copied = ''

    def on_mount(self) -> None:
        self.timer_func()
        self.timer = self.set_interval(0.1, self.timer_func)
        self.clear_clipboard_timer = self.set_timer(
            30, self.clear_clipboard_func, pause=True
        )

    def clear_clipboard_func(self) -> None:
        if pyperclip_paste() == self.copied:
            self.notify("Clipboard cleared", title="")
            pyperclip_copy("")

    def timer_func(self) -> None:
        now = time.time()
        for otp in self.otp_data.values():
            otp.tick(now)

    def compose(self) -> ComposeResult:
        yield Footer()
        with VerticalScroll() as v:
            v.can_focus = False
            for i, otp in enumerate(self.tokens):
                otp_name = TOTPLabel(
                    f"{otp.name} / {otp.issuer}",
                    classes=f"otp-name otp-name-{i} otp-{i}",
                    expand=True,
                )
                otp_value = Label(
                    "", classes=f"otp-value otp-value-{i} otp-{i}", expand=True
                )
                otp_progress = ProgressBar(
                    classes=f"otp-progress otp-progress-{i} otp-{i}",
                    show_percentage=False,
                    show_eta=False,
                )

                otp_progress.total = otp.interval
                otpdata = TOTPData(otp, otp_name, otp_value, otp_progress)
                self.otp_data[otp] = self.otp_data[i] = otpdata

                yield otp_value
                yield otp_name
                yield otp_progress

    def action_show(self) -> None:
        widget = self.focused
        if widget is not None:
            otp = self.otp_data[cast(TOTPLabel, widget).idx]
            otp.value_widget.update(otp.totp.now())

    def action_copy(self) -> None:
        widget = self.focused
        if widget is not None:
            otp = self.otp_data[cast(TOTPLabel, widget).idx]
            code = otp.totp.now()
            pyperclip_copy(code)
            self.copied = code
            self.clear_clipboard_timer.reset()
            self.clear_clipboard_timer.resume()

            self.notify("Code copied", title="")


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
        config_data = config_data.get(profile, None)
        if config_data is None:
            config_hint(f"The profile {profile!r} file does not exist.")

    otp_command = config_data.get("otp-command")
    if otp_command is None:
        config_hint("The otp-command value is missing.")

    if isinstance(otp_command, str) or is_str_list(otp_command):
        c = subprocess.check_output(
            otp_command, shell=isinstance(otp_command, str), text=True
        )
    else:
        config_hint("The otp-command value must be a string or list of strings.")

    tokens: list[pyotp.TOTP] = []
    for row in c.strip().split("\n"):
        if row.startswith("otpauth://"):
            tokens.append(parse_uri(row))

    if not tokens:
        config_hint("No tokens were found when running the given command.")

    TTOTP(tokens).run()


if __name__ == "__main__":
    main()
