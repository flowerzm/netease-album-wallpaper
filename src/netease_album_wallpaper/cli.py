from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .netease import NeteaseError
from .pipeline import generate_wallpaper


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="netease-album-wallpaper",
        description="粘贴网易云公开歌单链接，生成按颜色自然排列的专辑封面墙。",
    )
    parser.add_argument(
        "playlist",
        nargs="?",
        help="163cn.tv 短链、完整歌单链接、纯数字 ID 或整段分享文案",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("wallpaper.png"), help="输出 PNG 路径"
    )
    parser.add_argument("--covers-dir", type=Path, help="保留下载的原始封面到此目录")
    parser.add_argument("--width", type=int, default=3840, help="画布宽度，默认 3840")
    parser.add_argument("--height", type=int, default=2400, help="画布高度，默认 2400")
    parser.add_argument("--gap", type=int, default=10, help="封面间距，默认 10")
    parser.add_argument("--radius", type=int, help="圆角半径；默认按封面尺寸自动计算")
    parser.add_argument("--background", default="#090c13", help="背景色，默认 #090c13")
    parser.add_argument("--workers", type=int, default=4, help="下载并发数，默认 4，最大 8")
    parser.add_argument("--retries", type=int, default=2, help="封面下载重试次数，默认 2")
    parser.add_argument("--iterations", type=int, help="色彩排列优化次数；默认按封面数量计算")
    parser.add_argument("--no-shadow", action="store_true", help="关闭封面阴影")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    playlist_input = args.playlist
    if not playlist_input:
        playlist_input = input("请粘贴网易云歌单链接或分享文案：").strip()
    if not playlist_input:
        print("错误：没有提供歌单链接或 ID", file=sys.stderr)
        return 2

    try:
        result = generate_wallpaper(
            playlist_input=playlist_input,
            output=args.output,
            covers_dir=args.covers_dir,
            width=args.width,
            height=args.height,
            gap=args.gap,
            radius=args.radius,
            background=args.background,
            workers=args.workers,
            retries=args.retries,
            iterations=args.iterations,
            shadow=not args.no_shadow,
            progress=print,
        )
    except (NeteaseError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n已取消", file=sys.stderr)
        return 130

    print(f"完成：{result.wallpaper.resolve()}")
    print(f"布局：{result.layout_csv.resolve()}")
    print(f"清单：{result.manifest_json.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

