// -------------------------------------------------------
// APOLLOVA AURORA - After Effects Automation
// Uses pre-injected paths from GUI (no folder prompt)
// -------------------------------------------------------

// -----------------------------
// INJECTED PATHS (replaced by GUI)
// -----------------------------
var JOBS_PATH = "{{JOBS_PATH}}";
var TEMPLATE_PATH = "{{TEMPLATE_PATH}}";

// -----------------------------
// JSON Polyfill (for older AE)
// -----------------------------
if (typeof JSON === "undefined") {
    JSON = {};
    JSON.parse = function (s) {
        try { return eval("(" + s + ")"); }
        catch (e) { alert("Error parsing JSON: " + e.toString()); return null; }
    };
    JSON.stringify = function (obj) {
        var t = typeof obj;
        if (t !== "object" || obj === null) {
            if (t === "string") obj = '"' + obj + '"';
            return String(obj);
        } else {
            var n, v, json = [], arr = (obj && obj.constructor === Array);
            for (n in obj) {
                v = obj[n];
                t = typeof v;
                if (t === "string") v = '"' + v + '"';
                else if (t === "object" && v !== null) v = JSON.stringify(v);
                json.push((arr ? "" : '"' + n + '":') + String(v));
            }
            return (arr ? "[" : "{") + String(json) + (arr ? "]" : "}");
        }
    };
}


// -----------------------------
// MAIN
// -----------------------------
function main() {
    app.beginUndoGroup("Batch Music Video Build");

    clearAllJobComps();

    // Use injected path or fallback to prompt
    var jobsFolder;
    if (JOBS_PATH.indexOf("{{") === -1 && JOBS_PATH !== "") {
        jobsFolder = new Folder(JOBS_PATH);
        $.writeln("Using injected jobs path: " + JOBS_PATH);
    } else {
        jobsFolder = Folder.selectDialog("Select your /jobs folder");
    }
    
    if (!jobsFolder || !jobsFolder.exists) {
        alert("Jobs folder not found: " + JOBS_PATH);
        return;
    }

    var subfolders = jobsFolder.getFiles(function (f) { return f instanceof Folder; });
    var jsonFiles = [];
    
    for (var i = 0; i < subfolders.length; i++) {
        var files = subfolders[i].getFiles("job_data.json");
        if (files && files.length > 0) {
            jsonFiles.push(files[0]);
        }
    }
    
    if (jsonFiles.length === 0) {
        alert("No job_data.json files found inside subfolders of " + jobsFolder.fsName);
        return;
    }

    for (var j = 0; j < jsonFiles.length; j++) {
        var jobFile = jsonFiles[j];
        if (!jobFile.exists || !jobFile.open("r")) continue;
        var jsonText = jobFile.read();
        jobFile.close();
        if (!jsonText) continue;

        var jobData;
        try { jobData = JSON.parse(jsonText); }
        catch (e) { alert("Error parsing " + jobFile.name + ": " + e.toString()); continue; }

        var jobFolder = jobFile.parent;
        
        jobData.audio_trimmed = toAbsolute(jobData.audio_trimmed) || (jobFolder.fsName + "/audio_trimmed.wav");
        jobData.cover_image   = toAbsolute(jobData.cover_image) || (jobFolder.fsName + "/cover.png");
        jobData.lyrics_file   = toAbsolute(jobData.lyrics_file) || (jobFolder.fsName + "/lyrics.txt");
        jobData.job_folder    = jobFolder.fsName.replace(/\\/g, "/");

        $.writeln("──────── Job " + jobData.job_id + " ────────");

        var audioFile = new File(jobData.audio_trimmed);
        var imageFile = new File(jobData.cover_image);
        if (!audioFile.exists) { alert("Missing audio:\n" + jobData.audio_trimmed); continue; }
        if (!imageFile.exists) { alert("Missing image:\n" + jobData.cover_image); continue; }

        // Duplicate MAIN
        var template = findCompByName("MAIN");
        var newComp = template.duplicate();
        newComp.name = "MV_JOB_" + ("00" + jobData.job_id).slice(-3);

        moveItemToFolder(newComp, "OUTPUT" + jobData.job_id);
        relinkFootageInsideOutputFolder(jobData.job_id, jobData.audio_trimmed, jobData.cover_image);
        autoResizeCoverInOutput(jobData.job_id);
        setWorkAreaToAudioDuration(jobData.job_id);
        setOutputWorkAreaToAudio(jobData.job_id, jobData.audio_trimmed);
        updateSongTitle(jobData.job_id, jobData.song_title);
        applyBackgroundColors(jobData.job_id, jobData.colors);
        applyComplementarySpectrumColor(jobData.job_id, jobData.colors[0]);

        try {
            applyBeatSync(jobData.job_id, jobData.beats);
            $.writeln("Applied beat sync for job " + jobData.job_id);
        } catch (e) {
            $.writeln("Beat sync failed for job " + jobData.job_id + ": " + e.toString());
        }

        var outputComp, lyricComp;
        try { outputComp = findCompByName("OUTPUT " + jobData.job_id); }
        catch (e) { $.writeln("Missing OUTPUT " + jobData.job_id + " — skipping job."); continue; }
        try { lyricComp = findCompByName("LYRIC FONT " + jobData.job_id); }
        catch (e) { $.writeln("Missing LYRIC FONT " + jobData.job_id + " — skipping job."); continue; }

        var parsed = parseLyricsFile(jobData.lyrics_file);
        pushLyricsToCarousel(lyricComp, parsed.linesArray);
        setAudioMarkersFromTArray(lyricComp, parsed.tAndText);

        try {
            var assetsComp = findCompByName("Assets " + jobData.job_id);
            retargetImageLayersToFootage(assetsComp, "COVER");
            $.writeln("Album art retargeted to COVER for job " + jobData.job_id);
        } catch (e) {
            $.writeln("Assets " + jobData.job_id + " not found — skipping album art.");
        }

        try {
            var renderPath = addToRenderQueue(
                outputComp,
                jobData.job_folder,
                jobData.job_id,
                jobData.song_title
            );
            $.writeln("Queued: " + renderPath);
        } catch (e) {
            $.writeln("Render queue error: " + e);
        }
    }

    alert("All " + jsonFiles.length + " jobs processed!\n\nReview in Render Queue, then click Render.");
    app.endUndoGroup();
}


// -----------------------------
// Helper Functions
// -----------------------------

function findFolderByName(name) {
    for (var i = 1; i <= app.project.numItems; i++) {
        var it = app.project.item(i);
        if (it instanceof FolderItem && it.name === name) return it;
    }
    return null;
}

function moveItemToFolder(item, folderName) {
    var folder = findFolderByName(folderName);
    if (folder) item.parentFolder = folder;
}

function toAbsolute(p) {
    if (!p) return p;
    p = p.replace(/\\/g, "/");
    var f = new File(p);
    if (f.exists) return f.fsName.replace(/\\/g, "/");
    var base = File($.fileName).parent.parent.parent;
    f = new File(base.fsName + "/" + p);
    return f.fsName.replace(/\\/g, "/");
}

function hexToRGB(hex) {
    if (!hex || typeof hex !== "string") return [1, 1, 1];
    hex = hex.replace("#", "");
    try {
        return [
            parseInt(hex.substring(0, 2), 16) / 255,
            parseInt(hex.substring(2, 4), 16) / 255,
            parseInt(hex.substring(4, 6), 16) / 255
        ];
    } catch (e) { return [1, 1, 1]; }
}

function findCompByName(name) {
    for (var i = 1; i <= app.project.numItems; i++) {
        var it = app.project.item(i);
        if (it instanceof CompItem && it.name === name) return it;
    }
    throw new Error("Comp not found: " + name);
}

function readTextFile(p) {
    var f = new File(p);
    f.open("r");
    var t = f.read();
    f.close();
    return t;
}

function parseLyricsFile(p) {
    var raw = readTextFile(p);
    var data = JSON.parse(raw);
    
    var linesArray = [];
    var tAndText = [];
    
    for (var i = 0; i < data.length; i++) {
        var seg = data[i];
        var text = seg.lyric_current || seg.text || "";
        if (text) {
            linesArray.push(text);
            tAndText.push({ t: seg.t || seg.time || 0, text: text });
        }
    }
    
    return { linesArray: linesArray, tAndText: tAndText };
}

function pushLyricsToCarousel(lyricComp, linesArray) {
    for (var i = 0; i < linesArray.length && i < 50; i++) {
        try {
            var layer = lyricComp.layer("Line " + (i + 1));
            if (layer && layer.property("Source Text")) {
                var doc = layer.property("Source Text").value;
                doc.text = linesArray[i];
                layer.property("Source Text").setValue(doc);
            }
        } catch (e) {}
    }
}

function setAudioMarkersFromTArray(lyricComp, tAndText) {
    var audio = ensureAudioLayer(lyricComp);
    if (!audio) return;
    
    var mk = audio.property("Marker");
    if (!mk) return;
    
    for (var i = mk.numKeys; i >= 1; i--) mk.removeKey(i);
    
    for (var i = 0; i < tAndText.length; i++) {
        var item = tAndText[i];
        var mv = new MarkerValue(item.text);
        mk.setValueAtTime(item.t, mv);
    }
}

function ensureAudioLayer(comp) {
    for (var i = 1; i <= comp.numLayers; i++) {
        var lyr = comp.layer(i);
        if (lyr.name.toUpperCase() === "AUDIO") return lyr;
    }
    return null;
}

function relinkFootageInsideOutputFolder(jobId, audioPath, imagePath) {
    var folder = findFolderByName("OUTPUT" + jobId);
    if (!folder) return;

    for (var i = 1; i <= folder.numItems; i++) {
        var it = folder.item(i);
        if (!(it instanceof FootageItem)) continue;
        var n = it.name.toUpperCase();

        if (n.indexOf("AUDIO") !== -1 || n.indexOf("WAV") !== -1 || n.indexOf("MP3") !== -1) {
            var af = new File(audioPath);
            if (af.exists) try { it.replace(af); } catch(e) {}
        }
        if (n.indexOf("COVER") !== -1 || n.indexOf("IMAGE") !== -1 || n.indexOf("ART") !== -1) {
            var imgf = new File(imagePath);
            if (imgf.exists) try { it.replace(imgf); } catch(e) {}
        }
    }
}

function autoResizeCoverInOutput(jobId) {
    var comp;
    try { comp = findCompByName("OUTPUT " + jobId); } catch(_) { return; }

    for (var i = 1; i <= comp.numLayers; i++) {
        var lyr = comp.layer(i);
        if (!(lyr instanceof AVLayer)) continue;
        var isCover = (lyr.name.toUpperCase() === "COVER") || (lyr.source && lyr.source.name.toUpperCase() === "COVER");
        if (!isCover) continue;

        var lw = lyr.source.width, lh = lyr.source.height;
        if (!lw || !lh) continue;
        var scale = 100 * Math.max(comp.width / lw, comp.height / lh);
        try {
            lyr.property("Scale").setValue([scale, scale]);
            lyr.property("Position").setValue([comp.width / 2, comp.height / 2]);
        } catch(e) {}
        return;
    }
}

function setWorkAreaToAudioDuration(jobId) {
    var comp;
    try { comp = findCompByName("LYRIC FONT " + jobId); } catch(_) { return; }
    var audio = ensureAudioLayer(comp);
    if (!audio || !audio.source || !audio.source.duration) return;
    var dur = audio.source.duration;
    comp.duration = dur;
    comp.workAreaStart = 0;
    comp.workAreaDuration = dur;
}

function setOutputWorkAreaToAudio(jobId, audioPath) {
    var audioFile = new File(audioPath);
    if (!audioFile.exists) return;
    var imported = app.project.importFile(new ImportOptions(audioFile));
    var dur = imported.duration;
    imported.remove();

    try {
        var outputComp = findCompByName("OUTPUT " + jobId);
        outputComp.duration = dur;
        outputComp.workAreaStart = 0;
        outputComp.workAreaDuration = dur;
    } catch(e) {}

    try {
        var lyricComp = findCompByName("LYRIC FONT " + jobId);
        lyricComp.duration = dur;
        lyricComp.workAreaStart = 0;
        lyricComp.workAreaDuration = dur;
    } catch(e) {}
}

function updateSongTitle(jobId, titleText) {
    if (!titleText) return;
    try {
        var assetsComp = findCompByName("Assets " + jobId);
        for (var i = 1; i <= assetsComp.numLayers; i++) {
            var lyr = assetsComp.layer(i);
            var txtProp = lyr.property("Source Text");
            if (txtProp) {
                var doc = txtProp.value;
                doc.text = String(titleText);
                txtProp.setValue(doc);
                return;
            }
        }
    } catch (e) {}
}

function applyBackgroundColors(jobId, colors) {
    if (!colors || colors.length < 2) return;
    var bgComp;
    try { bgComp = findCompByName("BACKGROUND " + jobId); } catch (_) { return; }

    var gradientLayer = bgComp.layer("Gradient");
    if (!gradientLayer) return;

    var effectParade = gradientLayer.property("ADBE Effect Parade");
    if (!effectParade) return;

    var gradient4Color = effectParade.property("4-Color Gradient");
    if (!gradient4Color) return;

    try {
        var c1 = gradient4Color.property("Color 1");
        var c2 = gradient4Color.property("Color 2");
        var c3 = gradient4Color.property("Color 3");
        var c4 = gradient4Color.property("Color 4");
        if (c1) c1.setValue(hexToRGB(colors[0]));
        if (c2) c2.setValue(hexToRGB(colors[1]));
        if (c3) c3.setValue(hexToRGB(colors.length > 2 ? colors[2] : colors[0]));
        if (c4) c4.setValue(hexToRGB(colors[0]));
    } catch (e) {}
}

function applyComplementarySpectrumColor(jobId, baseHexColor) {
    try {
        var comp = findCompByName("Assets " + jobId);
        var target = null;
        for (var i = 1; i <= comp.numLayers; i++) {
            if (comp.layer(i).name === "Black Solid 1") { target = comp.layer(i); break; }
        }
        if (!target) return;

        var fx = target.property("ADBE Effect Parade").property("Audio Spectrum");
        if (!fx) return;

        var hex = baseHexColor.replace("#", "");
        var compColor = [
            (255 - parseInt(hex.substr(0, 2), 16)) / 255,
            (255 - parseInt(hex.substr(2, 2), 16)) / 255,
            (255 - parseInt(hex.substr(4, 2), 16)) / 255
        ];

        var inside = fx.property("Inside Color");
        var outside = fx.property("Outside Color");
        if (inside) inside.setValue(compColor);
        if (outside) outside.setValue(compColor);
    } catch (err) {}
}

function applyBeatSync(jobId, beatsArray) {
    if (!beatsArray || beatsArray.length < 2) return;
    var comp = findCompByName("OUTPUT " + jobId);
    if (!comp) return;
    var layer = comp.layer("Spot Light 2");
    if (!layer) return;

    var intensity = layer.property("ADBE Light Options Group") && layer.property("ADBE Light Options Group").property("ADBE Light Intensity");
    if (!intensity) intensity = layer.property("Light Options") && layer.property("Light Options").property("Intensity");
    if (!intensity) return;

    for (var k = intensity.numKeys; k >= 1; k--) intensity.removeKey(k);

    var PEAK = 75, BASE = 15;
    var oneFrame = 1 / comp.frameRate;

    for (var i = 0; i < beatsArray.length - 1; i++) {
        var t = beatsArray[i];
        var nextT = beatsArray[i + 1];
        intensity.setValueAtTime(t, PEAK);
        var tBase = nextT - oneFrame;
        if (tBase > t) intensity.setValueAtTime(tBase, BASE);
    }
    intensity.setValueAtTime(beatsArray[beatsArray.length - 1], PEAK);
}

function retargetImageLayersToFootage(assetComp, footageName) {
    if (!assetComp) return;
    var coverFootage = null;
    for (var i = 1; i <= app.project.numItems; i++) {
        var it = app.project.item(i);
        if (it instanceof FootageItem && it.name.toUpperCase() === footageName.toUpperCase()) {
            coverFootage = it; break;
        }
    }
    if (!coverFootage) return;

    for (var L = 1; L <= assetComp.numLayers; L++) {
        var lyr = assetComp.layer(L);
        if (!(lyr instanceof AVLayer) || !(lyr.source instanceof FootageItem)) continue;
        var lyrName = (lyr.name || "").toLowerCase();
        if (lyrName === "cover" || lyrName.indexOf("album") !== -1 || lyrName.indexOf("art") !== -1) {
            try { lyr.replaceSource(coverFootage, false); } catch (e) {}
        }
    }
}

function addToRenderQueue(comp, jobFolder, jobId, songTitle) {
    try {
        jobFolder = String(jobFolder).replace(/\\/g, "/");
        var root = new Folder(jobFolder).parent;
        var renderDir = new Folder(root.fsName + "/renders");
        if (!renderDir.exists) renderDir.create();

        var safeTitle = sanitizeFilename(songTitle);
        var outPath = renderDir.fsName.replace(/\\/g, "/") + "/" + safeTitle + ".mp4";
        var rq = app.project.renderQueue.items.add(comp);
        rq.outputModule(1).file = new File(outPath);
        return outPath;
    } catch (err) { return null; }
}

function sanitizeFilename(name) {
    if (!name) return "untitled";
    return String(name).replace(/[\/\\:*?"<>|]/g, "").replace(/\s+/g, " ").trim();
}

function clearAllJobComps() {
    for (var i = app.project.numItems; i >= 1; i--) {
        var it = app.project.item(i);
        if (it instanceof CompItem && it.name.indexOf("MV_JOB_") === 0) {
            try { it.remove(); } catch (e) {}
        }
    }
}

// -----------------------------
main();
