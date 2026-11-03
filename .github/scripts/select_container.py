#!/usr/bin/env python3
import json
import os
from pathlib import Path

GITHUB_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = GITHUB_DIR / "config.json"
IMAGES_FILE = GITHUB_DIR / "images.json"


def load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default


def main():
    cfg = load_json(CONFIG_FILE, {})
    images = load_json(IMAGES_FILE, {})

    distro = str(cfg.get("distro", "auto")).lower().strip()
    fallback_default = dict(images.get("default", {
        "image": "debian:latest",
        "install": "apt-get update && apt-get install -y git python3",
        "fallback": True,
    }))
    fallback_default["fallback"] = True

    selected = images.get(distro) if distro != "auto" else None
    if not selected:
        selected = fallback_default
        fallback = True
    else:
        fallback = bool(selected.get("fallback", False))

    image = (selected.get("image") or "").strip()
    install = (selected.get("install") or fallback_default["install"]).strip()
    if not image:
        image = fallback_default["image"]
        fallback = True

    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a") as f:
            f.write(f"image={image}\n")
            f.write(f"install={install}\n")
            f.write(f"fallback={'true' if fallback else 'false'}\n")
    else:
        print(f"image={image}")
        print(f"install={install}")
        print(f"fallback={'true' if fallback else 'false'}")


if __name__ == "__main__":
    main()
