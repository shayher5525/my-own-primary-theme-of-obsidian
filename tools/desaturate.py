#!/usr/bin/env python3
"""把 Obsidian Primary 主题的 theme.css 转为灰阶配色。

规则：
- hsl()/hsla()  -> 色相 0、饱和度 0%，保留亮度与 alpha
- rgb()/rgba()  -> 按 Rec.709 亮度转灰，保留 alpha
- 语义色（error/warning/success/danger/caution/invalid/fail）所在的声明行跳过，保留原色
- 已是中性色（R=G=B 或 S=0%）不计入改动数

用法: python3 desaturate.py <输入 css> <输出 css>
"""
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

stats = {"hsl": 0, "rgb": 0, "skipped_semantic": 0, "already_neutral": 0}


def fmt(n):
    """去掉多余小数点，1.0 -> 1"""
    s = f"{float(n):.4g}"
    return s


def hsl_sub(m):
    _hue, _deg, sat, light, alpha = m.groups()
    if float(sat) == 0:
        stats["already_neutral"] += 1
        return m.group(0)
    stats["hsl"] += 1
    if alpha is None:
        return f"hsl(0, 0%, {fmt(light)}%)"
    return f"hsla(0, 0%, {fmt(light)}%, {alpha})"


def rgb_sub(m):
    r, g, b, alpha = m.groups()
    r, g, b = float(r), float(g), float(b)
    if r == g == b:
        stats["already_neutral"] += 1
        return m.group(0)
    stats["rgb"] += 1
    y = round(0.2126 * r + 0.7152 * g + 0.0722 * b)
    if alpha is None:
        return f"rgb({y}, {y}, {y})"
    return f"rgba({y}, {y}, {y}, {alpha})"


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
/* ===== Primary Mono: 中性 accent 覆盖 =====
 * 强制把 Obsidian 的 accent 色相/饱和度归零，使链接、选中态、
 * 按钮高亮统一走中性灰，不受设置面板取色器影响。
 */
body {
  --accent-h: 0;
  --accent-s: 0%;
  --accent-l: 42%;
}

.theme-dark {
  --accent-l: 62%;
}
"""


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    src, dst = args[0], args[1]
    with open(src, encoding="utf-8") as f:
        text = f.read()
    result = convert(text)
    # accent 覆盖只追加到最终产物，避免在多个文件里重复定义
    if "--accent-override" in flags:
        result += ACCENT_OVERRIDE
    with open(dst, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"hsl/hsla 转灰      : {stats['hsl']}")
    print(f"rgb/rgba 转灰      : {stats['rgb']}")
    print(f"语义色行跳过（保留）: {stats['skipped_semantic']}")
    print(f"本就中性、未动      : {stats['already_neutral']}")


if __name__ == "__main__":
    main()
