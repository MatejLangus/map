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

    // ✅ Extract <desc> content from <trk> if available
    let trackDescription = '';
    let descNodes = doc.getElementsByTagName('trk')[0]?.getElementsByTagName('desc');

    if (descNodes && descNodes.length > 0 && descNodes[0].textContent.trim() !== '') {
      trackDescription = descNodes[0].textContent.trim();
    }

    // Convert GPX to GeoJSON using gpx2geojson
    const geojson = gpx2geojson.gpx(doc);  // Pass the DOM object to gpx2geojson

    // Create arrays to hold all coordinates, descriptions, and elevations
    const coordinates = [];
    const descriptions = [];

    const sanitizeCoordinates = (coordinates) => {
      return coordinates.filter(coord => typeof coord === 'number' && !isNaN(coord));
    };

    geojson.features.forEach(feature => {
      if (feature.geometry.type === 'Point') {
        // Extract coordinates from Point
        const validCoordinates = sanitizeCoordinates(feature.geometry.coordinates.slice(0, 2));  // Just keep latitude and longitude
        if (validCoordinates.length === 2) {
          coordinates.push(validCoordinates);
  
          // Add descriptions (if available, or use a placeholder)
          if (feature.properties && feature.properties.desc) {
            //feature.properties.desc = feature.properties.desc.split('<hr')[0];  // Keep only short description
            const description = feature.properties.desc ;
            descriptions.push(description);
          } else if (trackDescription) {
            descriptions.push(trackDescription); // ✅ fallback to <trk><desc>
          }
        }
      }
    });

    // Create a new simplified GeoJSON feature with the combined coordinates and descriptions
    const reducedGeoJSON = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {
            descriptions: descriptions[0],  // Store all descriptions

          },
          geometry: {
            type: 'LineString',
            coordinates: coordinates      // Store coordinates as a single line
          }
        }
      ]
    };


    //const simplified = turf.simplify(reducedGeoJSON, { tolerance: 0.01, highQuality: true });

    // Reduce the precision of coordinates
    const precisionGeoJSON = geojsonPrecision(reducedGeoJSON , 5);  // Rounding to 5 decimal places
  
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
