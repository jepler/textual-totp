<!--
SPDX-FileCopyrightText: 2023 Jeff Epler

SPDX-License-Identifier: MIT
-->

# textual-totp: TOTP (authenticator) application using Python & Textual

![ttotp in action](https://raw.githubusercontent.com/jepler/textual-totp/main/ttotp.png)

# Installation

You can install textual-totp with pip or pipx:
```
pipx install textual-totp
```

# Configuration

Configuration is in the form of a TOML file inside the user's standard configuration
directory. On Linux, this is `~/.config/ttotp/settings.toml`.

At startup, `ttotp` invokes a program that prints out TOTP URIs, one per line.
The author recommends storing your TOTPs in
[pass, the standard unix password manager](https://www.passwordstore.org/).
In this case, you would configure with a command like
```toml
otp-command = ['pass', 'show', 'totp-tokens']
```

If you hate security, you can use an insecure command like `cat`, or just test things with `echo`:
```toml
otp-command = "echo 'otpauth://totp/example?algorithm=SHA1&digits=6&secret=IHACDTJ2TFCSLUJLMSHYDBD74FS7OY5B'"
```

If the command is a string, it is interpreted with the shell; otherwise, the list of arguments is used directly.

# Obtaining TOTP URIs

There are a couple of ways to obtain your TOTP URIs, which are strings that begin `otpauth://totp/`.

 * Scan individual QR codes when signing up for 2FA
   * You can photograph or screen capture and then locally decode QR codes using a compatible tool such as [PyQRCode](https://pypi.org/project/PyQRCode/)
 * Scan the QR code(s) from Google Authenticator's "transfer accounts" feature. These are in the form of an "offline otpauth-migration" URL. Decode these with a compatible tool, such as [otpauth-migration-decode](https://github.com/trewlgns/otpauth-migration-decode)
   * Android does not permit this from being screenshotted, but your laptop probably has a camera
 * Transcribe the lengthy alphanumeric code that is shown during some 2FA signup processes into a complete otpauth URL, removing any whitespace that is present.

There are browser-based tools for helping with some of these tasks.
However, it is difficult to determine whether web pages treat data safely.
Therefore, none are recommended in this section.

# Using textual-totp

The command to start textual-totp is `ttotp`.
It has several options which can be shown with `ttotp --help`.

`ttotp` will first invoke the `otp-command` to get the list of TOTPs.
This may require interaction
(for instance, the `pass` command may need to request your GPG key passphrase)

Once the otp-command finishes, `ttotp` will show each available TOTP.
Each code will show as `******` until it is revealed.

Navigate up/down in several ways:
 * up and down keys
 * tab and shift-tab keys
 * "j" and "k" (vi keys)

To reveal a code, move to the desired line and press "s".
When the code expires, it will be replaced with `******` again.

Copy a code directly to the operating system's clipboard by pressing "c".
The code will be cleared from the clipboard after 30 seconds.
Your Operating System may report that `ttotp` "pasted from the clipboard".
This is because `ttotp` tries to only clear values that it set,
by checking that the current clipboard value is equal to the value it pasted earlier.

Search for a key by pressing "/" and then entering a modified case insensitive regular expression.
Press Ctrl+A to show all keys again.

In this type of regular expression, a space ` ` stands for "zero or more characters, followed by whitespace, followed by zero or more characters"; the sequence backslash-space stands for a literal space.

This makes it easy to search for e.g., "Jay Doe / example.com" by entering "ja d ex", while not requiring any sophisticated fuzzy search technology.

Due to the simple way this is implemented, a space character inside a character class does not function as expected.
Since complicated regular expressions are likely seldom used, this is not likely to be a huge limitation.

Exit the app with Ctrl+C.

# In-memory storage of TOTPs
As long as `ttotp` is open, the TOTP secret values are stored in memory in plain text.

`ttotp` never writes secret values to operating system files or stores them in environment variables.
(but your otp-command might! check any related documentation carefully)

# Development Status

I (@jepler) wrote this software because it was useful to me. It fits my needs
in its current form. I maintain it for my own needs and acting on issues and
pull requests is unlikely to be a high priority. Thank you for your understanding about this!

I develop the software on Linux, generally Debian Linux. I often make
compatibility with Debian Oldstable my goal, but this package has only been
tested on stable Debian Bookworm with Python 3.11 and almost certainly uses
constructs not in Python 3.9. Improvements for compatibility on other platforms
are welcome.

In the unlikely event that this project becomes popular, I would want to
convert it to a community-run project with multiple maintainers. There are some
issues in the tracker entered by me that seem like good directions to develop
the software in.
