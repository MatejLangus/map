const fs = require("fs");
const path = require("path");

const inputDir = "./geojson-files";
const outputFile = "./merged.geojson";

const files = fs.readdirSync(inputDir).filter(f => f.endsWith(".geojson"));

let allFeatures = [];

files.forEach(file => {
  const filePath = path.join(inputDir, file);
  let raw = fs.readFileSync(filePath, "utf8").trim();

  try {
    // Parse possibly double-encoded GeoJSON
    let data = JSON.parse(raw);
    if (typeof data === "string") {
      data = JSON.parse(data);
    }

    // Only take valid FeatureCollections
    if (data.type === "FeatureCollection" && Array.isArray(data.features)) {
      // Add file name as property
      data.features.forEach(f => {
        if (!f.properties) f.properties = {};
        f.properties.sourceFile = path.basename(file, ".geojson");
      });

      allFeatures.push(...data.features);
    } else {
      console.warn(`⚠️ Skipped invalid GeoJSON in ${file}`);
    }
  } catch (err) {
    console.warn(`❌ Error parsing ${file}: ${err.message}`);
  }
});

const merged = {
  type: "FeatureCollection",
  features: allFeatures
};

// Write minified JSON (no whitespace)
fs.writeFileSync(outputFile, JSON.stringify(merged));
console.log(`✅ Merged ${files.length} files into ${outputFile} (${allFeatures.length} features total).`);
