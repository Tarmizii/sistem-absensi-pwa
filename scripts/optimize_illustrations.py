"""Re-encode v2 illustrations to a display-appropriate width (B1.2).

The v2 illustrations were authored at 1402-1647px but render at 12-25rem
(192-400 CSS px). At 2x density the largest physical render is ~800px, so
downscaling to 800px keeps the visuals sharp on real devices while cutting
the precache payload that ships to students.

Quality is preserved deliberately: this script only rescales and re-encodes at
a high quality tier, it never recompresses an already-smaller file upward and
never touches the master PNGs in design/illustrations/v2/.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

MAX_WIDTH = 800
QUALITY = 92
METHOD = 6


def optimize(source_dir: Path, dry_run: bool = False) -> None:
    for path in sorted(source_dir.glob("*-v2.webp")):
        with Image.open(path) as image:
            width, height = image.size
            if width <= MAX_WIDTH:
                print(f"skip  {path.name} ({width}px already within budget)")
                continue
            scale = MAX_WIDTH / width
            target = (MAX_WIDTH, max(1, round(height * scale)))
            if dry_run:
                print(f"would {path.name}: {width}x{height} -> {target[0]}x{target[1]}")
                continue
            resized = image.resize(target, Image.LANCZOS)
            before = path.stat().st_size
            resized.save(path, "WEBP", quality=QUALITY, method=METHOD)
            after = path.stat().st_size
            print(
                f"ok    {path.name}: {width}x{height} -> {target[0]}x{target[1]}, "
                f"{before / 1024:.1f}KB -> {after / 1024:.1f}KB"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("app/static/illustrations"),
        help="directory holding the *-v2.webp files",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report the planned resize without writing"
    )
    args = parser.parse_args()
    optimize(args.source_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
