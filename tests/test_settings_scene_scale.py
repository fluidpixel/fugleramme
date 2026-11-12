from fugleramme.settings import SCENE_SCALE_MAX, SCENE_SCALE_MIN, Settings, _coerce


def test_scene_scale_defaults_to_one_and_is_clamped_and_parsed():
    assert Settings().scene_scale == 1.0
    assert _coerce({}).scene_scale == 1.0
    assert _coerce({"scene_scale": "1.5"}).scene_scale == 1.5
    assert _coerce({"scene_scale": 99}).scene_scale == SCENE_SCALE_MAX
    assert _coerce({"scene_scale": 0}).scene_scale == SCENE_SCALE_MIN
    assert _coerce({"scene_scale": "big"}).scene_scale == 1.0


def test_scene_slots_is_off_by_default_and_parsed():
    assert Settings().scene_slots is False
    assert _coerce({}).scene_slots is False
    assert _coerce({"scene_slots": "on"}).scene_slots is True
