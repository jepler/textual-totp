<!--
SPDX-FileCopyrightText: 2023 Jeff Epler

SPDX-License-Identifier: MIT
-->

# textual-totp: TOTP (authenticator) application using Python & Textual

# Installation

Right now you have to pick this up from github, it's not yet on pypi:
`pipx install https://github.com/jepler/textual-totp@main`

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

Exit the app with Ctrl+C.

# In-memory storage of TOTPs
As long as `ttotp` is open, the TOTP secret values are stored in memory in plain text.

`ttotp` never writes secret values to operating system files or stores them in environment variables.
(but your otp-command might! check any related documentation carefully)
