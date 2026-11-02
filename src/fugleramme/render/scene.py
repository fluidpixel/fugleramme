"""Scene backgrounds: a picture in place of the paper, with the spots birds sit on.

A scene set is a folder under `assets/scenes/` of pictures, each with a JSON file
of the same name that tags its slots:

    {"slots": [{"x": 0.42, "y": 0.31, "span": 0.18}, ...]}

`x` and `y` are where a bird's feet land, as fractions of the picture; `span` is
the most of the page's short side a bird sitting there may take. A page shows a
picture only at its own shape (`ASPECT_TOLERANCE`), so a set holds one or more
pictures per shape the kiosk is used at, and one is picked per day.

Nothing is packed. A bird goes on a slot, so there are no collision masks and
no size search: `place` pairs the two and the collage draws each bird on its slot.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import NamedTuple

from PIL import Image

from ..names import SUFFIXES

log = logging.getLogger(__name__)

ASPECT_TOLERANCE = 0.03  # of width over height, before a picture would be stretched
# A bird takes a slot only if the slot is at least this much of its own size, while
# a roomier one is free: a goose does not perch on a fence post.
MIN_FIT = 0.7


class Slot(NamedTuple):
    x: float
    y: float
    span: float


@dataclass(frozen=True)
class Scene:
    path: Path
    slots: tuple[Slot, ...]

    def background(self, size: tuple[int, int]) -> Image.Image:
        return Image.open(self.path).convert("RGB").resize(size, Image.Resampling.LANCZOS)


class Perch(NamedTuple):
    """Where one bird goes, in output pixels."""

    index: int
    feet: tuple[float, float]
    span: float  # the most the bird's own length may take here


def _slots(path: Path) -> tuple[Slot, ...] | None:
    """The slots tagged beside a picture, or None if there are none worth using."""
    tags = path.with_suffix(".json")
    try:
        raw = json.loads(tags.read_text())["slots"]
        slots = tuple(Slot(float(s["x"]), float(s["y"]), float(s["span"])) for s in raw)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.warning("%s: no usable slots (%s)", tags, exc)
        return None
    valid = all(0 <= s.x <= 1 and 0 <= s.y <= 1 and 0 < s.span <= 1 for s in slots)
    return slots if slots and valid else None


@cache  # keyed on the folder's newest file, so a retagged slot shows on the next render
def _catalog(folder: Path, stamp: float) -> tuple[tuple[Scene, float], ...]:
    """Each usable picture in the folder, with its width over height."""
    found = []
    for path in sorted(p for p in folder.iterdir() if p.suffix in SUFFIXES):
        slots = _slots(path)
        if slots is None:
            continue
        with Image.open(path) as image:
            found.append((Scene(path, slots), image.width / image.height))
    return tuple(found)


def pick(name: str, scenes_dir: Path, size: tuple[int, int], day: int) -> Scene | None:
    """The day's picture from the named set that fits a page of `size`, or None
    for no set named, or none of its pictures at this shape."""
    folder = scenes_dir / name
    if not name or not folder.is_dir():
        return None
    stamp = max((p.stat().st_mtime for p in folder.iterdir()), default=0.0)
    wanted = size[0] / size[1]
    fits = [
        s for s, aspect in _catalog(folder, stamp) if abs(aspect / wanted - 1) <= ASPECT_TOLERANCE
    ]
    return fits[day % len(fits)] if fits else None


def _preference(name: str, slot: int) -> int:
    return int.from_bytes(hashlib.blake2b(f"{name}/{slot}".encode(), digest_size=4).digest())


def place(scene: Scene, size: tuple[int, int], names: list[str], spans: list[float]) -> list[Perch]:
    """A slot for each bird that gets one, `spans` being each bird's own length
    at the size its mass asks for.

    Birds take their turn in name order, each going through the slots in an order
    of its own (a hash of its name), so a bird arriving moves only the ones after
    it in the alphabet, and never re-rolls the page. Birds beyond the slots are left off.
    """
    width, height = size
    short = min(size)
    free = list(range(len(scene.slots)))
    perches = []
    for i in sorted(range(len(names)), key=lambda i: names[i]):
        if not free:
            break
        order = sorted(free, key=lambda s: _preference(names[i], s))
        roomy = [s for s in order if scene.slots[s].span * short >= MIN_FIT * spans[i]]
        chosen = roomy[0] if roomy else max(order, key=lambda s: scene.slots[s].span)
        free.remove(chosen)
        slot = scene.slots[chosen]
        perches.append(
            Perch(i, (slot.x * width, slot.y * height), min(spans[i], slot.span * short))
        )
    return perches
