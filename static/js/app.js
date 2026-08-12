/**
 * static/js/app.js — Crypt Lab IDS Dashboard Controller
 * Handles: clock, /ws/ids-feed, /ws/log-feed, REST initial data, simulator wiring
 */

/* ── CLOCK ── */
function updateClock() {
    var el = document.getElementById('current-time');
    if (!el) return;
    el.textContent = new Date().toLocaleString('en-US', {
        timeZone: 'UTC', year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    }) + ' UTC';
}
updateClock();
setInterval(updateClock, 1000);

/* ── HELPERS ── */
function escHtml(str) {
    return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function formatTime(ts) {
    var d = ts ? new Date(ts) : new Date();
    return d.toLocaleTimeString('en-US', { hour12: false });
}
function severityBadge(sev) {
    var cls = { High: 'badge-high', Medium: 'badge-medium', Low: 'badge-low' }[sev] || 'badge-low';
    return '<span class="badge ' + cls + '">' + escHtml(sev) + '</span>';
}

/* ── ALERT TABLE ── */
var MAX_TABLE_ROWS = 50;
var alertCount = 0;

function addAlertRow(alert) {
    var tbody = document.getElementById('alert-table-body');
    if (!tbody) return;
    var empty = document.getElementById('alert-table-empty');
    if (empty) empty.remove();

    var conf = typeof alert.confidence === 'number'
        ? Math.round(alert.confidence * 100) + '%' : '\u2014';
    var loc = [alert.geo_city, alert.geo_country]
        .filter(function(x){ return x && x !== 'Unknown' && x !== 'Internal'; })
        .join(', ') || '\u2014';

    var detailId = 'detail-' + (alert.id || Math.random().toString(36).slice(2));

    var row = document.createElement('tr');
    row.className = 'alert-row alert-new border-b border-zinc-900/70';
    row.setAttribute('data-detail', detailId);
    row.innerHTML =
        '<td class="py-2 px-2 text-zinc-400 font-mono whitespace-nowrap">' + formatTime(alert.timestamp) + '</td>' +
        '<td class="py-2 px-2 font-semibold text-zinc-100 whitespace-nowrap">' + escHtml(alert.attack_type) + '</td>' +
        '<td class="py-2 px-2 font-mono text-blue-300 whitespace-nowrap chatbot-ip-cell" style="cursor:pointer;text-decoration:underline dotted" title="Click to ask AI about this IP">' + escHtml(alert.src_ip) + '</td>' +
        '<td class="py-2 px-2 text-zinc-400 whitespace-nowrap">' + escHtml(loc) + '</td>' +
        '<td class="py-2 px-2">' + severityBadge(alert.severity) + '</td>' +
        '<td class="py-2 px-2 font-mono text-zinc-400">' + conf + '</td>' +
        '<td class="py-2 px-2 text-zinc-300">' + escHtml((alert.alert_message || '').slice(0, 100)) + '</td>';

    // Wire IP cell click → chatbot ask-about-IP
    (function(srcIp) {
        var ipCell = row.querySelector('.chatbot-ip-cell');
        if (ipCell && srcIp) {
            ipCell.addEventListener('click', function(e) {
                e.stopPropagation();
                if (typeof chatbot !== 'undefined') chatbot.askAboutIP(srcIp);
            });
        }
    })(alert.src_ip);

    var cms = Array.isArray(alert.countermeasures) ? alert.countermeasures : [];
    var detail = document.createElement('tr');
    detail.id = detailId;
    detail.className = 'alert-detail bg-zinc-900/40';
    var cmsHtml = cms.length ? '<div><span class="text-zinc-500 uppercase tracking-wider text-[10px]">Countermeasures</span><ol class="mt-1 space-y-1">' +
        cms.map(function(c,i){ return '<li class="flex gap-2 text-xs text-zinc-300"><span class="text-amber-400 font-bold">'+(i+1)+'.</span>'+escHtml(c)+'</li>'; }).join('') +
        '</ol></div>' : '';
    detail.innerHTML = '<td colspan="7" class="px-4 py-3">' +
        '<div class="text-xs text-zinc-300 mb-2"><span class="text-zinc-500 uppercase tracking-wider text-[10px]">Technical Summary</span><br>' +
        escHtml(alert.technical_summary || '\u2014') + '</div>' + cmsHtml + '</td>';

    row.addEventListener('click', function() { detail.classList.toggle('open'); });

    tbody.insertBefore(detail, tbody.firstChild);
    tbody.insertBefore(row, tbody.firstChild);

    alertCount++;
    while (tbody.children.length > MAX_TABLE_ROWS * 2) {
        tbody.removeChild(tbody.lastChild);
    }
    var tc = document.getElementById('alert-table-count');
    if (tc) tc.textContent = Math.min(alertCount, MAX_TABLE_ROWS) + ' alerts';
    var ac = document.getElementById('alert-counter');
    if (ac) ac.textContent = alertCount + ' alerts';
}

/* ── DOUGHNUT CHART ── */
var CHART_COLORS = ['#ef4444','#f97316','#eab308','#22c55e','#06b6d4','#3b82f6','#8b5cf6','#ec4899','#f43f5e'];
var attackChart = null;
var chartData = {};

function initChart() {
    var ctx = document.getElementById('attack-chart');
    if (!ctx || typeof Chart === 'undefined') return;
    attackChart = new Chart(ctx, {
        type: 'doughnut',
        data: { labels: [], datasets: [{ data: [], backgroundColor: CHART_COLORS, borderColor: 'rgba(12,12,22,0.8)', borderWidth: 2 }] },
        options: {
            responsive: true, maintainAspectRatio: false, cutout: '68%',
            plugins: {
                legend: { position: 'bottom', labels: { color: '#a1a1aa', boxWidth: 12, font: { size: 11 }, padding: 10 } },
                tooltip: { callbacks: { label: function(ctx){ return ' ' + ctx.label + ': ' + ctx.raw; } } }
            }
        }
    });
}

function updateChart(statsObj) {
    if (!attackChart) return;
    var labels = Object.keys(statsObj);
    var values = labels.map(function(k){ return statsObj[k]; });
    var total = values.reduce(function(a,b){ return a+b; }, 0);
    attackChart.data.labels = labels;
    attackChart.data.datasets[0].data = values;
    attackChart.data.datasets[0].backgroundColor = labels.map(function(_,i){ return CHART_COLORS[i % CHART_COLORS.length]; });
    attackChart.update('active');
    var el = document.getElementById('chart-total');
    if (el) el.textContent = total;
}

function incrementChart(label) {
    chartData[label] = (chartData[label] || 0) + 1;
    updateChart(chartData);
}

/* ── COUNTERMEASURES PANEL ── */
var lastHighAlert = null;
var lastMediumAlert = null;

function updateCountermeasures(alert) {
    if (alert.severity === 'High') lastHighAlert = alert;
    else if (alert.severity === 'Medium' && !lastHighAlert) lastMediumAlert = alert;

    var source = lastHighAlert || lastMediumAlert;
    if (!source) return;
    var cms = Array.isArray(source.countermeasures) ? source.countermeasures : [];
    var list = document.getElementById('countermeasures-list');
    if (!list) return;
    var icons = ['\uD83D\uDD12','\uD83D\uDD0D','\uD83D\uDEE1\uFE0F','\uD83D\uDCE1'];
    list.innerHTML = '<div class="mb-2"><span class="text-[10px] uppercase tracking-wider text-zinc-500">' +
        escHtml(source.attack_type) + ' from ' + escHtml(source.src_ip) + '</span></div>' +
        cms.map(function(c,i){
            return '<div class="flex gap-2 items-start py-1.5 border-b border-zinc-800/50 last:border-0">' +
                '<span class="text-base leading-none mt-0.5">' + (icons[i] || '\u2022') + '</span>' +
                '<p class="text-xs text-zinc-300 leading-relaxed">' + escHtml(c) + '</p></div>';
        }).join('');

    var panel = document.getElementById('countermeasures-panel');
    if (panel) {
        panel.classList.remove('cm-pulse');
        void panel.offsetWidth;
        panel.classList.add('cm-pulse');
    }
}

/* ── LOG VIEWER ── */
var logPaused = false;
var logLineCount = 0;
var MAX_LOG_LINES = 200;
var LOG_TYPE_CLASS = {
    auth_failure: 'log-auth-failure',
    privilege_escalation: 'log-privilege-escalation',
    http_scan: 'log-http-scan',
    ssh_success: 'log-ssh-success'
};

function clearAlerts() {
    alertCount = 0;
    chartData = {};
    if (attackChart) {
        attackChart.data.labels = [];
        attackChart.data.datasets[0].data = [];
        attackChart.update('active');
    }
    var ct = document.getElementById('chart-total');
    if (ct) ct.textContent = '0';
    var tbody = document.getElementById('alert-table-body');
    if (tbody) {
        tbody.innerHTML = '<tr id="alert-table-empty"><td colspan="7" class="py-12 text-center text-zinc-600 text-xs">No alerts detected yet — system is monitoring</td></tr>';
    }
    var tc = document.getElementById('alert-table-count');
    if (tc) tc.textContent = '0 alerts';
    var ac = document.getElementById('alert-counter');
    if (ac) ac.textContent = '0 alerts';
    var cml = document.getElementById('countermeasures-list');
    if (cml) cml.innerHTML = '<p class="text-xs text-zinc-600 text-center mt-6">Countermeasures will appear<br>when a threat is detected</p>';
    lastHighAlert = null;
    lastMediumAlert = null;
    // Tell server to clear DB
    fetch('/api/alerts/clear', { method: 'DELETE' }).catch(function() {});
}

function clearLogs() {
    logLineCount = 0;
    var viewer = document.getElementById('log-viewer');
    if (viewer) viewer.innerHTML = '';
    // Tell server to clear in-memory log list
    fetch('/api/logs/clear', { method: 'DELETE' }).catch(function() {});
}

function appendLogLine(logEvent) {
    if (logPaused) return;
    var viewer = document.getElementById('log-viewer');
    if (!viewer) return;
    if (logLineCount === 0) viewer.innerHTML = '';
    var logType = logEvent.log_type || 'generic';
    var cls = LOG_TYPE_CLASS[logType] || 'log-generic';
    var ts = logEvent.timestamp
        ? new Date(logEvent.timestamp * 1000).toLocaleTimeString('en-US', { hour12: false })
        : new Date().toLocaleTimeString('en-US', { hour12: false });
    var line = document.createElement('div');
    line.className = cls;
    line.textContent = '[' + ts + '] ' + (logEvent.raw_line || JSON.stringify(logEvent));
    viewer.appendChild(line);
    logLineCount++;
    while (viewer.children.length > MAX_LOG_LINES) viewer.removeChild(viewer.firstChild);
    viewer.scrollTop = viewer.scrollHeight;
}

/* ── CONNECTION STATUS ── */
function setStatus(state) {
    var dot  = document.getElementById('ids-status-dot');
    var text = document.getElementById('ids-status-text');
    if (!dot || !text) return;
    if (state === 'connected') {
        dot.className = 'w-2 h-2 rounded-full dot-connected';
        text.textContent = 'Live';
        text.className = 'text-xs text-green-400';
    } else if (state === 'error') {
        dot.className = 'w-2 h-2 rounded-full dot-error';
        text.textContent = 'Disconnected';
        text.className = 'text-xs text-red-400';
    } else {
        dot.className = 'w-2 h-2 rounded-full dot-connecting';
        text.textContent = 'Connecting\u2026';
        text.className = 'text-xs text-zinc-400';
    }
}

/* ── WS: IDS FEED ── */
var simulatorPanel = null;

function connectIdsFeed() {
    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var ws = new WebSocket(proto + '//' + location.host + '/ws/ids-feed');
    ws.onopen = function() { setStatus('connected'); };
    ws.onmessage = function(ev) {
        var msg;
        try { msg = JSON.parse(ev.data); } catch(e) { return; }
        if (msg.type === 'ids_alert' && msg.data) {
            var alert = msg.data;
            addAlertRow(alert);
            if (window.attackMap) window.attackMap.addMarker(alert);
            incrementChart(alert.attack_type);
            updateCountermeasures(alert);
            if (simulatorPanel) simulatorPanel.onDetected(alert);
            // Notify chatbot of new alert (High or Medium)
            if (typeof chatbot !== 'undefined' &&
                (alert.severity === 'High' || alert.severity === 'Medium')) {
                chatbot.notifyNewAlert(alert);
            }
            // Debounced stats refresh — at most once every 5 s
            clearTimeout(_statsRefreshTimer);
            _statsRefreshTimer = setTimeout(loadExtendedStats, 5000);
        }
        if (msg.type === 'clear_alerts') {
            loadExtendedStats();
            if (typeof chatbot !== 'undefined') chatbot.clearNotification();
        }
    };
    ws.onclose = function() { setStatus('error'); setTimeout(connectIdsFeed, 3000); };
    ws.onerror = function() { setStatus('error'); };
}

/* ── WS: LOG FEED ── */
function connectLogFeed() {
    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var ws = new WebSocket(proto + '//' + location.host + '/ws/log-feed');
    ws.onmessage = function(ev) {
        var msg;
        try { msg = JSON.parse(ev.data); } catch(e) { return; }
        if (msg.type === 'log' && msg.data) appendLogLine(msg.data);
    };
    ws.onclose = function() { setTimeout(connectLogFeed, 3000); };
}

/* ── INITIAL DATA LOAD ── */
function loadInitialData() {
    fetch('/api/alerts').then(function(r){ return r.json(); }).then(function(data){
        if (data.ok && data.alerts) {
            var reversed = data.alerts.slice().reverse();
            reversed.forEach(addAlertRow);
            var high = data.alerts.find(function(a){ return a.severity === 'High'; });
            var med  = data.alerts.find(function(a){ return a.severity === 'Medium'; });
            if (high || med) updateCountermeasures(high || med);
        }
    }).catch(function(e){ console.warn('alerts load failed:', e); });

    fetch('/api/stats').then(function(r){ return r.json(); }).then(function(data){
        if (data.ok && data.stats) { chartData = data.stats; updateChart(chartData); }
    }).catch(function(e){ console.warn('stats load failed:', e); });

    fetch('/api/logs').then(function(r){ return r.json(); }).then(function(data){
        if (data.ok && data.logs) data.logs.slice(-50).forEach(appendLogLine);
    }).catch(function(e){ console.warn('logs load failed:', e); });

    loadExtendedStats();
}

/* ── EXTENDED STATS DASHBOARD ── */
var _statsRefreshTimer = null;

function loadExtendedStats() {
    fetch('/api/stats/extended').then(function(r){ return r.json(); }).then(function(data){
        if (!data.ok) return;
        renderTopIps(data.top_ips || []);
        renderHourly(data.hourly || []);
        renderAttackDist(data.attack_dist || {});
        renderSeverityBadges(data.severity || {});
        var el = document.getElementById('stats-last-updated');
        if (el) el.textContent = 'updated ' + new Date().toLocaleTimeString('en-US',{hour12:false});
    }).catch(function(e){ console.warn('extended stats load failed:', e); });
}

function renderSeverityBadges(sev) {
    var h = document.getElementById('stats-badge-high');
    var m = document.getElementById('stats-badge-medium');
    var l = document.getElementById('stats-badge-low');
    if (h) h.textContent = 'High: ' + (sev.High || 0);
    if (m) m.textContent = 'Med: '  + (sev.Medium || 0);
    if (l) l.textContent = 'Low: '  + (sev.Low || 0);
}

function renderTopIps(topIps) {
    var el = document.getElementById('stats-top-ips');
    if (!el) return;
    if (!topIps.length) { el.innerHTML = '<p class="text-zinc-600 text-[11px]">No data yet</p>'; return; }
    var maxCount = topIps[0].count;
    var COLORS = ['#ef4444','#f97316','#eab308','#22c55e','#06b6d4','#818cf8','#c084fc','#f472b6','#94a3b8','#64748b'];
    el.innerHTML = topIps.slice(0, 8).map(function(ip, i) {
        var pct = maxCount > 0 ? Math.round((ip.count / maxCount) * 100) : 0;
        var color = COLORS[i % COLORS.length];
        var types = (ip.attack_types || []).slice(0, 3).join(', ');
        return '<div class="mb-1.5">' +
            '<div class="flex justify-between items-center mb-0.5">' +
            '<span class="font-mono text-[11px] text-zinc-200">' + escHtml(ip.src_ip) + '</span>' +
            '<span class="text-[10px] text-zinc-500 font-mono">' + ip.count + ' alerts</span>' +
            '</div>' +
            '<div class="stat-bar-wrap">' +
            '<div class="stat-bar-bg"><div class="stat-bar-fill" style="width:' + pct + '%;background:' + color + '"></div></div>' +
            '</div>' +
            (types ? '<div class="text-[9px] text-zinc-600 mt-0.5">' + escHtml(types) + '</div>' : '') +
            '</div>';
    }).join('');
}

function renderHourly(hourly) {
    var el = document.getElementById('stats-hourly');
    if (!el) return;
    if (!hourly.length) { el.innerHTML = '<span class="text-zinc-600 text-[11px] self-center">No data yet</span>'; return; }
    // Fill 24 slots: build a map from existing data, fill gaps with 0
    var buckets = {};
    hourly.forEach(function(h) { buckets[h.hour] = h.count; });
    // Generate 24 hour labels ending now
    var slots = [];
    var now = new Date();
    for (var i = 23; i >= 0; i--) {
        var d = new Date(now.getTime() - i * 3600000);
        var key = d.getFullYear() + '-' +
            String(d.getMonth()+1).padStart(2,'0') + '-' +
            String(d.getDate()).padStart(2,'0') + 'T' +
            String(d.getHours()).padStart(2,'0') + ':00';
        slots.push({ key: key, count: buckets[key] || 0 });
    }
    var maxCount = Math.max.apply(null, slots.map(function(s){ return s.count; })) || 1;
    el.innerHTML = slots.map(function(s) {
        var h = Math.max(2, Math.round((s.count / maxCount) * 56));
        var opacity = s.count > 0 ? (0.4 + 0.6 * s.count / maxCount) : 0.15;
        var title = s.key + ': ' + s.count + ' alert' + (s.count !== 1 ? 's' : '');
        return '<span class="hourly-col" title="' + escHtml(title) + '" ' +
               'style="height:' + h + 'px;opacity:' + opacity + ';flex:1;max-width:12px"></span>';
    }).join('');
}

function renderAttackDist(dist) {
    var el = document.getElementById('stats-attack-dist');
    if (!el) return;
    var entries = Object.entries(dist).sort(function(a,b){ return b[1]-a[1]; });
    if (!entries.length) { el.innerHTML = '<p class="text-zinc-600 text-[11px]">No data yet</p>'; return; }
    var total = entries.reduce(function(s,e){ return s+e[1]; }, 0);
    var COLORS = ['#ef4444','#f97316','#eab308','#22c55e','#06b6d4','#818cf8','#c084fc','#f472b6','#94a3b8'];
    el.innerHTML = entries.map(function(e, i) {
        var pct = total > 0 ? Math.round((e[1]/total)*100) : 0;
        var color = COLORS[i % COLORS.length];
        return '<div class="flex items-center gap-2">' +
            '<div class="w-2 h-2 rounded-full flex-shrink-0" style="background:' + color + '"></div>' +
            '<span class="text-zinc-300 flex-1 truncate text-[11px]">' + escHtml(e[0]) + '</span>' +
            '<span class="font-mono text-[10px] text-zinc-500">' + e[1] + '</span>' +
            '<div class="w-16 stat-bar-bg ml-1"><div class="stat-bar-fill" style="width:' + pct + '%;background:' + color + '"></div></div>' +
            '</div>';
    }).join('');
}

/* ── INIT ── */
document.addEventListener('DOMContentLoaded', function() {
    // Fetch sensor IP from health endpoint and display in header
    fetch('/api/health').then(function(r){ return r.json(); }).then(function(data){
        var el = document.getElementById('sensor-ip');
        if (el && data.sensor_ip) el.textContent = data.sensor_ip;
    }).catch(function(){});

    // Log pause button
    var btn = document.getElementById('log-pause-btn');
    if (btn) {
        btn.addEventListener('click', function() {
            logPaused = !logPaused;
            btn.textContent = logPaused ? '\u25B6 Resume' : '\u23F8 Pause';
            btn.className = logPaused
                ? 'text-[11px] px-3 py-1 rounded bg-green-900 hover:bg-green-800 text-green-300 transition font-mono'
                : 'text-[11px] px-3 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition font-mono';
        });
    }

    // Clear alerts button
    var clearAlertsBtn = document.getElementById('clear-alerts-btn');
    if (clearAlertsBtn) clearAlertsBtn.addEventListener('click', clearAlerts);

    // Clear logs button
    var clearLogsBtn = document.getElementById('clear-logs-btn');
    if (clearLogsBtn) clearLogsBtn.addEventListener('click', clearLogs);

    // Chart
    initChart();

    // Map
    window.attackMap = new AttackMap('attack-map');

    // Simulator
    simulatorPanel = new SimulatorPanel();

    // REST initial data
    loadInitialData();

    // Refresh stats every 60 s (catches changes while panel is closed)
    setInterval(loadExtendedStats, 60000);

    // WebSockets
    connectIdsFeed();
    connectLogFeed();
});
