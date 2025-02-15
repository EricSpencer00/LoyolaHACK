// Initialize the Leaflet map
var map = L.map('map').setView([41.8781, -87.6298], 13);

// Add OpenStreetMap tile layer
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// Function to fetch and display real-time transit data
function fetchRealtimeData() {
    fetch('/api/realtime')
        .then(response => response.json())
        .then(data => {
            // Clear existing markers (for simplicity, this demo does not remove old markers)
            data.forEach(transit => {
                // Create a marker for each transit vehicle
                L.marker([transit.lat, transit.lng])
                    .addTo(map)
                    .bindPopup(`<b>${transit.type.toUpperCase()} ${transit.line}</b>`);
            });
        })
        .catch(error => console.error('Error fetching realtime data:', error));
}

// Function to fetch and display predictive analytics data
function fetchPredictions() {
    fetch('/api/predictions')
        .then(response => response.json())
        .then(data => {
            const predictionList = document.getElementById('prediction-list');
            predictionList.innerHTML = '';
            data.forEach(prediction => {
                let li = document.createElement('li');
                li.textContent = `Line ${prediction.line} - Predicted Arrival: ${new Date(prediction.predicted_arrival).toLocaleTimeString()} (Confidence: ${Math.round(prediction.confidence * 100)}%)`;
                predictionList.appendChild(li);
            });
        })
        .catch(error => console.error('Error fetching predictions:', error));
}

// Initial fetch for data
fetchRealtimeData();
fetchPredictions();

// Optionally, refresh data periodically (e.g., every 30 seconds)
setInterval(() => {
    fetchRealtimeData();
    fetchPredictions();
}, 30000);
