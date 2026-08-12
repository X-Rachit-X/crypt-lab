/**
 * static/js/simulator.js — Simulator control panel UI for Crypt Lab.
 */

class SimulatorPanel {
    constructor() {
        this.active = false;
        this.activeScenario = null;
        this.buttons = {};
        this.statusBar = null;
        this.progressBar = null;
        this.init();
    }

    init() {
        this.statusBar = document.getElementById('sim-status');
        this.progressBar = document.getElementById('sim-progress');

        const scenarios = ['PORT_SCAN', 'DOS_FLOOD', 'BRUTE_FORCE_SSH', 'WEB_SCAN', 'DDOS', 'HEARTBLEED'];
        scenarios.forEach(name => {
            const btn = document.getElementById(`sim-btn-${name}`);
            if (btn) {
                this.buttons[name] = btn;
                btn.addEventListener('click', () => this.runScenario(name));
            }
        });
    }

    async runScenario(scenario) {
        if (this.active) return;

        this.active = true;
        this.activeScenario = scenario;
        this.disableButtons(true);

        // Update status bar
        if (this.statusBar) {
            this.statusBar.textContent = `Running: ${scenario} — detection expected in ~5s`;
            this.statusBar.className = 'text-sm text-amber-400 mt-2 font-mono';
        }

        // Start progress bar
        this.startProgress(8);

        try {
            const resp = await fetch('/api/simulate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ scenario: scenario }),
            });
            const data = await resp.json();
            if (!data.ok) {
                this.showError(data.error || 'Simulation failed');
                return;
            }

            const expectedSec = data.expected_seconds || 5;
            if (this.statusBar) {
                this.statusBar.textContent = `Running: ${scenario} — detection expected in ~${expectedSec}s`;
            }
        } catch (e) {
            this.showError('Network error: ' + e.message);
        }
    }

    /**
     * Called when an alert matching the active simulation arrives on /ws/ids-feed.
     */
    onDetected() {
        if (!this.active) return;

        if (this.statusBar) {
            this.statusBar.textContent = '✅ Detected by IDS';
            this.statusBar.className = 'text-sm text-green-400 mt-2 font-mono font-bold';
        }
        if (this.progressBar) {
            this.progressBar.style.width = '100%';
            this.progressBar.className = 'h-1 bg-green-500 rounded transition-all duration-300';
        }

        // Reset after 3 seconds
        setTimeout(() => this.reset(), 3000);
    }

    startProgress(durationSec) {
        if (!this.progressBar) return;
        this.progressBar.style.width = '0%';
        this.progressBar.className = 'h-1 bg-amber-500 rounded transition-all';
        this.progressBar.style.transition = `width ${durationSec}s linear`;
        // Force reflow
        void this.progressBar.offsetWidth;
        this.progressBar.style.width = '100%';
    }

    showError(msg) {
        if (this.statusBar) {
            this.statusBar.textContent = `❌ ${msg}`;
            this.statusBar.className = 'text-sm text-red-400 mt-2 font-mono';
        }
        setTimeout(() => this.reset(), 3000);
    }

    reset() {
        this.active = false;
        this.activeScenario = null;
        this.disableButtons(false);
        if (this.statusBar) {
            this.statusBar.textContent = 'Ready — select a scenario';
            this.statusBar.className = 'text-sm text-zinc-500 mt-2 font-mono';
        }
        if (this.progressBar) {
            this.progressBar.style.transition = 'none';
            this.progressBar.style.width = '0%';
            this.progressBar.className = 'h-1 bg-zinc-700 rounded';
        }
    }

    disableButtons(disabled) {
        Object.values(this.buttons).forEach(btn => {
            btn.disabled = disabled;
            btn.style.opacity = disabled ? '0.5' : '1';
            btn.style.cursor = disabled ? 'not-allowed' : 'pointer';
        });
    }
}
