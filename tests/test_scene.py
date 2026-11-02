import json
from pathlib import Path

from PIL import Image

from fugleramme.render.scene import Scene, Slot, pick, place


def _set(folder: Path, name: str, size: tuple[int, int], slots: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "green").save(folder / f"{name}.png")
    (folder / f"{name}.json").write_text(json.dumps({"slots": slots}))


def test_pick_matches_shape_and_rotates(tmp_path):
    slot = [{"x": 0.5, "y": 0.5, "span": 0.2}]
    _set(tmp_path / "s", "a", (160, 90), slot)
    _set(tmp_path / "s", "b", (160, 90), slot)
    _set(tmp_path / "s", "tall", (90, 160), slot)
    wide = {pick("s", tmp_path, (1920, 1080), d).path.stem for d in range(2)}
    assert wide == {"a", "b"}
    assert pick("s", tmp_path, (1080, 1920), 0).path.stem == "tall"
    assert pick("s", tmp_path, (1600, 1200), 0) is None
    assert pick("", tmp_path, (1920, 1080), 0) is None
    assert pick("missing", tmp_path, (1920, 1080), 0) is None


def test_untagged_picture_is_skipped(tmp_path):
    _set(tmp_path / "s", "bad", (160, 90), [{"x": 2, "y": 0.5, "span": 0.2}])
    assert pick("s", tmp_path, (1920, 1080), 0) is None


def test_place_is_stable_and_leaves_extras_off():
    scene = Scene(Path("x.png"), tuple(Slot(i / 10, 0.5, 0.2) for i in range(1, 4)))
    names = ["d", "a", "c", "b"]
    spans = [100.0] * 4
    perches = place(scene, (1000, 1000), names, spans)
    assert len(perches) == 3
    assert len({p.feet for p in perches}) == 3
    assert perches == place(scene, (1000, 1000), names, spans)


def test_big_bird_takes_roomy_slot():
    scene = Scene(Path("x.png"), (Slot(0.1, 0.5, 0.05), Slot(0.9, 0.5, 0.4)))
    (perch,) = place(scene, (1000, 1000), ["goose"], [300.0])
    assert perch.feet[0] == 900
