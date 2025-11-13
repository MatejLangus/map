const fs = require('fs');
const path = require('path');
const gpx2geojson = require('gpx2geojson');
const { DOMParser } = require('xmldom');
const geojsonPrecision = require('geojson-precision');

// Folders
const inputFolder = path.join(__dirname, 'gpx-files');  // GPX files
const mergedFilePath = path.join(__dirname, 'merged.geojson'); // merged output in project root

// Ensure input folder exists
if (!fs.existsSync(inputFolder)) {
  console.error("❌ 'gpx-files' folder not found.");
  process.exit(1);
}

// Read all GPX files
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

  // Extract <desc> from <trk>
  let trackDescription = '';
  const descNodes = doc.getElementsByTagName('trk')[0]?.getElementsByTagName('desc');
  if (descNodes && descNodes.length > 0 && descNodes[0].textContent.trim() !== '') {
    trackDescription = descNodes[0].textContent.trim();
  }

  // Convert GPX to GeoJSON
  const geojson = gpx2geojson.gpx(doc);

  // Collect coordinates and description
  const coordinates = [];
  const descriptions = [];
  const sanitizeCoordinates = coords => coords.filter(c => typeof c === 'number' && !isNaN(c));

  geojson.features.forEach(feature => {
    if (feature.geometry.type === 'Point') {
      const validCoords = sanitizeCoordinates(feature.geometry.coordinates.slice(0, 2));
      if (validCoords.length === 2) {
        coordinates.push(validCoords);
        if (feature.properties?.desc) {
          descriptions.push(feature.properties.desc);
        } else if (trackDescription) {
          descriptions.push(trackDescription);
        }
      }
    }
  });

  if (coordinates.length === 0) return; // skip empty tracks

  const feature = {
    type: "Feature",
    properties: {
      descriptions: descriptions[0] || '',
      sourceFile: path.basename(file, ".gpx")
    },
    geometry: {
      type: "LineString",
      coordinates
    }
  };

  // Reduce precision to 5 decimals for smaller file
  const preciseFeature = geojsonPrecision({ type: "FeatureCollection", features: [feature] }, 5).features[0];

  mergedFeatures.push(preciseFeature);
});

// Write merged and minified GeoJSON (no whitespace)
const mergedGeoJSON = { type: "FeatureCollection", features: mergedFeatures };
fs.writeFileSync(mergedFilePath, JSON.stringify(mergedGeoJSON));
console.log(`✅ Merged ${mergedFeatures.length} features → ${mergedFilePath}`);
