# Scenes

A scene set is a folder here of pictures, each with a JSON file of the same name that tags where birds sit:

    {"slots": [{"x": 0.42, "y": 0.31, "span": 0.18}]}

`x` and `y` are where a bird's feet land, as fractions of the picture. `span` is the most of the page's short side a bird there may take.

A page shows a picture only at its own shape (within 3% of width over height), so add one or more pictures per kiosk shape. One is picked per day. Birds beyond the slots are left off.

Pick a set with the `scene` setting (the folder name). Empty keeps the paper. Only a collage uses scenes.

Use pictures you have the right to use. Pictures are not shipped with the repo.
