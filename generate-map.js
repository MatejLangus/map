const fs = require('fs');
const path = require('path');

// Find all GPX files in the 'gpx-files' directory
const gpxDir = './gpx-files';
const gpxFiles = fs.readdirSync(gpxDir).filter(file => file.endsWith('.gpx'));

// Generate HTML content dynamically
const leafletHTML = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Matej lezel je taM</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet-gpx/1.5.0/gpx.min.js"></script>
    <style>
        #map { height: 100vh; margin: 0; }
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        const map = L.map('map').setView([46, 14.5], 8);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        }).addTo(map);

        const gpxFiles = ${JSON.stringify(gpxFiles.map(file => `./gpx-files/${file}`))};

        const allBounds = L.latLngBounds();

        gpxFiles.forEach(file => {
            new L.GPX(file, { async: true,
      }).on('loaded', function(e) {
        allBounds.extend(e.target.getBounds());   
            }).addTo(map);
        });
        
        map.fitBounds(allBounds);
    </script>
</body>
</html>
`;

// Write the HTML content to index.html
fs.writeFileSync('./index.html', leafletHTML, 'utf8');
console.log('Generated index.html with GPX tracks.');
