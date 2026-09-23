# Anki Farm

An Anki add-on: every review earns a seed; merge identical plants into bigger crops. See [PLAN.md](PLAN.md) for the design.

## Develop

The add-on lives in `anki_farm/`. It's symlinked into Anki's add-on folder:

    ln -sn "$PWD/anki_farm" ~/Library/Application\ Support/Anki2/addons21/anki_farm

Restart Anki after changing Python code.

- **Tests** (pure game logic, no Anki needed): `python3 -m unittest discover -s tests`
- **UI preview in a browser** (fake bridge, real game rules): `python3 dev/preview_server.py`, then open http://localhost:8777 (farm) or http://localhost:8777/decks (almanac panel).
- **Package**: `cd anki_farm && zip -r ../anki_farm.ankiaddon . -x '__pycache__/*' 'meta.json'`
