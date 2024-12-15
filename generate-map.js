const fs = require('fs');
const path = require('path');

// Directories
const geojsonDir = './geojson-files';
const htmlFile = './index.html';

// Find all GeoJSON files in the 'geojson-files' directory
const geojsonFiles = fs.readdirSync(geojsonDir).filter(file => file.endsWith('.geojson'));

// Generate HTML content dynamically
const leafletHTML = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GeoJSON Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        #map { height: 100vh; margin: 0; }
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        const map = L.map('map').setView([0, 0], 2);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);

        // Loop through each GeoJSON file and add the features to the map
        const geojsonFiles = ${JSON.stringify(geojsonFiles.map(file => `./geojson-files/${file}`))};

        geojsonFiles.forEach(file => {
            fetch(file)
                .then(response => response.json())
                .then(geojsonData => {
                    const allBounds = L.latLngBounds();

                    geojsonData.features.forEach(feature => {
                        if (feature.geometry.type === 'LineString') {
                            const coordinates = feature.geometry.coordinates;
                            const latLngs = coordinates.map(coord => [coord[1], coord[0]]); // Convert [lon, lat] to [lat, lon]

                            L.polyline(latLngs, {
                                color: 'blue',
                                weight: 3,
                                opacity: 1,
                                smoothFactor: 1
                            }).addTo(map);
                            
                            // Extend the bounds of the map based on the feature's coordinates
                            allBounds.extend(latLngs);
                        }
                    });

                    // Adjust the map's bounds to fit all features
                    map.fitBounds(allBounds);
                })
                .catch(error => {
                    console.error('Error loading GeoJSON file:', file, error);
                });
        });
    </script>
</body>
</html>
`;

// Write the HTML content to index.html
fs.writeFileSync(htmlFile, leafletHTML, 'utf8');
console.log(`Generated ${htmlFile} with GeoJSON tracks.`);