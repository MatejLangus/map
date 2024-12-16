const fs = require('fs');
const path = require('path');
const gpx2geojson = require('gpx2geojson');
const { DOMParser } = require('xmldom');  // Import DOMParser from xmldom

const turf = require('@turf/turf');  // Import turf
const geojsonPrecision = require('geojson-precision');
const zlib = require('zlib');

// Define the folder paths
const inputFolder = path.join(__dirname, 'gpx-files');  // Folder containing GPX files
const outputFolder = path.join(__dirname, 'geojson-files');  // Folder to store GeoJSON files

// Ensure the output folder exists
if (!fs.existsSync(outputFolder)) {
  fs.mkdirSync(outputFolder);
}

// Get all GPX files in the input folder
const gpxFiles = fs.readdirSync(inputFolder).filter(file => file.endsWith('.gpx'));

if (gpxFiles.length === 0) {
  console.log("No GPX files found in the 'gpx-files' folder.");
} else {
  gpxFiles.forEach(file => {
    const inputFilePath = path.join(inputFolder, file);
    const gpxData = fs.readFileSync(inputFilePath, 'utf8');

    // Parse the GPX data into a DOM using xmldom
    const parser = new DOMParser();
    const doc = parser.parseFromString(gpxData, 'application/xml');

    // Convert GPX to GeoJSON using gpx2geojson
    const geojson = gpx2geojson.gpx(doc);  // Pass the DOM object to gpx2geojson

    // Filter out the unwanted properties (heartRates and coordTimes)
    geojson.features.forEach(feature => {
        // Remove heartRates and coordTimes properties if they exist
        delete feature.properties.heartRates;
        delete feature.properties.coordTimes;
    });

    const simplified = turf.simplify(geojson, { tolerance: 0.01, highQuality: false });

    // Reduce the precision of coordinates
    const precisionGeoJSON = geojsonPrecision(simplified , 5);  // Rounding to 5 decimal places
  
    // Minify the GeoJSON
    const minifiedGeoJSON = JSON.stringify(precisionGeoJSON);
  
   
  

  
  




    // Define the output file name
    const outputFileName = file.replace('.gpx', '.geojson');
    const outputFilePath = path.join(outputFolder, outputFileName);

    // Write the GeoJSON file
    fs.writeFileSync(outputFilePath, JSON.stringify(minifiedGeoJSON, null, 2));
    console.log(`Converted ${file} to ${outputFileName}`);
  });

  console.log("Conversion complete. Check the 'geojson-files' folder for results.");
}
