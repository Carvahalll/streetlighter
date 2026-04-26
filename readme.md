# Night Ride

First-person neon bicycle racer. Built as an outdoor art installation: a real bicycle with Arduino brake triggers drives the game.

---

## Hardware & platform

| Target | Details |
|--------|---------|
| Display | 1080p screen (fullscreen) |
| Compute | Raspberry Pi 5 (production), macOS (development) |
| Input | Arduino Leonardo presenting as USB keyboard — LEFT arrow (left brake), RIGHT arrow (right brake) |
| Restart | Hold LEFT + RIGHT simultaneously (game over screen) or SPACE |

The same Love2D source runs on both platforms without modification. Flip `FULLSCREEN = true` at the top of `main.lua` for deployment.

---

## Repository layout

```
Night_Ride/
├── nightride_game.py           pygame prototype (reference, do not delete)
├── arduino_code/               Arduino Leonardo sketch
├── README.md                   this file
├── .gitignore
├── love/                       Love2D project (run with: love love/)
│   ├── conf.lua                window / module config
│   ├── main.lua                entry point; FULLSCREEN flag lives here
│   ├── input.lua               key polling + both-brakes edge detection
│   ├── assets/
│   │   ├── background/
│   │   │   ├── pilatus.svg     source artwork
│   │   │   └── pilatus.png     white-on-transparent PNG (rendered from SVG)
│   │   └── scenery/
│   │       ├── *.svg           source artwork (altstadt, bahnhof, hofkirche, …)
│   │       └── *.png           white-on-transparent PNGs (rendered from SVGs)
│   └── game/
│       ├── constants.lua       all magic numbers; HORIZON_Y controls sky height
│       ├── state.lua           game state + reset
│       ├── road.lua            project() + drawRoad()
│       ├── objects.lua         RoadObject — obstacles, swans, coins, gate
│       ├── background.lua      Pilatus image + lake shimmer
│       ├── scenery.lua         Lucerne landmark sprites (perspective zoom-in)
│       ├── sparks.lua          particle burst on coin collect
│       ├── bloom.lua           GPU bloom shader
│       └── hud.lua             score, speed bar, combo, hitbox, game-over overlay
└── docs/                       GitHub Pages site (served from main branch /docs)
    ├── index.html              landing page
    └── game/
        ├── shell.html          custom dark shell (do NOT delete — survives rebuilds)
        ├── game.data           bundled game assets (rebuilt by love.js)
        ├── game.js             love.js loader glue  (rebuilt by love.js)
        ├── love.js             Emscripten runtime   (rebuilt by love.js)
        └── love.wasm           Love2D WebAssembly   (rebuilt by love.js)
```

---

## Deploying to GitHub Pages

The live site is at **https://carvahalll.github.io/night-ride/**.
GitHub Pages serves the `docs/` folder on the `main` branch automatically — pushing is all that's needed.

### Steps

**1. Rebuild the web bundle**

```bash
npx love.js@11.4.1 -c -t "Night Ride" love/ docs/game/
```

This regenerates `docs/game/game.data`, `game.js`, `love.js`, and `love.wasm`.
It also overwrites `docs/game/index.html` with a default shell — ignore that file,
the custom shell lives in `docs/game/shell.html` and is never touched by the rebuild.

**2. Stage only the rebuilt files**

```bash
git add docs/game/game.data docs/game/game.js docs/game/love.js docs/game/love.wasm
# Do NOT add docs/game/index.html
```

If you also changed Lua source or assets, stage those too:

```bash
git add love/
```

**3. Commit and push**

```bash
git commit -m "Rebuild web bundle: <short description>"

# The large love.wasm (≈4.5 MB) needs a bigger HTTP buffer:
git -c http.postBuffer=524288000 push origin main
```

GitHub Pages rebuilds automatically within ~1–2 minutes after the push.

### Lua compatibility note

love.js runs **Lua 5.1**. Avoid:
- `goto` / `::label::` statements (Lua 5.2+)
- `table.unpack` with index range args — use a helper table instead

### Re-rendering SVG assets

The scenery and Pilatus images are stored as both `.svg` (source) and `.png` (white-on-transparent, loaded by the game). To re-render after editing an SVG:

```bash
# Pilatus (full game width)
sed 's/fill="#000000"/fill="#ffffff"/g' love/assets/background/pilatus.svg > /tmp/w.svg
sips -s format png --resampleWidth 1280 /tmp/w.svg --out love/assets/background/pilatus.png

# Scenery items (max 600 px)
for svg in love/assets/scenery/*.svg; do
  name=$(basename "${svg%.svg}")
  sed 's/fill="#000000"/fill="#ffffff"/g' "$svg" > /tmp/w.svg
  sips -s format png -Z 600 /tmp/w.svg --out "love/assets/scenery/${name}.png"
done
```

Then run `git add love/assets/` and rebuild the bundle.

---

## Running the game

```bash
# macOS (Homebrew)
brew install love
love love/

# Raspberry Pi (apt)
sudo apt install love
love love/
```

---

## Gameplay

- **Steer** left/right by squeezing the corresponding brake
- **Avoid** neon obstacles (pink/orange/red) rushing toward you
- **Collect** yellow coins for combo-multiplied score
- Speed increases every 10 seconds
- Game over on obstacle collision; restart with SPACE or both brakes

---

## Key technical decisions

| Decision | Rationale |
|----------|-----------|
| Love2D over pygame | GPU-accelerated rendering; runs well on Pi 5; LÖVE is stable and minimal |
| Logical canvas (1280×720) scaled to window | Single codebase for dev (windowed) and installation (1080p fullscreen) without changing draw code |
| CPU glow for first pass | Concentric transparent shapes, no shader dependency — gets gameplay running first |
| Shader-based bloom (planned) | Will replace CPU glow once gameplay is confirmed; real GPU bloom is the aesthetic goal |
| Edge-triggered both-brakes restart | Prevents accidental instant re-restart after game over |
| `love.math.random` throughout | Deterministic seeding possible for reproducibility |

---

## Implementation status

### Love2D port
- [x] Project structure and conf.lua
- [x] Constants (mirrors all pygame globals)
- [x] Game state + reset
- [x] Input module (steer, both-brakes edge detect, SPACE restart)
- [x] Perspective road (grid lines, lane dashes, neon edges)
- [x] RoadObject — obstacles (car shape + headlights) and coins (circle + spin)
- [x] Collision detection (matches pygame logic exactly)
- [x] Spark particles on coin collect
- [x] HUD (score, speed bar, combo display, hitbox square)
- [x] Game-over overlay + restart
- [x] Logical canvas → letterboxed window scaling
- [x] GPU bloom shader (threshold → half-res Gaussian blur → additive composite)

### Planned
- [ ] Sound effects (coin collect, obstacle hit, engine hum)
- [ ] Custom pixel/neon font
- [ ] Raspberry Pi deployment test
- [ ] Configurable key bindings (for remapping Arduino if needed)

---

## Pygame prototype notes

`nightride_game.py` is the original prototype. Key differences from the Love2D port:
- Uses pre-baked `SRCALPHA` surfaces for glow (expensive on Pi)
- Hardcoded to 1920×1080 fullscreen
- Glow cache warms on startup to avoid first-frame stutter

The Love2D port preserves all gameplay constants and collision logic exactly. Visual parity (especially glow quality) will improve once the shader pass is added.
