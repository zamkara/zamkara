#!/usr/bin/env python3
import os
import re
import sys
import json
import html
import platform
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GITHUB_DIR = REPO_ROOT / ".github"
CONFIG_FILE = GITHUB_DIR / "config.json"
ASCII_DIR = GITHUB_DIR / "ascii"
DISTROS_FILE = ASCII_DIR / "distros.json"
SVG_FILE = GITHUB_DIR / "neofetch.svg"
README_FILE = REPO_ROOT / "README.md"

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to parse config.json ({e}), using defaults.")
    return {}

def load_distro_meta():
    if DISTROS_FILE.exists():
        try:
            with open(DISTROS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def get_user_at_host(cfg):
    custom = cfg.get("user", "auto")
    if custom and custom != "auto":
        return custom

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        repo_name = repo.split("/")[-1]
        return f"{repo_name}@github"
    try:
        r = subprocess.run(["git", "config", "--get", "remote.origin.url"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            url = r.stdout.strip()
            repo_name = url.split("/")[-1].replace(".git", "")
            if repo_name:
                return f"{repo_name}@github"
    except Exception:
        pass
    return "github@github"

def get_os_name():
    pretty = None
    if os.path.exists("/etc/os-release"):
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        pretty = line.split("=", 1)[1].strip("\"' \n")
                        break
                    elif line.startswith("NAME=") and not pretty:
                        pretty = line.split("=", 1)[1].strip("\"' \n")
        except Exception:
            pass
    if not pretty:
        pretty = "Arch Linux"
    return f"{pretty} [{platform.machine()}]"

def get_kernel(cfg):
    custom = cfg.get("kernel", "auto")
    if custom and custom != "auto":
        return custom

    distro_key = cfg.get("distro", "arch").lower()

    if "arch" in distro_key or "arch" in get_os_name().lower():
        try:
            rel = platform.release().strip()
            if "zen" in rel:
                return f"{rel} ({platform.machine()})"
        except Exception:
            pass

        try:
            url = "https://archlinux.org/packages/extra/x86_64/linux-zen/json/"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (GitHubActions)"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                pkgver = data.get("pkgver", "")
                pkgrel = data.get("pkgrel", "")
                if pkgver and pkgrel:
                    formatted = pkgver.replace(".zen", "-zen") + f"-{pkgrel}-zen"
                    return f"{formatted} ({platform.machine()})"
        except Exception:
            pass

    return f"{platform.release()} ({platform.machine()})"

def github_api_request(path):
    url = f"https://api.github.com/{path.lstrip('/')}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Mozilla/5.0 (GitHubActions)",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_github_username():
    username = os.environ.get("GITHUB_USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER")
    if username:
        return username.strip()

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        return repo.split("/", 1)[0].strip()

    try:
        r = subprocess.run(["git", "config", "--get", "remote.origin.url"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            url = r.stdout.strip()
            match = re.search(r"github\.com[:/]([^/]+)/", url)
            if match:
                return match.group(1)
    except Exception:
        pass

    raise RuntimeError("Unable to determine GitHub username")


def get_github_profile():
    username = get_github_username()
    profile = github_api_request(f"users/{username}")
    created_at = datetime.strptime(profile["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    public_total = int(profile.get("public_repos", 0)) + int(profile.get("public_gists", 0))
    account_seconds = max(int((datetime.now(timezone.utc) - created_at).total_seconds()), 0)
    return account_seconds, public_total

def get_memory():
    try:
        meminfo = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    meminfo[key] = int(val)

        total_mb = meminfo.get("MemTotal", 0) // 1024
        avail_mb = meminfo.get("MemAvailable", meminfo.get("MemFree", 0)) // 1024
        used_mb = total_mb - avail_mb
        pct = (used_mb / total_mb * 100) if total_mb > 0 else 0
        return f"{used_mb}MiB / {total_mb}MiB ({pct:.1f}%)"
    except Exception:
        return "0MiB / 0MiB (0%)"

def format_uptime(total_seconds):
    days = int(total_seconds // 86400)
    hours = int((total_seconds % 86400) // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")

    return " ".join(parts)

def get_distro_ascii(cfg, distros_meta):
    distro_choice = cfg.get("distro", "arch").lower().strip()

    if distro_choice == "auto":
        os_lower = get_os_name().lower()
        for k in distros_meta:
            if k in os_lower:
                distro_choice = k
                break
        if distro_choice == "auto":
            distro_choice = "arch"

    meta = distros_meta.get(distro_choice, {})
    logo_color = meta.get("color", "#1793d1")

    # Read from .github/ascii/<distro>.txt
    txt_file = ASCII_DIR / f"{distro_choice}.txt"
    logo_lines = []
    if txt_file.exists():
        try:
            with open(txt_file, "r") as f:
                logo_lines = [l.rstrip("\r\n") for l in f.readlines()]
                # Strip trailing empty lines
                while logo_lines and not logo_lines[-1].strip():
                    logo_lines.pop()
        except Exception:
            pass

    if not logo_lines:
        logo_lines = [
            "       /\\",
            "      /  \\",
            "     /\\   \\",
            "    /      \\",
            "   /   ,,   \\",
            "  /   |  |  -\\",
            " /_-''    ''-_\\",
        ]

    custom_col = cfg.get("custom_colors", {})
    if custom_col.get("logo"):
        logo_color = custom_col["logo"]

    return logo_lines, logo_color

def generate_neofetch_svg(cfg, distros_meta, user_header, os_name, host_name, kernel_name, uptime_str, pkgs_count, memory_str):
    logo_lines, logo_color = get_distro_ascii(cfg, distros_meta)

    info_rows = [
        ("", user_header, True),
        ("os        ", os_name, False),
        ("host      ", host_name, False),
        ("kernel    ", kernel_name, False),
        ("uptime    ", uptime_str, False),
        ("pkgs      ", pkgs_count, False),
        ("memory    ", memory_str, False),
    ]

    total_rows = max(len(logo_lines), len(info_rows))

    fontSize = 13
    lineHeight = 16
    paddingY = 8
    logo_x = 8
    charWidth = 7.8

    max_logo_w = max(len(l) for l in logo_lines) if logo_lines else 14
    max_info_w = max(len(t + v) for t, v, _ in info_rows)

    info_x = int(logo_x + max_logo_w * charWidth + 24)
    width = int(info_x + max_info_w * charWidth + 16)
    height = int(total_rows * lineHeight) + paddingY * 2

    custom_col = cfg.get("custom_colors", {})
    header_color = (custom_col.get("title") or "").strip() or "#58a6ff"
    title_color = (custom_col.get("title") or "").strip() or "#58a6ff"
    val_color = (custom_col.get("value") or "").strip() or "#c9d1d9"

    svg_lines = []
    for i in range(total_rows):
        y = int(paddingY + (i + 1) * lineHeight - 3)

        # Col 1: Logo (rendered at fixed logo_x)
        if i < len(logo_lines) and logo_lines[i].strip():
            esc_logo = html.escape(logo_lines[i])
            svg_lines.append(f'  <text x="{logo_x}" y="{y}" xml:space="preserve" class="logo">{esc_logo}</text>')

        # Col 2: Info (rendered at fixed info_x)
        if i < len(info_rows):
            title, val, is_header = info_rows[i]
            if is_header:
                esc_val = html.escape(val)
                svg_lines.append(f'  <text x="{info_x}" y="{y}" xml:space="preserve" class="header">{esc_val}</text>')
            elif title or val:
                esc_title = html.escape(title)
                esc_val = html.escape(val)
                svg_lines.append(f'  <text x="{info_x}" y="{y}" xml:space="preserve"><tspan class="title">{esc_title}</tspan><tspan class="val">{esc_val}</tspan></text>')

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <style>
    text {{
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
      font-size: {fontSize}px;
    }}
    .logo {{ fill: {logo_color}; font-weight: bold; }}
    .header {{ fill: {header_color}; font-weight: bold; }}
    .title {{ fill: {title_color}; font-weight: 600; }}
    .val {{ fill: {val_color}; }}
    @media (prefers-color-scheme: light) {{
      .header {{ fill: #0969da; }}
      .title {{ fill: #0969da; }}
      .val {{ fill: #24292f; }}
    }}
  </style>
""" + "\n".join(svg_lines) + "\n</svg>\n"
    return svg_content

def update_readme():
    cfg = load_config()
    distros_meta = load_distro_meta()

    user = get_user_at_host(cfg)
    os_name = get_os_name()
    host_name = cfg.get("host", "ASUS TUF Gaming F15 FX506LH_FX506LH 1.0")
    if host_name == "auto":
        host_name = "ASUS TUF Gaming F15 FX506LH_FX506LH 1.0"

    kernel_name = get_kernel(cfg)
    account_age_seconds, public_total = get_github_profile()
    uptime_str = format_uptime(account_age_seconds)
    pkgs_count = f"{public_total} (github)"
    memory_str = get_memory()

    # Generate .github/neofetch.svg
    SVG_FILE.parent.mkdir(parents=True, exist_ok=True)
    svg_content = generate_neofetch_svg(cfg, distros_meta, user, os_name, host_name, kernel_name, uptime_str, pkgs_count, memory_str)
    with open(SVG_FILE, "w") as f:
        f.write(svg_content)

    # Clean up any leftover neofetch.svg in root if exists
    root_svg = REPO_ROOT / "neofetch.svg"
    if root_svg.exists():
        root_svg.unlink()

    # Generate root README.md referencing .github/neofetch.svg
    readme_content = f"""<p align="left">
  <img src=".github/neofetch.svg" alt="{user}" />
</p>
"""
    with open(README_FILE, "w") as f:
        f.write(readme_content)

    print(".github/neofetch.svg and README.md updated successfully:")
    print(svg_content)

if __name__ == "__main__":
    update_readme()
