-- Scenery: Lucerne landmarks that zoom in from the horizon on both sides of the
-- road, using the same perspective projection as road objects.
-- Images are solid-filled silhouettes (any color on transparent); the shader
-- discards the pixel RGB and substitutes the neon tint color, using only the
-- image alpha as a mask.

local C = require("game.constants")

local Scenery = {}

-- ── Asset manifest ────────────────────────────────────────────────────────────
local IMAGE_PATHS = {
    "assets/scenery/altstadt.png",
    "assets/scenery/bahnhof.png",
    "assets/scenery/hofkirche.png",
    "assets/scenery/jesuitenkirche.png",
    "assets/scenery/kapellbruecke.png",
    "assets/scenery/ringer.png",
    "assets/scenery/suva.png",
}

local NEON_PALETTE = {
    {0.0, 1.0, 1.0},   -- cyan
    {1.0, 0.0, 0.71},  -- pink
    {0.62, 0.0, 1.0},  -- purple
    {1.0, 0.31, 0.0},  -- orange
    {0.0, 1.0, 0.31},  -- neon-green
}

-- Replaces each pixel's RGB with the draw color; alpha comes from the image.
local SILHOUETTE_SHADER = love.graphics.newShader([[
    vec4 effect(vec4 color, Image tex, vec2 uv, vec2 sc) {
        float a = Texel(tex, uv).a;
        if (a < 0.01) { discard; }
        return vec4(color.rgb, color.a * a);
    }
]])

-- ── Module state ──────────────────────────────────────────────────────────────
local images       = {}    -- { img, w, h }
local items        = {}    -- active scenery items
local spawn_timer  = 0
local next_side    = -1    -- alternates: -1 = left, 1 = right
local last_img_idx = nil   -- prevent same image appearing twice in a row

local SPAWN_INTERVAL = 6.0   -- seconds between single spawns (alternating left/right)
local CULL_Z         = 0.42  -- remove item when it gets this close (before road fills screen)

-- lane_frac controls how far outside the road edges the building appears.
-- Values > 0.5 are outside the right road edge; < -0.5 outside the left edge.
local LANE_MIN = 0.72   -- closest to road edge
local LANE_MAX = 1.05   -- furthest from road edge

-- ── Internal helpers ──────────────────────────────────────────────────────────

local function randcol()
    return NEON_PALETTE[love.math.random(#NEON_PALETTE)]
end

local function spawnOne(speed)
    if #images == 0 then return end

    -- Pool: images not currently visible on screen
    local on_screen = {}
    for _, item in ipairs(items) do
        on_screen[item.img_idx] = true
    end
    local pool = {}
    for i = 1, #images do
        if not on_screen[i] then pool[#pool+1] = i end
    end

    -- All images already on screen — skip this spawn
    if #pool == 0 then return end

    -- Prefer not repeating the last spawned image; fall back if no other choice
    local preferred = {}
    for _, i in ipairs(pool) do
        if i ~= last_img_idx then preferred[#preferred+1] = i end
    end
    local candidates = #preferred > 0 and preferred or pool

    local idx        = candidates[love.math.random(#candidates)]
    last_img_idx     = idx

    local side       = next_side
    next_side        = -next_side
    local lane_frac  = side * (LANE_MIN + love.math.random() * (LANE_MAX - LANE_MIN))

    items[#items+1] = {
        z          = C.OBJ_SPAWN_Z,
        speed      = speed * 0.020,
        lane_frac  = lane_frac,
        img_idx    = idx,
        color      = randcol(),
    }
end

-- ── Public API ────────────────────────────────────────────────────────────────

function Scenery.load()
    for _, path in ipairs(IMAGE_PATHS) do
        local ok, img = pcall(love.graphics.newImage, path)
        if ok then
            images[#images+1] = { img = img, w = img:getWidth(), h = img:getHeight() }
        end
    end
end

function Scenery.update(dt, speed)
    spawn_timer = spawn_timer + dt
    if spawn_timer >= SPAWN_INTERVAL then
        spawn_timer = 0
        spawnOne(speed)
    end

    -- Advance each item toward the camera, cull when too close
    local i = 1
    while i <= #items do
        local item = items[i]
        item.z = item.z - item.speed * (1.0 - item.z + 0.08) * dt
        if item.z < CULL_Z then
            items[i] = items[#items]
            items[#items] = nil
        else
            i = i + 1
        end
    end
end

function Scenery.draw(cam_x)
    -- Sort far-to-near so closer buildings overdraw distant ones
    table.sort(items, function(a, b) return a.z > b.z end)

    for _, item in ipairs(items) do
        local idata = images[item.img_idx]
        if idata then
            -- Road perspective projection (mirrors Road.project logic)
            local half_w   = C.ROAD_HALF_BOT + (C.ROAD_HALF_TOP - C.ROAD_HALF_BOT) * item.z
            local screen_y = C.HORIZON_Y + (C.H - C.HORIZON_Y) * (1.0 - item.z)
            local center_x = C.W / 2 + cam_x * (1.0 - item.z)
            local screen_x = center_x + item.lane_frac * half_w * 2
            local sc       = math.max(0, 1.0 - item.z)

            if sc >= 0.01 then
                local col = item.color
                love.graphics.setShader(SILHOUETTE_SHADER)
                love.graphics.setColor(col[1], col[2], col[3], 0.92)
                love.graphics.draw(idata.img,
                    screen_x - idata.w * sc / 2,
                    screen_y - idata.h * sc,
                    0, sc, sc)
                love.graphics.setShader()
            end
        end
    end

    love.graphics.setColor(1, 1, 1, 1)
end

function Scenery.reset()
    items        = {}
    spawn_timer  = 0
    next_side    = -1
    last_img_idx = nil
end

return Scenery
