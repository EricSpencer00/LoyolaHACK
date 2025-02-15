// Initialize the Leaflet map
var map = L.map('map').setView([41.8781, -87.6298], 13);

// Add base tile layer from OpenStreetMap
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// Create layer groups for buses and trains
var busLayer = L.layerGroup();
var trainLayer = L.layerGroup();

// Fetch and display bus data (ensure your API supports the "type" query param)
fetch('/api/realtime?type=bus')
    .then(response => response.json())
    .then(data => {
        data.forEach(bus => {
            L.marker([bus.lat, bus.lng], {
                icon: L.icon({
                    iconUrl: '/static/images/bus-icon.png',
                    iconSize: [25, 25]
                })
            })
            .bindPopup(`<strong>Bus ${bus.line}</strong>`)
            .addTo(busLayer);
        });
    });

// Fetch and display train data
fetch('/api/realtime?type=train')
    .then(response => response.json())
    .then(data => {
        data.forEach(train => {
            L.marker([train.lat, train.lng], {
                icon: L.icon({
                    iconUrl: '/static/images/train-icon.png', // Update with your correct path
                    iconSize: [25, 25]
                })
            })
            .bindPopup(`<strong>Train ${train.line}</strong>`)
            .addTo(trainLayer);
        });
    });

// Add control for overlays
var overlays = {
    "Buses": busLayer,
    "Trains": trainLayer
};
L.control.layers(null, overlays).addTo(map);

// Add layers to map by default
busLayer.addTo(map);
trainLayer.addTo(map);
