"""
build.py - turn the source code into a Windows installer, in 3 steps:

    1. Artwork : make app.ico and the setup wizard pictures from logo/play.png
    2. App     : PyInstaller bundles Python + Qt + libmpv + our code into dist/DialogueBoostPlayer/
    3. Setup   : Inno Setup packs that folder into release/DialogueBoostPlayer_Setup_<version>.exe

Run it with:   python build.py
Needs:         pip install -r requirements-build.txt   and Inno Setup 6 (https://jrsoftware.org/isdl.php)
"""

import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import app_info

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "assets")
LOGO = os.path.join(ROOT, "logo", "play.png")
FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def font(name, size):
    try:
        return ImageFont.truetype(os.path.join(FONTS, name), size)
    except OSError:
        return ImageFont.load_default()


# ---------------------------------------------------------------- 1. artwork
def make_icon():
    """A Windows .ico holds the same picture in several sizes."""
    logo = Image.open(LOGO).convert("RGBA")
    logo.save(os.path.join(ASSETS, "app.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                                      (64, 64), (128, 128), (256, 256)])


def vertical_gradient(width, height, top, bottom):
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / (height - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    return image


def make_wizard_side_image():
    """The tall picture on the left of the setup wizard's first and last page.
    Drawn once at 410x797 (250% DPI size) and scaled down for smaller screens."""
    w, h = 410, 797
    img = vertical_gradient(w, h, (40, 46, 120), (12, 14, 24)).convert("RGBA")

    # soft glow behind the logo
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([w / 2 - 170, 70, w / 2 + 170, 410], fill=(110, 125, 255, 120))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(60)))

    logo = Image.open(LOGO).convert("RGBA").resize((210, 210), Image.LANCZOS)
    img.alpha_composite(logo, ((w - 210) // 2, 135))

    draw = ImageDraw.Draw(img)

    def centered(text, y, fnt, fill):
        width = draw.textlength(text, font=fnt)
        draw.text(((w - width) / 2, y), text, font=fnt, fill=fill)

    centered("Dialogue Boost", 390, font("segoeuib.ttf", 40), (255, 255, 255))
    centered("Player", 438, font("segoeuib.ttf", 40), (255, 255, 255))
    centered(f"Version {app_info.VERSION}", 498, font("segoeui.ttf", 20), (182, 186, 208))

    draw.line([(70, 580), (w - 70, 580)], fill=(255, 255, 255, 50), width=2)
    centered("BUILT BY", 605, font("seguisb.ttf", 18), (142, 162, 255))
    centered(app_info.AUTHOR, 634, font("segoeuib.ttf", 30), (255, 255, 255))
    centered("github.com/tamimrijan", 690, font("segoeui.ttf", 20), (182, 186, 208))
    centered("@tamim_ahmed_rijan", 720, font("segoeui.ttf", 20), (182, 186, 208))

    img = img.convert("RGB")
    names = []
    # Inno Setup picks the size that best fits the user's display scaling.
    for scale, (sw, sh) in {100: (164, 314), 150: (246, 471), 200: (328, 628), 250: (410, 797)}.items():
        name = f"wizard_large_{scale}.png"
        img.resize((sw, sh), Image.LANCZOS).save(os.path.join(ASSETS, name))
        names.append(name)
    return names


def make_wizard_small_image():
    """The small logo in the top-right corner of the other wizard pages."""
    logo = Image.open(LOGO).convert("RGBA")
    for scale, size in {100: 55, 150: 83, 200: 110, 250: 138}.items():
        logo.resize((size, size), Image.LANCZOS).save(os.path.join(ASSETS, f"wizard_small_{scale}.png"))


def make_version_file():
    """Windows shows this in the .exe's Properties > Details tab."""
    major, minor, patch = (int(x) for x in app_info.VERSION.split("."))
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({major}, {minor}, {patch}, 0), prodvers=({major}, {minor}, {patch}, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', '{app_info.AUTHOR}'),
      StringStruct('FileDescription', '{app_info.APP_NAME}'),
      StringStruct('FileVersion', '{app_info.VERSION}'),
      StringStruct('InternalName', '{app_info.EXE_NAME}'),
      StringStruct('LegalCopyright', 'Copyright (C) 2026 {app_info.AUTHOR}'),
      StringStruct('OriginalFilename', '{app_info.EXE_NAME}.exe'),
      StringStruct('ProductName', '{app_info.APP_NAME}'),
      StringStruct('ProductVersion', '{app_info.VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)"""
    path = os.path.join(ASSETS, "version_info.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# ---------------------------------------------------------------- 2. app
def build_app(version_file):
    """--onedir (a folder, not one big .exe) starts much faster, and the
    installer puts that folder in Program Files anyway."""
    for folder in ("build", os.path.join("dist", app_info.EXE_NAME)):
        shutil.rmtree(os.path.join(ROOT, folder), ignore_errors=True)
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onedir", "--windowed",
        "--name", app_info.EXE_NAME,
        "--icon", os.path.join(ASSETS, "app.ico"),
        "--version-file", version_file,
        "--add-binary", f"{os.path.join(ROOT, 'libmpv-2.dll')};.",
        "--add-data", f"{os.path.join(ROOT, 'logo')};logo",
        "--add-data", f"{os.path.join(ROOT, 'fonts')};fonts",     # Roboto Flex + Material Symbols
        "main.py",
    ], cwd=ROOT, check=True)
    shutil.rmtree(os.path.join(ROOT, "build"), ignore_errors=True)


# ---------------------------------------------------------------- 3. setup
def find_iscc():
    candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe"),
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    return next((c for c in candidates if os.path.isfile(c)), shutil.which("ISCC"))


def build_installer():
    iscc = find_iscc()
    if not iscc:
        sys.exit("Inno Setup 6 not found. Install it from https://jrsoftware.org/isdl.php and run again.")
    subprocess.run([iscc, f"/DAppVersion={app_info.VERSION}", os.path.join(ROOT, "installer", "setup.iss")],
                   check=True)


if __name__ == "__main__":
    if not os.path.isfile(os.path.join(ROOT, "libmpv-2.dll")):
        sys.exit("libmpv-2.dll is missing. See README.md.")
    os.makedirs(ASSETS, exist_ok=True)
    print("== 1/3 Artwork ==")
    make_icon()
    make_wizard_side_image()
    make_wizard_small_image()
    version_file = make_version_file()
    print("== 2/3 Building the app with PyInstaller ==")
    build_app(version_file)
    print("== 3/3 Building the setup wizard with Inno Setup ==")
    build_installer()
    print(f"\nDone! Installer: release\\{app_info.EXE_NAME}_Setup_{app_info.VERSION}.exe")
