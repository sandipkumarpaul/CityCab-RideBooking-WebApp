let map, dashboardMap;
let pickupMarker, dropoffMarker, assignedDriverMarker;
let nearbyDriverMarkers = [];
let pickupRouteLine = null, destinationRouteLine = null, previewRouteLine = null;
let selectedTier = 'Comfort';
let currentRating = 5;

const SIMULATED_DRIVERS = [
    { name: "Karim Rahman", vehicle: "Toyota Axio (Comfort)", plate: "DKA-11-2233" },
    { name: "Rahim Uddin", vehicle: "Honda Grace (Economy)", plate: "DKA-55-9988" },
    { name: "Tanvir Hossain", vehicle: "Yamaha FZ (Bike)", plate: "DKA-88-1122" },
    { name: "Alamgir Kabir", vehicle: "CNG Auto-Rickshaw", plate: "DKA-77-3344" },
    { name: "Farhan Ahmed", vehicle: "Toyota Camry (Premium)", plate: "DKA-99-0011" }
];

const POPULAR_LOCATIONS = [
    { title: "Banani Road 11", subtitle: "Banani, Dhaka", lat: 23.7937, lng: 90.4066 },
    { title: "BRAC University", subtitle: "Merul Badda / Mohakhali, Dhaka", lat: 23.7771, lng: 90.4043 },
    { title: "Gulshan 2 Circle", subtitle: "Gulshan, Dhaka", lat: 23.7979, lng: 90.4144 },
    { title: "Hazrat Shahjalal Int'l Airport", subtitle: "Kurmitola / Airport, Dhaka", lat: 23.8511, lng: 90.4074 },
    { title: "Dhanmondi 32", subtitle: "Dhanmondi, Dhaka", lat: 23.7516, lng: 90.3782 },
    { title: "Uttara Sector 7", subtitle: "Uttara, Dhaka", lat: 23.8700, lng: 90.3980 },
    { title: "Farmgate Bus Stop", subtitle: "Tejgaon / Farmgate, Dhaka", lat: 23.7588, lng: 90.3892 },
    { title: "Jamuna Future Park", subtitle: "Kuril / Pragati Sarani, Dhaka", lat: 23.8135, lng: 90.4242 },
    { title: "Bashundhara Residential Area", subtitle: "Baridhara / Bashundhara, Dhaka", lat: 23.8103, lng: 90.4312 },
    { title: "Shahbagh Intersection", subtitle: "Shahbagh / Dhaka University", lat: 23.7388, lng: 90.3956 },
    { title: "Motijheel Commercial Area", subtitle: "Motijheel, Dhaka", lat: 23.7289, lng: 90.4172 },
    { title: "Mirpur 10 Circle", subtitle: "Mirpur, Dhaka", lat: 23.8069, lng: 90.3687 }
];

document.addEventListener('DOMContentLoaded', function() {
    initBookingMap();
    initDashboardMap();
    recalculateFare();

    document.addEventListener('click', function(e) {
        if (!e.target.closest('.uber-input-group')) {
            document.querySelectorAll('.autocomplete-dropdown').forEach(el => el.classList.add('d-none'));
        }
    });
});

function createCustomIcon(emoji, bgClass = 'bg-dark') {
    return L.divIcon({
        html: `<div class="rounded-circle ${bgClass} border border-2 border-white d-flex align-items-center justify-content-center shadow-lg" style="width:36px; height:36px; font-size:1.2rem;">${emoji}</div>`,
        className: 'custom-leaflet-icon',
        iconSize: [36, 36],
        iconAnchor: [18, 18]
    });
}

function spawnNearbyDrivers(centerLat, centerLng) {
    clearNearbyDrivers();
    if (!map) return;

    const icons = ['🏍️', '🛺', '🚗', '🚕', '🚘'];
    for (let i = 0; i < 6; i++) {
        const offsetLat = (Math.random() - 0.5) * 0.015;
        const offsetLng = (Math.random() - 0.5) * 0.015;
        const lat = centerLat + offsetLat;
        const lng = centerLng + offsetLng;

        const vehicleEmoji = icons[i % icons.length];
        const marker = L.marker([lat, lng], {
            icon: createCustomIcon(vehicleEmoji)
        }).addTo(map).bindPopup(`Nearby Available ${vehicleEmoji}`);

        nearbyDriverMarkers.push(marker);
    }
}

function clearNearbyDrivers() {
    nearbyDriverMarkers.forEach(m => map.removeLayer(m));
    nearbyDriverMarkers = [];
}

let searchTimeout;
function handleAddressSearch(type) {
    clearTimeout(searchTimeout);
    const inputEl = document.getElementById(type + '_address');
    const dropdownEl = document.getElementById(type + '_suggestions');
    const query = inputEl.value.trim().toLowerCase();

    if (query.length === 0) {
        dropdownEl.classList.add('d-none');
        return;
    }

    const matches = POPULAR_LOCATIONS.filter(loc =>
        loc.title.toLowerCase().includes(query) || loc.subtitle.toLowerCase().includes(query)
    );

    renderSuggestions(type, matches);

    if (query.length > 2) {
        searchTimeout = setTimeout(() => {
            fetch(`https://nominatim.openstreetmap.org/search?format=json&countrycodes=bd&q=${encodeURIComponent(query + ' Dhaka')}`)
                .then(res => res.json())
                .then(data => {
                    if (data && data.length > 0) {
                        const apiMatches = data.slice(0, 5).map(item => ({
                            title: item.display_name.split(',')[0],
                            subtitle: item.display_name,
                            lat: parseFloat(item.lat),
                            lng: parseFloat(item.lon)
                        }));
                        renderSuggestions(type, [...matches, ...apiMatches]);
                    }
                })
                .catch(() => {});
        }, 300);
    }
}

function renderSuggestions(type, items) {
    const dropdownEl = document.getElementById(type + '_suggestions');
    if (!items || items.length === 0) {
        dropdownEl.classList.add('d-none');
        return;
    }

    let html = '';
    items.forEach((item) => {
        html += `
            <div class="autocomplete-item" onclick="selectLocationOption('${type}', '${escapeHtml(item.title)}', ${item.lat}, ${item.lng})">
                <i class="fa-solid fa-location-dot"></i>
                <div>
                    <div class="autocomplete-title">${item.title}</div>
                    <div class="autocomplete-subtitle">${item.subtitle}</div>
                </div>
            </div>
        `;
    });

    dropdownEl.innerHTML = html;
    dropdownEl.classList.remove('d-none');
}

function escapeHtml(text) {
    return text.replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

function selectLocationOption(type, title, lat, lng) {
    document.getElementById(type + '_address').value = title;
    document.getElementById(type + '_lat').value = lat;
    document.getElementById(type + '_lng').value = lng;
    document.getElementById(type + '_suggestions').classList.add('d-none');

    if (type === 'pickup' && pickupMarker) {
        pickupMarker.setLatLng([lat, lng]);
        spawnNearbyDrivers(lat, lng);
    } else if (type === 'dropoff' && dropoffMarker) {
        dropoffMarker.setLatLng([lat, lng]);
    }

    if (map && pickupMarker && dropoffMarker) {
        const bounds = L.latLngBounds([pickupMarker.getLatLng(), dropoffMarker.getLatLng()]);
        map.fitBounds(bounds, { padding: [40, 40] });
    }

    recalculateFare();
}

async function fetchRoadRoute(startCoord, endCoord) {
    try {
        const url = `https://router.project-osrm.org/route/v1/driving/${startCoord.lng},${startCoord.lat};${endCoord.lng},${endCoord.lat}?overview=full&geometries=geojson`;
        const res = await fetch(url);
        const data = await res.json();
        if (data && data.routes && data.routes.length > 0) {
            const coordinates = data.routes[0].geometry.coordinates;
            return coordinates.map(c => ({ lat: c[1], lng: c[0] }));
        }
    } catch (e) {
    }
    return [
        { lat: startCoord.lat, lng: startCoord.lng },
        { lat: endCoord.lat, lng: endCoord.lng }
    ];
}

function initBookingMap() {
    const mapElement = document.getElementById('map');
    if (!mapElement) return;

    map = L.map('map').setView([23.7937, 90.4066], 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap'
    }).addTo(map);

    const pickupLat = parseFloat(document.getElementById('pickup_lat').value) || 23.7937;
    const pickupLng = parseFloat(document.getElementById('pickup_lng').value) || 90.4066;
    const dropoffLat = parseFloat(document.getElementById('dropoff_lat').value) || 23.7771;
    const dropoffLng = parseFloat(document.getElementById('dropoff_lng').value) || 90.4043;

    pickupMarker = L.marker([pickupLat, pickupLng], {
        draggable: true,
        icon: createCustomIcon('📍', 'bg-success')
    }).addTo(map).bindPopup('Pickup Location');

    dropoffMarker = L.marker([dropoffLat, dropoffLng], {
        draggable: true,
        icon: createCustomIcon('🏁', 'bg-danger')
    }).addTo(map).bindPopup('Dropoff Destination');

    pickupMarker.on('dragend', function(e) {
        const coord = e.target.getLatLng();
        document.getElementById('pickup_lat').value = coord.lat;
        document.getElementById('pickup_lng').value = coord.lng;
        spawnNearbyDrivers(coord.lat, coord.lng);
        recalculateFare();
    });

    dropoffMarker.on('dragend', function(e) {
        const coord = e.target.getLatLng();
        document.getElementById('dropoff_lat').value = coord.lat;
        document.getElementById('dropoff_lng').value = coord.lng;
        recalculateFare();
    });

    spawnNearbyDrivers(pickupLat, pickupLng);
}

function initDashboardMap() {
    const dashMapEl = document.getElementById('dashboard-map');
    if (!dashMapEl) return;

    dashboardMap = L.map('dashboard-map').setView([23.785, 90.405], 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap'
    }).addTo(dashboardMap);

    L.marker([23.7800, 90.4010], { icon: createCustomIcon('🚨', 'bg-danger') }).addTo(dashboardMap).bindPopup('Active Emergency Spot (Mohakhali)');
    L.marker([23.7950, 90.4120], { icon: createCustomIcon('🛡️', 'bg-success') }).addTo(dashboardMap).bindPopup('Your Responder Position (1.4 km away)');
}

function recalculateFare() {
    const pLat = parseFloat(document.getElementById('pickup_lat')?.value || 23.7937);
    const pLng = parseFloat(document.getElementById('pickup_lng')?.value || 90.4066);
    const dLat = parseFloat(document.getElementById('dropoff_lat')?.value || 23.7771);
    const dLng = parseFloat(document.getElementById('dropoff_lng')?.value || 90.4043);

    fetch('/api/estimate_fare', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            pickup_lat: pLat, pickup_lng: pLng,
            dropoff_lat: dLat, dropoff_lng: dLng
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            document.getElementById('distance-display').innerText = data.distance_km.toFixed(2) + ' km';
            if (document.getElementById('price-Bike')) document.getElementById('price-Bike').innerText = '$' + data.estimates.Bike.toFixed(2);
            if (document.getElementById('price-CNG')) document.getElementById('price-CNG').innerText = '$' + data.estimates.CNG.toFixed(2);
            if (document.getElementById('price-Economy')) document.getElementById('price-Economy').innerText = '$' + data.estimates.Economy.toFixed(2);
            if (document.getElementById('price-Comfort')) document.getElementById('price-Comfort').innerText = '$' + data.estimates.Comfort.toFixed(2);
            if (document.getElementById('price-Premium')) document.getElementById('price-Premium').innerText = '$' + data.estimates.Premium.toFixed(2);
        }
    });
}

function selectTier(tier) {
    selectedTier = tier;
    document.querySelectorAll('.uber-tier-item').forEach(card => card.classList.remove('active'));
    document.getElementById('tier-' + tier)?.classList.add('active');
}

function animateMarkerAlongRoadPath(marker, points, durationMs, onProgress, onComplete) {
    if (!points || points.length === 0) {
        if (onComplete) onComplete();
        return;
    }
    if (points.length === 1) {
        marker.setLatLng([points[0].lat, points[0].lng]);
        if (onComplete) onComplete();
        return;
    }

    let distances = [0];
    let totalDist = 0;
    for (let i = 0; i < points.length - 1; i++) {
        const p1 = points[i];
        const p2 = points[i + 1];
        const d = Math.hypot(p2.lat - p1.lat, p2.lng - p1.lng);
        totalDist += d;
        distances.push(totalDist);
    }

    if (totalDist === 0) {
        marker.setLatLng([points[0].lat, points[0].lng]);
        if (onComplete) onComplete();
        return;
    }

    const startTime = performance.now();

    function frame(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / durationMs, 1.0);
        const currentTargetDist = progress * totalDist;

        let segmentIdx = 0;
        for (let i = 0; i < distances.length - 1; i++) {
            if (currentTargetDist >= distances[i] && currentTargetDist <= distances[i + 1]) {
                segmentIdx = i;
                break;
            }
        }

        const segStartDist = distances[segmentIdx];
        const segEndDist = distances[segmentIdx + 1] || totalDist;
        const segDist = segEndDist - segStartDist;
        const segProgress = segDist === 0 ? 0 : (currentTargetDist - segStartDist) / segDist;

        const pA = points[segmentIdx];
        const pB = points[Math.min(segmentIdx + 1, points.length - 1)];

        const curLat = pA.lat + (pB.lat - pA.lat) * segProgress;
        const curLng = pA.lng + (pB.lng - pA.lng) * segProgress;

        marker.setLatLng([curLat, curLng]);

        if (onProgress) onProgress(progress);

        if (progress < 1.0) {
            requestAnimationFrame(frame);
        } else if (onComplete) {
            onComplete();
        }
    }

    requestAnimationFrame(frame);
}

function addTripToRecentTable(ride) {
    const tbody = document.getElementById('recent-trips-table-body');
    if (!tbody) return;
    const noTripsRow = document.getElementById('no-trips-row');
    if (noTripsRow) noTripsRow.remove();

    const now = new Date();
    const dateStr = now.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) + ' ' +
                    now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });

    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td>
            <div class="fw-semibold text-white small">${ride.pickup_address} &rarr; ${ride.dropoff_address}</div>
            <div class="text-secondary extra-small">${dateStr}</div>
        </td>
        <td class="fw-bold text-success">$${parseFloat(ride.estimated_fare).toFixed(2)}</td>
        <td>
            <span class="badge badge-uber-success rounded-pill px-3 py-1">Completed</span>
        </td>
        <td class="text-end">
            <a href="/ride/${ride.id}/invoice" class="btn btn-outline-light btn-sm rounded-circle me-1" title="Download PDF Receipt">
                <i class="fa-solid fa-file-pdf text-warning"></i>
            </a>
            <button class="btn btn-success btn-sm rounded-pill px-3" onclick="openPaymentModal('${ride.id}', '${ride.estimated_fare}')">Pay</button>
        </td>
    `;

    tbody.insertBefore(tr, tbody.firstChild);
}

function requestRide() {
    const pickupAddress = document.getElementById('pickup_address').value;
    const dropoffAddress = document.getElementById('dropoff_address').value;
    const pLat = parseFloat(document.getElementById('pickup_lat').value);
    const pLng = parseFloat(document.getElementById('pickup_lng').value);
    const dLat = parseFloat(document.getElementById('dropoff_lat').value);
    const dLng = parseFloat(document.getElementById('dropoff_lng').value);

    fetch('/api/request_ride', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            pickup_address: pickupAddress,
            dropoff_address: dropoffAddress,
            pickup_lat: pLat, pickup_lng: pLng,
            dropoff_lat: dLat, dropoff_lng: dLng,
            vehicle_tier: selectedTier
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status !== 'success') {
            alert('Error requesting ride: ' + data.message);
            return;
        }

        const createdRide = data.ride;
        const vehicleIcon = selectedTier === 'Bike' ? '🏍️' : (selectedTier === 'CNG' ? '🛺' : '🚕');
        
        // Use the exact driver matched from backend
        const assignedDriver = createdRide.driver || {
            name: selectedTier === 'Bike' ? 'Shakil Hasan' : (selectedTier === 'CNG' ? 'Alamgir Kabir' : (selectedTier === 'Economy' ? 'Rahim Uddin' : (selectedTier === 'Premium' ? 'Tanvir Hossain' : 'Karim Rahman'))),
            vehicle_model: selectedTier === 'Bike' ? 'Yamaha FZ-S (Bike)' : (selectedTier === 'CNG' ? 'Bajaj RE 4S CNG' : (selectedTier === 'Economy' ? 'Honda Grace' : (selectedTier === 'Premium' ? 'Toyota Camry' : 'Toyota Axio'))),
            license_plate: selectedTier === 'Bike' ? 'DKA-88-1122' : (selectedTier === 'CNG' ? 'DKA-77-3344' : (selectedTier === 'Economy' ? 'DKA-55-9988' : (selectedTier === 'Premium' ? 'DKA-99-0011' : 'DKA-11-2233'))),
            current_lat: pLat + 0.008,
            current_lng: pLng - 0.007
        };

        clearNearbyDrivers();
        showSimulationStatusOverlay('SEARCHING', `Searching for closest available ${selectedTier} driver nearby on city roads...`, '0%');

        setTimeout(async () => {
            const initialDriverPos = {
                lat: assignedDriver.current_lat || (pLat + 0.010),
                lng: assignedDriver.current_lng || (pLng - 0.008)
            };
            const pickupCoords = { lat: pLat, lng: pLng };
            const dropoffCoords = { lat: dLat, lng: dLng };

            const pickupRoadPoints = await fetchRoadRoute(initialDriverPos, pickupCoords);
            const destinationRoadPoints = await fetchRoadRoute(pickupCoords, dropoffCoords);

            showAssignmentModal(assignedDriver.name, assignedDriver.vehicle_model, assignedDriver.license_plate, function() {
                assignedDriverMarker = L.marker([pickupRoadPoints[0].lat, pickupRoadPoints[0].lng], {
                    icon: createCustomIcon(vehicleIcon, 'bg-warning')
                }).addTo(map).bindPopup(`Assigned Driver: ${assignedDriver.name} (${assignedDriver.vehicle_model})`);

                const pickupPolylineLatlngs = pickupRoadPoints.map(p => [p.lat, p.lng]);
                pickupRouteLine = L.polyline(pickupPolylineLatlngs, {
                    color: '#f59e0b',
                    dashArray: '6, 8',
                    weight: 5,
                    opacity: 0.9
                }).addTo(map);

                map.fitBounds(pickupRouteLine.getBounds(), { padding: [50, 50] });

                showSimulationStatusOverlay('EN_ROUTE_PICKUP', `Driver ${assignedDriver.name} is navigating road network to pickup!`, '0%');

                animateMarkerAlongRoadPath(
                    assignedDriverMarker,
                    pickupRoadPoints,
                    7000,
                    function(progress) {
                        const pct = Math.round(progress * 100);
                        showSimulationStatusOverlay('EN_ROUTE_PICKUP', `Driver ${assignedDriver.name} driving on road to pickup... (${pct}%)`, pct + '%');
                    },
                    function() {
                        if (pickupRouteLine) map.removeLayer(pickupRouteLine);
                        alert(`🚕 ${assignedDriver.name} has arrived at pickup! Ride started. Driving on roads to destination.`);

                        const destPolylineLatlngs = destinationRoadPoints.map(p => [p.lat, p.lng]);
                        destinationRouteLine = L.polyline(destPolylineLatlngs, {
                            color: '#10b981',
                            weight: 5,
                            opacity: 0.9
                        }).addTo(map);

                        map.fitBounds(destinationRouteLine.getBounds(), { padding: [50, 50] });

                        showSimulationStatusOverlay('EN_ROUTE_DESTINATION', `Following city roads to ${dropoffAddress}...`, '0%');

                        animateMarkerAlongRoadPath(
                            assignedDriverMarker,
                            destinationRoadPoints,
                            9000,
                            function(progress) {
                                const pct = Math.round(progress * 100);
                                showSimulationStatusOverlay('EN_ROUTE_DESTINATION', `Driving along road route... (${pct}%)`, pct + '%');
                            },
                            function() {
                                if (destinationRouteLine) map.removeLayer(destinationRouteLine);
                                if (assignedDriverMarker) map.removeLayer(assignedDriverMarker);

                                fetch(`/api/ride/${createdRide.id}/status`, {
                                    method: 'POST',
                                    headers: {'Content-Type': 'application/json'},
                                    body: JSON.stringify({ status: 'completed' })
                                })
                                .then(r => r.json())
                                .then(() => {
                                    createdRide.status = 'completed';
                                    addTripToRecentTable(createdRide);

                                    showSimulationStatusOverlay('COMPLETED', '🎉 Trip Completed! Thank you for riding with CityCab.', '100%');

                                    setTimeout(() => {
                                        alert(`🎉 Ride Completed! You have safely reached ${dropoffAddress}.\n\nThis ride is now saved in your Recent Trips log.`);
                                        hideSimulationStatusOverlay();
                                        spawnNearbyDrivers(pLat, pLng);
                                        openPaymentModal(createdRide.id, createdRide.estimated_fare);
                                    }, 1000);
                                });
                            }
                        );
                    }
                );
            });

        }, 5000);
    });
}

function showAssignmentModal(name, vehicle, plate, onConfirm) {
    const modalHtml = `
        <div class="modal fade show" id="assignmentModal" style="display:block; background:rgba(0,0,0,0.85); z-index:2000;">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content bg-dark text-light border-warning rounded-4 p-3 shadow-lg text-center">
                    <div class="modal-body">
                        <div class="fs-1 mb-2">🎉</div>
                        <h4 class="fw-bold text-warning mb-1">Driver Assigned!</h4>
                        <h5 class="text-white fw-semibold mb-2">${name}</h5>
                        <p class="text-secondary small mb-3">${vehicle} • <span class="badge bg-secondary font-monospace">${plate}</span></p>
                        <div class="bg-black p-3 rounded-3 border border-secondary mb-3">
                            <span class="text-secondary small">Status:</span>
                            <div class="text-success fw-bold">Driving through city street network to pickup</div>
                            <span class="text-warning small">Estimated Arrival: 2 Mins</span>
                        </div>
                        <button type="button" class="btn btn-warning w-100 fw-bold py-3 rounded-pill text-dark" onclick="closeAssignmentModal()">
                            Track Driver Along Real Roads 🚀
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
    window.closeAssignmentModal = function() {
        const el = document.getElementById('assignmentModal');
        if (el) el.remove();
        if (onConfirm) onConfirm();
    };
}

function showSimulationStatusOverlay(state, message, pct) {
    let overlay = document.getElementById('sim-status-overlay');
    if (!overlay) {
        const html = `
            <div id="sim-status-overlay" class="uber-card p-3 mb-3 border-warning bg-black shadow-lg">
                <div class="d-flex align-items-center justify-content-between mb-2">
                    <div class="d-flex align-items-center gap-2">
                        <span class="spinner-border spinner-border-sm text-warning" id="sim-spinner"></span>
                        <h6 class="fw-bold text-white mb-0" id="sim-title">Live Road Navigator</h6>
                    </div>
                    <span class="badge bg-warning text-dark fw-bold" id="sim-pct">${pct}</span>
                </div>
                <div class="progress bg-secondary mb-2" style="height: 6px;">
                    <div class="progress-bar bg-warning progress-bar-striped progress-bar-animated" id="sim-bar" style="width: ${pct}"></div>
                </div>
                <div class="text-secondary small" id="sim-msg">${message}</div>
            </div>
        `;
        const container = document.getElementById('map').parentElement;
        container.insertAdjacentHTML('afterbegin', html);
        overlay = document.getElementById('sim-status-overlay');
    }

    document.getElementById('sim-msg').innerText = message;
    document.getElementById('sim-pct').innerText = pct;
    document.getElementById('sim-bar').style.width = pct;

    if (state === 'SEARCHING') {
        document.getElementById('sim-title').innerText = 'Searching Driver on Road Network...';
    } else if (state === 'EN_ROUTE_PICKUP') {
        document.getElementById('sim-title').innerText = 'Driver Driving on City Streets to Pickup';
    } else if (state === 'EN_ROUTE_DESTINATION') {
        document.getElementById('sim-title').innerText = 'En-Route: Driving Along Real Road Route';
    } else if (state === 'COMPLETED') {
        document.getElementById('sim-title').innerText = 'Trip Completed!';
        document.getElementById('sim-spinner').classList.add('d-none');
    }
}

function hideSimulationStatusOverlay() {
    const el = document.getElementById('sim-status-overlay');
    if (el) el.remove();
}

function triggerEmergencySOS(rideId) {
    if (!confirm('Are you sure you want to trigger Emergency SOS? Trusted contacts and community responders will be alerted immediately!')) return;

    fetch('/api/trigger_sos', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ ride_id: rideId, alert_lat: 23.7800, alert_lng: 90.4010 })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        window.location.reload();
    });
}

function respondToSOS(alertId) {
    fetch(`/api/respond_sos/${alertId}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ user_lat: 23.7950, user_lng: 90.4120 })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            alert(data.message);
            window.location.reload();
        } else {
            alert('Error: ' + data.message);
        }
    });
}

function toggleDriverAvailability() {
    fetch('/api/driver/toggle_availability', { method: 'POST' })
    .then(res => res.json())
    .then(data => { window.location.reload(); });
}

function acceptRide(rideId) {
    fetch(`/api/driver/accept_ride/${rideId}`, { method: 'POST' })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            alert('Trip accepted! Proceeding to pickup.');
            window.location.reload();
        } else {
            alert(data.message);
        }
    });
}

function updateRideStatus(rideId, status) {
    fetch(`/api/ride/${rideId}/status`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ status: status })
    })
    .then(res => res.json())
    .then(data => { window.location.reload(); });
}

function toggleGatewayFields() {
    const method = document.getElementById('payment_method')?.value || 'bkash';
    const container = document.getElementById('gateway_dynamic_fields');
    if (!container) return;

    if (method === 'bkash') {
        container.innerHTML = `
            <div class="p-3 rounded-3 mb-3 border border-danger bg-black">
                <div class="d-flex align-items-center justify-content-between mb-2">
                    <span class="text-danger fw-bold"><i class="fa-solid fa-mobile-screen me-1"></i> bKash Sandbox Gateway</span>
                    <span class="badge bg-danger">Simulated</span>
                </div>
                <div class="mb-2">
                    <label class="extra-small text-secondary mb-1">bKash Mobile Account Number</label>
                    <input type="text" class="form-control uber-input form-control-sm ps-3 font-monospace" id="bkash_acc" value="01711223344" placeholder="017xxxxxxxx">
                </div>
                <div>
                    <label class="extra-small text-secondary mb-1">bKash 5-Digit PIN</label>
                    <input type="password" class="form-control uber-input form-control-sm ps-3 font-monospace" id="bkash_pin" value="12345" placeholder="•••••">
                </div>
            </div>
        `;
    } else if (method === 'nagad') {
        container.innerHTML = `
            <div class="p-3 rounded-3 mb-3 border border-warning bg-black">
                <div class="d-flex align-items-center justify-content-between mb-2">
                    <span class="text-warning fw-bold"><i class="fa-solid fa-wallet me-1"></i> Nagad Sandbox Gateway</span>
                    <span class="badge bg-warning text-dark">Simulated</span>
                </div>
                <div class="mb-2">
                    <label class="extra-small text-secondary mb-1">Nagad Mobile Account Number</label>
                    <input type="text" class="form-control uber-input form-control-sm ps-3 font-monospace" id="nagad_acc" value="01999887766" placeholder="019xxxxxxxx">
                </div>
                <div>
                    <label class="extra-small text-secondary mb-1">Nagad 4-Digit PIN</label>
                    <input type="password" class="form-control uber-input form-control-sm ps-3 font-monospace" id="nagad_pin" value="1234" placeholder="••••">
                </div>
            </div>
        `;
    } else if (method === 'card') {
        container.innerHTML = `
            <div class="p-3 rounded-3 mb-3 border border-primary bg-black">
                <div class="d-flex align-items-center justify-content-between mb-2">
                    <span class="text-primary fw-bold"><i class="fa-solid fa-credit-card me-1"></i> Visa / Mastercard 3D Secure</span>
                    <span class="badge bg-primary">Sandbox</span>
                </div>
                <div class="mb-2">
                    <label class="extra-small text-secondary mb-1">Card Number</label>
                    <input type="text" class="form-control uber-input form-control-sm ps-3 font-monospace" id="card_num" value="4242 •••• •••• 4242">
                </div>
                <div class="row g-2">
                    <div class="col-6">
                        <label class="extra-small text-secondary mb-1">Expiry Date</label>
                        <input type="text" class="form-control uber-input form-control-sm ps-3 font-monospace" id="card_exp" value="12/28">
                    </div>
                    <div class="col-6">
                        <label class="extra-small text-secondary mb-1">CVV Code</label>
                        <input type="password" class="form-control uber-input form-control-sm ps-3 font-monospace" id="card_cvv" value="123">
                    </div>
                </div>
            </div>
        `;
    } else if (method === 'wallet') {
        container.innerHTML = `
            <div class="p-3 rounded-3 mb-3 border border-success bg-black text-center">
                <i class="fa-solid fa-wallet text-success fs-3 mb-2 d-block"></i>
                <div class="text-success fw-bold">CityCab Digital Wallet Balance</div>
                <div class="extra-small text-secondary mt-1">1-Tap Instant settlement directly deducted from balance.</div>
            </div>
        `;
    }
}

function openPaymentModal(rideId, amount) {
    document.getElementById('pay_ride_id').value = rideId;
    document.getElementById('pay_amount_display').innerText = '$' + parseFloat(amount).toFixed(2);
    toggleGatewayFields();
    const modal = new bootstrap.Modal(document.getElementById('paymentModal'));
    modal.show();
}

function processPayment() {
    const rideId = document.getElementById('pay_ride_id').value;
    const method = document.getElementById('payment_method').value;

    const btn = document.querySelector('#paymentModal .btn-success');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Authorizing Gateway...';
    }

    setTimeout(() => {
        fetch('/api/pay_ride', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ride_id: rideId, payment_method: method })
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                alert(`✅ Payment Authorized!\n${data.message}\nReference Ref: ${data.transaction_ref}`);
                window.location.reload();
            } else {
                alert('Payment Error: ' + data.message);
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = 'Authorize & Pay';
                }
            }
        })
        .catch(err => {
            alert('Payment failed: ' + err);
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = 'Authorize & Pay';
            }
        });
    }, 1000);
}

function openReviewModal(rideId) {
    document.getElementById('review_ride_id').value = rideId;
    const modal = new bootstrap.Modal(document.getElementById('reviewModal'));
    modal.show();
}

function setRating(rating) {
    currentRating = rating;
    document.getElementById('review_rating_val').value = rating;
    const stars = document.getElementById('star-rating-container').children;
    for (let i = 0; i < 5; i++) {
        if (i < rating) {
            stars[i].classList.replace('fa-regular', 'fa-solid');
        } else {
            stars[i].classList.replace('fa-solid', 'fa-regular');
        }
    }
}

function submitReview() {
    const rideId = document.getElementById('review_ride_id').value;
    const rating = document.getElementById('review_rating_val').value;
    const comment = document.getElementById('review_comment').value;

    fetch('/api/submit_review', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ ride_id: rideId, rating: rating, comment: comment })
    })
    .then(res => res.json())
    .then(data => {
        alert(data.message);
        window.location.reload();
    });
}

function useCurrentGPSLocation() {
    if (!navigator.geolocation) {
        alert('Geolocation is not supported by your browser.');
        return;
    }

    const btn = document.getElementById('btn-gps-pickup');
    if (btn) {
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Locating...';
        btn.disabled = true;
    }

    navigator.geolocation.getCurrentPosition(
        function(position) {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;

            document.getElementById('pickup_lat').value = lat;
            document.getElementById('pickup_lng').value = lng;
            document.getElementById('pickup_address').value = 'Current GPS Location (' + lat.toFixed(4) + ', ' + lng.toFixed(4) + ')';

            if (pickupMarker) {
                pickupMarker.setLatLng([lat, lng]);
            }
            if (map) {
                map.setView([lat, lng], 15);
            }
            spawnNearbyDrivers(lat, lng);
            recalculateFare();

            // Reverse geocode with Nominatim
            fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`)
                .then(res => res.json())
                .then(data => {
                    if (data && data.display_name) {
                        const name = data.display_name.split(',')[0];
                        document.getElementById('pickup_address').value = name + ' (Current Location)';
                    }
                })
                .catch(() => {})
                .finally(() => {
                    if (btn) {
                        btn.innerHTML = '<i class="fa-solid fa-location-crosshairs me-1"></i> Use My GPS Location';
                        btn.disabled = false;
                    }
                });
        },
        function(err) {
            if (btn) {
                btn.innerHTML = '<i class="fa-solid fa-location-crosshairs me-1"></i> Use My GPS Location';
                btn.disabled = false;
            }
            alert('Unable to retrieve GPS coordinates. Please ensure location permissions are enabled or click one of the quick landmarks below.');
        },
        { enableHighAccuracy: true, timeout: 8000 }
    );
}

function quickSelectLocation(type, title, lat, lng) {
    selectLocationOption(type, title, lat, lng);
}

