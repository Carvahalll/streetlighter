-- GPU bloom: threshold → half-res downsample → separable Gaussian blur → additive composite.
-- All heavy lifting happens in shaders; Lua only manages canvas ping-pong.

local Bloom = {}

-- ── Tuning ────────────────────────────────────────────────────────────────────
local THRESHOLD   = 0.15   -- luminance cutoff; lower = more colours glow
local BLOOM_MIX   = 1.0    -- additive strength of the bloom overlay
local BLUR_PASSES = 4      -- more passes = wider, softer halo

-- ── Shader sources ────────────────────────────────────────────────────────────

-- Extract pixels above the luminance threshold (soft roll-off, not hard clip).
local SRC_THRESHOLD = [[
extern float threshold;
vec4 effect(vec4 color, Image tex, vec2 tc, vec2 sc) {
    vec4 px  = Texel(tex, tc);
    float lum = dot(px.rgb, vec3(0.2126, 0.7152, 0.0722));
    float w   = max(0.0, lum - threshold) / max(lum, 0.0001);
    return vec4(px.rgb * w, px.a) * color;
}
]]

-- 9-tap separable Gaussian.  'direction' is (1/w, 0) or (0, 1/h).
local SRC_BLUR = [[
extern vec2 direction;
vec4 effect(vec4 color, Image tex, vec2 tc, vec2 sc) {
    vec4 c = vec4(0.0);
    c += Texel(tex, tc + direction * -4.0) * 0.0162162162;
    c += Texel(tex, tc + direction * -3.0) * 0.0540540541;
    c += Texel(tex, tc + direction * -2.0) * 0.1216216216;
    c += Texel(tex, tc + direction * -1.0) * 0.1945945946;
    c += Texel(tex, tc                   ) * 0.2270270270;
    c += Texel(tex, tc + direction *  1.0) * 0.1945945946;
    c += Texel(tex, tc + direction *  2.0) * 0.1216216216;
    c += Texel(tex, tc + direction *  3.0) * 0.0540540541;
    c += Texel(tex, tc + direction *  4.0) * 0.0162162162;
    return c * color;
}
]]

-- ── Module state ──────────────────────────────────────────────────────────────
local canvas_bright, canvas_blur_a, canvas_blur_b
local shader_threshold, shader_blur
local hw, hh   -- half logical resolution

-- ── Public API ────────────────────────────────────────────────────────────────

function Bloom.load(w, h)
    hw = math.floor(w / 2)
    hh = math.floor(h / 2)

    canvas_bright = love.graphics.newCanvas(hw, hh)
    canvas_blur_a = love.graphics.newCanvas(hw, hh)
    canvas_blur_b = love.graphics.newCanvas(hw, hh)

    for _, c in ipairs({canvas_bright, canvas_blur_a, canvas_blur_b}) do
        c:setFilter("linear", "linear")
    end

    shader_threshold = love.graphics.newShader(SRC_THRESHOLD)
    shader_threshold:send("threshold", THRESHOLD)

    shader_blur = love.graphics.newShader(SRC_BLUR)
end

-- Run the bloom pipeline.  Call once per frame after rendering to `source`.
-- Leaves canvas and shader state reset (no canvas set, no shader active).
function Bloom.apply(source)
    local sw, sh = source:getDimensions()

    -- 1. Threshold + downsample → canvas_bright (half-res)
    love.graphics.setCanvas(canvas_bright)
    love.graphics.clear(0, 0, 0, 1)
    love.graphics.setShader(shader_threshold)
    love.graphics.setColor(1, 1, 1, 1)
    love.graphics.draw(source, 0, 0, 0, hw / sw, hh / sh)

    -- 2. Ping-pong blur: canvas_bright → blur_a (H) → blur_b (V), repeat
    love.graphics.setShader(shader_blur)
    local ping = canvas_bright
    for _ = 1, BLUR_PASSES do
        love.graphics.setCanvas(canvas_blur_a)
        love.graphics.clear(0, 0, 0, 1)
        shader_blur:send("direction", {1 / hw, 0})
        love.graphics.draw(ping)

        love.graphics.setCanvas(canvas_blur_b)
        love.graphics.clear(0, 0, 0, 1)
        shader_blur:send("direction", {0, 1 / hh})
        love.graphics.draw(canvas_blur_a)

        ping = canvas_blur_b
    end

    love.graphics.setShader()
    love.graphics.setCanvas()
    love.graphics.setColor(1, 1, 1, 1)
end

-- Composite the bloom result additively.
-- x, y, sx, sy must match the transform used to draw the game canvas to screen.
function Bloom.draw(x, y, sx, sy)
    -- canvas_blur_b is half logical size, so scale *2 to match game canvas footprint.
    love.graphics.setBlendMode("add")
    love.graphics.setColor(BLOOM_MIX, BLOOM_MIX, BLOOM_MIX, 1)
    love.graphics.draw(canvas_blur_b, x, y, 0, sx * 2, sy * 2)
    love.graphics.setBlendMode("alpha")
    love.graphics.setColor(1, 1, 1, 1)
end

return Bloom
