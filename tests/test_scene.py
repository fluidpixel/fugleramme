import json
import os
from pathlib import Path

import pytest
from PIL import Image

from fugleramme.render.collage import copies_for, render_collage
from fugleramme.render.scene import AUTO, Scene, Slot, grade, names, period_at, pick, place, recede
from fugleramme.render.sizes import feet_of


def _set(folder: Path, name: str, size: tuple[int, int], slots: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "green").save(folder / f"{name}.png")
    (folder / f"{name}.json").write_text(json.dumps({"slots": slots}))


def test_auto_takes_the_closest_shape_and_rotates(tmp_path):
    slot = [{"x": 0.5, "y": 0.5, "span": 0.2}]
    _set(tmp_path / "s", "a", (160, 90), slot)
    _set(tmp_path / "s", "b", (160, 90), slot)
    _set(tmp_path, "tall", (90, 160), slot)
    wide = {pick(AUTO, tmp_path, (1920, 1080), d, 12).path.stem for d in range(2)}
    assert wide == {"a", "b"}
    assert pick(AUTO, tmp_path, (1080, 1920), 0, 12).path.stem == "tall"
    assert pick(AUTO, tmp_path, (1600, 1200), 0, 12).path.stem in {"a", "b"}
    assert pick("", tmp_path, (1920, 1080), 0, 12) is None
    assert pick(AUTO, tmp_path / "missing", (1920, 1080), 0, 12) is None


def test_a_named_picture_is_used_whatever_its_shape(tmp_path):
    slot = [{"x": 0.5, "y": 0.5, "span": 0.2}]
    _set(tmp_path / "s", "a", (160, 90), slot)
    _set(tmp_path, "tall", (90, 160), slot)
    assert pick("s/a", tmp_path, (1080, 1920), 0, 12).ident == "s/a"
    assert pick("tall", tmp_path, (1920, 1080), 0, 12).ident == "tall"
    assert names(tmp_path) == ["tall", "s/a"]
    # a name that has gone falls back to the day's pick
    assert pick("s/gone", tmp_path, (1920, 1080), 0, 12).ident == "s/a"


def test_untagged_picture_is_skipped(tmp_path):
    _set(tmp_path / "s", "bad", (160, 90), [{"x": 2, "y": 0.5, "span": 0.2}])
    assert pick(AUTO, tmp_path, (1920, 1080), 0, 12) is None


def test_cover_crops_and_drops_slots_off_the_page(tmp_path):
    slots = [
        {"x": 0.5, "y": 0.5, "span": 0.2},
        {"x": 0.05, "y": 0.5, "span": 0.2},
    ]
    _set(tmp_path / "s", "a", (160, 90), slots)
    scene = pick(AUTO, tmp_path, (900, 1600), 0, 12)
    assert scene.background((900, 1600)).size == (900, 1600)
    (kept,) = scene.slots_on((900, 1600))
    assert (kept.x, kept.y) == (0.5, 0.5)
    assert kept.span > 0.2


def test_place_is_stable_and_leaves_extras_off():
    slots = tuple(Slot(i / 10, 0.5, 0.2) for i in range(1, 4))
    names = ["d", "a", "c", "b"]
    spans = [100.0] * 4
    perches = place(slots, (1000, 1000), names, spans, [frozenset()] * 4)
    assert len(perches) == 3
    assert len({p.feet for p in perches}) == 3
    assert perches == place(slots, (1000, 1000), names, spans, [frozenset()] * 4)


def test_big_bird_takes_roomy_slot():
    slots = (Slot(0.1, 0.5, 0.05), Slot(0.9, 0.5, 0.4))
    (perch,) = place(slots, (1000, 1000), ["goose"], [300.0], [frozenset()])
    assert perch.feet[0] == 900


def test_bird_takes_a_slot_of_a_kind_its_plate_suits():
    slots = (Slot(0.2, 0.5, 0.2, "tree"), Slot(0.8, 0.9, 0.2, "ground"))
    for name in ("a", "b", "c", "d"):
        (perch,) = place(slots, (1000, 1000), [name], [100.0], [frozenset({"ground"})])
        assert perch.feet[0] == 800


def test_bird_with_no_slot_for_its_pose_is_left_off():
    slots = (Slot(0.2, 0.5, 0.2, "flying"),)
    assert place(slots, (1000, 1000), ["a"], [100.0], [frozenset({"ground"})]) == []


def test_an_untagged_plate_never_takes_a_flying_slot():
    slots = (Slot(0.2, 0.5, 0.2, "flying"), Slot(0.8, 0.5, 0.2, "ground"))
    tags = [frozenset(), frozenset({"flying"})]
    perches = place(slots, (1000, 1000), ["x", "y"], [100.0, 100.0], tags)
    assert {p.bird: p.feet[0] for p in perches} == {0: 800, 1: 200}
    assert place(slots[:1], (1000, 1000), ["x"], [100.0], [frozenset()]) == []


def test_unknown_slot_kind_voids_the_picture(tmp_path):
    _set(tmp_path / "s", "bad", (160, 90), [{"x": 0.5, "y": 0.5, "span": 0.2, "kind": "sky"}])
    assert pick(AUTO, tmp_path, (1920, 1080), 0, 12) is None


def test_a_background_bird_is_paler_and_greyer_with_its_edge_untouched():
    bird = Image.new("RGBA", (2, 1))
    bird.putpixel((0, 0), (200, 40, 40, 255))
    bird.putpixel((1, 0), (200, 40, 40, 90))
    far = recede(bird)
    r, g, b, _ = far.getpixel((0, 0))
    assert (r + g + b) / 3 > (200 + 40 + 40) / 3  # brighter
    assert (max(r, g, b) - min(r, g, b)) / max(r, g, b) < (200 - 40) / 200  # less saturated
    assert [far.getpixel((x, 0))[3] for x in (0, 1)] == [255, 90]


def test_a_background_bird_is_darker_at_night_and_milder_at_dusk():
    bird = Image.new("RGBA", (1, 1), (200, 40, 40, 255))
    day, dusk, night = (sum(recede(bird, p).getpixel((0, 0))[:3]) for p in ("day", "dusk", "night"))
    assert night < sum((200, 40, 40)) < dusk < day


def test_slot_depth_is_read_and_a_bad_one_voids_the_picture(tmp_path):
    _set(tmp_path / "s", "a", (160, 90), [{"x": 0.5, "y": 0.5, "span": 0.2, "depth": "background"}])
    assert pick(AUTO, tmp_path, (1920, 1080), 0, 12).slots[0].depth == "background"
    _set(tmp_path / "bad", "a", (160, 90), [{"x": 0.5, "y": 0.5, "span": 0.2, "depth": "far"}])
    assert pick(AUTO, tmp_path / "bad", (1920, 1080), 0, 12) is None


def test_slot_sink_is_read_and_carried_to_the_perch(tmp_path):
    _set(tmp_path / "s", "a", (160, 90), [{"x": 0.5, "y": 0.5, "span": 0.2, "sink": 0.12}])
    scene = pick(AUTO, tmp_path, (1920, 1080), 0, 12)
    (perch,) = place(scene.slots_on((1920, 1080)), (1920, 1080), ["a"], [100.0], [frozenset()])
    assert perch.sink == 0.12
    _set(tmp_path / "bad", "a", (160, 90), [{"x": 0.5, "y": 0.5, "span": 0.2, "sink": 0.9}])
    assert pick(AUTO, tmp_path / "bad", (1920, 1080), 0, 12) is None


def test_a_scene_shows_its_version_for_the_hour(tmp_path):
    _set(tmp_path, "tree", (160, 90), [{"x": 0.5, "y": 0.5, "span": 0.2}])
    for period in ("night", "dusk"):  # no json of their own: they share the scene's
        Image.new("RGB", (160, 90), "navy").save(tmp_path / f"tree.{period}.png")

    def at(hour: int) -> str:
        return pick("tree", tmp_path, (1920, 1080), 0, hour).path.stem

    assert [at(h) for h in (2, 17, 20)] == ["tree.night", "tree.dusk", "tree.night"]
    assert [at(h) for h in (9, 14)] == ["tree", "tree"]  # no version of its own: the plain one
    assert names(tmp_path) == ["tree"]
    assert pick(AUTO, tmp_path, (1920, 1080), 0, 18).path.stem == "tree.dusk"


def test_without_a_plain_version_the_nearest_in_the_day_stands_in(tmp_path):
    for period in ("night", "dusk"):
        _set(tmp_path, f"tree.{period}", (160, 90), [{"x": 0.5, "y": 0.5, "span": 0.2}])
    assert pick("tree", tmp_path, (1920, 1080), 0, 9).path.stem == "tree.night"
    assert pick("tree", tmp_path, (1920, 1080), 0, 15).path.stem == "tree.dusk"


def test_a_species_heard_tenfold_gets_another_bird_up_to_three():
    assert [copies_for(n) for n in (0, 1, 9, 10, 99, 100, 5000)] == [1, 1, 1, 2, 2, 3, 3]


def test_every_species_is_seated_before_anyones_second_bird():
    slots = (Slot(0.2, 0.5, 0.2), Slot(0.8, 0.5, 0.2))
    keys = ["1/a", "0/b", "0/c"]  # a's second bird is listed first, and sits out
    perches = place(slots, (1000, 1000), keys, [100.0] * 3, [frozenset()] * 3)
    assert {p.bird for p in perches} == {1, 2}


def test_dusk_warms_a_bird_and_night_cools_and_dims_it():
    bird = Image.new("RGBA", (2, 1), (200, 200, 200, 255))
    bird.putpixel((1, 0), (200, 200, 200, 90))
    for period in ("morning", "dusk"):
        r, g, b, _ = grade(bird, period).getpixel((0, 0))
        assert r > 200 > b
    assert grade(bird, "dusk").getpixel((0, 0))[1] < grade(bird, "morning").getpixel((0, 0))[1]
    r, g, b, _ = grade(bird, "night").getpixel((0, 0))
    assert b > r and r + g + b < 600
    assert [grade(bird, "night").getpixel((x, 0))[3] for x in (0, 1)] == [255, 90]
    assert grade(bird, "") is bird and grade(bird, "day") is bird


def test_scene_scale_multiplies_the_span_of_every_slot(tmp_path):
    _set(tmp_path, "a", (160, 90), [{"x": 0.5, "y": 0.5, "span": 0.2}])
    scene = pick(AUTO, tmp_path, (1920, 1080), 0, 12)
    one, one_and_a_half = (scene.slots_on((1920, 1080), f)[0].span for f in (1.0, 1.5))
    assert one_and_a_half == pytest.approx(one * 1.5)


def test_show_slots_marks_each_slot_even_with_no_birds(tmp_path):
    _set(tmp_path, "a", (160, 90), [{"x": 0.5, "y": 0.5, "span": 0.2, "kind": "tree"}])
    scene = pick(AUTO, tmp_path, (160, 90), 0, 12)
    plain = render_collage([], (160, 90), scene=scene)
    marked = render_collage([], (160, 90), scene=scene, scene_slots=True)
    assert plain.tobytes() != marked.tobytes()
    assert marked.getpixel((80, 45)) != plain.getpixel((80, 45))


def test_retagging_a_picture_in_place_is_seen_on_the_next_look(tmp_path):
    folder = tmp_path / "s"
    _set(folder, "a", (160, 90), [{"x": 0.5, "y": 0.5, "span": 0.2}])
    assert pick(AUTO, tmp_path, (160, 90), 0, 12).slots[0].x == 0.5
    tags = folder / "a.json"
    folder_time = folder.stat().st_mtime
    tags.write_text(json.dumps({"slots": [{"x": 0.25, "y": 0.5, "span": 0.2}]}))
    os.utime(tags, (folder_time + 10, folder_time + 10))  # an in-place write moves no folder
    os.utime(folder, (folder_time, folder_time))
    assert pick(AUTO, tmp_path, (160, 90), 0, 12).slots[0].x == 0.25


def test_the_day_is_cut_into_its_parts_at_the_hours_they_start():
    hours = {0: "night", 4: "night", 5: "morning", 9: "morning", 10: "day", 15: "day"}
    hours |= {16: "dusk", 18: "dusk", 19: "night", 23: "night"}
    assert {h: period_at(h) for h in hours} == hours


def test_a_plate_record_can_say_where_the_feet_stand(tmp_path):
    birds = tmp_path / "s" / "birds"
    birds.mkdir(parents=True)
    plate = birds / "x.png"
    Image.new("RGBA", (10, 40)).save(plate)
    record = {"box": [0.1, 0.0, 0.9, 0.5], "cut": [10, 40]}
    for feet, expected in (([0.5, 0.6], (0.5, 0.6)), (None, None), ([2, 0.6], None)):
        entry = record | ({"feet": feet} if feet is not None else {})
        (tmp_path / "s" / "geometry.json").write_text(json.dumps({"birds/x.png": entry}))
        assert feet_of(plate, (10, 40)) == expected
    assert feet_of(plate, (10, 50)) is None  # drawn on another crop: not to be trusted


def test_a_slot_size_scales_the_bird_on_it_and_is_checked(tmp_path):
    slots = [{"x": 0.5, "y": 0.5, "span": 0.2, "size": 0.7}]
    _set(tmp_path / "s", "a", (160, 90), slots)
    scene = pick(AUTO, tmp_path, (1920, 1080), 0, 12)
    assert scene.slots[0].size == 0.7
    (perch,) = place(scene.slots_on((1920, 1080)), (1920, 1080), ["a"], [100.0], [frozenset()])
    assert perch.span == pytest.approx(70.0)
    _set(tmp_path / "t", "a", (160, 90), [{"x": 0.5, "y": 0.5, "span": 0.2, "size": 0}])
    assert pick(AUTO, tmp_path / "t", (1920, 1080), 0, 12) is None


def test_a_bird_with_a_flying_plate_takes_the_empty_flying_slot(tmp_path):
    def plate(name: str) -> Path:
        path = tmp_path / name
        Image.new("RGBA", (40, 40), (200, 30, 30, 255)).save(path)
        return path

    perched, flying = plate("turdus-merula-1.ground.png"), plate("turdus-merula-2.flying.png")
    slots = (Slot(0.5, 0.2, 0.2, "flying"), Slot(0.5, 0.9, 0.2, "ground"))
    scene = Scene(tmp_path / "s.png", (100, 100), slots, "s")
    Image.new("RGB", (100, 100), (255, 255, 255)).save(scene.path)
    # Whichever plate the day picks, the one bird goes to the sky: it was the only
    # one that could, and the ground is left bare.
    for species in ("Turdus merula", "Parus major", "Pica pica", "Corvus corax"):
        page = render_collage(
            [(species, perched)], (100, 100), scene=scene, variants=lambda _n: [perched, flying]
        )
        assert page.getpixel((50, 15)) != (255, 255, 255), species
