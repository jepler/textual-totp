# SPDX-FileCopyrightText: 2023 Jeff Epler
#
# SPDX-License-Identifier: MIT
from __future__ import annotations

TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import Generator, Sequence

    MatrixType = Sequence[Sequence[bool]]
    SixelMapType = dict[tuple[int, int, int, int, int, int], str]

_sixels = {
    (0, 0, 0, 0, 0, 0): " ",  # Exception
    (1, 0, 0, 0, 0, 0): "\U0001fb00",
    (0, 1, 0, 0, 0, 0): "\U0001fb01",
    (1, 1, 0, 0, 0, 0): "\U0001fb02",
    (0, 0, 1, 0, 0, 0): "\U0001fb03",
    (1, 0, 1, 0, 0, 0): "\U0001fb04",
    (0, 1, 1, 0, 0, 0): "\U0001fb05",
    (1, 1, 1, 0, 0, 0): "\U0001fb06",
    (0, 0, 0, 1, 0, 0): "\U0001fb07",
    (1, 0, 0, 1, 0, 0): "\U0001fb08",
    (0, 1, 0, 1, 0, 0): "\U0001fb09",
    (1, 1, 0, 1, 0, 0): "\U0001fb0a",
    (0, 0, 1, 1, 0, 0): "\U0001fb0b",
    (1, 0, 1, 1, 0, 0): "\U0001fb0c",
    (0, 1, 1, 1, 0, 0): "\U0001fb0d",
    (1, 1, 1, 1, 0, 0): "\U0001fb0e",
    (0, 0, 0, 0, 1, 0): "\U0001fb0f",
    (1, 0, 0, 0, 1, 0): "\U0001fb10",
    (0, 1, 0, 0, 1, 0): "\U0001fb11",
    (1, 1, 0, 0, 1, 0): "\U0001fb12",
    (0, 0, 1, 0, 1, 0): "\U0001fb13",
    (1, 0, 1, 0, 1, 0): "\u258c",  # Exception
    (0, 1, 1, 0, 1, 0): "\U0001fb14",
    (1, 1, 1, 0, 1, 0): "\U0001fb15",
    (0, 0, 0, 1, 1, 0): "\U0001fb16",
    (1, 0, 0, 1, 1, 0): "\U0001fb17",
    (0, 1, 0, 1, 1, 0): "\U0001fb18",
    (1, 1, 0, 1, 1, 0): "\U0001fb19",
    (0, 0, 1, 1, 1, 0): "\U0001fb1a",
    (1, 0, 1, 1, 1, 0): "\U0001fb1b",
    (0, 1, 1, 1, 1, 0): "\U0001fb1c",
    (1, 1, 1, 1, 1, 0): "\U0001fb1d",
    (0, 0, 0, 0, 0, 1): "\U0001fb1e",
    (1, 0, 0, 0, 0, 1): "\U0001fb1f",
    (0, 1, 0, 0, 0, 1): "\U0001fb20",
    (1, 1, 0, 0, 0, 1): "\U0001fb21",
    (0, 0, 1, 0, 0, 1): "\U0001fb22",
    (1, 0, 1, 0, 0, 1): "\U0001fb23",
    (0, 1, 1, 0, 0, 1): "\U0001fb24",
    (1, 1, 1, 0, 0, 1): "\U0001fb25",
    (0, 0, 0, 1, 0, 1): "\U0001fb26",
    (1, 0, 0, 1, 0, 1): "\U0001fb27",
    (0, 1, 0, 1, 0, 1): "\u2590",  # Exception
    (1, 1, 0, 1, 0, 1): "\U0001fb28",
    (0, 0, 1, 1, 0, 1): "\U0001fb29",
    (1, 0, 1, 1, 0, 1): "\U0001fb2a",
    (0, 1, 1, 1, 0, 1): "\U0001fb2b",
    (1, 1, 1, 1, 0, 1): "\U0001fb2c",
    (0, 0, 0, 0, 1, 1): "\U0001fb2d",
    (1, 0, 0, 0, 1, 1): "\U0001fb2e",
    (0, 1, 0, 0, 1, 1): "\U0001fb2f",
    (1, 1, 0, 0, 1, 1): "\U0001fb30",
    (0, 0, 1, 0, 1, 1): "\U0001fb31",
    (1, 0, 1, 0, 1, 1): "\U0001fb32",
    (0, 1, 1, 0, 1, 1): "\U0001fb33",
    (1, 1, 1, 0, 1, 1): "\U0001fb34",
    (0, 0, 0, 1, 1, 1): "\U0001fb35",
    (1, 0, 0, 1, 1, 1): "\U0001fb36",
    (0, 1, 0, 1, 1, 1): "\U0001fb37",
    (1, 1, 0, 1, 1, 1): "\U0001fb38",
    (0, 0, 1, 1, 1, 1): "\U0001fb39",
    (1, 0, 1, 1, 1, 1): "\U0001fb3a",
    (0, 1, 1, 1, 1, 1): "\U0001fb3b",
    (1, 1, 1, 1, 1, 1): "\u2588",  # Exception
}


def _sixel_gen(m: MatrixType, sixels: SixelMapType = _sixels) -> Generator[str]:
    n_rows = len(m)
    n_cols = len(m[0])

    def get(r: int, c: int) -> bool:
        if r >= n_rows or c >= n_cols:
            return False
        return m[r][c]

    for r in range(0, n_rows, 3):
        for c in range(0, n_cols, 2):
            sixel = (
                get(r, c),
                get(r, c + 1),
                get(r + 1, c),
                get(r + 1, c + 1),
                get(r + 2, c),
                get(r + 2, c + 1),
            )
            yield sixels[sixel]
        yield "\n"


def matrix_to_sixel(m: MatrixType) -> str:
    return "".join(_sixel_gen(m))
