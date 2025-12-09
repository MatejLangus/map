const fs = require('fs');
const path = require('path');
const gpx2geojson = require('gpx2geojson');
const { DOMParser } = require('xmldom');
const geojsonPrecision = require('geojson-precision');
const { parse } = require('csv-parse/sync');
 // synchronous CSV parser

// -------------------------------------------------------------
// 1) LOAD CSV → map { gpx_file → CSV data }
// -------------------------------------------------------------
const csvPath = path.join(__dirname, 'matched_activities.csv');
if (!fs.existsSync(csvPath)) {
    console.error("❌ relive.csv not found.");
    process.exit(1);
}

const csvContent = fs.readFileSync(csvPath, 'utf8');
const rows = parse(csvContent, {
    columns: true,
    skip_empty_lines: true
});

const csvData = {}; // gpx_file → row
rows.forEach(row => {
    if (!row.gpx_file) return;

    const gpxFile = row.gpx_file.replace(/^"|"$/g, ''); // remove quotes if any
    csvData[gpxFile] = {
        relive_id: row.relive_id?.replace(/^"|"$/g, '') || '',
        relive_url: row.relive_url?.replace(/^"|"$/g, '') || '',
        name: row.name?.replace(/^"|"$/g, '') || '',
        date: row.date?.replace(/^"|"$/g, '') || '',
        video_url: row.video_url?.replace(/^"|"$/g, '').replace('.com', '.cc') || '',
        cover_photo: row.cover_photo?.replace(/^"|"$/g, '') || ''
    };
});

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
    // 3) MERGE CSV DATA
    // -------------------------------------------------------------
    const baseName = path.basename(file); // keep full filename for CSV match
    const csvRow = csvData[baseName];

    if (csvRow) {
        descriptionText += `<br><p><strong>Relive:</strong> ` +
            `<a href="${csvRow.relive_url}" target="_blank">${csvRow.name}</a></p>`;
    }

    const feature = {
        type: "Feature",
        properties: {
            descriptions: descriptionText,
            sourceFile: baseName,
            relive_id: csvRow?.relive_id || '',
            relive_url: csvRow?.relive_url || '',
            name: csvRow?.name || '',
            date: csvRow?.date || '',
            video_url: csvRow?.video_url || '',
            cover_photo: csvRow?.cover_photo || ''
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
let output = '{\n' +
    '  "type": "FeatureCollection",\n' +
    '  "features": [\n' +
    mergedFeatures
        .map(f => "    " + JSON.stringify(f))   // one line per GPX track
        .join(",\n") +
    '\n  ]\n' +
    '}\n';

fs.writeFileSync(mergedFilePath, output);
console.log(`✅ Merged ${mergedFeatures.length} tracks → ${mergedFilePath}`);
