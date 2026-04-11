"""快速测试：1～9 张图 → 描述 → 文案。"""
from __future__ import annotations

import argparse
import sys

from llm.caption import generate_three_captions, parse_three_candidates
from prompts import OUTPUT_LANGUAGE_INSTRUCTIONS
from vision_tools import generate_caption, get_image_description


def main() -> int:
    p = argparse.ArgumentParser(description="测试千问 VL + DeepSeek/千问文案")
    p.add_argument(
        "images",
        nargs="*",
        default=["test.jpg"],
        metavar="IMAGE",
        help="本地图片，1～9 张；不写则默认 test.jpg",
    )
    p.add_argument("--style", default="幽默风趣", help="文案风格")
    p.add_argument("--length", default="不超过50字", help="字数要求")
    p.add_argument(
        "--provider",
        default=None,
        help="deepseek 或 qwen（默认读 CAPTION_PROVIDER）",
    )
    p.add_argument(
        "--emoji",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="--no-emoji 关闭 emoji",
    )
    p.add_argument(
        "--punctuation",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="--no-punctuation 关闭标点",
    )
    p.add_argument(
        "--supplement",
        default="",
        help="补充要求（想法、示例、避雷等）",
    )
    p.add_argument(
        "--language",
        choices=sorted(OUTPUT_LANGUAGE_INSTRUCTIONS.keys()),
        default="zh-Hans",
        help="文案输出语言",
    )
    p.add_argument(
        "--three",
        action="store_true",
        help="与网页一致：一次生成三条候选（否则只输出一条）",
    )
    p.add_argument("--min-chars", type=int, default=10, help="--three 时最短字数")
    p.add_argument("--max-chars", type=int, default=72, help="--three 时最长字数")
    args = p.parse_args()

    if len(args.images) > 9:
        print("错误：最多 9 张图片。", file=sys.stderr)
        return 2

    description = get_image_description(args.images)
    if not description:
        print("图片分析失败，请检查 QWEN_API_KEY 与图片路径。")
        return 1

    sup = (args.supplement or "").strip() or None
    if sup and len(sup) > 4000:
        sup = sup[:4000]

    if args.three:
        raw = generate_three_captions(
            description,
            args.style,
            args.length,
            args.min_chars,
            args.max_chars,
            provider=args.provider,
            use_emoji=args.emoji,
            use_punctuation=args.punctuation,
            diversify=False,
            supplement=sup,
            output_language=args.language,
            temperature=0.82,
            verbose=False,
        )
        if not raw:
            print("文案生成失败，请检查 DEEPSEEK_API_KEY / QWEN_API_KEY 与网络。")
            return 1
        cands = parse_three_candidates(raw)
        print("\n✨ 三条候选（与网页同逻辑）✨")
        for i, t in enumerate(cands[:3], start=1):
            print(f"\n候选{i}：{t}")
        if len(cands) < 3:
            print("\n（解析不足 3 条，原始输出如下）\n")
            print(raw)
        return 0

    caption = generate_caption(
        description,
        style=args.style,
        length=args.length,
        provider=args.provider,
        use_emoji=args.emoji,
        use_punctuation=args.punctuation,
        supplement=sup,
        output_language=args.language,
    )
    if not caption:
        print("文案生成失败，请检查 DEEPSEEK_API_KEY / QWEN_API_KEY 与网络。")
        return 1

    print("\n✨ 生成的朋友圈文案 ✨")
    print(caption)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
