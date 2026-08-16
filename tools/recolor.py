#!/usr/bin/env python3
"""把 Obsidian Primary 主题的配色统一到单一色相。

规则：
- hsl()/hsla()  -> 色相改为 --hue，饱和度按上限封顶，保留亮度与 alpha
- rgb()/rgba()  -> 转 HSL 后同样处理，再转回 rgb，保留 alpha
- 语义色（error/warning/success/danger/caution/invalid/fail）所在声明跳过，保留原色
- 中性色（S=0% 或 R=G=B）默认不动；加 --tint-neutrals 则染为同色相的淡色，
  纯白（L≥99）与纯黑（L≤2）始终不动

饱和度用「封顶」而非「缩放」：原本就淡的颜色保持淡，原本浓的压到上限，
结果是整体色调统一且亮度层次不变。

用法:
    python3 recolor.py <输入> <输出> [选项]

选项:
    --hue=210            目标色相
    --max-sat=14         全域饱和度上限（未指定 --curve 时生效）
    --curve=bluetopaz    改用按亮度分段的上限，模拟 Blue Topaz 的蓝白观感
    --tint-neutrals      中性灰也染上色相，使灰面呈蓝灰而非中性灰
    --accent-override    在输出末尾追加 accent 覆盖块（只对最终产物用）

--max-sat=0 且不加 --curve / --tint-neutrals 时等价于转灰阶。
"""
import colorsys
import re
import sys

SEMANTIC = re.compile(
    r"error|warning|success|danger|caution|invalid|fail|--color-red|--color-orange|--color-green|--color-yellow",
    re.I,
)

HSL = re.compile(
    r"\bhsla?\(\s*([\d.]+)(deg)?\s*[, ]\s*([\d.]+)%\s*[, ]\s*([\d.]+)%\s*(?:[,/]\s*([\d.%]+)\s*)?\)",
    re.I,
)
RGB = re.compile(
    r"\brgba?\(\s*([\d.]+)\s*[, ]\s*([\d.]+)\s*[, ]\s*([\d.]+)\s*(?:[,/]\s*([\d.%]+)\s*)?\)",
    re.I,
)

HUE = 210.0
MAX_SAT = 14.0
CURVE = None
TINT_NEUTRALS = False


def sat_cap(light):
    """按亮度返回饱和度上限。

    平直模式（CURVE 为空）全域用 MAX_SAT，结果偏灰。
    bluetopaz 模式模拟 Blue Topaz 的 --simple-* 色板规律：越亮的面越蓝，
    中间调收敛为蓝灰，暗部略微回升以避免深色模式发死。
    """
    if CURVE != "bluetopaz":
        return MAX_SAT
    if light >= 92:
        return 42.0
    if light >= 80:
        return 24.0
    if light >= 30:
        return 15.0
    return 20.0

stats = {"hsl": 0, "rgb": 0, "skipped_semantic": 0, "already_neutral": 0, "tinted_neutral": 0}


def fmt(n):
    return f"{float(n):.4g}"


def neutral_sat(light):
    """纯中性色要不要染一点色相。

    Blue Topaz 的灰是蓝灰而非中性灰，界面因此整体发凉。纯白与纯黑保持
    不动——给它们染色会让「白」不再是白，反而显脏。
    """
    if not TINT_NEUTRALS or light >= 99 or light <= 2:
        return 0.0
    return min(10.0, sat_cap(light))


def hsl_sub(m):
    _hue, _deg, sat, light, alpha = m.groups()
    if float(sat) == 0:
        ns = neutral_sat(float(light))
        if ns == 0:
            stats["already_neutral"] += 1
            return m.group(0)
        stats["tinted_neutral"] += 1
        if alpha is None:
            return f"hsl({fmt(HUE)}, {fmt(ns)}%, {fmt(light)}%)"
        return f"hsla({fmt(HUE)}, {fmt(ns)}%, {fmt(light)}%, {alpha})"
    stats["hsl"] += 1
    s = min(float(sat), sat_cap(float(light)))
    if alpha is None:
        return f"hsl({fmt(HUE)}, {fmt(s)}%, {fmt(light)}%)"
    return f"hsla({fmt(HUE)}, {fmt(s)}%, {fmt(light)}%, {alpha})"


def rgb_sub(m):
    r, g, b, alpha = m.groups()
    r, g, b = float(r), float(g), float(b)
    _h, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    if r == g == b:
        ns = neutral_sat(light * 100)
        if ns == 0:
            stats["already_neutral"] += 1
            return m.group(0)
        stats["tinted_neutral"] += 1
        s = ns / 100
    else:
        stats["rgb"] += 1
        s = min(sat * 100, sat_cap(light * 100)) / 100
    nr, ng, nb = colorsys.hls_to_rgb(HUE / 360, light, s)
    nr, ng, nb = round(nr * 255), round(ng * 255), round(nb * 255)
    if alpha is None:
        return f"rgb({nr}, {ng}, {nb})"
    return f"rgba({nr}, {ng}, {nb}, {alpha})"


def convert(text):
    # theme.css 是压缩过的，单行可长达数万字符，不能按行判断语义色；
    # 按 `;` / `{` / `}` 切成单条声明，逐条判断。
    chunks = re.split(r"(?<=[;{}])", text)
    out = []
    for chunk in chunks:
        if SEMANTIC.search(chunk):
            if HSL.search(chunk) or RGB.search(chunk):
                stats["skipped_semantic"] += 1
            out.append(chunk)
            continue
        chunk = HSL.sub(hsl_sub, chunk)
        chunk = RGB.sub(rgb_sub, chunk)
        out.append(chunk)
    return "".join(out)


ACCENT_OVERRIDE = """
/* ===== Primary Mono: accent 覆盖 =====
 * 取 Blue Topaz 的 --simple-blue-1 = hsla(209, 95%, 62%) 作强调色，
 * 不受设置面板取色器影响。浅色模式压暗一档以保证文字对比度。
 */
body {
  --accent-h: 209;
  --accent-s: 88%;
  --accent-l: 54%;
}

.theme-dark {
  --accent-l: 62%;
}
"""


def main():
    global HUE, MAX_SAT, CURVE, TINT_NEUTRALS
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    # 带值的参数用 key=value 形式，避免与开关混淆
    for f in flags:
        if f.startswith("--hue="):
            HUE = float(f.split("=", 1)[1])
        elif f.startswith("--max-sat="):
            MAX_SAT = float(f.split("=", 1)[1])
        elif f.startswith("--curve="):
            CURVE = f.split("=", 1)[1]
        elif f == "--tint-neutrals":
            TINT_NEUTRALS = True

    src, dst = args[0], args[1]
    with open(src, encoding="utf-8") as f:
        text = f.read()
    result = convert(text)
    if "--accent-override" in flags:
        result += ACCENT_OVERRIDE
    with open(dst, "w", encoding="utf-8") as f:
        f.write(result)
    cap = f"按亮度分段（{CURVE}）" if CURVE else f"全域封顶 {fmt(MAX_SAT)}%"
    print(f"色相统一为 {fmt(HUE)}，饱和度{cap}")
    print(f"  hsl/hsla 处理 : {stats['hsl']}")
    print(f"  rgb/rgba 处理 : {stats['rgb']}")
    print(f"  语义色跳过    : {stats['skipped_semantic']}")
    print(f"  中性染蓝      : {stats['tinted_neutral']}")
    print(f"  保持中性      : {stats['already_neutral']}")


if __name__ == "__main__":
    main()
