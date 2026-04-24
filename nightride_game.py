"""
Night Ride — first-person neon bicycle racer
Performance-first rewrite: pre-baked surfaces, no per-frame SRCALPHA allocation in hot paths.
"""
import pygame
import random
import sys
import math

# ── Screen ───────────────────────────────────────────────────────────────────
W, H = 1920, 1080
FPS  = 60

# ── Perspective geometry ─────────────────────────────────────────────────────
# Road now fills the whole screen — horizon sits at the very top.
HORIZON_Y     = 0
ROAD_HALF_BOT = W * 0.50
ROAD_HALF_TOP = W * 0.004   # tiny vanishing point at the very top

# Player can now steer all the way to the road edges.
CAM_X_MAX     = W * 0.50
CAM_STEER_SPD = 1.5    # lerp speed when steering
CAM_RETURN_SPD= 2.0    # lerp speed when releasing (was 5.5)

NUM_OBJ_LANES = 5

INITIAL_SPEED     = 6.0
SPEED_INCREMENT   = 0.55
OBSTACLE_INTERVAL = 2.0 
COIN_INTERVAL     = 2.5 

OBJ_SPAWN_Z = 0.98
OBJ_HIT_Z   = 0.03
OBJ_CULL_Z  = -0.02

# ── Player hitbox (single source of truth) ───────────────────────────────────
# The visible square at the bottom AND the collision test both use this.
HITBOX_HALF = 36                       # half-size of the drawn square (px)
HITBOX_Y    = H - 10 - HITBOX_HALF * 2 # top-Y of the drawn square
HITBOX_CX_SCREEN = W // 2              # horizontal centre on screen (fixed)
# Collision tolerance in screen pixels at the near-plane (z≈0).
# Matches the drawn square's half-width so what you see is what you hit.
HITBOX_COLLIDE_PX = HITBOX_HALF

# ── Neon palette ─────────────────────────────────────────────────────────────
C_BG        = (  2,   0,  10)
C_ROAD      = (  5,   3,  16)

NEON_CYAN   = (  0, 255, 255)
NEON_CYAN2  = (  0, 180, 210)
NEON_PINK   = (255,   0, 180)
NEON_YELLOW = (255, 230,   0)
NEON_GREEN  = (  0, 255,  80)
NEON_GREEN2 = ( 40, 255, 120)
NEON_PURPLE = (160,   0, 255)
NEON_PURPLE2= (200,  60, 255)
NEON_ORANGE = (255,  80,   0)
NEON_WHITE  = (230, 220, 255)
NEON_RED    = (255,  10,  60)

OBS_COLORS  = [NEON_PINK, NEON_ORANGE, NEON_RED]

# ── Glow cache — build once, blit many ───────────────────────────────────────
_GLOW_CACHE: dict = {}

def _make_circle_glow(color, radius, passes=4, spread=5):
    total = radius + passes * spread
    size  = total * 2
    surf  = pygame.Surface((size, size), pygame.SRCALPHA)
    for i in range(passes, 0, -1):
        r     = radius + i * spread
        alpha = int(210 * (i / passes) ** 1.6)
        pygame.draw.circle(surf, (*color, alpha), (total, total), r)
    pygame.draw.circle(surf, color, (total, total), radius)
    white = tuple(min(255, c + 140) for c in color)
    pygame.draw.circle(surf, white, (total, total), max(2, radius // 3))
    return surf, total

def get_circle_glow(color, radius):
    key = ('c', color, radius)
    if key not in _GLOW_CACHE:
        _GLOW_CACHE[key] = _make_circle_glow(color, radius)
    return _GLOW_CACHE[key]

def blit_circle_glow(surf, color, pos, radius):
    gs, off = get_circle_glow(color, radius)
    surf.blit(gs, (pos[0] - off, pos[1] - off))

def _make_rect_glow(color, w, h, passes=4, spread=6):
    pad   = passes * spread
    sw, sh = w + pad * 2, h + pad * 2
    gs    = pygame.Surface((sw, sh), pygame.SRCALPHA)
    for i in range(passes, 0, -1):
        inf   = i * spread
        alpha = int(190 * (i / passes) ** 1.5)
        r2    = pygame.Rect(pad - inf, pad - inf, w + inf * 2, h + inf * 2)
        pygame.draw.rect(gs, (*color, alpha), r2,
                         border_radius=max(4, int(w * 0.15)))
    pygame.draw.rect(gs, color, pygame.Rect(pad, pad, w, h),
                     border_radius=max(4, int(w * 0.15)))
    white = tuple(min(255, c + 130) for c in color)
    inner = pygame.Rect(pad + w // 5, pad + h // 5, w * 3 // 5, h * 3 // 5)
    pygame.draw.rect(gs, white, inner, border_radius=3)
    return gs, pad

def get_rect_glow(color, w, h):
    key = ('r', color, w, h)
    if key not in _GLOW_CACHE:
        _GLOW_CACHE[key] = _make_rect_glow(color, w, h)
    return _GLOW_CACHE[key]

def blit_rect_glow(surf, color, rect):
    gs, pad = get_rect_glow(color, rect.w, rect.h)
    surf.blit(gs, (rect.x - pad, rect.y - pad))

# ── Perspective helpers ───────────────────────────────────────────────────────

def project(lane_frac, z, cam_x):
    half_w   = ROAD_HALF_BOT + (ROAD_HALF_TOP - ROAD_HALF_BOT) * z
    screen_y = HORIZON_Y + (H - HORIZON_Y) * (1.0 - z)
    center_x = W / 2 + cam_x * (1.0 - z)
    screen_x = center_x + lane_frac * half_w * 2
    scale    = max(0.0, 1.0 - z)
    return screen_x, screen_y, scale

# ── Road drawing (hot path — no SRCALPHA surfaces) ───────────────────────────

def draw_scene(surf, cam_x, road_offset, gt):
    # Fill everything with the dark road colour — no sky anymore.
    surf.fill(C_ROAD)

    def ex(frac, z): return project(frac, z, cam_x)[0]

    # 1. Road trapezoid (goes all the way up now)
    road_poly = [
        (ex(-0.5, 0.999), HORIZON_Y),
        (ex( 0.5, 0.999), HORIZON_Y),
        (ex( 0.5, 0.001), H),
        (ex(-0.5, 0.001), H),
    ]
    pygame.draw.polygon(surf, C_ROAD, road_poly)

    # 2. Scrolling horizontal grid lines — plain lines (no alpha)
    stripe_z_step = 0.09
    z_off = (road_offset * 0.005) % stripe_z_step
    z = z_off
    while z < 0.97:
        lx = int(ex(-0.5, z))
        rx = int(ex( 0.5, z))
        sy2 = int(HORIZON_Y + (H - HORIZON_Y) * (1.0 - z))
        brightness = int(55 * (1 - z) ** 2)
        if brightness > 3:
            r2 = int(NEON_PURPLE[0] * brightness / 55)
            g2 = int(NEON_PURPLE[1] * brightness / 55)
            b2 = int(NEON_PURPLE[2] * brightness / 55)
            pygame.draw.line(surf, (r2, g2, b2), (lx, sy2), (rx, sy2),
                             max(2, int(6 * (1 - z))))
        z += stripe_z_step

    # 3. Lane dashes — plain lines, sampled coarsely
    NUM_SEGS = 16
    for lane in range(1, NUM_OBJ_LANES):
        frac = (lane / NUM_OBJ_LANES) - 0.5
        prev = None
        for si in range(NUM_SEGS + 1):
            z2 = si / NUM_SEGS
            sx2 = int(ex(frac, z2))
            sy2 = int(HORIZON_Y + (H - HORIZON_Y) * (1.0 - z2))
            pt  = (sx2, sy2)
            if prev and si % 2 == 0:   # dash pattern
                bright = int(140 * (1 - z2))
                c = (int(NEON_PURPLE[0] * bright / 140),
                     int(NEON_PURPLE[1] * bright / 140),
                     int(NEON_PURPLE[2] * bright / 140))
                thick = max(2, int(4 * (1 - z2)))
                pygame.draw.line(surf, c, prev, pt, thick)
            prev = pt

    # 4. Road edges — bright neon cyan, plain lines
    for side in [-0.5, 0.5]:
        prev = None
        for si in range(NUM_SEGS + 1):
            z2  = si / NUM_SEGS
            sx2 = int(ex(side, z2))
            sy2 = int(HORIZON_Y + (H - HORIZON_Y) * (1.0 - z2))
            pt  = (sx2, sy2)
            if prev:
                bright = int(255 * (1 - z2))
                c = (0, bright, bright)
                thick = max(2, int(10 * (1 - z2)))
                pygame.draw.line(surf, c, prev, pt, thick)
            prev = pt

# ── Objects ───────────────────────────────────────────────────────────────────

OBS_SIZES  = [4, 8, 12, 16, 22, 28, 36, 46, 58, 72, 88, 104, 120]
COIN_SIZES = [3, 5, 7, 10, 14, 18, 22, 28, 34]

def nearest(val, lst):
    return min(lst, key=lambda v: abs(v - val))

class RoadObject:
    def __init__(self, speed, kind):
        self.lane  = random.randint(0, NUM_OBJ_LANES - 1)
        self.z     = OBJ_SPAWN_Z
        self.speed = speed
        self.kind  = kind
        self.pulse = random.uniform(0, 6.28)
        self.color = random.choice(OBS_COLORS) if kind == 'obstacle' else NEON_YELLOW

    @property
    def lane_frac(self):
        return (self.lane / (NUM_OBJ_LANES - 1)) - 0.5

    def update(self, dt):
        self.z     -= self.speed * (1.0 - self.z + 0.08) * dt
        self.pulse += dt * 5.0

    def is_hit(self, cam_x):
        if self.z >= OBJ_HIT_Z:
            return False
        # Project obstacle to screen-X at current z, then compare against the
        # drawn hitbox square at the screen centre. Tolerance = visible square half-width.
        half_w   = ROAD_HALF_BOT + (ROAD_HALF_TOP - ROAD_HALF_BOT) * self.z
        center_x = W / 2 + cam_x * (1.0 - self.z)
        obj_sx   = center_x + self.lane_frac * half_w * 2
        return abs(obj_sx - HITBOX_CX_SCREEN) < HITBOX_COLLIDE_PX

    def off_screen(self):
        return self.z < OBJ_CULL_Z

    def draw(self, surf, cam_x):
        if self.z <= 0.005:
            return
        sx, sy, scale = project(self.lane_frac, self.z, cam_x)
        if scale < 0.015:
            return

        pulse = 0.78 + 0.22 * math.sin(self.pulse)
        color = tuple(int(c * pulse) for c in self.color)

        if self.kind == 'obstacle':
            pw = nearest(int(110 * scale), OBS_SIZES)
            ph = nearest(int(155 * scale), OBS_SIZES)
            if pw < 4 or ph < 4:
                return
            r = pygame.Rect(int(sx) - pw // 2, int(sy) - ph, pw, ph)
            blit_rect_glow(surf, color, r)
            # Windshield
            if pw > 18:
                wr = pygame.Rect(r.x + pw // 5, r.y + ph // 8,
                                 pw * 3 // 5, ph // 3)
                pygame.draw.rect(surf, C_BG, wr, border_radius=2)
                pygame.draw.rect(surf, color, wr, max(2, int(4 * scale)),
                                 border_radius=2)
            # Headlights
            if pw > 12:
                hl_r = max(2, int(5 * scale))
                for hx in [r.left + hl_r + 2, r.right - hl_r - 2]:
                    blit_circle_glow(surf, (255, 220, 100), (hx, r.bottom - hl_r - 2), hl_r)

        else:  # coin
            cr = nearest(int(32 * scale), COIN_SIZES)
            if cr < 3:
                return
            spin_w = max(2, int(cr * 2 * abs(math.sin(self.pulse))))
            blit_circle_glow(surf, color, (int(sx), int(sy)), cr)
            if spin_w > 4:
                e_rect = pygame.Rect(int(sx) - spin_w // 2, int(sy) - cr,
                                     spin_w, cr * 2)
                pygame.draw.ellipse(surf, (170, 130, 0), e_rect, max(2, int(6 * scale)))

# ── Sparks ────────────────────────────────────────────────────────────────────

class Spark:
    def __init__(self, x, y, color):
        a  = random.uniform(0, math.pi * 2)
        sp = random.uniform(120, 440)
        self.x, self.y   = float(x), float(y)
        self.vx, self.vy = math.cos(a) * sp, math.sin(a) * sp
        self.life         = random.uniform(0.3, 0.75)
        self.max_life     = self.life
        self.color        = color

    def update(self, dt):
        self.x  += self.vx * dt
        self.y  += self.vy * dt
        self.vy += 270 * dt
        self.life -= dt
        return self.life > 0

    def draw(self, surf):
        a = self.life / self.max_life
        r = max(1, int(5 * a))
        c = tuple(int(ch * a) for ch in self.color)
        pygame.draw.circle(surf, c, (int(self.x), int(self.y)), r)

# ── HUD ───────────────────────────────────────────────────────────────────────

def draw_hud(surf, score, speed, combo, player_lane, cam_x, font_big, font_small, font_tiny):
    # Score — top left
    sc_str  = f"{score:,}"
    shadow  = font_big.render(sc_str, True, (0, 55, 20))
    sc_surf = font_big.render(sc_str, True, NEON_GREEN)
    surf.blit(shadow,  (31, 15))
    surf.blit(sc_surf, (28, 12))

    # Speed — top right
    surf.blit(font_tiny.render("KM/H",              True, (90, 60, 150)), (W - 215, 14))
    surf.blit(font_small.render(f"{int(speed*22)}", True, NEON_PURPLE2),  (W - 215, 38))

    # Speed bar
    bar_max = 330
    bar_w   = int(bar_max * min(1.0, speed / 16.0))
    pygame.draw.rect(surf, (18, 8, 38), pygame.Rect(W - 215, 78, bar_max, 13),
                     border_radius=4)
    if bar_w > 0:
        pygame.draw.rect(surf, NEON_PURPLE2, pygame.Rect(W - 215, 78, bar_w, 13),
                         border_radius=4)

    # Combo — below the score on the left
    if combo > 1:
        t  = min(combo, 8) / 8
        cc = (int(NEON_YELLOW[0]*t + NEON_GREEN[0]*(1-t)),
              int(NEON_YELLOW[1]*t + NEON_GREEN[1]*(1-t)),
              int(NEON_YELLOW[2]*t + NEON_GREEN[2]*(1-t)))
        surf.blit(font_small.render(f"x{combo}  COMBO", True, cc), (28, 95))

    # ── Hitbox square — matches the actual collision box ───────────────────
    hx        = HITBOX_CX_SCREEN
    sq        = HITBOX_HALF
    sq_y      = HITBOX_Y
    sq_rect   = pygame.Rect(hx - sq, sq_y, sq * 2, sq * 2)
    # Glow outline
    for i in range(4, 0, -1):
        gr = sq_rect.inflate(i * 5, i * 5)
        gc = (0, int(NEON_CYAN[1] * i // 4), int(NEON_CYAN[2] * i // 4))
        pygame.draw.rect(surf, gc, gr, 4, border_radius=4)
    # Solid filled square
    pygame.draw.rect(surf, NEON_CYAN, sq_rect, border_radius=4)
    # Bright white centre cross-hair
    pygame.draw.line(surf, (255,255,255), (hx - 6, sq_y + sq), (hx + 6, sq_y + sq), 4)
    pygame.draw.line(surf, (255,255,255), (hx, sq_y + sq - 6), (hx, sq_y + sq + 6), 4)

def draw_game_over(surf, score, font_huge, font_big, font_small, t):
    ov = pygame.Surface((W, H))
    ov.set_alpha(210)
    ov.fill((0, 0, 0))
    surf.blit(ov, (0, 0))

    cx  = W // 2
    cy  = H // 2
    flk = 0.80 + 0.20 * math.sin(t * 24)
    go_c = tuple(int(c * flk) for c in NEON_PINK)
    go   = font_huge.render("GAME  OVER", True, go_c)
    gx   = cx - go.get_width() // 2
    gy   = cy - 175
    for dx, dy in [(-5,-5),(5,5),(-5,5),(5,-5)]:
        surf.blit(font_huge.render("GAME  OVER", True, (80,0,45)), (gx+dx, gy+dy))
    surf.blit(go, (gx, gy))

    sc  = font_big.render(f"SCORE   {score:,}", True, NEON_GREEN)
    rst = font_small.render("BOTH BRAKES or SPACE · restart          ESC · quit", True, (120, 80, 190))
    surf.blit(sc,  (cx - sc.get_width()  // 2, cy - 20))
    surf.blit(rst, (cx - rst.get_width() // 2, cy + 82))

    for i in range(5):
        a  = max(0, 85 - i * 16)
        c  = (int(NEON_PINK[0]*a//85), int(NEON_PINK[1]*a//85), int(NEON_PINK[2]*a//85))
        pygame.draw.line(surf, c, (0, cy - 235 + i*3), (W, cy - 235 + i*3), 4)
        pygame.draw.line(surf, c, (0, cy + 148 - i*3), (W, cy + 148 - i*3), 4)

# ── State ─────────────────────────────────────────────────────────────────────

def make_state():
    return dict(
        objects     = [],
        sparks      = [],
        score       = 0,
        speed       = float(INITIAL_SPEED),
        obs_timer   = 0.0,
        coin_timer  = 0.0,
        speed_timer = 0.0,
        road_offset = 0.0,
        alive       = True,
        combo       = 0,
        combo_timer = 0.0,
        cam_x       = 0.0,
        player_lane = (NUM_OBJ_LANES - 1) / 2.0,
    )

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H), pygame.FULLSCREEN)
    pygame.display.set_caption("Night Ride")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    # Warm the glow cache for common obstacle/coin sizes so first frames don't stutter
    for col in OBS_COLORS:
        for sz in OBS_SIZES[-6:]:
            get_rect_glow(col, sz, int(sz * 1.45))
    for sz in COIN_SIZES[-5:]:
        get_circle_glow(NEON_YELLOW, sz)

    font_huge  = pygame.font.SysFont("Courier New", 110, bold=True)
    font_big   = pygame.font.SysFont("Courier New",  66, bold=True)
    font_small = pygame.font.SysFont("Courier New",  32, bold=True)
    font_tiny  = pygame.font.SysFont("Courier New",  22)

    s  = make_state()
    gt = 0.0
    both_prev = False  # tracks previous-frame state of LEFT+RIGHT for edge-trigger restart

    while True:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        gt += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if event.key == pygame.K_SPACE and not s["alive"]:
                    s = make_state()
                    both_prev = False

        keys  = pygame.key.get_pressed()

        # Restart on both brakes (LEFT + RIGHT) while dead — edge-triggered so
        # holding both down doesn't instantly re-restart after a new game.
        both_now = keys[pygame.K_LEFT] and keys[pygame.K_RIGHT]
        if both_now and not both_prev and not s["alive"]:
            s = make_state()
        both_prev = both_now

        steer = ( 1.0 if keys[pygame.K_LEFT] else 0.0) + \
                (-1.0 if keys[pygame.K_RIGHT] else 0.0)

        if s["alive"]:
            if steer != 0:
                s["cam_x"] += steer * CAM_STEER_SPD * CAM_X_MAX * dt
                s["cam_x"]  = max(-CAM_X_MAX, min(CAM_X_MAX, s["cam_x"]))

            s["player_lane"] = ((s["cam_x"] / CAM_X_MAX) * 0.5 + 0.5) * (NUM_OBJ_LANES - 1)

            s["road_offset"] += s["speed"] * dt * 60
            s["speed_timer"] += dt
            if s["speed_timer"] >= 10.0:
                s["speed_timer"] = 0.0
                s["speed"]      += SPEED_INCREMENT
            s["score"] += int(s["speed"] * dt * 3)

            s["combo_timer"] += dt
            if s["combo_timer"] > 3.0:
                s["combo"] = 0

            s["obs_timer"] += dt
            if s["obs_timer"] >= OBSTACLE_INTERVAL:
                s["obs_timer"] = 0.0
                s["objects"].append(RoadObject(s["speed"] * 0.026, 'obstacle'))
            s["coin_timer"] += dt
            if s["coin_timer"] >= COIN_INTERVAL:
                s["coin_timer"] = 0.0
                s["objects"].append(RoadObject(s["speed"] * 0.026, 'coin'))

            for obj in s["objects"][:]:
                obj.update(dt)
                if obj.off_screen():
                    s["objects"].remove(obj)
                elif obj.is_hit(s["cam_x"]):
                    if obj.kind == 'obstacle':
                        s["alive"] = False
                    else:
                        ox, oy, _ = project(obj.lane_frac, obj.z, s["cam_x"])
                        s["objects"].remove(obj)
                        s["combo"]      += 1
                        s["combo_timer"] = 0.0
                        s["score"]      += 100 * max(1, s["combo"])
                        for _ in range(22):
                            s["sparks"].append(
                                Spark(ox, oy,
                                      random.choice([NEON_YELLOW, NEON_GREEN2,
                                                     (255, 255, 180)])))

            s["sparks"] = [sp for sp in s["sparks"] if sp.update(dt)]

        # ── Draw ──────────────────────────────────────────────────────────
        screen.fill(C_BG)
        draw_scene(screen, s["cam_x"], s["road_offset"], gt)

        for obj in sorted(s["objects"], key=lambda o: o.z, reverse=True):
            obj.draw(screen, s["cam_x"])

        for sp in s["sparks"]:
            sp.draw(screen) 

        draw_hud(screen, s["score"], s["speed"], s["combo"],
                 s["player_lane"], s["cam_x"],
                 font_big, font_small, font_tiny)

        if not s["alive"]:
            draw_game_over(screen, s["score"], font_huge, font_big, font_small, gt)

        pygame.display.flip()


if __name__ == "__main__":
    main()