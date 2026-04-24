-- ── Config flags (edit here for deployment) ───────────────────────────────────
local FULLSCREEN = false   -- set true for 1080p installation mode
local RES_W      = 1920    -- used only when FULLSCREEN = true
local RES_H      = 1080

-- ── Requires ──────────────────────────────────────────────────────────────────
local C       = require("game.constants")
local State   = require("game.state")
local Road    = require("game.road")
local Objects = require("game.objects")
local Sparks  = require("game.sparks")
local HUD     = require("game.hud")
local Bloom   = require("game.bloom")
local Input   = require("input")

-- ── Globals ───────────────────────────────────────────────────────────────────
local s           -- current game state
local scale_x, scale_y, offset_x, offset_y  -- logical→physical transform
local canvas      -- off-screen canvas at logical resolution

-- ── Love callbacks ────────────────────────────────────────────────────────────

function love.load()
    if FULLSCREEN then
        love.window.setMode(RES_W, RES_H, {fullscreen=true, vsync=1})
    end

    -- Logical canvas always renders at C.W × C.H; scaled to window at draw time.
    canvas = love.graphics.newCanvas(C.W, C.H)

    -- Compute scale + letterbox offsets
    local pw, ph = love.graphics.getDimensions()
    scale_x  = pw / C.W
    scale_y  = ph / C.H
    local sc = math.min(scale_x, scale_y)
    scale_x, scale_y = sc, sc
    offset_x = (pw - C.W * sc) / 2
    offset_y = (ph - C.H * sc) / 2

    HUD.load()
    Bloom.load(C.W, C.H)

    s = State.new()
    Input.reset()

    love.graphics.setLineStyle("rough")  -- crisp lines, better for neon look
end

function love.update(dt)
    dt = math.min(dt, 0.05)   -- cap to avoid spiral-of-death after focus loss
    s.gt = s.gt + dt

    local steer, restart = Input.poll(s.alive)

    if restart then
        s = State.new()
        Input.reset()
        return
    end

    if not s.alive then return end

    -- Steering — hold position when no key is pressed
    if steer ~= 0 then
        s.cam_x = s.cam_x + steer * C.CAM_STEER_SPD * C.CAM_X_MAX * dt
        s.cam_x = math.max(-C.CAM_X_MAX, math.min(C.CAM_X_MAX, s.cam_x))
    end

    -- Road scroll & speed ramp
    s.road_offset = s.road_offset + s.speed * dt * 60
    s.speed_timer = s.speed_timer + dt
    if s.speed_timer >= 10 then
        s.speed_timer = 0
        s.speed       = s.speed + C.SPEED_INCREMENT
    end

    -- Score ticks up while alive
    s.score = s.score + s.speed * dt * 3

    -- Combo decay
    s.combo_timer = s.combo_timer + dt
    if s.combo_timer > 3 then s.combo = 0 end

    -- Spawn objects
    s.obs_timer = s.obs_timer + dt
    if s.obs_timer >= C.OBSTACLE_INTERVAL then
        s.obs_timer = 0
        s.objects[#s.objects+1] = Objects.newObstacle(s.speed * 0.026)
    end
    s.coin_timer = s.coin_timer + dt
    if s.coin_timer >= C.COIN_INTERVAL then
        s.coin_timer = 0
        s.objects[#s.objects+1] = Objects.newCoin(s.speed * 0.026)
    end

    -- Update objects; detect collisions
    local i = 1
    while i <= #s.objects do
        local obj = s.objects[i]
        obj:update(dt)

        if obj:offScreen() then
            s.objects[i] = s.objects[#s.objects]
            s.objects[#s.objects] = nil

        elseif obj:isHit(s.cam_x) then
            if obj.kind == 'obstacle' then
                s.alive = false
                i = i + 1   -- leave in list so it draws on game-over frame
            else
                local ox, oy = Road.project(obj:laneFrac(), obj.z, s.cam_x)
                s.objects[i] = s.objects[#s.objects]
                s.objects[#s.objects] = nil
                s.combo       = s.combo + 1
                s.combo_timer = 0
                s.score       = s.score + 100 * math.max(1, s.combo)
                Sparks.burst(s.sparks, ox, oy, 22)
            end
        else
            i = i + 1
        end
    end

    Sparks.update(s.sparks, dt)
end

function love.draw()
    -- Render game at logical resolution into canvas
    love.graphics.setCanvas(canvas)
    love.graphics.clear(C.COL.BG[1], C.COL.BG[2], C.COL.BG[3], 1)

    Road.draw(s.cam_x, s.road_offset)

    -- Draw objects back-to-front (highest z first = furthest away)
    table.sort(s.objects, function(a, b) return a.z > b.z end)
    for _, obj in ipairs(s.objects) do
        obj:draw(s.cam_x)
    end

    Sparks.draw(s.sparks)

    HUD.draw(s.score, s.speed, s.combo, s.gt)

    if not s.alive then
        HUD.drawGameOver(s.score, s.gt)
    end

    -- Bloom pass (threshold → half-res Gaussian blur, stored internally)
    love.graphics.setCanvas()
    Bloom.apply(canvas)

    -- Blit game canvas to window (letterboxed / scaled)
    love.graphics.setColor(1, 1, 1, 1)
    love.graphics.draw(canvas, offset_x, offset_y, 0, scale_x, scale_y)

    -- Additive bloom overlay on top
    Bloom.draw(offset_x, offset_y, scale_x, scale_y)
end

function love.keypressed(key)
    if key == "escape" then
        love.event.quit()
    end
    if key == "space" and not s.alive then
        s = State.new()
        Input.reset()
    end
end
