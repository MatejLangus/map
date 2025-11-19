const fs = require('fs');
const path = require('path');
const gpx2geojson = require('gpx2geojson');
const { DOMParser } = require('xmldom');
const geojsonPrecision = require('geojson-precision');

// -------------------------------------------------------------
// 1) PARSE RELIVE HTML → extract { date → {title, url} }
// -------------------------------------------------------------
const reliveHtmlPath = path.join(__dirname, "Relive _ Settings.html");
let reliveVideos = {}; // { "2025-04-12": { title, url } }

if (fs.existsSync(reliveHtmlPath)) {
    const html = fs.readFileSync(reliveHtmlPath, 'utf8');

    // Full correct regex:
    // <h6>TITLE</h6> <small class="subtitle">DATE | <a href="URL">
    const regex = /<h6[^>]*>([^<]+)<\/h6>\s*<small[^>]*>\s*([^|]+?)\s*\|\s*<a[^>]+href="([^"]+)"/gi;

    let match;
    while ((match = regex.exec(html)) !== null) {
        const title = match[1].trim();        // e.g. "Jbel Asstef, Toudra"
        const longDate = match[2].trim();     // e.g. "15 September 2025"
        const url = match[3].trim();          // relive video URL

        // Convert "15 September 2025" → "2025-09-15"
        let dateObj = new Date(longDate);
        if (isNaN(dateObj)) continue;

        const date = new Intl.DateTimeFormat("en-CA", {
            timeZone: "Europe/Ljubljana", // force correct timezone
        }).format(dateObj);
        

        reliveVideos[date] = { title, url };
    }

    console.log(`📹 Loaded ${Object.keys(reliveVideos).length} Relive video entries (by date)`);
} else {
    console.log("⚠ Relive _ Settings.html not found → skipping Relive linking");
}


// -------------------------------------------------------------
// 2) GPX → MERGED.GEOJSON
// -------------------------------------------------------------
const inputFolder = path.join(__dirname, 'gpx-files');
const mergedFilePath = path.join(__dirname, 'merged.geojson');

if (!fs.existsSync(inputFolder)) {
    console.error("❌ 'gpx-files' folder not found.");
    process.exit(1);
}

const gpxFiles = fs.readdirSync(inputFolder).filter(f => f.endsWith('.gpx'));
if (gpxFiles.length === 0) {
    console.log("No GPX files found in 'gpx-files'.");
    process.exit(0);
}

const mergedFeatures = [];

gpxFiles.forEach(file => {
    const filePath = path.join(inputFolder, file);
    const gpxData = fs.readFileSync(filePath, 'utf8');

    const parser = new DOMParser();
    const doc = parser.parseFromString(gpxData, 'application/xml');

    // read <trk><desc>
    let trackDescription = '';
    const descNodes = doc.getElementsByTagName('trk')[0]?.getElementsByTagName('desc');
    if (descNodes && descNodes.length > 0 && descNodes[0].textContent.trim() !== '') {
        trackDescription = descNodes[0].textContent.trim();
    }

    // convert GPX → GeoJSON
    const geojson = gpx2geojson.gpx(doc);

    const coordinates = [];
    let descriptionText = trackDescription;

    const sanitize = arr => arr.filter(n => typeof n === 'number' && !isNaN(n));

    geojson.features.forEach(feature => {
        if (feature.geometry.type === 'Point') {
            const coords = sanitize(feature.geometry.coordinates.slice(0, 2));
            if (coords.length === 2) coordinates.push(coords);

            if (feature.properties?.desc) {
                descriptionText = feature.properties.desc;
            }
        }
    });

    if (coordinates.length === 0) return;

    // -------------------------------------------------------------
    // 3) MATCH RELIVE BY DATE (YYYY-MM-DD extracted from filename)
    // -------------------------------------------------------------

    const baseName = path.basename(file, ".gpx");
    const dateMatch = baseName.match(/\b\d{4}-\d{2}-\d{2}\b/);

    let reliveBlock = "";

    if (dateMatch) {
        const date = dateMatch[0];

        if (reliveVideos[date]) {
            const { title, url } = reliveVideos[date];

            reliveBlock =
                `<br><p><strong>Relive:</strong> ` +
                `<a href="${url}" target="_blank">${title}</a></p>`;
        }
    }

    // append video block
    if (reliveBlock !== "") {
        descriptionText += reliveBlock;
    }

    // create feature
    const feature = {
        type: "Feature",
        properties: {
            descriptions: descriptionText,
            sourceFile: baseName
        },
        geometry: {
            type: "LineString",
            coordinates
        }
    };

    const preciseFeature = geojsonPrecision(
        { type: "FeatureCollection", features: [feature] }, 5
    ).features[0];

    mergedFeatures.push(preciseFeature);
});

// -------------------------------------------------------------
// 4) WRITE MERGED GEOJSON (minified)
// -------------------------------------------------------------
const mergedGeoJSON = { type: "FeatureCollection", features: mergedFeatures };
fs.writeFileSync(mergedFilePath, JSON.stringify(mergedGeoJSON));
console.log(`✅ Merged ${mergedFeatures.length} tracks → ${mergedFilePath}`);
