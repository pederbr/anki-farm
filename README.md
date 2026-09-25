# Anki Farm

An Anki add-on: every review earns a seed; merge identical plants into bigger crops.

## How to install

## Develop

The add-on lives in `anki_farm/`. It's symlinked into Anki's add-on folder:

    ln -sn "$PWD/anki_farm" ~/Library/Application\ Support/Anki2/addons21/anki_farm

Edit files in `anki_farm/` and restart Anki to load them — no build step.

- **Tests** (pure game logic, no Anki needed): `python3 -m unittest discover -s tests`
- **UI preview in a browser** (fake bridge, real game rules): `python3 dev/preview_server.py`, then open http://localhost:8777 (farm) or http://localhost:8777/decks (almanac panel).

> **Don't install a built `.ankiaddon` on your dev machine.** Anki replaces
> the symlink with a frozen copy, and your edits stop reaching Anki. If that
> happens, move `addons21/anki_farm` out of the way and re-run the `ln -sn`
> command above.

- **Package** (only for sharing / AnkiWeb):

        cd anki_farm && zip -r ../anki_farm.ankiaddon . -x '__pycache__/*' 'meta.json'