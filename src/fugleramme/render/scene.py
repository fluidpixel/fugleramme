"""Scene backgrounds: a picture in place of the paper, with the spots birds sit on.

A scene is a picture under `assets/scenes/` (in the folder itself or a folder one
level down, which only groups them) with a JSON file of the same name that tags its
slots:

    {"slots": [{"x": 0.42, "y": 0.31, "span": 0.18, "kind": "tree", "depth": "background", "size": 0.8}, ...]}

`x` and `y` are where a bird's feet land, as fractions of the picture; `span` is
the most of the picture's short side a bird sitting there may take, and the optional
`size` how much of its size a bird keeps there (0.7 for a spot further back). A page fills
with the picture it is given, cropping the overflow about the middle; slots cropped
off are not used. Left to `AUTO`, it takes the picture whose shape is closest to its
own, and pictures within `ASPECT_TOLERANCE` of the closest one take turns, one per day.

Nothing is packed. A bird goes on a slot, so there are no collision masks and
no size search: `place` pairs the two and the collage draws each bird on its slot.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import NamedTuple

from PIL import Image, ImageEnhance

from ..names import KINDS, SUFFIXES

log = logging.getLogger(__name__)

# A bird's feet go a little below its slot, so a point on the very edge of a branch
# or bush has it sitting on the surface rather than hovering over it.
SINK = 0.05
SINK_MAX = 0.5
# The parts of the day a picture may be drawn for ("tree.night.png"): the frame shows
# the one for the hour, or the nearest it has. Each starts at its hour (local time);
# night runs through midnight to the first.
PERIODS = ("night", "morning", "day", "dusk")
STARTS = ((5, "morning"), (10, "day"), (16, "dusk"), (19, "night"))
AUTO = "auto"  # for `pick`: a new picture each day
FOREGROUND, BACKGROUND = "foreground", "background"
DEPTHS = (FOREGROUND, BACKGROUND)
# A bird far off is paler and greyer, as things are through air.
RECEDE_COLOR = 0.7  # of its saturation
# And by day lighter, in the haze; at night there is none and far off is darker.
RECEDE_BRIGHTNESS = {"dusk": 1.2, "night": 0.85}
RECEDE_BRIGHTNESS_DAY = 1.5
ASPECT_TOLERANCE = 0.03  # of width over height, for two pictures to count as one shape
# A bird takes a slot only if the slot is at least this much of its own size, while
# a roomier one is free: a goose does not perch on a fence post.
MIN_FIT = 0.7
SIZE_MAX = 2.0  # of a bird's own size, the most a slot may ask for


class Slot(NamedTuple):
    x: float
    y: float
    span: float
    kind: str = ""  # one of `names.KINDS`; empty takes any bird
    depth: str = FOREGROUND
    sink: float = SINK  # of a bird's height, how far its feet go below the point
    size: float = 1.0  # of the bird's size here: under 1 for a spot further back


@dataclass(frozen=True)
class Scene:
    path: Path
    size: tuple[int, int]  # of the picture itself
    slots: tuple[Slot, ...]
    ident: str  # its path under the scenes folder, without the suffix or period
    period: str = ""  # of the day it is drawn for, one of `PERIODS`; empty for any

    def _cover(self, page: tuple[int, int]) -> tuple[float, float, float]:
        """The scale that fills `page` with the picture, and the pixels cropped
        off the left and top."""
        scale = max(page[0] / self.size[0], page[1] / self.size[1])
        return (
            scale,
            (self.size[0] * scale - page[0]) / 2,
            (self.size[1] * scale - page[1]) / 2,
        )

    def background(self, page: tuple[int, int]) -> Image.Image:
        scale, left, top = self._cover(page)
        full = (round(self.size[0] * scale), round(self.size[1] * scale))
        with Image.open(self.path) as image:
            fitted = image.convert("RGB").resize(full, Image.Resampling.LANCZOS)
        box = (round(left), round(top), round(left) + page[0], round(top) + page[1])
        return fitted.crop(box)

    def slots_on(self, page: tuple[int, int], scale: float = 1.0) -> tuple[Slot, ...]:
        """The slots that land on a page of `page`, as fractions of the page, their
        spans as fractions of its short side, times `scale`."""
        fill, left, top = self._cover(page)
        short = min(page)
        seen = (
            Slot(
                (s.x * self.size[0] * fill - left) / page[0],
                (s.y * self.size[1] * fill - top) / page[1],
                s.span * scale * min(self.size) * fill / short,
                s.kind,
                s.depth,
                s.sink,
                s.size,
            )
            for s in self.slots
        )
        return tuple(s for s in seen if 0 <= s.x <= 1 and 0 <= s.y <= 1)


@dataclass(frozen=True)
class Grade:
    """How the light of a part of the day changes a bird's colour: each channel
    scaled by its factor, then its saturation and brightness."""

    channels: tuple[float, float, float]
    saturation: float = 1.0
    brightness: float = 1.0


# Measured off plates graded by eye in an editor, on a white bird that began at
# (247, 242, 231). Night (temperature -50%, brightness -33%, saturation -11%) took
# it to (226, 237, 238): the editor's brightness barely moved a white, so there is
# none here. Dusk (temperature +50%, tint +25% magenta) took it to
# (255, 233, 217), and morning (temperature +50% alone) to (254, 238, 213). Each is a
# gain per channel, which holds for a light bird; a dark one takes more of the tint
# in the editor than this gives it.
GRADES = {
    "morning": Grade(channels=(1.03, 0.975, 0.90)),
    "dusk": Grade(channels=(1.03, 0.96, 0.94)),
    "night": Grade(channels=(0.92, 0.98, 1.03), saturation=0.89),
}


def grade(bird: Image.Image, period: str) -> Image.Image:
    """The bird as the light of `period` has it. Alpha is left as it is."""
    light = GRADES.get(period)
    if light is None:
        return bird
    bands = [
        band.point([min(255, round(v * factor)) for v in range(256)])
        for band, factor in zip(bird.convert("RGB").split(), light.channels, strict=True)
    ]
    rgb = ImageEnhance.Color(Image.merge("RGB", bands)).enhance(light.saturation)
    rgb = ImageEnhance.Brightness(rgb).enhance(light.brightness)
    rgb.putalpha(bird.getchannel("A"))
    return rgb


class Perch(NamedTuple):
    """Where one bird goes, in output pixels."""

    bird: int  # position in the names given to `place`
    feet: tuple[float, float]
    span: float  # the most the bird's own length may take here
    depth: str  # of the slot
    sink: float  # of the slot


def _slots(path: Path) -> tuple[Slot, ...] | None:
    """The slots tagged beside a picture, or None if there are none worth using. A
    time-of-day variant without a file of its own shares its scene's."""
    tags = path.with_suffix(".json")
    if not tags.exists():
        tags = path.with_name(_split(path.stem)[0] + ".json")
    try:
        raw = json.loads(tags.read_text())["slots"]
        slots = tuple(
            Slot(
                float(s["x"]),
                float(s["y"]),
                float(s["span"]),
                str(s.get("kind", "")).strip().lower(),
                str(s.get("depth", FOREGROUND)).strip().lower(),
                float(s.get("sink", SINK)),
                float(s.get("size", 1.0)),
            )
            for s in raw
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.warning("%s: no usable slots (%s)", tags, exc)
        return None
    valid = all(
        0 <= s.x <= 1
        and 0 <= s.y <= 1
        and 0 < s.span <= 1
        and s.kind in ("", *KINDS)
        and s.depth in DEPTHS
        and 0 <= s.sink <= SINK_MAX
        and 0 < s.size <= SIZE_MAX
        for s in slots
    )
    return slots if slots and valid else None


def _split(stem: str) -> tuple[str, str]:
    """A picture's name and the period it is drawn for: "tree.night" -> ("tree", "night")."""
    name, _, tail = stem.rpartition(".")
    return (name, tail) if tail in PERIODS else (stem, "")


def period_at(hour: int) -> str:
    return next((name for start, name in reversed(STARTS) if hour >= start), "night")


def _pictures(scenes_dir: Path) -> list[Path]:
    """Picture files in `scenes_dir` and in the folders one level down, which only
    group them."""
    try:
        places = [scenes_dir, *sorted(d for d in scenes_dir.iterdir() if d.is_dir())]
        return [p for d in places for p in sorted(d.iterdir()) if p.suffix in SUFFIXES]
    except OSError:
        return []


@cache  # keyed on the newest file or folder, so a retagged slot shows on the next render
def _catalog(scenes_dir: Path, stamp: float) -> tuple[Scene, ...]:
    """Each usable picture, named by its path under `scenes_dir` without the suffix
    and period."""
    found = []
    for path in _pictures(scenes_dir):
        slots = _slots(path)
        if slots is None:
            continue
        name, period = _split(path.stem)
        ident = path.relative_to(scenes_dir).with_name(name).as_posix()
        with Image.open(path) as image:
            found.append(Scene(path, image.size, slots, ident, period))
    return tuple(found)


def _scenes(scenes_dir: Path) -> tuple[Scene, ...]:
    try:
        stamp = max(
            p.stat().st_mtime for p in [scenes_dir, *scenes_dir.iterdir(), *_pictures(scenes_dir)]
        )
    except (OSError, ValueError):
        return ()
    return _catalog(scenes_dir, stamp)


def names(scenes_dir: Path) -> list[str]:
    """The scenes there are to choose from, each as `pick` is asked for it."""
    return list(dict.fromkeys(s.ident for s in _scenes(scenes_dir)))


def _for_period(versions: list[Scene], period: str) -> Scene:
    """The version drawn for the period, else one for any, else the nearest in the day."""
    wanted = PERIODS.index(period)

    def away(scene: Scene) -> int:
        if not scene.period:
            return 1
        gap = abs(PERIODS.index(scene.period) - wanted)
        return 0 if gap == 0 else 1 + min(gap, len(PERIODS) - gap)

    return min(versions, key=away)


def pick(name: str, scenes_dir: Path, size: tuple[int, int], day: int, hour: int) -> Scene | None:
    """The scene for a page of `size`: None for paper (no name), the scene named,
    or - for `AUTO`, or a name that no longer matches one - the day's pick from
    them all, of the shape closest to the page's. Of a scene's versions, the one for
    the hour of the day."""
    scenes = _scenes(scenes_dir)
    if not name or not scenes:
        return None
    versions: dict[str, list[Scene]] = {}
    for scene in scenes:
        versions.setdefault(scene.ident, []).append(scene)
    if name not in versions:
        wanted = size[0] / size[1]

        def off(ident: str) -> float:
            width, height = versions[ident][0].size
            return abs(math.log(width / height / wanted))

        closest = min(off(i) for i in versions)
        fits = [i for i in versions if off(i) - closest <= ASPECT_TOLERANCE]
        name = fits[day % len(fits)]
    return _for_period(versions[name], period_at(hour))


def _preference(name: str, slot: int) -> int:
    return int.from_bytes(hashlib.blake2b(f"{name}/{slot}".encode(), digest_size=4).digest())


def suits(slot: Slot, tags: frozenset[str]) -> bool:
    """Whether a plate with these pose tags can sit on the slot. A slot of no kind
    takes any plate, and so does a plate of no tags any slot."""
    return not slot.kind or not tags or slot.kind in tags


def place(
    slots: tuple[Slot, ...],
    size: tuple[int, int],
    names: list[str],
    spans: list[float],
    tags: list[frozenset[str]],
) -> list[Perch]:
    """A slot for each bird that gets one, `spans` being each bird's own length
    at the size its mass asks for and `tags` the poses of the plate it wears.

    A bird only ever takes a slot its plate suits, so one with no such slot is
    left off, as are birds beyond the slots. Birds take their turn in name order,
    each through the suiting slots in an order of its own (a hash of its name,
    roomy slots first). A bird whose slots are all taken has the one holding
    a slot move to another it suits, if it can: a flying plate gets the flying
    slot even when a plate that sits anywhere took it first.
    """
    width, height = size
    short = min(size)

    def choices(i: int) -> list[int]:
        order = sorted(
            (s for s in range(len(slots)) if suits(slots[s], tags[i])),
            key=lambda s: _preference(names[i], s),
        )
        roomy = [s for s in order if slots[s].span * short >= MIN_FIT * spans[i]]
        rest = sorted((s for s in order if s not in roomy), key=lambda s: -slots[s].span)
        return roomy + rest

    options = [choices(i) for i in range(len(names))]
    holder: dict[int, int] = {}  # slot -> bird

    def seat(i: int, tried: set[int]) -> bool:
        for s in options[i]:
            if s not in holder:
                holder[s] = i
                return True
        for s in options[i]:
            if s in tried:
                continue
            tried.add(s)
            if seat(holder[s], tried):
                holder[s] = i
                return True
        return False

    for i in sorted(range(len(names)), key=lambda i: names[i]):
        seat(i, set())
    return [
        Perch(
            i,
            (slots[s].x * width, slots[s].y * height),
            min(spans[i], slots[s].span * short) * slots[s].size,
            slots[s].depth,
            slots[s].sink,
        )
        for s, i in sorted(holder.items(), key=lambda item: item[1])
    ]


def recede(bird: Image.Image, period: str = "") -> Image.Image:
    """The bird as it looks in the background: less saturated, and brighter in the
    haze of the day or darker at night. The enhancers work on the colour alone, as
    brightening an RGBA image would scale its alpha with it."""
    brightness = RECEDE_BRIGHTNESS.get(period, RECEDE_BRIGHTNESS_DAY)
    rgb = ImageEnhance.Color(bird.convert("RGB")).enhance(RECEDE_COLOR)
    rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
    rgb.putalpha(bird.getchannel("A"))
    return rgb
