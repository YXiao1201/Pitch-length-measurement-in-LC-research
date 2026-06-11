// Fiji/ImageJ macro for interactive pitch-length ROI collection.
// Called by pitch_length_workflow.py with:
// ImageJ.exe -macro pitch_length_interactive.ijm "mesh=[...] sample=[...] name=[...] out=[...]"
//
// Flow:
// 1. Open mesh image and calibrate from a user-drawn line.
// 2. Open real/sample image.
// 3. Draw profile lines one at a time. Each line runs Plot Profile.
// 4. Ask whether to continue drawing lines.
// 5. If no, start scale-bar labelling.
// 6. When the batch is finished, write a done marker so Python can save results
//    without waiting for ImageJ itself to close.

macro "Pitch Length Interactive" {
    meshPath = getArgumentValue("mesh");
    outDir = getArgumentValue("out");
    donePath = getArgumentValue("done");

    if (meshPath == "" || outDir == "") {
        exit("Missing macro arguments. Required: mesh, out.");
    }

    File.makeDirectory(outDir);
    manifestCsv = outDir + File.separator + "samples.csv";
    if (File.exists(manifestCsv)) File.delete(manifestCsv);
    if (donePath != "" && File.exists(donePath)) File.delete(donePath);
    File.append("sample,sample_image,sample_out\n", manifestCsv);

    open(meshPath);
    meshTitle = getTitle();

    Dialog.create("Mesh calibration");
    Dialog.addNumber("Mesh periods covered by your drawn line", 10);
    Dialog.addNumber("Mesh periods per 1 mm", 50);
    Dialog.addMessage("Calibration is fixed from the mesh standard.\nDefault: 50 mesh lines = 1 mm.\nDraw across any convenient number of mesh periods.");
    Dialog.show();
    unit = "mm";
    meshPeriods = Dialog.getNumber();
    periodsPerUnit = Dialog.getNumber();
    knownDistance = meshPeriods / periodsPerUnit;

    waitForUser("Calibration line", "Draw a straight line across exactly " + meshPeriods + " mesh periods, then click OK.");
    if (selectionType() != 5) {
        exit("Calibration selection must be a straight line.");
    }
    getLine(cx1, cy1, cx2, cy2, cw);
    calibrationPixels = sqrt((cx2 - cx1) * (cx2 - cx1) + (cy2 - cy1) * (cy2 - cy1));
    unitPerPixel = knownDistance / calibrationPixels;
    selectWindow(meshTitle);
    close(meshTitle);

    sampleIndex = 1;
    continueSamples = true;
    while (continueSamples) {
        samplePath = File.openDialog("Open real sample image for pitch measurement");
        if (samplePath == "") exit("No real sample image selected.");

        sampleName = stripExtension(getFileName(samplePath));
        if (sampleName == "") sampleName = "sample_" + sampleIndex;
        sampleOut = outDir + File.separator + sampleName;
        File.makeDirectory(sampleOut);

        roiCsv = sampleOut + File.separator + sampleName + "_roi_data.csv";
        calCsv = sampleOut + File.separator + sampleName + "_calibration.csv";
        labelledPath = sampleOut + File.separator + sampleName + "_labelled.tif";

        if (File.exists(roiCsv)) File.delete(roiCsv);
        if (File.exists(calCsv)) File.delete(calCsv);
        if (File.exists(labelledPath)) File.delete(labelledPath);

        File.append("sample,kind,index,x1_px,y1_px,x2_px,y2_px,length_px,length_unit,note\n", roiCsv);
        File.append("sample,mesh_image,sample_image,calibration_pixels,mesh_periods_drawn,periods_per_unit,unit,unit_per_pixel\n", calCsv);
        File.append(sampleName + "," + meshPath + "," + samplePath + "," + calibrationPixels + "," + meshPeriods + "," + periodsPerUnit + "," + unit + "," + unitPerPixel + "\n", calCsv);
        File.append(sampleName + "," + samplePath + "," + sampleOut + "\n", manifestCsv);

        open(samplePath);
        sampleTitle = getTitle();
        run("Set Scale...", "distance=1 known=" + unitPerPixel + " unit=" + unit + " global");
        roiManager("reset");

        i = 1;
        continueDrawing = true;
        while (continueDrawing) {
            selectWindow(sampleTitle);
            waitForUser("Pitch profile " + i, "Draw profile line " + i + " across the periodic pattern, then click OK.");
            if (selectionType() != 5) {
                exit("Profile " + i + " must be a straight line.");
            }
            getLine(px1, py1, px2, py2, pw);
            lengthPx = sqrt((px2 - px1) * (px2 - px1) + (py2 - py1) * (py2 - py1));
            lengthUnit = lengthPx * unitPerPixel;
            roiManager("Add");
            roiManager("Select", roiManager("count") - 1);
            roiManager("Rename", "pitch_profile_" + i);
            File.append(sampleName + ",pitch_profile," + i + "," + px1 + "," + py1 + "," + px2 + "," + py2 + "," + lengthPx + "," + lengthUnit + ",user_line_on_sample_image\n", roiCsv);
            run("Plot Profile");

            continueDrawing = getBoolean("Do you still wanna continue draw lines?");
            i++;
        }

        Dialog.create("Scale bar label");
        Dialog.addChoice("Scale bar unit", newArray("mm", "um", "nm"), unit);
        Dialog.addNumber("Scale bar length as integer", 1);
        Dialog.addMessage("Fixed format:\nWhite color\n25 pixel height\n60 pt font\nText underneath\nLower right corner");
        Dialog.show();
        scaleUnit = Dialog.getChoice();
        scaleLength = round(Dialog.getNumber());
        if (scaleLength <= 0) exit("Scale bar length must be a positive integer.");

        scaleLengthInCalibrationUnit = convertLength(scaleLength, scaleUnit, unit);
        scalePixels = scaleLengthInCalibrationUnit / unitPerPixel;

        selectWindow(sampleTitle);
        run("Duplicate...", "title=" + sampleName + "_labelled");
        labelledTitle = getTitle();
        run("RGB Color");
        drawScaleBar(scalePixels, scaleLength, scaleUnit);
        saveAs("Tiff", labelledPath);
        close(labelledTitle);
        close(sampleTitle);

        continueSamples = getBoolean("Do you want to open another real sample image?");
        sampleIndex++;
    }

    if (donePath != "") File.saveString("done\n", donePath);
    showMessage("Batch finished", "No more sample images selected.\nPython will now save the final Excel table, labelled images, and profile plots.\nYou can keep ImageJ open.");
}

function getArgumentValue(key) {
    args = getArgument();
    start = indexOf(args, key + "=[");
    if (start < 0) start = indexOf(args, key + "=");
    if (start < 0) return "";
    start = indexOf(args, key + "=") + lengthOf(key) + 1;
    if (substring(args, start, start + 1) == "[") {
        start = start + 1;
        stop = indexOf(args, "]", start);
        return substring(args, start, stop);
    }
    stop = indexOf(args, " ", start);
    if (stop < 0) stop = lengthOf(args);
    return substring(args, start, stop);
}

function getFileName(path) {
    slash = lastPositionOf(path, File.separator);
    if (slash < 0) slash = lastPositionOf(path, "/");
    if (slash < 0) slash = lastPositionOf(path, "\\");
    if (slash < 0) return path;
    return substring(path, slash + 1);
}

function stripExtension(name) {
    dot = lastPositionOf(name, ".");
    if (dot < 0) return name;
    return substring(name, 0, dot);
}

function lastPositionOf(text, pattern) {
    last = -1;
    start = 0;
    while (start < lengthOf(text)) {
        found = indexOf(text, pattern, start);
        if (found < 0) return last;
        last = found;
        start = found + 1;
    }
    return last;
}

function convertLength(value, fromUnit, toUnit) {
    valueInMm = value * unitToMm(fromUnit);
    return valueInMm / unitToMm(toUnit);
}

function unitToMm(unitName) {
    if (unitName == "mm") return 1;
    if (unitName == "um") return 0.001;
    if (unitName == "µm") return 0.001;
    if (unitName == "nm") return 0.000001;
    return 1;
}

function drawScaleBar(barPx, labelValue, labelUnit) {
    barPx = round(barPx);
    if (barPx < 1) barPx = 1;
    if (barPx > getWidth() - 80) barPx = getWidth() - 80;

    label = d2s(labelValue, 0) + " " + labelUnit;
    bx = round(getWidth() - barPx - 60);
    by = getHeight() - 115;
    if (bx < 20) bx = 20;

    setColor("white");
    makeRectangle(bx, by - 12, barPx, 25);
    run("Fill");

    setFont("SansSerif", 60, "bold");
    labelWidth = getStringWidth(label);
    tx = round(bx + (barPx - labelWidth) / 2);
    if (tx < 20) tx = 20;
    drawString(label, tx, by + 80);
}
