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
├── nightride_game.py       pygame prototype (reference, do not delete)
├── arduino_code/           Arduino Leonardo sketch
├── README.md               this file
├── .gitignore
└── love/                   Love2D project (run with: love love/)
    ├── conf.lua            window / module config
    ├── main.lua            entry point; FULLSCREEN flag lives here
    ├── input.lua           key polling + both-brakes edge detection
    ├── game/
    │   ├── constants.lua   all magic numbers (mirrors pygame globals)
    │   ├── state.lua       makeState() / reset
    │   ├── road.lua        project() + drawRoad()
    │   ├── objects.lua     RoadObject — obstacles & coins
    │   ├── sparks.lua      particle burst on coin collect
    │   └── hud.lua         score, speed bar, combo, hitbox, game-over overlay
    └── audio/              placeholder — sound effects go here
```

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
