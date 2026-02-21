// -------------------------------------------------------
// APOLLOVA MONO - After Effects Automation
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
    app.beginUndoGroup("Mono Batch Music Video Build");

    clearAllJobComps();

    // Use injected path or fallback to prompt
    var jobsFolder;
    if (JOBS_PATH.indexOf("{{") === -1 && JOBS_PATH !== "") {
        jobsFolder = new Folder(JOBS_PATH);
        $.writeln("Using injected jobs path: " + JOBS_PATH);
    } else {
        jobsFolder = Folder.selectDialog("Select your /jobs folder (Apollova-Mono/jobs)");
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
        jobData.job_folder = jobFolder.fsName.replace(/\\/g, "/");
        
        var hasCoverImage = false;
        if (jobData.cover_image) {
            jobData.cover_image = toAbsolute(jobData.cover_image);
            var imageFile = new File(jobData.cover_image);
            hasCoverImage = imageFile.exists;
        }

        var jobId = jobData.job_id || (j + 1);
        var songTitle = jobData.song_title || "Unknown";

        $.writeln("──────── MONO Job " + jobId + " ────────");
        $.writeln("Song: " + songTitle);
        $.writeln("Markers: " + markers.length);

        var audioFile = new File(jobData.audio_trimmed);
        if (!audioFile.exists) { 
            alert("Missing audio:\n" + jobData.audio_trimmed); 
            continue; 
        }

        // Duplicate MAIN template
        var template = findCompByName("MAIN");
        var newComp = template.duplicate();
        newComp.name = "MONO_JOB_" + ("00" + jobId).slice(-3);

        moveItemToFolder(newComp, "OUTPUT" + jobId);

        if (hasCoverImage) {
            relinkFootageInsideOutputFolder(jobId, jobData.audio_trimmed, jobData.cover_image);
            autoResizeCoverInOutput(jobId);
        } else {
            relinkAudioOnly(jobId, jobData.audio_trimmed);
        }
        
        setWorkAreaToAudioDuration(jobId);
        setOutputWorkAreaToAudio(jobId, jobData.audio_trimmed);
        updateSongTitle(jobId, songTitle);

        var lyricComp;
        try { lyricComp = findCompByName("LYRIC FONT " + jobId); }
        catch (e) { $.writeln("Missing LYRIC FONT " + jobId + " – skipping lyrics."); continue; }

        addMonoMarkersToAudio(lyricComp, markers);
        injectMonoSegmentsToLyricText(lyricComp, markers);

        try {
            var bgComp = findCompByName("BACKGROUND " + jobId);
            addMonoMarkersToBackground(bgComp, markers);
            $.writeln("Added markers to BACKGROUND " + jobId);
        } catch (e) {
            $.writeln("BACKGROUND " + jobId + " not found – skipping color flip markers.");
        }

        if (hasCoverImage) {
            try {
                var assetsComp = findCompByName("Assets " + jobId);
                retargetImageLayersToFootage(assetsComp, "COVER");
                $.writeln("Album art retargeted for job " + jobId);
            } catch (e) {
                $.writeln("Assets " + jobId + " not found – skipping album art.");
            }
        }

        try {
            var outputComp = findCompByName("OUTPUT " + jobId);
            var renderPath = addToRenderQueue(outputComp, jobData.job_folder, jobId, songTitle);
            $.writeln("Queued: " + renderPath);
        } catch (e) {
            $.writeln("Render queue error: " + e);
        }
    }

    alert("MONO: All " + jsonFiles.length + " jobs processed!\n\nReview in Render Queue, then click Render.");
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
            words: seg.words || buildWordsFromText(cleanText, seg.t || 0),
            color: (markers.length % 2 === 0) ? "white" : "black"
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
    var avgWordDuration = 0.3;
    
    for (var i = 0; i < words.length; i++) {
        if (words[i]) {
            result.push({
                word: words[i],
                start: startTime + (i * avgWordDuration),
                end: startTime + ((i + 1) * avgWordDuration)
            });
        }
    }
    return result;
}


// -----------------------------
// Mono-specific functions
// -----------------------------
function addMonoMarkersToAudio(lyricComp, markers) {
    var audio = ensureAudioLayer(lyricComp);
    if (!audio) return;

    var mk = audio.property("Marker");
    if (!mk) return;

    for (var i = mk.numKeys; i >= 1; i--) mk.removeKey(i);

    var lastT = 0;
    for (var k = 0; k < markers.length; k++) {
        var m = markers[k];
        var t = Number(m.time) || 0;
        
        var commentData = {
            index: k,
            text: m.text || "",
            words: m.words || [],
            color: m.color || "white",
            end_time: m.end_time || (t + 3)
        };
        
        var mv = new MarkerValue(m.text || "");
        mv.comment = JSON.stringify(commentData);

        if (t > lastT) {
            mk.setValueAtTime(t, mv);
            lastT = t;
        } else {
            mk.setValueAtTime(lastT + 0.01, mv);
            lastT = lastT + 0.01;
        }
    }
    $.writeln("Added " + markers.length + " markers to AUDIO");
}

function addMonoMarkersToBackground(bgComp, markers) {
    var targetLayer = null;
    for (var i = 1; i <= bgComp.numLayers; i++) {
        var lyr = bgComp.layer(i);
        var lyrName = lyr.name.toLowerCase();
        if (lyrName.indexOf("background") !== -1 || lyrName.indexOf("bg") !== -1 || lyrName.indexOf("solid") !== -1) {
            targetLayer = lyr;
            break;
        }
    }
    if (!targetLayer && bgComp.numLayers > 0) targetLayer = bgComp.layer(1);
    if (!targetLayer) return;
    
    var mk = targetLayer.property("Marker");
    if (!mk) return;
    
    for (var i = mk.numKeys; i >= 1; i--) mk.removeKey(i);
    
    var lastT = 0;
    for (var k = 0; k < markers.length; k++) {
        var m = markers[k];
        var t = Number(m.time) || 0;
        var mv = new MarkerValue(m.color || "white");
        mv.comment = m.color || "white";
        
        if (t > lastT) {
            mk.setValueAtTime(t, mv);
            lastT = t;
        } else {
            mk.setValueAtTime(lastT + 0.01, mv);
            lastT = lastT + 0.01;
        }
    }
}

function injectMonoSegmentsToLyricText(lyricComp, markers) {
    var textLayer = null;
    for (var i = 1; i <= lyricComp.numLayers; i++) {
        var lyr = lyricComp.layer(i);
        if (lyr.name.toUpperCase().indexOf("LYRIC") !== -1 && lyr.property("Source Text")) {
            textLayer = lyr;
            break;
        }
    }
    if (!textLayer) {
        for (var i = 1; i <= lyricComp.numLayers; i++) {
            if (lyricComp.layer(i).property("Source Text")) {
                textLayer = lyricComp.layer(i);
                break;
            }
        }
    }
    if (!textLayer) return;
    
    var segmentsCode = "var segments = [\n";
    for (var k = 0; k < markers.length; k++) {
        var m = markers[k];
        var wordsArr = m.words || [];
        
        var wordsStr = "[";
        for (var w = 0; w < wordsArr.length; w++) {
            var word = wordsArr[w];
            wordsStr += '{word:"' + escapeForExpression(word.word || "") + '",start:' + (word.start || 0) + ',end:' + (word.end || 0) + '}';
            if (w < wordsArr.length - 1) wordsStr += ",";
        }
        wordsStr += "]";
        
        segmentsCode += '  {time:' + (m.time || 0) + ',text:"' + escapeForExpression(m.text || "") + '",words:' + wordsStr + ',end_time:' + (m.end_time || (m.time + 3)) + '}';
        if (k < markers.length - 1) segmentsCode += ",";
        segmentsCode += "\n";
    }
    segmentsCode += "];\n\n";
    
    var expression = segmentsCode + 
        'var t = time;\nvar output = "";\nvar currentSeg = null;\n\n' +
        'for (var i = segments.length - 1; i >= 0; i--) {\n' +
        '  if (t >= segments[i].time) { currentSeg = segments[i]; break; }\n}\n\n' +
        'if (currentSeg && currentSeg.words.length > 0) {\n' +
        '  for (var w = 0; w < currentSeg.words.length; w++) {\n' +
        '    if (t >= currentSeg.words[w].start) output += currentSeg.words[w].word + " ";\n' +
        '  }\n} else if (currentSeg) { output = currentSeg.text; }\n\noutput.trim();';
    
    try {
        textLayer.property("Source Text").expression = expression;
        $.writeln("Injected word-by-word expression");
    } catch (e) {
        $.writeln("Failed to set expression: " + e.toString());
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

function findCompByName(name) {
    for (var i = 1; i <= app.project.numItems; i++) {
        var it = app.project.item(i);
        if (it instanceof CompItem && it.name === name) return it;
    }
    throw new Error("Comp not found: " + name);
}

function ensureAudioLayer(comp) {
    for (var i = 1; i <= comp.numLayers; i++) {
        var lyr = comp.layer(i);
        if (lyr.name.toUpperCase() === "AUDIO" || (lyr.source && lyr.source.hasAudio && !lyr.source.hasVideo)) {
            return lyr;
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
        if (n.indexOf("COVER") !== -1 || n.indexOf("IMAGE") !== -1 || n.indexOf("ART") !== -1) {
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

    try {
        var bgComp = findCompByName("BACKGROUND " + jobId);
        bgComp.duration = dur;
        bgComp.workAreaStart = 0;
        bgComp.workAreaDuration = dur;
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
        if (it instanceof CompItem && it.name.indexOf("MONO_JOB_") === 0) {
            try { it.remove(); } catch (e) {}
        }
    }
}

// -----------------------------
main();
