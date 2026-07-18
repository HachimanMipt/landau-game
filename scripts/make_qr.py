"""Create a QR code PNG for the deployed game URL.

Usage:
    python scripts/make_qr.py https://your-game.onrender.com
"""

from __future__ import annotations

import argparse
from pathlib import Path

import qrcode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Public HTTPS URL to encode")
    parser.add_argument(
        "-o",
        "--output",
        default="landau-game-qr.png",
        help="Output PNG path (default: landau-game-qr.png)",
    )
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    image = qrcode.make(args.url)
    image.save(output)
    print(f"Saved QR code to {output}")


if __name__ == "__main__":
    main()
