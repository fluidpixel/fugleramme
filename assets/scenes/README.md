# Scenes

A scene is a picture here, in this folder or in a folder inside it (which only groups them), with a JSON file of the same name that tags where birds sit:

    {"slots": [{"x": 0.42, "y": 0.31, "span": 0.18, "kind": "tree"}]}

`x` and `y` are the spot a bird stands on, such as the top edge of a branch or bush, as fractions of the picture. Its feet sink a little below it, 5% of its height unless the slot gives a `sink` (0 to 0.5): a bird nestling into a bush takes more. `span` is the most of the picture's short side a bird there may take, times the `scene_scale` setting (the admin's Bird scale, 1 by default; 1.5 draws every bird half as big again). `size` is optional: how much of its size a bird keeps there, above 0 and up to 2, 1 by default. Give a spot further back in the picture a smaller one (0.75) so the bird does not look bigger than those nearer. It scales the bird itself, so a bird already under the slot's `span` shrinks too.

A page fills the screen with its picture, cropping the overflow about the middle. Slots cropped off are not used, so an odd shape has fewer places for birds. Birds beyond the slots are left off.

`kind` is optional: `tree`, `bush`, `perch`, `ground` or `flying`. A slot without one takes any bird. `depth` is optional too: `foreground` (the default) or `background`. A bird on a background slot is drawn 30% less saturated, to sit back in the picture, and by day 50% brighter in the haze (20% at dusk), or at night 15% darker (`RECEDE_BRIGHTNESS` in `scene.py`). A bird's plates say what they show in dotted tags before the suffix, so `turdus-merula-2.ground.webp` is a blackbird on the ground and `turdus-merula-3.perch.tree.webp` one on a branch. Untagged plates suit every slot except `flying` ones, which only take plates tagged `.flying`.

The bird is chosen first, then its slot. Each bird wears its plate of the day, picked from those the scene has a slot for, and only sits on a slot that plate suits. A bird with no such slot free is left off rather than put where its pose is wrong; if the slot it needs is held by a bird that could sit elsewhere, that one moves.

Plates are taken to face right, so a bird sits facing the middle of the page, turned round on the right half. A scene is the one place this is assumed: pictures of birds facing left will face away from the middle.

A scene can have a version for each part of the day, named with a tag before the suffix: `tree.morning.png` (05:00 to 10:00), `tree.day.png` (10:00 to 16:00), `tree.dusk.png` (16:00 to 19:00) and `tree.night.png` (19:00 to 05:00, local time; `STARTS` in `scene.py`), beside the plain `tree.png`. The frame shows the version for the hour. A scene without one for the hour shows its plain picture, and without that the nearest version in the day. A version with no JSON of its own uses the plain picture's slots (`tree.json`), so they only need their own if the slots move. Birds take the light of the version shown: warmer in the morning, warmer and a touch pinker at dusk, and at night cooler, a little greyer and dimmer (`GRADES` in `scene.py`, measured off plates graded in an editor). The plain picture and the day one leave them as they are. The versions are one scene: the admin lists `tree` once, and automatic rotation counts it once.

A bird with a long tail hanging below its feet, or any plate whose lowest point is not where the bird stands, is planted by its feet if the style's `geometry.json` gives them: `"feet": [x, y]` in the plate's entry, as fractions of the trimmed cut-out, beside its `box` and `cut` (`assets/artwork/custom/geometry.json`). The `box` rounds the bird's body and the near part of the tail, which is what sets its size.

Tick Show slots in the admin (the `scene_slots` setting) to draw each slot over the page: a dot where a bird stands, a circle as wide as its `span`, and its kind and `x`, `y` as the JSON has them, coloured by kind. It is for placing slots by eye.

Pick one in the admin, or with the `scene` setting: a picture's path here without the suffix (`garden/tree`), `auto` (the default, and what empty means). Automatic takes the picture whose shape is closest to the page's, and pictures of about the same shape take turns, one per day. With no pictures here the page is the paper. Only a collage uses scenes, and not with the shipped classic artwork, which is always on paper: any other style, such as `custom`, always sits its birds on a scene.

Use pictures you have the right to use. Pictures are not shipped with the repo.
