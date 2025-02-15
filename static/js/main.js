var map = L.map('map').setView([41.8781, -87.6298], 13);

// Add base tile layer
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// Bus Layer
var busLayer = L.layerGroup();
var trainLayer = L.layerGroup();

// Fetch and display bus data
fetch('/api/realtime?type=bus')
    .then(response => response.json())
    .then(data => {
        data.forEach(bus => {
            L.marker([bus.lat, bus.lng], {icon: L.icon({iconUrl: 'bus-icon.png', iconSize: [25, 25]})})
                .bindPopup(`<strong>Bus ${bus.line}</strong>`)
                .addTo(busLayer);
        });
    });

// Fetch and display train data
fetch('/api/realtime?type=train')
    .then(response => response.json())
    .then(data => {
        data.forEach(train => {
            L.marker([train.lat, train.lng], {icon: L.icon({iconUrl: 'train-icon.png', iconSize: [25, 25]})})
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
L.tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token=YOUR_ACCESS_TOKEN', {
    attribution: 'Map data &copy; OpenStreetMap contributors, Map imagery © Mapbox',
    id: 'mapbox/dark-v10'
}).addTo(map);


// Add layers to map by default
busLayer.addTo(map);
trainLayer.addTo(map);
