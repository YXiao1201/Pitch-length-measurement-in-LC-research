from __future__ import annotations

import subprocess
from pathlib import Path
from tkinter import Tk, filedialog


DEFAULT_IMAGEJ = Path(r"C:\Users\User\Downloads\ij153-win-java8\ImageJ\ImageJ.exe")


def choose_file(title: str, filetypes: list[tuple[str, str]]) -> Path:
    root = Tk()
    root.withdraw()
    path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    root.destroy()
    if not path:
        raise SystemExit("No file selected.")
    return Path(path)


def resolve_imagej(path: Path) -> Path:
    if path.is_file():
        return path

    candidates = [
        path / "ImageJ-win64.exe",
        path / "ImageJ.exe",
        path / "Fiji.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    matches = list(path.rglob("ImageJ-win64.exe")) + list(path.rglob("ImageJ.exe"))
    if matches:
        return matches[0]

    raise SystemExit(f"Could not find ImageJ executable inside: {path}")


def main() -> int:
    if DEFAULT_IMAGEJ.exists():
        imagej_path = DEFAULT_IMAGEJ
    else:
        imagej_path = choose_file(
            "Choose ImageJ/Fiji executable, usually ImageJ.exe",
            [("Executable files", "*.exe"), ("All files", "*.*")],
        )
    image_path = choose_file(
        "Choose image to open in ImageJ",
        [("Image files", "*.tif *.tiff *.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")],
    )

    imagej_path = resolve_imagej(imagej_path)
    print(f"Opening ImageJ/Fiji:\n  {imagej_path}")
    print(f"Opening image:\n  {image_path}")

    subprocess.Popen([str(imagej_path), str(image_path)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
