# Periodic Length Measurement Workflow

This workflow follows the same style as the `SEM analysis` project:

- ImageJ/Fiji opens images and lets you draw lines interactively.
- Python reads the saved line data, samples profiles, detects periodic lengths, saves profile plots, and writes Excel results.

## Install

```powershell
python -m pip install -r requirements.txt
```

## Run

Easiest option:

```powershell
python pitch_length_workflow.py
```

The script will open pop-up windows to choose:

- Fiji/ImageJ executable
- mesh calibration image
- output folder

Advanced option with paths typed manually:

```powershell
python pitch_length_workflow.py --fiji "C:\Path\To\ImageJ.exe" --mesh "C:\Path\To\mesh_image.tif" --output "C:\Path\To\pitch_results"
```

Replace the example paths above with your real paths. Do not run them exactly as written.

## ImageJ Steps

Fiji asks you to:

1. Open the mesh calibration image.
2. Enter how many mesh periods your calibration line crosses.
3. Enter how many mesh periods equal 1 mm, normally `50`.
4. The workflow calibrates internally in `mm` using the mesh standard: 50 lines = 1 mm.
5. Draw the calibration line on the mesh.
6. Choose/open a real sample image.
7. Draw one pitch profile line on the sample image.
8. ImageJ runs `Plot Profile` for that line and saves the line coordinates.
9. Answer `Yes` to `Do you still wanna continue draw lines?` to draw another line on the same sample.
10. Answer `No` to start scale-bar labelling for that sample.
11. Choose the scale bar display unit (`mm`, `um`, or `nm`) and enter an integer scale bar length.
12. Close/save that labelled sample image.
13. Answer `Yes` to `Do you want to open another real sample image?` to continue with another image.

Python then exports:

- combined `pitch_length_results.xlsx` in the output folder
- per-sample `*_periodic_lengths.xlsx` inside each sample folder, next to the labelled image and plot folder
- per-sample ROI/calibration CSV files
- profile plots with detected pitch points
- `*_labelled.tif` images with a scale bar in the lower right corner
- `samples.csv`, showing every measured image source and output folder

Periodic length results are reported in `um`.

Use `--min-pitch` if Python detects small false periods. The value is still entered in the calibration unit, which is `mm` from the mesh calibration.

Scale bar format is fixed:

- white color
- 25 pixel height
- 60 pt font
- text underneath the scale bar
- lower right corner
