/**
 * static/js/map.js — Leaflet map controller for Crypt Lab attack map.
 */

class AttackMap {
    constructor(containerId) {
        this.containerId = containerId;
        this.markers = {};
        this.map = null;
        this.init();
    }

    init() {
        this.map = L.map(this.containerId, {
            center: [20, 0],
            zoom: 2,
            zoomControl: true,
            attributionControl: false,
        });

        // Dark tile layer
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            maxZoom: 18,
        }).addTo(this.map);

        // Load existing markers from API
        this.loadExisting();
    }

    async loadExisting() {
        try {
            const resp = await fetch('/api/map');
            const data = await resp.json();
            if (data.ok && data.markers) {
                data.markers.forEach(m => this.addMarker(m));
            }
        } catch (e) {
            console.error('Failed to load map data:', e);
        }
    }

    addMarker(alert) {
        const lat = alert.geo_lat || alert.lat;
        const lon = alert.geo_lon || alert.lon;

        // Skip private IPs (lat=0, lon=0) and "Local Network"
        if (lat === 0 && lon === 0) return;
        if (alert.geo_city === 'Local Network' || alert.city === 'Local Network') return;

        const severity = alert.severity || 'Low';
        const confidence = alert.confidence || 0.5;

        // Color by severity
        const colors = { High: '#ef4444', Medium: '#f59e0b', Low: '#22c55e' };
        const color = colors[severity] || colors.Low;

        // Radius scales with confidence
        const radius = Math.max(4, Math.min(12, confidence * 14));

        const marker = L.circleMarker([lat, lon], {
            radius: radius,
            fillColor: color,
            color: color,
            weight: 2,
            opacity: 0.9,
            fillOpacity: 0.6,
        }).addTo(this.map);

        // Popup content
        const ip = alert.src_ip || 'Unknown';
        const city = alert.geo_city || alert.city || 'Unknown';
        const country = alert.geo_country || alert.country || 'Unknown';
        const attackType = alert.attack_type || 'Unknown';
        const message = alert.alert_message || '';

        marker.bindPopup(`
            <div style="font-family: monospace; font-size: 12px; min-width: 200px;">
                <div style="font-weight: bold; color: ${color}; margin-bottom: 4px;">
                    ${attackType}
                </div>
                <div><b>IP:</b> ${ip}</div>
                <div><b>Location:</b> ${city}, ${country}</div>
                <div><b>Severity:</b> <span style="color: ${color}">${severity}</span></div>
                ${message ? `<div style="margin-top: 4px; font-style: italic;">${message}</div>` : ''}
            </div>
        `);

        // Pulsing animation for High severity
        if (severity === 'High') {
            marker.getElement && marker.getElement() && 
                marker.getElement().classList.add('pulse-marker');
        }
    }
}
