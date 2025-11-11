const fs = require('fs');
const path = require('path');

// Directories
const geojsonDir = './geojson-files';
const htmlFile = './index.html';

// Find all GeoJSON files
const geojsonFiles = fs.readdirSync(geojsonDir).filter(file => file.endsWith('.geojson'));

// Prepare entries with URL and filename
const geojsonFileEntries = geojsonFiles.map(file => ({
    url: `./geojson-files/${file}`,
    name: file
}));

// Generate HTML content
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

        const geojsonFiles = ${JSON.stringify(geojsonFileEntries)};

        geojsonFiles.forEach(entry => {
            fetch(entry.url)
                .then(response => response.json())
                .then(geojsonData => {
                    const allBounds = L.latLngBounds();
                    geojsonData = JSON.parse(geojsonData)
                    const allCoordinates = [];


                    geojsonData.features.forEach(feature => {
                        const geometry = feature.geometry;
                        if (!geometry) return;

                        if (geometry.type === 'LineString') {
                            geometry.coordinates.forEach(coord => {
                                const [lon, lat] = coord;
                                allCoordinates.push([lat, lon]);
                            });
                        }
                    });

                    if (allCoordinates.length > 1) {
                        const polyline = L.polyline(allCoordinates, {
                            color: 'blue',
                            weight: 3,
                            opacity: 1,
                            smoothFactor: 1
                        }).addTo(map);

                        polyline.on('click', function () {
                            // Toggle color
                            const currentColor = polyline.options.color;
                            polyline.setStyle({ color: currentColor === 'blue' ? 'red' : 'blue' });
                            polyline.bringToFront();

                            // Popup content
                            const props = geojsonData.features[0].properties || {};
                            const propsHtml = Object.entries(props)
                                .filter(([key]) => key !== 'ele' && key !== 'type')
                                .map(([key, value]) => '<strong>' + key + ':</strong> ' + value)
                                .join('<br>');

                            const popupContent = \`
                                <h3 style="margin:0; font-size:1.1em;">\${entry.name}</h3>
                                <hr>
                                \${propsHtml}
                            \`;

                            polyline.bindPopup(popupContent).openPopup();
                        });
                    }
                })
                .catch(error => {
                    console.error('Error loading GeoJSON file:', entry.url, error);
                });
        });
    </script>
</body>
</html>
`;

// Write the HTML file
fs.writeFileSync(htmlFile, leafletHTML, 'utf8');
console.log(`✅ Generated ${htmlFile} with GeoJSON tracks and popup filenames.`);
