// static/js/main.js

// Set default center if no home coordinates (e.g., Chicago center)
var defaultCenter = [41.8781, -87.6298];
// Use passed-in home coordinates if available
var mapCenter = (typeof userHome !== 'undefined' && userHome.lat && userHome.lng) 
                ? [userHome.lat, userHome.lng] 
                : defaultCenter;

// Initialize the Leaflet map
var map = L.map('map').setView(mapCenter, 13);

// Use a simpler tile layer (Stamen Toner Lite)
L.tileLayer('https://stamen-tiles.a.ssl.fastly.net/toner-lite/{z}/{x}/{y}.png', {
    attribution: 'Map tiles by Stamen Design',
    maxZoom: 18
}).addTo(map);

// Create layer groups for buses and trains
var busLayer = L.layerGroup();
var trainLayer = L.layerGroup();

// Fetch and display bus data
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
                    iconUrl: '/static/images/train-icon.png',
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
