// -------------------------------------------------------
// AUTO BUILD FROM JSON - MACBOOKVISUALS
// -------------------------------------------------------

function importJobData() {
    // Prompt user to select job_data.json
    var jsonFile = File.openDialog("Select your job_data.json file", "*.json");
    if (!jsonFile) return null;

    jsonFile.open("r");
    var jsonText = jsonFile.read();
    jsonFile.close();

    try {
        return JSON.parse(jsonText);
    } catch (e) {
        alert("Error parsing JSON: " + e.toString());
        return null;
    }
}

// -------------------------------------------------------
// MAIN SCRIPT
// -------------------------------------------------------

function main() {
    app.beginUndoGroup("Auto Music Video Build");

    var job = importJobData();
    if (!job) {
        alert("No JSON data found.");
        return;
    }

    // Paths from JSON
    var audioFile = new File(job.audio_trimmed);
    var imageFile = new File(job.cover_image);
    var lyricsFile = new File(job.lyrics_file);
    var colors = job.colors;

    // Import audio and image
    var importOptsAudio = new ImportOptions(audioFile);
    var importOptsImage = new ImportOptions(imageFile);

    var audioItem = app.project.importFile(importOptsAudio);
    var imageItem = app.project.importFile(importOptsImage);

    // Locate your main template comp
    var templateComp = app.project.item(1); // change index if needed
    if (templateComp.name !== "3D Apple Music") {
        // Optionally find by name
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name === "3D Apple Music") {
                templateComp = app.project.item(i);
                break;
            }
        }
    }

    // Duplicate the template comp for the new job
    var newComp = templateComp.duplicate();
    newComp.name = "MV_JOB_" + job.job_id;

    // Replace placeholders
    replaceLayer(newComp, "AUDIO", audioItem);
    replaceLayer(newComp, "COVER", imageItem);

    // Apply colors to gradient or background layers
    updateBackgroundColors(newComp, colors);

    // Inject lyrics JSON into the control layer (next phase)

    app.endUndoGroup();
    alert("✅ Build complete for Job " + job.job_id);
}

// -------------------------------------------------------
// HELPER FUNCTIONS
// -------------------------------------------------------

function replaceLayer(comp, layerName, newItem) {
    for (var i = 1; i <= comp.numLayers; i++) {
        if (comp.layer(i).name === layerName) {
            comp.layer(i).replaceSource(newItem, false);
            return;
        }
    }
}

function updateBackgroundColors(comp, colors) {
    // Example: Apply to a 4-Color Gradient effect named "4-Color Gradient"
    for (var i = 1; i <= comp.numLayers; i++) {
        var lyr = comp.layer(i);
        if (lyr.property("Effects") && lyr.property("Effects")("4-Color Gradient")) {
            var effect = lyr.property("Effects")("4-Color Gradient");
            for (var j = 0; j < colors.length; j++) {
                var aeColor = hexToRGB(colors[j]);
                effect.property("Color " + (j + 1)).setValue(aeColor);
            }
        }
    }
}

function hexToRGB(hex) {
    hex = hex.replace("#", "");
    var r = parseInt(hex.substring(0, 2), 16) / 255;
    var g = parseInt(hex.substring(2, 4), 16) / 255;
    var b = parseInt(hex.substring(4, 6), 16) / 255;
    return [r, g, b];
}

// -------------------------------------------------------
main();
