const fs = require("fs");
const path = require("path");
const gpx2geojson = require("gpx2geojson");

const inputFolder = path.join(__dirname, "gpx-files");
const outputFolder = path.join(__dirname, "output-geojson");

// Ensure the output folder exists
if (!fs.existsSync(outputFolder)) {
  fs.mkdirSync(outputFolder);
}

// Get all GPX files in the input folder
const gpxFiles = fs.readdirSync(inputFolder).filter(file => file.endsWith(".gpx"));

if (gpxFiles.length === 0) {
  console.log("No GPX files found in the 'gpx-files' folder.");
} else {
  gpxFiles.forEach(file => {
    const inputFilePath = path.join(inputFolder, file);
    const gpxData = fs.readFileSync(inputFilePath, "utf8");

    // Convert GPX to GeoJSON
    const geojson = gpx2geojson(gpxData);  // Correct method call

    // Define the output file name
    const outputFileName = file.replace(".gpx", ".geojson");
    const outputFilePath = path.join(outputFolder, outputFileName);

    // Write the GeoJSON file
    fs.writeFileSync(outputFilePath, JSON.stringify(geojson, null, 2));
    console.log(`Converted ${file} to ${outputFileName}`);
  });

  console.log("Conversion complete. Check the 'output-geojson' folder for results.");
}
