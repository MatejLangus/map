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
        .leaflet-popup-content h3 {
            margin: 0;
            font-size: 1.1em;
            color: #2a4d9f;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        const map = L.map('map').setView([46, 14.5], 6);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);

        // List of GeoJSON files
        const geojsonFiles = ${JSON.stringify(geojsonFiles.map(file => `./geojson-files/${file}`))};

        geojsonFiles.forEach(file => {
            fetch(file)
                .then(response => response.json())
                .then(geojsonData => {
                    const allBounds = L.latLngBounds();
                    geojsonData = JSON.parse(geojsonData)
                    const allCoordinates = [];

                    geojsonData.features.forEach(feature => {
                        const geometry = feature.geometry;

                        if (geometry.type === 'LineString') {
                            geometry.coordinates.forEach(coord => {
                                const [lon, lat] = coord;
                                allCoordinates.push([lat, lon]);
                            });
                        }
                    });

                    if (allCoordinates.length > 1) {
                        const firstSegment = allCoordinates.slice(2, allCoordinates.length);
                        const polyline = L.polyline(firstSegment, {
                            color: 'blue',
                            weight: 3,
                            opacity: 1,
                            smoothFactor: 1
                        }).addTo(map);

                        polyline.on('click', function (e) {
                            // Toggle color on click
                            const currentColor = polyline.options.color;
                            const newColor = currentColor === 'blue' ? 'red' : 'blue';
                            polyline.setStyle({ color: newColor });
                            polyline.bringToFront();

                            // Popup content: file name + properties
                            const popupContent = \`
                                <h3>\${'${path.basename('${' + 'file' + '}')}'}<\/h3>
                                <hr>
                                \${Object.entries(geojsonData.features[0].properties || {})
                                    .filter(([key]) => key !== 'ele')
                                    .filter(([key]) => key !== 'type')
                                    .map(([key, value]) => '<strong>' + key + ':</strong> ' + value)
                                    .join('<br>')}
                            \`;

                            polyline.bindPopup(popupContent).openPopup();
                        });
                    }
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
console.log(`✅ Generated ${htmlFile} with GeoJSON tracks and popup filenames.`);
