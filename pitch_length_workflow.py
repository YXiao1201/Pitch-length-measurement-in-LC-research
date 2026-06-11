from __future__ import annotations

import argparse
import csv
import importlib
import math
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


IMAGE_SUFFIXES = {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp"}
DEFAULT_IMAGEJ = Path(r"C:\Users\User\Downloads\ij153-win-java8\ImageJ\ImageJ.exe")

np: Any = None
pd: Any = None
plt: Any = None
tifffile: Any = None
Image: Any = None
find_peaks: Any = None
profile_line: Any = None


@dataclass
class Sample:
    name: str
    image_path: Path


def load_dependencies() -> None:
    global np, pd, plt, tifffile, Image, find_peaks, profile_line
    try:
        np = importlib.import_module("numpy")
        pd = importlib.import_module("pandas")
        plt = importlib.import_module("matplotlib.pyplot")
        tifffile = importlib.import_module("tifffile")
        Image = importlib.import_module("PIL.Image")
        scipy_signal = importlib.import_module("scipy.signal")
        skimage_measure = importlib.import_module("skimage.measure")
    except ModuleNotFoundError as exc:
        missing = exc.name or "a required package"
        raise SystemExit(
            f"Missing Python package: {missing}\n"
            "Install dependencies with:\n"
            "  python -m pip install -r requirements.txt"
        ) from exc

    find_peaks = scipy_signal.find_peaks
    profile_line = skimage_measure.profile_line


def discover_samples(input_dir: Path, mesh_path: Path) -> list[Sample]:
    mesh_resolved = mesh_path.resolve()
    samples = []
    for path in sorted(input_dir.iterdir()):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if path.resolve() == mesh_resolved:
            continue
        samples.append(Sample(path.stem, path))
    return samples


def choose_file(title: str, filetypes: list[tuple[str, str]]) -> Path:
    try:
        from tkinter import Tk, filedialog
    except Exception as exc:
        raise SystemExit(f"Could not open file picker. Please provide the path in the command line.\n{exc}") from exc

    root = Tk()
    root.withdraw()
    path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    root.destroy()
    if not path:
        raise SystemExit("No file selected.")
    return Path(path)


def choose_folder(title: str) -> Path:
    try:
        from tkinter import Tk, filedialog
    except Exception as exc:
        raise SystemExit(f"Could not open folder picker. Please provide the path in the command line.\n{exc}") from exc

    root = Tk()
    root.withdraw()
    path = filedialog.askdirectory(title=title)
    root.destroy()
    if not path:
        raise SystemExit("No folder selected.")
    return Path(path)


def resolve_fiji_path(path: Path) -> Path:
    if path.is_file():
        return path

    candidates = [
        path / "ImageJ-win64.exe",
        path / "ImageJ.exe",
        path / "Fiji.exe",
        path / "Contents" / "MacOS" / "ImageJ-macosx",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    matches = list(path.rglob("ImageJ-win64.exe")) + list(path.rglob("ImageJ.exe"))
    if matches:
        return matches[0]

    raise SystemExit(
        f"Could not find the Fiji/ImageJ executable inside:\n  {path}\n\n"
        "Please choose the actual executable, usually ImageJ-win64.exe inside the Fiji.app folder."
    )


def looks_like_placeholder(path: Path | None) -> bool:
    if path is None:
        return True
    text = str(path)
    return "C:\\Path\\To" in text or "/Path/To" in text or "Path\\To" in text


def run_fiji_macro(fiji: Path, macro: Path, mesh: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    done_path = output_dir / "_imagej_batch_done.txt"
    if done_path.exists():
        done_path.unlink()
    macro_args = (
        f"mesh=[{mesh.resolve()}] "
        f"out=[{output_dir.resolve()}] "
        f"done=[{done_path.resolve()}]"
    )
    cmd = [str(fiji), "-macro", str(macro.resolve()), macro_args]
    print("\nOpening ImageJ. Calibrate once, then choose real sample images one by one.")
    print(f"Fiji/ImageJ executable: {fiji}")
    print(f"Macro: {macro.resolve()}")
    process = subprocess.Popen(cmd)
    print("Waiting for the ImageJ macro to finish this measurement batch. You do not need to close ImageJ.")
    while not done_path.exists():
        if process.poll() is not None:
            raise SystemExit("ImageJ closed before the batch-finished marker was written.")
        time.sleep(1)


def read_manifest(output_dir: Path) -> list[Sample]:
    manifest = output_dir / "samples.csv"
    if not manifest.exists():
        samples = []
        for cal_csv in sorted(output_dir.glob("*/*_calibration.csv")):
            row = read_one_row(cal_csv)
            sample_name = row.get("sample") or cal_csv.parent.name
            sample_image = row.get("sample_image")
            if sample_image:
                samples.append(Sample(sample_name, Path(sample_image)))
        if samples:
            return samples
        raise SystemExit(f"ImageJ did not create the sample manifest:\n  {manifest}")
    samples = []
    with manifest.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if not row.get("sample"):
                continue
            samples.append(Sample(row["sample"], Path(row["sample_image"])))
    if not samples:
        raise SystemExit(f"No samples were recorded in:\n  {manifest}")
    return samples


def read_one_row(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"No rows found in {path}")
    return rows[0]


def read_csv_rows(path: Path) -> Any:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return pd.DataFrame(list(csv.DictReader(handle)))


def load_grayscale(path: Path) -> Any:
    try:
        image = tifffile.imread(path)
    except ValueError as exc:
        if "imagecodecs" not in str(exc).lower() and "compression" not in str(exc).lower():
            raise
        pil_image = Image.open(path)
        image = np.asarray(pil_image.convert("L"))
    if image.ndim == 3:
        image = image[..., :3].mean(axis=2)
    image = image.astype(np.float32)
    if image.max() > image.min():
        image = (image - image.min()) / (image.max() - image.min())
    return image


def sample_profile(image: Any, row: Any) -> Any:
    src = (float(row["y1_px"]), float(row["x1_px"]))
    dst = (float(row["y2_px"]), float(row["x2_px"]))
    length = max(2, int(round(float(row["length_px"]))))
    return profile_line(image, src, dst, linewidth=1, mode="reflect", order=1)[:length]


def detect_pitch(profile: Any, unit_per_pixel: float, min_pitch_unit: float) -> dict[str, Any]:
    if profile.size < 5:
        return {"periods": [], "feature_kind": "", "feature_indices": []}

    profile_range = float(np.nanmax(profile) - np.nanmin(profile))
    prominence = max(profile_range * 0.08, float(np.nanstd(profile)) * 0.25)
    min_distance = max(1, int(round(min_pitch_unit / unit_per_pixel))) if min_pitch_unit > 0 else max(2, int(profile.size * 0.02))

    peaks, _ = find_peaks(profile, prominence=prominence, distance=min_distance)
    valleys, _ = find_peaks(-profile, prominence=prominence, distance=min_distance)

    peak_periods = np.diff(peaks) * unit_per_pixel if len(peaks) >= 2 else np.asarray([])
    valley_periods = np.diff(valleys) * unit_per_pixel if len(valleys) >= 2 else np.asarray([])

    peak_score = regularity_score(peak_periods)
    valley_score = regularity_score(valley_periods)

    if peak_score <= valley_score:
        return {"periods": clean_periods(peak_periods), "feature_kind": "peak_to_peak", "feature_indices": [int(x) for x in peaks]}
    return {"periods": clean_periods(valley_periods), "feature_kind": "valley_to_valley", "feature_indices": [int(x) for x in valleys]}


def unit_to_um(unit: str) -> float:
    normalized = unit.strip().lower()
    if normalized == "mm":
        return 1000.0
    if normalized in {"um", "µm"}:
        return 1.0
    if normalized == "nm":
        return 0.001
    return 1.0


def regularity_score(periods: Any) -> float:
    if len(periods) == 0:
        return 1e9
    if len(periods) == 1:
        return 0.5
    mean = float(np.mean(periods))
    if mean <= 0:
        return 1e9
    return float(np.std(periods) / mean)


def clean_periods(periods: Any) -> list[float]:
    return [float(v) for v in periods if math.isfinite(float(v)) and float(v) > 0]


def mean_sd(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], 0.0
    return float(np.mean(values)), float(np.std(values, ddof=1))


def compact_name(name: str, max_length: int = 32) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in name)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return (cleaned or "sample")[:max_length]


def write_profile_plot(sample_out: Path, sample: str, index: int, profile: Any, result: dict[str, Any], unit_per_pixel_um: float) -> Path:
    plot_dir = sample_out.parent / "profile_plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    x = np.arange(profile.size) * unit_per_pixel_um
    feature_indices = result["feature_indices"]

    fig, ax = plt.subplots(figsize=(7, 3.5), constrained_layout=True)
    ax.plot(x, profile, color="black", linewidth=1)
    if feature_indices:
        ax.scatter(x[feature_indices], profile[feature_indices], color="red", s=22)
    ax.set_title(f"{sample} profile {index}")
    ax.set_xlabel("Distance (um)")
    ax.set_ylabel("Normalized intensity")
    out = plot_dir / f"{compact_name(sample)}_profile_{index}.png"
    fig.savefig(out, dpi=180)
    plt.close(fig)
    return out


def copy_if_exists(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        shutil.copy2(source, destination)
    return destination


def analyze_sample(sample: Sample, sample_out: Path, min_pitch_unit: float) -> dict[str, Any]:
    calibration = read_one_row(sample_out / f"{sample.name}_calibration.csv")
    rois = read_csv_rows(sample_out / f"{sample.name}_roi_data.csv")
    selected_sample_path = Path(calibration["sample_image"])
    image = load_grayscale(selected_sample_path)
    unit = calibration["unit"]
    unit_per_pixel = float(calibration["unit_per_pixel"])
    unit_per_pixel_um = unit_per_pixel * unit_to_um(unit)
    min_pitch_um = min_pitch_unit * unit_to_um(unit)

    profile_records = []
    period_records = []
    all_periods = []
    profiles = rois[rois["kind"] == "pitch_profile"]

    for _, row in profiles.iterrows():
        index = int(row["index"])
        profile = sample_profile(image, row)
        result = detect_pitch(profile, unit_per_pixel_um, min_pitch_um)
        periods_um = result["periods"]
        periods = periods_um
        pitch_lengths = [2 * value for value in periods]
        all_periods.extend(periods)
        plot_path = write_profile_plot(sample_out, sample.name, index, profile, result, unit_per_pixel_um)
        mean_period, sd_period = mean_sd(periods)
        mean_pitch, sd_pitch = mean_sd(pitch_lengths)

        profile_records.append(
            {
                "sample": sample.name,
                "image_source": str(selected_sample_path),
                "profile_index": index,
                "number_of_drawn_lines": len(profiles),
                "n_periodic_lengths": len(periods),
                "mean_periodic_length_um": mean_period,
                "sd_periodic_length_um": sd_period,
                "mean_pitch_length_um": mean_pitch,
                "sd_pitch_length_um": sd_pitch,
                "_plot_path": str(plot_path),
            }
        )

        for period_index, value in enumerate(periods, start=1):
            period_records.append(
                {
                    "sample": sample.name,
                    "image_source": str(selected_sample_path),
                    "profile_index": index,
                    "periodic_length_index": period_index,
                    "periodic_length_um": value,
                    "pitch_length_um": 2 * value,
                    "feature_kind": result["feature_kind"],
                }
            )

    average, sd = mean_sd(all_periods)
    line_mean_pitch_lengths = [
        float(record["mean_pitch_length_um"])
        for record in profile_records
        if record["mean_pitch_length_um"] is not None and pd.notna(record["mean_pitch_length_um"])
    ]
    average_pitch, sd_pitch = mean_sd(line_mean_pitch_lengths)
    calibration_record = {
        "sample": sample.name,
        "image_source": str(selected_sample_path),
        "mesh_image": calibration["mesh_image"],
        "calibration_pixels": float(calibration["calibration_pixels"]),
        "mesh_periods_drawn": float(calibration["mesh_periods_drawn"]),
        "periods_per_mm": float(calibration["periods_per_unit"]),
        "unit": unit,
        "unit_per_pixel": unit_per_pixel,
        "um_per_pixel": unit_per_pixel_um,
    }
    summary = {
        "sample": sample.name,
        "image": str(selected_sample_path),
        "number_of_drawn_lines": len(profile_records),
        "n_profiles": len(profile_records),
        "n_periodic_lengths": len(all_periods),
        "final_average_pitch_length_um": average_pitch,
        "final_sd_pitch_length_um": sd_pitch,
        "labelled_image": str(sample_out / f"{sample.name}_labelled.tif"),
    }
    return {"summary": summary, "calibration": calibration_record, "profiles": profile_records, "periods": period_records}


def organize_visual_outputs(results: list[dict[str, Any]], output_dir: Path) -> None:
    labelled_dir = output_dir / "labelled_images"
    plot_dir = output_dir / "profile_plots"

    for result in results:
        sample = result["summary"]["sample"]
        labelled_source = Path(result["summary"]["labelled_image"])
        labelled_destination = labelled_dir / f"{compact_name(sample)}_labelled.tif"
        copy_if_exists(labelled_source, labelled_destination)
        result["summary"]["labelled_image"] = str(labelled_destination)

        for profile in result["profiles"]:
            plot_source_text = profile.get("_plot_path")
            if not plot_source_text:
                continue
            plot_source = Path(plot_source_text)
            if plot_source.parent.resolve() == plot_dir.resolve():
                profile["_plot_path"] = str(plot_source)
            else:
                plot_destination = plot_dir / plot_source.name
                copy_if_exists(plot_source, plot_destination)
                profile["_plot_path"] = str(plot_destination)


def clean_working_csvs(results: list[dict[str, Any]], output_dir: Path) -> None:
    for result in results:
        sample = result["summary"]["sample"]
        sample_dir = output_dir / sample
        for suffix in ("_roi_data.csv", "_calibration.csv"):
            path = sample_dir / f"{sample}{suffix}"
            if path.exists():
                path.unlink()
    manifest = output_dir / "samples.csv"
    if manifest.exists():
        manifest.unlink()
    done_marker = output_dir / "_imagej_batch_done.txt"
    if done_marker.exists():
        done_marker.unlink()


def write_excel(results: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    calibration = pd.DataFrame([result["calibration"] for result in results])
    raw_periodicity = pd.DataFrame([item for result in results for item in result["periods"]])
    line_results = pd.DataFrame([item for result in results for item in result["profiles"]])
    final_results = pd.DataFrame([result["summary"] for result in results])
    if not line_results.empty:
        line_results = line_results[[column for column in line_results.columns if not str(column).startswith("_")]]

    try:
        writer_context = pd.ExcelWriter(output_path, engine="openpyxl")
    except PermissionError:
        output_path = output_path.with_name(output_path.stem + "_updated" + output_path.suffix)
        writer_context = pd.ExcelWriter(output_path, engine="openpyxl")

    with writer_context as writer:
        calibration.to_excel(writer, index=False, sheet_name="calibration")
        raw_periodicity.to_excel(writer, index=False, sheet_name="periodicity_raw_data")
        line_results.to_excel(writer, index=False, sheet_name="line_results")
        final_results.to_excel(writer, index=False, sheet_name="final_results")
        for sheet_name in ("calibration", "periodicity_raw_data", "line_results", "final_results"):
            ws = writer.book[sheet_name]
            ws.freeze_panes = "A2"
            for column_cells in ws.columns:
                width = min(70, max(12, max(len(str(cell.value or "")) for cell in column_cells) + 2))
                ws.column_dimensions[column_cells[0].column_letter].width = width
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mesh-calibrated pitch length measurement workflow.")
    parser.add_argument("--fiji", type=Path, help="Path to Fiji/ImageJ executable.")
    parser.add_argument("--mesh", type=Path, help="Mesh calibration image.")
    parser.add_argument("--output", type=Path, help="Output folder.")
    parser.add_argument("--min-pitch", type=float, default=0.0, help="Minimum expected pitch in the selected calibration unit. Use 0 for automatic.")
    parser.add_argument("--skip-fiji", action="store_true", help="Reuse existing ImageJ CSV outputs and only run Python analysis.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dependencies()

    if not args.skip_fiji and looks_like_placeholder(args.fiji) and DEFAULT_IMAGEJ.exists():
        args.fiji = DEFAULT_IMAGEJ
    elif not args.skip_fiji and looks_like_placeholder(args.fiji):
        try:
            args.fiji = choose_file(
                "Choose Fiji/ImageJ executable, for example ImageJ.exe",
                [("Executable files", "*.exe"), ("All files", "*.*")],
            )
        except SystemExit:
            args.fiji = choose_folder("Choose Fiji.app folder")
    if looks_like_placeholder(args.mesh):
        args.mesh = choose_file(
            "Choose mesh calibration image",
            [("Image files", "*.tif *.tiff *.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")],
        )
    if args.output is None or looks_like_placeholder(args.output):
        args.output = choose_folder("Choose your measurement results folder. The Excel table will be saved here.")

    output_dir = args.output.resolve()
    print(f"\nMeasurement results folder: {output_dir}")
    mesh = args.mesh.resolve()
    if args.fiji is not None:
        args.fiji = resolve_fiji_path(args.fiji.resolve())
    macro = Path(__file__).with_name("pitch_length_interactive.ijm")

    if not args.skip_fiji:
        if args.fiji is None:
            print("Missing --fiji. Provide the path to Fiji/ImageJ, or use --skip-fiji to reuse existing CSV outputs.")
            return 1
        run_fiji_macro(args.fiji, macro, mesh, output_dir)

    samples = read_manifest(output_dir)
    print("\nSamples recorded by ImageJ:")
    for sample in samples:
        print(f"  {sample.name}: {sample.image_path}")

    results = [analyze_sample(sample, output_dir / sample.name, args.min_pitch) for sample in samples]
    organize_visual_outputs(results, output_dir)
    excel_path = output_dir / "pitch_length_results.xlsx"
    excel_path = write_excel(results, excel_path)
    clean_working_csvs(results, output_dir)
    print(f"\nDone. Combined Excel results: {excel_path}")
    print("Labelled images are in labelled_images. Plot profiles are in profile_plots.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
