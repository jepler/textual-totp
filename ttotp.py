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

from textual.app import App
from textual.widgets import Label, Footer, ProgressBar
from textual.binding import Binding
from textual.containers import VerticalScroll

import pyperclip
import click
import pyotp
import platformdirs
import tomllib


# Copied from pyotp with the issuer mismatch check removed
def parse_uri(uri: str) -> pyotp.OTP:
    """
    Parses the provisioning URI for the OTP; works for either TOTP or HOTP.

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
    elif parsed_uri.netloc == "hotp":
        return pyotp.HOTP(secret, **otp_data)

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
    def idx(self):
        return int(self.css_class.split("-")[1])

    @property
    def css_class(self):
        for c in self.classes:
            if re.match("otp-[0-9]", c):
                return c
        return None

    @property
    def related(self, arg=""):
        return self.screen.query(f".{self.css_class}{arg}")

    def related_remove_class(self, cls):
        for widget in self.related:
            widget.remove_class(cls)

    def related_add_class(self, cls):
        for widget in self.related:
            widget.add_class(cls)

    def on_blur(self):
        self.related_remove_class("otp-focused")
        self.shown = False

    def on_focus(self):
        self.related_add_class("otp-focused")


@dataclass
class TOTPData:
    totp: pyotp.TOTP
    name_widget: Label
    value_widget: Label
    progress_widget: ProgressBar
    generation = None

    def tick(self, now):
        now = time.time()
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

    def __init__(self, tokens):
        super().__init__()
        self.tokens = tokens
        self.otp_data = {}
        self.timer = None
        self.clear_clipboard_timer = None
        self.copied = None

    def on_mount(self):
        self.timer_func()
        self.timer = self.set_interval(0.1, self.timer_func)
        self.clear_clipboard_timer = self.set_timer(
            30, self.clear_clipboard_func, pause=True
        )

    def clear_clipboard_func(self):
        if pyperclip.paste() == self.copied:
            self.notify("Clipboard cleared", title="")
            pyperclip.copy("")

    def timer_func(self):
        now = time.time()
        for otp in self.otp_data.values():
            otp.tick(now)

    def compose(self):
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

    def action_show(self):
        widget = self.focused
        otp = self.otp_data[widget.idx]
        otp.value_widget.update(otp.totp.now())

    def action_copy(self):
        widget = self.focused
        otp = self.otp_data[widget.idx]
        code = otp.totp.now()
        pyperclip.copy(code)
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
def main(config, profile):
    def config_hint():
        config.parent.mkdir(parents=True, exist_ok=True)
        print(
            f"""\
You need to create the configuration file: {config}

It's a toml file which specifies a command to run to retrieve the list of OTPs.
One way to do this is with the `pass` program from https://www.passwordstore.org/
(it keeps your secrets safe using GPG):

    otp-command = ['pass', 'totp-tokens']

You can have multiple profiles as configuration file sections:

    [work]
    otp-command = ['pass', 'totp-tokens-work']

"""
        )
        raise SystemExit(2)

    if not config.exists():
        config_hint()

    with open(config, "rb") as f:
        config_data = tomllib.load(f)

    print(config_data)

    if profile:
        config_data = config_data[profile]

    otp_command = config_data.get("otp-command")
    if otp_command is None:
        config_hint()

    c = subprocess.check_output(
        otp_command, shell=isinstance(otp_command, str), text=True
    )
    print(f"{c=!r}")

    global tokens
    tokens = []
    for row in c.strip().split("\n"):
        if row.startswith("otpauth://"):
            print(f"parsing {row=!r}")
            tokens.append(parse_uri(row))

    TTOTP(tokens).run()


if __name__ == "__main__":
    main()
