// -------------------------------------------------------
// APOLLOVA ONYX - After Effects Automation
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
            if (t === "string") obj = '"' + obj.replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"';
            return String(obj);
        } else {
            var n, v, json = [], arr = (obj && obj.constructor === Array);
            for (n in obj) {
                v = obj[n];
                t = typeof v;
                if (t === "string") v = '"' + v.replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"';
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
    app.beginUndoGroup("ONYX Batch Music Video Build");

    clearAllJobComps();

    // Use injected path or fallback to prompt
    var jobsFolder;
    if (JOBS_PATH.indexOf("{{") === -1 && JOBS_PATH !== "") {
        jobsFolder = new Folder(JOBS_PATH);
        $.writeln("Using injected jobs path: " + JOBS_PATH);
    } else {
        jobsFolder = Folder.selectDialog("Select your /jobs folder (Apollova-Onyx/jobs)");
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
        var jobText = jobFile.read();
        jobFile.close();
        if (!jobText) continue;

        var jobData;
        try { jobData = JSON.parse(jobText); }
        catch (e) { alert("Error parsing " + jobFile.name + ": " + e.toString()); continue; }

        var jobFolder = jobFile.parent;
        
        // Read lyrics.txt and convert to markers
        var lyricsFile = new File(jobFolder.fsName + "/lyrics.txt");
        var markers = [];
        
        if (lyricsFile.exists && lyricsFile.open("r")) {
            var lyricsText = lyricsFile.read();
            lyricsFile.close();
            try {
                var lyricsData = JSON.parse(lyricsText);
                markers = convertLyricsToMarkers(lyricsData);
            } catch (e) {
                $.writeln("Could not parse lyrics.txt: " + e.toString());
            }
        }

        jobData.audio_trimmed = toAbsolute(jobData.audio_trimmed) || (jobFolder.fsName + "/audio_trimmed.wav");
        jobData.cover_image = toAbsolute(jobData.cover_image) || (jobFolder.fsName + "/cover.png");
        jobData.job_folder = jobFolder.fsName.replace(/\\/g, "/");
        
        var jobId = jobData.job_id || (j + 1);
        var songTitle = jobData.song_title || "Unknown";
        var colors = jobData.colors || [];

        $.writeln("──────── ONYX Job " + jobId + " ────────");
        $.writeln("Song: " + songTitle);
        $.writeln("Markers: " + markers.length);

        var audioFile = new File(jobData.audio_trimmed);
        var coverFile = new File(jobData.cover_image);
        
        if (!audioFile.exists) { 
            alert("Missing audio:\n" + jobData.audio_trimmed); 
            continue; 
        }

        // Duplicate MAIN template
        var template = findCompByName("MAIN");
        var newComp = template.duplicate();
        newComp.name = "ONYX_JOB_" + ("00" + jobId).slice(-3);

        moveItemToFolder(newComp, "OUTPUT" + jobId);

        if (coverFile.exists) {
            relinkFootageInsideOutputFolder(jobId, jobData.audio_trimmed, jobData.cover_image);
        } else {
            relinkAudioOnly(jobId, jobData.audio_trimmed);
        }
        
        setAllCompDurations(jobId, jobData.audio_trimmed);
        updateSongTitle(jobId, songTitle);

        if (colors && colors.length >= 2) {
            applyBackgroundColors(jobId, colors);
        }

        var lyricComp;
        try { lyricComp = findCompByName("LYRIC FONT " + jobId); } 
        catch (e) { $.writeln("Missing LYRIC FONT " + jobId); continue; }

        addOnyxMarkersToAudio(lyricComp, markers);
        injectOnyxSegmentsToLyricText(lyricComp, markers);

        if (coverFile.exists) {
            try {
                var assetsComp = findCompByName("Assets " + jobId);
                retargetImageLayersToFootage(assetsComp, "COVER");
            } catch (e) {}
        }

        try {
            var outputComp = findCompByName("OUTPUT " + jobId);
            var renderPath = addToRenderQueue(outputComp, jobData.job_folder, jobId, songTitle, "_ONYX");
            $.writeln("Queued: " + renderPath);
        } catch (e) {
            $.writeln("Render queue error: " + e);
        }
    }

    alert("ONYX: All " + jsonFiles.length + " jobs processed!\n\nReview in Render Queue, then click Render.");
    app.endUndoGroup();
}


// -----------------------------
// Convert lyrics.txt to markers
// -----------------------------
function convertLyricsToMarkers(lyricsData) {
    var markers = [];
    for (var i = 0; i < lyricsData.length; i++) {
        var seg = lyricsData[i];
        var text = seg.lyric_current || seg.text || "";
        if (!text || text.replace(/\s/g, "") === "") continue;
        
        var cleanText = text.replace(/\\r/g, " ").replace(/\s+/g, " ").trim();
        var marker = {
            time: seg.t || seg.time || 0,
            text: cleanText,
            words: seg.words || buildWordsFromText(cleanText, seg.t || 0)
        };
        
        if (i < lyricsData.length - 1) {
            marker.end_time = lyricsData[i + 1].t || lyricsData[i + 1].time || (marker.time + 3);
        } else {
            marker.end_time = marker.time + 3;
        }
        markers.push(marker);
    }
    return markers;
}

function buildWordsFromText(text, startTime) {
    var words = text.split(/\s+/);
    var result = [];
    for (var i = 0; i < words.length; i++) {
        if (words[i]) {
            result.push({
                word: words[i],
                start: startTime + (i * 0.3),
                end: startTime + ((i + 1) * 0.3)
            });
        }
    }
    return result;
}


// -----------------------------
// Onyx-specific functions
// -----------------------------
function addOnyxMarkersToAudio(lyricComp, markers) {
    var audio = ensureAudioLayer(lyricComp);
    if (!audio) return;

    var mk = audio.property("Marker");
    if (!mk) return;

    for (var i = mk.numKeys; i >= 1; i--) mk.removeKey(i);

    var lastT = 0;
    for (var k = 0; k < markers.length; k++) {
        var m = markers[k];
        var t = Number(m.time) || 0;
        try {
            mk.setValueAtTime(t, new MarkerValue(m.text || ""));
            if (t > lastT) lastT = t;
        } catch (e) {}
    }
    
    if (lastT + 2 > lyricComp.duration) lyricComp.duration = lastT + 2;
    $.writeln("Added " + markers.length + " markers to AUDIO");
}

function injectOnyxSegmentsToLyricText(lyricComp, markers) {
    var lyricText = null;
    try { lyricText = lyricComp.layer("LYRIC_TEXT"); } catch(e) {}
    
    if (!lyricText) {
        for (var i = 1; i <= lyricComp.numLayers; i++) {
            var lyr = lyricComp.layer(i);
            if (lyr.name.toUpperCase().indexOf("LYRIC") !== -1 && lyr.property("Source Text")) {
                lyricText = lyr;
                break;
            }
        }
    }
    if (!lyricText) {
        for (var i = 1; i <= lyricComp.numLayers; i++) {
            if (lyricComp.layer(i).property("Source Text")) {
                lyricText = lyricComp.layer(i);
                break;
            }
        }
    }
    if (!lyricText) return;

    var segmentsCode = "var segments = [\n";
    for (var k = 0; k < markers.length; k++) {
        var m = markers[k];
        var wordsArr = m.words || [];
        var wordsStr = "[";
        for (var w = 0; w < wordsArr.length; w++) {
            wordsStr += '{word:"' + escapeForExpression(wordsArr[w].word || "") + '",start:' + (wordsArr[w].start || 0) + ',end:' + (wordsArr[w].end || 0) + '}';
            if (w < wordsArr.length - 1) wordsStr += ",";
        }
        wordsStr += "]";
        segmentsCode += '    {time:' + (m.time || 0) + ',text:"' + escapeForExpression(m.text || "") + '",words:' + wordsStr + ',end_time:' + (m.end_time || (m.time + 3)) + '}';
        if (k < markers.length - 1) segmentsCode += ",";
        segmentsCode += "\n";
    }
    segmentsCode += "];\n\n";

    var expression = segmentsCode +
        'var t = time;\nvar output = "";\nvar currentSeg = null;\n\n' +
        'for (var i = segments.length - 1; i >= 0; i--) {\n' +
        '    if (t >= segments[i].time) { currentSeg = segments[i]; break; }\n}\n\n' +
        'if (currentSeg && currentSeg.words && currentSeg.words.length > 0) {\n' +
        '    var revealedWords = [];\n' +
        '    for (var w = 0; w < currentSeg.words.length; w++) {\n' +
        '        if (t >= currentSeg.words[w].start) revealedWords.push(currentSeg.words[w].word);\n' +
        '    }\n' +
        '    var lines = [];\n' +
        '    for (var i = 0; i < revealedWords.length; i += 3) {\n' +
        '        lines.push(revealedWords.slice(i, Math.min(i + 3, revealedWords.length)).join(" "));\n' +
        '    }\n' +
        '    output = lines.join("\\n");\n' +
        '} else if (currentSeg) { output = currentSeg.text; }\n\noutput;';

    try {
        lyricText.property("Source Text").expression = expression;
        $.writeln("Injected Onyx expression");
    } catch (e) {
        $.writeln("Failed to inject expression: " + e.toString());
    }
}

function escapeForExpression(str) {
    if (!str) return "";
    return String(str).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n").replace(/\r/g, "");
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
    return p;
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

function ensureAudioLayer(comp) {
    var lyr = comp.layer("AUDIO");
    if (lyr) return lyr;
    for (var i = 1; i <= comp.numLayers; i++) {
        var L = comp.layer(i);
        if (L instanceof AVLayer && L.hasAudio) {
            try { L.name = "AUDIO"; } catch (_) {}
            return L;
        }
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
        if (n.indexOf("COVER") !== -1 || n.indexOf("IMAGE") !== -1 || n.indexOf("ART") !== -1 || n.indexOf("PNG") !== -1) {
            var imgf = new File(imagePath);
            if (imgf.exists) try { it.replace(imgf); } catch(e) {}
        }
    }
}

function relinkAudioOnly(jobId, audioPath) {
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
    }
}

function setAllCompDurations(jobId, audioPath) {
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

    try {
        var bgComp = findCompByName("BACKGROUND " + jobId);
        bgComp.duration = dur;
        bgComp.workAreaStart = 0;
        bgComp.workAreaDuration = dur;
    } catch(e) {}
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

function addToRenderQueue(comp, jobFolder, jobId, songTitle, suffix) {
    try {
        jobFolder = String(jobFolder).replace(/\\/g, "/");
        var root = new Folder(jobFolder).parent;
        var renderDir = new Folder(root.fsName + "/renders");
        if (!renderDir.exists) renderDir.create();
        var safeTitle = sanitizeFilename(songTitle);
        var outPath = renderDir.fsName.replace(/\\/g, "/") + "/" + safeTitle + (suffix || "") + ".mp4";
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
        if (it instanceof CompItem && it.name.indexOf("ONYX_JOB_") === 0) {
            try { it.remove(); } catch (e) {}
        }
    }
}

// -----------------------------
main();
