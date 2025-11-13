const fs = require('fs');
const path = require('path');
const gpx2geojson = require('gpx2geojson');
const { DOMParser } = require('xmldom');
const geojsonPrecision = require('geojson-precision');

// Define folder paths
const inputFolder = path.join(__dirname, 'gpx-files');    // GPX files
const outputFolder = path.join(__dirname, 'geojson-files'); // Individual GeoJSON
const mergedFilePath = path.join(outputFolder, 'merged.geojson'); // Merged GeoJSON

// Ensure output folder exists
if (!fs.existsSync(outputFolder)) fs.mkdirSync(outputFolder);

// Get all GPX files
const gpxFiles = fs.readdirSync(inputFolder).filter(f => f.endsWith('.gpx'));

if (gpxFiles.length === 0) {
  console.log("No GPX files found in 'gpx-files'.");
  process.exit(0);
}

// Array to hold merged features
const mergedFeatures = [];

gpxFiles.forEach(file => {
  const inputFilePath = path.join(inputFolder, file);
  const gpxData = fs.readFileSync(inputFilePath, 'utf8');

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

  // Collect coordinates and descriptions
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

  if (coordinates.length === 0) return; // Skip empty tracks

  // Create simplified GeoJSON feature
  const reducedGeoJSON = {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: {
          descriptions: descriptions[0] || '', // keep only first description
        },
        geometry: {
          type: 'LineString',
          coordinates
        }
      }
    ]
  };

  // Reduce precision
  const precisionGeoJSON = geojsonPrecision(reducedGeoJSON, 5);

  // Save individual GeoJSON
  const outputFileName = file.replace('.gpx', '.geojson');
  const outputFilePath = path.join(outputFolder, outputFileName);
  fs.writeFileSync(outputFilePath, JSON.stringify(precisionGeoJSON, null, 2));
  console.log(`Converted ${file} → ${outputFileName}`);

  // Add feature to merged array
  mergedFeatures.push(precisionGeoJSON.features[0]);
});

// Save merged GeoJSON
const mergedGeoJSON = { type: 'FeatureCollection', features: mergedFeatures };
fs.writeFileSync(mergedFilePath, JSON.stringify(mergedGeoJSON, null, 2));
console.log(`✅ Merged ${mergedFeatures.length} features → merged.geojson`);
