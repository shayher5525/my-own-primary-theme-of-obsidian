#!/usr/bin/env python3
"""把 Obsidian Primary 主题的配色统一到单一色相。

规则：
- hsl()/hsla()  -> 色相改为 --hue，饱和度按 --max-sat 封顶，保留亮度与 alpha
- rgb()/rgba()  -> 转 HSL 后同样处理，再转回 rgb，保留 alpha
- 语义色（error/warning/success/danger/caution/invalid/fail）所在声明跳过，保留原色
- 已是中性色（S=0% 或 R=G=B）不动

饱和度用「封顶」而非「缩放」：原本就淡的颜色保持淡，原本浓的压到上限，
结果是整体色调统一且亮度层次不变。

用法:
    python3 recolor.py <输入> <输出> [--hue=210] [--max-sat=14] [--accent-override]

--max-sat 0 等价于转灰阶。
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

stats = {"hsl": 0, "rgb": 0, "skipped_semantic": 0, "already_neutral": 0}


def fmt(n):
    return f"{float(n):.4g}"


def hsl_sub(m):
    _hue, _deg, sat, light, alpha = m.groups()
    if float(sat) == 0:
        stats["already_neutral"] += 1
        return m.group(0)
    stats["hsl"] += 1
    s = min(float(sat), MAX_SAT)
    if alpha is None:
        return f"hsl({fmt(HUE)}, {fmt(s)}%, {fmt(light)}%)"
    return f"hsla({fmt(HUE)}, {fmt(s)}%, {fmt(light)}%, {alpha})"


def rgb_sub(m):
    r, g, b, alpha = m.groups()
    r, g, b = float(r), float(g), float(b)
    if r == g == b:
        stats["already_neutral"] += 1
        return m.group(0)
    stats["rgb"] += 1
    _h, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    s = min(sat * 100, MAX_SAT) / 100
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
 * 强制 accent 走主色相，不受设置面板取色器影响。
 */
body {
  --accent-h: 210;
  --accent-s: 32%;
  --accent-l: 45%;
}

.theme-dark {
  --accent-l: 62%;
}
"""


def main():
    global HUE, MAX_SAT
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    # 带值的参数用 key=value 形式，避免与开关混淆
    for f in flags:
        if f.startswith("--hue="):
            HUE = float(f.split("=", 1)[1])
        elif f.startswith("--max-sat="):
            MAX_SAT = float(f.split("=", 1)[1])

    src, dst = args[0], args[1]
    with open(src, encoding="utf-8") as f:
        text = f.read()
    result = convert(text)
    if "--accent-override" in flags:
        result += ACCENT_OVERRIDE
    with open(dst, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"色相统一为 {fmt(HUE)}，饱和度封顶 {fmt(MAX_SAT)}%")
    print(f"  hsl/hsla 处理 : {stats['hsl']}")
    print(f"  rgb/rgba 处理 : {stats['rgb']}")
    print(f"  语义色跳过    : {stats['skipped_semantic']}")
    print(f"  本就中性      : {stats['already_neutral']}")


if __name__ == "__main__":
    main()
