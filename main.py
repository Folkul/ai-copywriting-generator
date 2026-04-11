"""命令行：1～9 张本地图 → 千问 VL → DeepSeek / 千问文本 生成朋友圈文案。"""
from __future__ import annotations

import argparse
import sys

from llm.caption import describe_caption_providers, generate_caption, list_caption_providers
from prompts import OUTPUT_LANGUAGE_INSTRUCTIONS
from vision_tools import get_image_description


def _print_provider_help() -> None:
    print("文案后端（--provider / 环境变量 CAPTION_PROVIDER）：")
    for pid, label, ok in describe_caption_providers():
        flag = "已配置" if ok else "未配置密钥"
        print(f"  {pid:10}  {label:24}  [{flag}]")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="根据 1～9 张图片生成朋友圈文案（视觉：千问 VL；文案：DeepSeek 或通义千问）"
    )
    parser.add_argument(
        "images",
        nargs="+",
        metavar="IMAGE",
        help="本地图片路径，1～9 张（可多写几个路径）",
    )
    parser.add_argument("--style", default="幽默风趣", help="文案风格")
    parser.add_argument("--length", default="不超过50字", help="字数要求说明")
    parser.add_argument(
        "--provider",
        choices=list_caption_providers(),
        default=None,
        help="文案模型：deepseek 或 qwen（默认读 CAPTION_PROVIDER）",
    )
    parser.add_argument(
        "--emoji",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否允许 emoji（默认允许，使用 --no-emoji 关闭）",
    )
    parser.add_argument(
        "--punctuation",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否使用标点（默认使用，使用 --no-punctuation 关闭）",
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="列出文案后端与密钥配置状态后退出",
    )
    parser.add_argument(
        "--supplement",
        default="",
        help="补充要求：想法、喜欢的示例、避雷点等（会写入提示词）",
    )
    parser.add_argument(
        "--language",
        choices=sorted(OUTPUT_LANGUAGE_INSTRUCTIONS.keys()),
        default="zh-Hans",
        help="文案输出语言（默认简体中文）",
    )
    args = parser.parse_args(argv)

    if args.list_providers:
        _print_provider_help()
        return 0

    if len(args.images) > 9:
        print("错误：最多 9 张图片。", file=sys.stderr)
        return 2

    description = get_image_description(args.images)
    if not description:
        return 1

    sup = (args.supplement or "").strip() or None
    if sup and len(sup) > 4000:
        sup = sup[:4000]

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
        return 1

    print("\n--- 最终文案 ---")
    print(caption)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
