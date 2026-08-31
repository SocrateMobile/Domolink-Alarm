class DomolinkPanel extends HTMLElement {
  set panel(panel) {
    this._panel = panel;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._activeTab = 'arm';
      this._codeValue = '';
      this._selectedCameraIndex = 0;
      this._cameraRefreshTimer = null;
      this._theme = localStorage.getItem('domolink_theme') || (hass.themes && hass.themes.darkMode ? 'dark' : 'dark');
      this._buildShell();
      this._startClock();
      this._startCameraStream();
      this._initialized = true;
    }
    try {
      this.render();
    } catch (err) {
      console.error("Domolink Alarm render error:", err);
    }
  }

  disconnectedCallback() {
    if (this._clockTimer) clearInterval(this._clockTimer);
    if (this._cameraRefreshTimer) clearInterval(this._cameraRefreshTimer);
  }

  _startClock() {
    const updateTime = () => {
      const clockEl = this.querySelector('#live-clock');
      if (clockEl) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
        const dateStr = now.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' });
        clockEl.innerHTML = `<span class="clock-time">${timeStr}</span><span class="clock-date">${dateStr}</span>`;
      }
    };
    updateTime();
    this._clockTimer = setInterval(updateTime, 10000);
  }

  _startCameraStream() {
    this._cameraRefreshTimer = setInterval(() => {
      const camImg = this.querySelector('#live-camera-img');
      if (camImg && camImg.dataset.camEntity) {
        const entityId = camImg.dataset.camEntity;
        const stateObj = this._hass && this._hass.states ? this._hass.states[entityId] : null;
        if (stateObj && stateObj.attributes && stateObj.attributes.entity_picture) {
          camImg.src = stateObj.attributes.entity_picture + '&t=' + Date.now();
        } else {
          camImg.src = `/api/camera_proxy/${entityId}?time=${Date.now()}`;
        }
      }
    }, 2500);
  }

  _toggleTheme() {
    this._theme = this._theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('domolink_theme', this._theme);
    const wrap = this.querySelector('.panel-wrap');
    if (wrap) {
      wrap.classList.remove('theme-dark', 'theme-light');
      wrap.classList.add(`theme-${this._theme}`);
    }
    const btn = this.querySelector('#theme-toggle-btn');
    if (btn) {
      btn.innerHTML = `<ha-icon icon="${this._theme === 'dark' ? 'mdi:weather-sunny' : 'mdi:weather-night'}"></ha-icon>`;
    }
  }

  _getAlarmEntity() {
    if (!this._hass || !this._hass.states) return null;
    const states = Object.values(this._hass.states);
    return states.find(s => 
      (s.attributes && (s.attributes.domolink_alarm === true || s.attributes.opening_sensors !== undefined)) ||
      s.entity_id.startsWith('alarm_control_panel.domolink') ||
      (s.attributes && s.attributes.attribution && String(s.attributes.attribution).toLowerCase().includes('domolink'))
    ) || states.find(s => s.entity_id.startsWith('alarm_control_panel.')) || null;
  }

  _buildShell() {
    this.innerHTML = `
      <style>
        :host {
          display: block;
          min-height: 100vh;
          box-sizing: border-box;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          margin: 0;
          padding: 0;
        }

        /* ─── Themes & CSS Variables ─────────────── */
        .panel-wrap.theme-dark {
          --d-bg: #0d1117;
          --d-surface: rgba(22, 27, 34, 0.85);
          --d-surface-card: rgba(26, 32, 44, 0.75);
          --d-border: rgba(255, 255, 255, 0.1);
          --d-border-light: rgba(255, 255, 255, 0.06);
          --d-text: #f0f6fc;
          --d-subtext: #8b949e;
          --d-sec-bg: rgba(255, 255, 255, 0.05);
          --d-pill-active-bg: #ffffff;
          --d-pill-active-text: #0d1117;
          --d-card-blur: blur(20px);
          --d-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
          --d-key-bg: rgba(255, 255, 255, 0.06);
          --d-key-border: rgba(255, 255, 255, 0.12);
        }

        .panel-wrap.theme-light {
          --d-bg: #f3f4f6;
          --d-surface: rgba(255, 255, 255, 0.9);
          --d-surface-card: rgba(255, 255, 255, 0.85);
          --d-border: rgba(0, 0, 0, 0.1);
          --d-border-light: rgba(0, 0, 0, 0.05);
          --d-text: #111827;
          --d-subtext: #6b7280;
          --d-sec-bg: rgba(0, 0, 0, 0.04);
          --d-pill-active-bg: #111827;
          --d-pill-active-text: #ffffff;
          --d-card-blur: blur(20px);
          --d-shadow: 0 8px 24px 0 rgba(0, 0, 0, 0.08);
          --d-key-bg: rgba(0, 0, 0, 0.04);
          --d-key-border: rgba(0, 0, 0, 0.08);
        }

        .panel-wrap {
          background-color: var(--d-bg);
          background-image: 
            radial-gradient(at 10% 10%, rgba(245, 158, 11, 0.07) 0px, transparent 50%),
            radial-gradient(at 90% 90%, rgba(16, 185, 129, 0.07) 0px, transparent 50%);
          color: var(--d-text);
          min-height: 100vh;
          padding: 24px 28px 48px;
          box-sizing: border-box;
          transition: background 0.3s ease, color 0.3s ease;
        }

        .container {
          max-width: 1440px;
          margin: 0 auto;
          display: flex;
          flex-direction: column;
          gap: 24px;
        }

        /* ─── Top Header Navigation ──────────────── */
        .top-nav {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 16px;
        }

        .brand-section {
          display: flex;
          align-items: center;
          gap: 14px;
        }
        .brand-logo-disc {
          width: 44px;
          height: 44px;
          border-radius: 14px;
          background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
          display: flex;
          align-items: center;
          justify-content: center;
          color: #ffffff;
          box-shadow: 0 4px 16px rgba(245, 158, 11, 0.4);
        }
        .brand-logo-disc ha-icon { --mdc-icon-size: 26px; }
        .brand-title {
          font-size: 22px;
          font-weight: 800;
          letter-spacing: -0.5px;
        }

        .nav-capsule {
          display: inline-flex;
          background: var(--d-surface);
          backdrop-filter: var(--d-card-blur);
          padding: 6px;
          border-radius: 9999px;
          border: 1px solid var(--d-border);
          box-shadow: var(--d-shadow);
          gap: 4px;
          user-select: none;
        }

        .nav-tab {
          padding: 8px 20px;
          border-radius: 9999px;
          font-size: 13.5px;
          font-weight: 600;
          color: var(--d-subtext);
          cursor: pointer;
          transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .nav-tab:hover { color: var(--d-text); }
        .nav-tab.active {
          background: var(--d-pill-active-bg);
          color: var(--d-pill-active-text);
          font-weight: 700;
          box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
        }

        .header-actions {
          display: flex;
          align-items: center;
          gap: 16px;
        }
        .clock-widget {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          line-height: 1.2;
        }
        .clock-time {
          font-size: 16px;
          font-weight: 800;
          letter-spacing: 0.5px;
        }
        .clock-date {
          font-size: 11.5px;
          color: var(--d-subtext);
          text-transform: capitalize;
        }

        .icon-btn-circle {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          background: var(--d-surface);
          border: 1px solid var(--d-border);
          color: var(--d-text);
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .icon-btn-circle:hover {
          background: var(--d-sec-bg);
          transform: scale(1.05);
        }

        /* ─── Glass Cards & Shared Styles ────────── */
        .glass-card {
          background: var(--d-surface-card);
          backdrop-filter: var(--d-card-blur);
          -webkit-backdrop-filter: var(--d-card-blur);
          border: 1px solid var(--d-border);
          border-radius: 24px;
          box-shadow: var(--d-shadow);
          padding: 20px;
          box-sizing: border-box;
          color: var(--d-text);
          position: relative;
        }

        /* ─── 3-Column Dashboard Layout ──────────── */
        .arm-layout-grid {
          display: grid;
          grid-template-columns: 290px 1fr 340px;
          gap: 20px;
          align-items: start;
        }
        @media (max-width: 1180px) {
          .arm-layout-grid { grid-template-columns: 1fr 1fr; }
          .left-widgets-col { grid-column: span 2; display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        }
        @media (max-width: 820px) {
          .arm-layout-grid { grid-template-columns: 1fr; }
          .left-widgets-col { grid-column: span 1; display: flex; flex-direction: column; }
        }

        /* ─── Left Column (Widgets) ──────────────── */
        .left-widgets-col {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .widget-card {
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 10px;
          border-radius: 20px;
        }
        .widget-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          font-size: 11.5px;
          font-weight: 800;
          letter-spacing: 0.8px;
          text-transform: uppercase;
          color: var(--d-subtext);
        }

        /* Camera Live Preview Widget */
        .camera-preview-container {
          position: relative;
          width: 100%;
          height: 140px;
          border-radius: 14px;
          overflow: hidden;
          background: #000000;
          border: 1px solid var(--d-border);
        }
        .camera-live-badge {
          position: absolute;
          top: 8px;
          left: 8px;
          background: rgba(0, 0, 0, 0.7);
          backdrop-filter: blur(8px);
          padding: 4px 8px;
          border-radius: 6px;
          font-size: 10px;
          font-weight: 700;
          color: #ffffff;
          display: flex;
          align-items: center;
          gap: 5px;
          z-index: 2;
        }
        .live-red-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: #ef4444;
          box-shadow: 0 0 8px #ef4444;
          animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        .camera-img-stream {
          width: 100%;
          height: 100%;
          object-fit: cover;
          display: block;
        }
        .camera-footer-status {
          font-size: 11px;
          font-weight: 700;
          color: var(--d-text);
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding-top: 2px;
        }

        .stat-big-value {
          font-size: 24px;
          font-weight: 800;
          letter-spacing: -0.5px;
        }
        .stat-sub-label {
          font-size: 12px;
          color: var(--d-subtext);
        }

        .recent-events-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .recent-event-row {
          font-size: 11.5px;
          line-height: 1.4;
          color: var(--d-subtext);
        }
        .recent-event-row strong {
          color: var(--d-text);
        }

        .health-stats-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .health-item-stat {
          display: flex;
          flex-direction: column;
        }

        /* ─── Center Column (Neon Hero Encadrés) ─── */
        .center-hero-col {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        /* Large Rounded Encadré Pill with Neon Glow */
        .neon-pill-card {
          border-radius: 9999px;
          padding: 24px 32px;
          display: flex;
          align-items: center;
          gap: 20px;
          position: relative;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          box-sizing: border-box;
        }

        /* Secure / Normal State (Neon Green) */
        .neon-pill-card.secure {
          border: 2px solid #10b981;
          background: radial-gradient(circle at center, rgba(16, 185, 129, 0.18) 0%, rgba(16, 185, 129, 0.04) 100%), var(--d-surface-card);
          box-shadow: 0 0 30px rgba(16, 185, 129, 0.35), inset 0 0 15px rgba(16, 185, 129, 0.2);
        }
        .neon-pill-card.secure .pill-icon-badge {
          background: rgba(16, 185, 129, 0.25);
          color: #10b981;
          box-shadow: 0 0 20px rgba(16, 185, 129, 0.6);
          border: 1.5px solid #10b981;
        }

        /* Alert / Triggered State (Neon Red) */
        .neon-pill-card.alert {
          border: 2px solid #ef4444;
          background: radial-gradient(circle at center, rgba(239, 68, 68, 0.22) 0%, rgba(239, 68, 68, 0.05) 100%), var(--d-surface-card);
          box-shadow: 0 0 35px rgba(239, 68, 68, 0.45), inset 0 0 20px rgba(239, 68, 68, 0.25);
          animation: pulseBorder 2s infinite;
        }
        @keyframes pulseBorder {
          0%, 100% { box-shadow: 0 0 35px rgba(239, 68, 68, 0.45), inset 0 0 20px rgba(239, 68, 68, 0.25); }
          50% { box-shadow: 0 0 50px rgba(239, 68, 68, 0.7), inset 0 0 30px rgba(239, 68, 68, 0.4); }
        }
        .neon-pill-card.alert .pill-icon-badge {
          background: rgba(239, 68, 68, 0.25);
          color: #ef4444;
          box-shadow: 0 0 20px rgba(239, 68, 68, 0.6);
          border: 1.5px solid #ef4444;
        }

        /* Armed State (Neon Blue / Purple) */
        .neon-pill-card.armed {
          border: 2px solid #3b82f6;
          background: radial-gradient(circle at center, rgba(59, 130, 246, 0.18) 0%, rgba(59, 130, 246, 0.04) 100%), var(--d-surface-card);
          box-shadow: 0 0 30px rgba(59, 130, 246, 0.35), inset 0 0 15px rgba(59, 130, 246, 0.2);
        }
        .neon-pill-card.armed .pill-icon-badge {
          background: rgba(59, 130, 246, 0.25);
          color: #3b82f6;
          box-shadow: 0 0 20px rgba(59, 130, 246, 0.6);
          border: 1.5px solid #3b82f6;
        }

        /* Pending State (Neon Amber) */
        .neon-pill-card.pending {
          border: 2px solid #f59e0b;
          background: radial-gradient(circle at center, rgba(245, 158, 11, 0.18) 0%, rgba(245, 158, 11, 0.04) 100%), var(--d-surface-card);
          box-shadow: 0 0 30px rgba(245, 158, 11, 0.35), inset 0 0 15px rgba(245, 158, 11, 0.2);
        }
        .neon-pill-card.pending .pill-icon-badge {
          background: rgba(245, 158, 11, 0.25);
          color: #f59e0b;
          box-shadow: 0 0 20px rgba(245, 158, 11, 0.6);
          border: 1.5px solid #f59e0b;
        }

        .pill-icon-badge {
          width: 56px;
          height: 56px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }
        .pill-icon-badge ha-icon { --mdc-icon-size: 32px; }

        .pill-text-content {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .pill-main-title {
          font-size: 26px;
          font-weight: 900;
          letter-spacing: 1px;
          line-height: 1.1;
        }
        .pill-sub-desc {
          font-size: 13px;
          color: var(--d-subtext);
          font-weight: 500;
        }

        /* Room Status Badges Grid */
        .room-badges-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 12px;
        }
        @media (max-width: 600px) {
          .room-badges-grid { grid-template-columns: repeat(2, 1fr); }
        }
        .room-badge-item {
          padding: 12px 10px;
          border-radius: 16px;
          background: var(--d-sec-bg);
          border: 1px solid var(--d-border);
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          text-align: center;
          gap: 4px;
        }
        .room-badge-name {
          font-size: 11px;
          font-weight: 800;
          letter-spacing: 0.5px;
        }
        .room-badge-status {
          font-size: 10px;
          font-weight: 700;
          text-transform: uppercase;
        }
        .room-badge-item.ok {
          border-color: rgba(16, 185, 129, 0.4);
          background: rgba(16, 185, 129, 0.08);
          color: #10b981;
        }
        .room-badge-item.warning {
          border-color: rgba(245, 158, 11, 0.4);
          background: rgba(245, 158, 11, 0.08);
          color: #f59e0b;
        }
        .room-badge-item.danger {
          border-color: rgba(239, 68, 68, 0.4);
          background: rgba(239, 68, 68, 0.08);
          color: #ef4444;
        }
        .room-badge-item.info {
          border-color: rgba(59, 130, 246, 0.4);
          background: rgba(59, 130, 246, 0.08);
          color: #3b82f6;
        }

        /* Carousel Pagination Dots */
        .carousel-dots {
          display: flex;
          justify-content: center;
          align-items: center;
          gap: 6px;
          margin-top: -6px;
        }
        .dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: var(--d-subtext);
          opacity: 0.4;
          transition: all 0.2s ease;
        }
        .dot.active {
          opacity: 1;
          background: #f59e0b;
          width: 16px;
          border-radius: 9999px;
        }

        /* Center Mode Switcher Pills */
        .center-modes-row {
          display: flex;
          gap: 10px;
          justify-content: center;
        }
        .center-mode-btn {
          flex: 1;
          padding: 12px 18px;
          border-radius: 9999px;
          border: 1px solid var(--d-border);
          background: var(--d-sec-bg);
          color: var(--d-text);
          font-size: 13px;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.2s ease;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
        }
        .center-mode-btn:hover {
          border-color: var(--d-text);
          background: var(--d-surface);
        }
        .center-mode-btn.active {
          background: var(--d-pill-active-bg);
          color: var(--d-pill-active-text);
          border-color: var(--d-pill-active-bg);
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
        }

        /* ─── Right Column (PIN Keypad) ──────────── */
        .keypad-glass-card {
          border-radius: 28px;
          padding: 24px 20px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 16px;
        }
        .keypad-title {
          font-size: 15px;
          font-weight: 800;
          letter-spacing: 1.5px;
          text-transform: uppercase;
        }

        .keypad-feedback-box {
          width: 100%;
          padding: 10px;
          border-radius: 12px;
          background: var(--d-sec-bg);
          border: 1px solid var(--d-border-light);
          display: flex;
          justify-content: center;
          align-items: center;
          min-height: 20px;
        }
        .pin-indicators-row {
          display: flex;
          gap: 12px;
          align-items: center;
        }
        .pin-dot-light {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          background: var(--d-sec-bg);
          border: 1.5px solid var(--d-border);
          transition: all 0.15s ease;
        }
        .pin-dot-light.active {
          background: #f59e0b;
          border-color: #f59e0b;
          box-shadow: 0 0 12px rgba(245, 158, 11, 0.8);
          transform: scale(1.25);
        }

        /* 3x4 Circular Matrix */
        .keypad-buttons-grid {
          display: grid;
          grid-template-columns: repeat(3, 72px);
          gap: 14px;
        }
        .keypad-circle-btn {
          width: 72px;
          height: 72px;
          border-radius: 50%;
          background: var(--d-key-bg);
          border: 1px solid var(--d-key-border);
          color: var(--d-text);
          font-size: 24px;
          font-weight: 600;
          cursor: pointer;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
          user-select: none;
          box-sizing: border-box;
          position: relative;
        }
        .keypad-circle-btn:hover {
          background: var(--d-surface);
          border-color: #f59e0b;
          transform: translateY(-2px);
        }
        .keypad-circle-btn:active {
          transform: scale(0.92);
          background: #f59e0b;
          color: #ffffff;
          box-shadow: 0 0 20px rgba(245, 158, 11, 0.7);
        }
        .key-led-dot {
          width: 4px;
          height: 4px;
          border-radius: 50%;
          background: #f59e0b;
          margin-top: 3px;
          box-shadow: 0 0 4px #f59e0b;
        }

        .keypad-bottom-actions {
          display: flex;
          gap: 8px;
          width: 100%;
          margin-top: 4px;
        }
        .keypad-action-pill {
          flex: 1;
          padding: 12px 6px;
          border-radius: 9999px;
          border: 1px solid var(--d-border);
          background: var(--d-sec-bg);
          color: var(--d-text);
          font-size: 11px;
          font-weight: 800;
          cursor: pointer;
          text-align: center;
          transition: all 0.2s ease;
        }
        .keypad-action-pill:hover {
          border-color: var(--d-text);
        }
        .keypad-action-pill.primary {
          background: var(--d-pill-active-bg);
          color: var(--d-pill-active-text);
          border-color: var(--d-pill-active-bg);
          box-shadow: 0 0 16px rgba(255, 255, 255, 0.3);
        }

        .btn-sos-danger {
          width: 100%;
          margin-top: 8px;
          padding: 12px;
          border-radius: 16px;
          background: rgba(239, 68, 68, 0.15);
          border: 1px solid rgba(239, 68, 68, 0.4);
          color: #ef4444;
          font-size: 12px;
          font-weight: 800;
          letter-spacing: 0.5px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          transition: all 0.2s ease;
        }
        .btn-sos-danger:hover {
          background: #ef4444;
          color: #ffffff;
          box-shadow: 0 0 20px rgba(239, 68, 68, 0.5);
        }

        /* ─── Tab Content Panes ───────────────────── */
        .tab-pane { display: none; }
        .tab-pane.active { display: block; animation: fadeIn 0.2s ease; }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }

        /* ─── Équipements Grid Styles ─────────────── */
        .equip-matrix {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
          gap: 12px;
        }
        .equip-item-card {
          background: var(--d-sec-bg);
          border: 1px solid var(--d-border);
          border-radius: 16px;
          padding: 14px 16px;
          display: flex;
          align-items: center;
          gap: 14px;
        }
        .equip-icon-disc {
          width: 42px;
          height: 42px;
          border-radius: 12px;
          background: var(--d-surface);
          border: 1px solid var(--d-border);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--d-subtext);
          flex-shrink: 0;
        }
        .equip-icon-disc.active { background: rgba(239, 68, 68, 0.15); color: #ef4444; border-color: rgba(239, 68, 68, 0.3); }
        .equip-icon-disc.success { background: rgba(16, 185, 129, 0.15); color: #10b981; border-color: rgba(16, 185, 129, 0.3); }
        .equip-icon-disc.bypassed { background: rgba(245, 158, 11, 0.15); color: #f59e0b; border-color: rgba(245, 158, 11, 0.3); }

        .btn-action-pill {
          padding: 6px 12px;
          border-radius: 8px;
          border: none;
          font-size: 11px;
          font-weight: 700;
          cursor: pointer;
          margin-left: auto;
        }
        .btn-action-pill.bypass { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }
        .btn-action-pill.restore { background: var(--d-surface); color: var(--d-subtext); border: 1px solid var(--d-border); }

        /* ─── Timeline Logs ───────────────────────── */
        .log-timeline {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        .log-entry.row-alert {
          background: rgba(239, 68, 68, 0.15);
          border-left: 4px solid #ef4444;
        }
        .log-entry.row-warning {
          background: rgba(249, 115, 22, 0.15);
          border-left: 4px solid #f97316;
        }
        .log-entry {
          display: flex;
          align-items: center;
          gap: 14px;
          padding: 12px 16px;
          background: var(--d-sec-bg);
          border-radius: 14px;
          border: 1px solid var(--d-border);
        }
        .log-dot {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          color: white;
        }
        .log-dot.disarm { background: #10b981; }
        .log-dot.arm { background: #ef4444; }
        .log-dot.sim { background: #8b5cf6; }
        .log-dot.event { background: #3b82f6; }

        .empty-placeholder {
          text-align: center;
          padding: 30px 20px;
          color: var(--d-subtext);
          font-size: 13px;
        }
      </style>

      <div class="panel-wrap theme-${this._theme}">
        <div class="container">
          <!-- Top Navigation Header -->
          <div class="top-nav">
            <div class="brand-section">
              <div class="brand-logo-disc">
                <ha-icon icon="mdi:shield-lock-outline"></ha-icon>
              </div>
              <div class="brand-title">Dashboard</div>
            </div>

            <div class="nav-capsule">
              <div class="nav-tab active" data-tab="arm">
                <ha-icon icon="mdi:shield-check"></ha-icon> Armement
              </div>
              <div class="nav-tab" data-tab="equip">
                <ha-icon icon="mdi:devices"></ha-icon> Équipements
              </div>
              <div class="nav-tab" data-tab="log">
                <ha-icon icon="mdi:history"></ha-icon> Journal
              </div>
              <div class="nav-tab" data-tab="health">
                <ha-icon icon="mdi:heart-pulse"></ha-icon> Santé
              </div>
              <div class="nav-tab" data-tab="sim">
                <ha-icon icon="mdi:home-clock"></ha-icon> Simulation
              </div>
              <div class="nav-tab" data-tab="param">
                <ha-icon icon="mdi:cog"></ha-icon> Paramètres
              </div>
            </div>

            <div class="header-actions">
              <div class="clock-widget" id="live-clock">
                <span class="clock-time">--:--</span>
                <span class="clock-date">---</span>
              </div>
              <button class="icon-btn-circle" id="theme-toggle-btn" title="Changer de thème (Jour/Nuit)">
                <ha-icon icon="${this._theme === 'dark' ? 'mdi:weather-sunny' : 'mdi:weather-night'}"></ha-icon>
              </button>
            </div>
          </div>

          <!-- Tab 1: Armement (Exact 3-Column Visual) -->
          <div id="pane-arm" class="tab-pane active"></div>

          <!-- Tab 2: Équipements -->
          <div id="pane-equip" class="tab-pane"></div>

          <!-- Tab 3: Journal -->
          <div id="pane-log" class="tab-pane"></div>

          <!-- Tab 4: Santé -->
          <div id="pane-health" class="tab-pane"></div>

          <!-- Tab 5: Simulation de Présence -->
          <div id="pane-sim" class="tab-pane"></div>

          <!-- Tab 6: Paramètres -->
          <div id="pane-param" class="tab-pane"></div>
        </div>
      </div>
    `;

    // Bind Navigation Click Events
    this.querySelectorAll('.nav-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        this._activeTab = tab.getAttribute('data-tab');
        this.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        this.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        const targetPane = this.querySelector('#pane-' + this._activeTab);
        if (targetPane) targetPane.classList.add('active');
        this.render();
      });
    });

    // Bind Theme Toggle
    const themeBtn = this.querySelector('#theme-toggle-btn');
    if (themeBtn) {
      themeBtn.addEventListener('click', () => this._toggleTheme());
    }
  }

  // ─── Service Dispatcher ─────────────────────────

  callAlarmService(service) {
    const alarmEntity = this._getAlarmEntity();
    if (!alarmEntity) {
      alert("Entité DomoLink Alarm introuvable dans Home Assistant.");
      return;
    }
    const data = { entity_id: alarmEntity.entity_id };
    if (this._codeValue) {
      data.code = this._codeValue;
    }
    
    this._hass.callService('alarm_control_panel', service, data).then(() => {
      this._codeValue = '';
      this._updatePinDisplay();
    }).catch(err => {
      this._codeValue = '';
      this._updatePinDisplay();
      const msg = err && err.message ? err.message : String(err);
      if (msg.includes("PIN") || msg.includes("code")) {
        alert("🔒 Code PIN requis ou incorrect pour cette action.");
      } else {
        alert("⚠️ Action impossible: " + msg);
      }
    });
  }

  _updatePinDisplay() {
    const dots = this.querySelectorAll('.pin-dot-light');
    dots.forEach((dot, index) => {
      if (index < this._codeValue.length) dot.classList.add('active');
      else dot.classList.remove('active');
    });
  }

  formatDate(dateStr) {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    const timeStr = date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    if (isToday) return `Aujourd'hui à ${timeStr}`;
    return date.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }) + ` à ${timeStr}`;
  }

  escapeHtml(text) {
    if (!text) return "";
    return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // ─── Tab 1: Armement (Mockup UI) ────────────────

  _renderArmTab(alarmEntity) {
    const container = this.querySelector('#pane-arm');
    if (!container) return;

    const state = alarmEntity ? alarmEntity.state : 'disarmed';
    const attrs = alarmEntity ? alarmEntity.attributes : {};

    // 1. Resolve Cameras
    const cameraList = attrs.cameras || Object.keys(this._hass.states).filter(k => k.startsWith('camera.'));
    const currentCamEntity = cameraList.length > 0 ? cameraList[this._selectedCameraIndex % cameraList.length] : null;
    const currentCamState = currentCamEntity ? this._hass.states[currentCamEntity] : null;
    const camFriendlyName = currentCamState ? (currentCamState.attributes.friendly_name || currentCamEntity) : "Aucune caméra";
    const camImgSrc = currentCamState && currentCamState.attributes.entity_picture 
      ? currentCamState.attributes.entity_picture 
      : (currentCamEntity ? `/api/camera_proxy/${currentCamEntity}` : '');

    // 2. Resolve Sensors & Stats
    const openingSensors = attrs.opening_sensors || [];
    const motionSensors = attrs.motion_sensors || [];
    const tamperSensors = attrs.tamper_sensors || [];
    const totalSensorsCount = openingSensors.length + motionSensors.length + tamperSensors.length;

    let activeTriggers = [];
    [...openingSensors, ...motionSensors, ...tamperSensors].forEach(id => {
      const s = this._hass.states[id];
      if (s && s.state === 'on') {
        activeTriggers.push(s.attributes.friendly_name || id);
      }
    });

    // 3. Status Hero Banner config
    const isDisarmed = state === 'disarmed';
    const isTriggered = state === 'triggered';
    const isPending = state === 'pending' || state === 'arming';
    const isArmed = state.startsWith('armed');

    let heroClass = 'secure';
    let heroIcon = 'mdi:shield-check';
    let heroTitle = 'SÉCURISÉ';
    let heroDesc = attrs.last_user ? `Désarmée par ${attrs.last_user}` : 'Système au repos • Résidence Principale';

    if (isArmed) {
      heroClass = 'armed';
      heroIcon = 'mdi:shield-lock';
      heroTitle = state === 'armed_away' ? 'ARMÉ (ABSENCE)' : (state === 'armed_night' ? 'ARMÉ (NUIT)' : 'ARMÉ (PRÉSENCE)');
      heroDesc = attrs.last_user ? `Armée par ${attrs.last_user}` : 'Surveillance active • Périmètre sous alarme';
    } else if (isTriggered) {
      heroClass = 'alert';
      heroIcon = 'mdi:bell-alert';
      heroTitle = 'ALERTE INTRUSION';
      heroDesc = attrs.triggered_by ? `Déclenchée par ${attrs.triggered_by}` : 'Sirènes et alertes actives !';
    } else if (isPending) {
      heroClass = 'pending';
      heroIcon = 'mdi:timer-sand';
      heroTitle = 'TEMPORISATION';
      heroDesc = 'Armement en cours... Sortez du domicile';
    }

    const telegramStatus = attrs.telegram_status || 'Inconnu';
    const ftpStatus = attrs.ftp_status || 'Inconnu';
    const camerasArmed = attrs.cameras_armed || false;

    // 4. Alert Bottom Encadré
    let alertTitle = 'ALERTE';
    let alertDesc = 'Aucune alerte active (Tout est sécurisé)';
    let alertClass = 'secure';
    let alertIcon = 'mdi:bell-check-outline';

    if (activeTriggers.length > 0) {
      alertTitle = 'ALERTE';
      alertDesc = `${activeTriggers[0]} Détecté (Ouvert)`;
      alertClass = 'alert';
      alertIcon = 'mdi:bell-ring-outline';
    } else if (attrs.triggered_by) {
      alertTitle = 'DERNIÈRE ALERTE';
      alertDesc = `${attrs.triggered_by} (${this.formatDate(attrs.last_triggered_by_time || Date.now())})`;
      alertClass = 'alert';
      alertIcon = 'mdi:bell-alert';
    }

    // 5. Real Unified Recent Events
    const allRecentEvents = [];
    (attrs.system_events || []).forEach(ev => {
      if (ev && ev.message) allRecentEvents.push({ time: ev.time, text: ev.message });
    });
    (attrs.arm_history || []).forEach(ev => {
      if (ev) {
        const title = ev.action === 'arm' ? `Armement (${ev.mode || 'Absent'})` : 'Désarmement';
        allRecentEvents.push({ time: ev.time, text: `${title} par ${ev.user || 'Système'}` });
      }
    });
    allRecentEvents.sort((a, b) => new Date(b.time) - new Date(a.time));

    const recentEvent1 = allRecentEvents.length > 0 
      ? `${new Date(allRecentEvents[0].time).toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'})} ${allRecentEvents[0].text}`
      : 'Surveillance active';
    const recentEvent2 = allRecentEvents.length > 1 
      ? `${new Date(allRecentEvents[1].time).toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'})} ${allRecentEvents[1].text}`
      : (activeTriggers.length > 0 ? `Alerte: ${activeTriggers[0]}` : 'Système opérationnel');

    // 6. Real Subsystem Health & Categories
    const healthData = attrs.sensor_health || {};
    let minBattery = null;
    let offlineCount = 0;
    const allDeviceIds = [
      ...(attrs.opening_sensors || []),
      ...(attrs.motion_sensors || []),
      ...(attrs.tamper_sensors || []),
      ...(attrs.night_sensors || []),
      ...(attrs.safety_sensors || []),
      ...(attrs.sirens || []),
      ...(attrs.cameras || [])
    ];

    allDeviceIds.forEach(id => {
      const s = this._hass.states[id];
      if (s) {
        if (s.state === 'unavailable' || s.state === 'unknown') offlineCount++;
        const b = s.attributes && (s.attributes.battery_level !== undefined ? s.attributes.battery_level : s.attributes.battery);
        if (typeof b === 'number' && !isNaN(b)) {
          if (minBattery === null || b < minBattery) minBattery = Math.round(b);
        }
      }
    });

    Object.values(healthData).forEach(item => {
      if (item.offline) offlineCount++;
      if (item.battery !== null && !isNaN(item.battery)) {
        if (minBattery === null || item.battery < minBattery) minBattery = Math.round(item.battery);
      }
    });

    const battLabel = minBattery !== null ? `${minBattery}%` : 'Secteur';
    const battColor = minBattery !== null ? (minBattery > 50 ? '#10b981' : (minBattery > 15 ? '#f59e0b' : '#ef4444')) : '#10b981';
    const netLabel = offlineCount > 0 ? `${offlineCount} HS` : 'OK';
    const netColor = offlineCount > 0 ? '#ef4444' : '#10b981';

    // 7. Real Subsystem Badges
    const openDoors = (attrs.opening_sensors || []).filter(id => {
      const s = this._hass.states[id];
      return s && ['on', 'open', 'true', 'detected', 'unlocked', '1'].includes(String(s.state).toLowerCase());
    });
    const activeMotions = (attrs.motion_sensors || []).filter(id => {
      const s = this._hass.states[id];
      return s && ['on', 'detected', 'motion', 'true', '1'].includes(String(s.state).toLowerCase());
    });
    const activeSabotages = [...(attrs.tamper_sensors || []), ...(attrs.safety_sensors || [])].filter(id => {
      const s = this._hass.states[id];
      return s && ['on', 'detected', 'true', '1'].includes(String(s.state).toLowerCase());
    });
    const totalPersons = (attrs.persons || []).length;
    const homePersons = (attrs.persons || []).filter(id => {
      const s = this._hass.states[id];
      return s && s.state === 'home';
    });

    const html = `
      <div class="arm-layout-grid">
        <!-- ─── Left Column (Widgets) ─────────────── -->
        <div class="left-widgets-col">
          <!-- Widget 1: Cameras -->
          <div class="glass-card widget-card">
            <div class="widget-header">
              <span>Caméras</span>
              <div style="display:flex; gap:6px; cursor:pointer;" id="btn-switch-camera" title="Changer de caméra">
                <ha-icon icon="mdi:chevron-right" style="--mdc-icon-size:18px;"></ha-icon>
              </div>
            </div>

            <div class="camera-preview-container" id="camera-preview-box" style="${currentCamEntity ? 'cursor:pointer;' : ''}" title="${currentCamEntity ? 'Cliquer pour ouvrir le flux direct plein écran' : ''}">
              <div class="camera-live-badge">
                <div class="live-red-dot"></div>
                <span>${this.escapeHtml(camFriendlyName)}</span>
              </div>
              ${currentCamEntity ? `
                <img id="live-camera-img" class="camera-img-stream" data-cam-entity="${currentCamEntity}" src="${camImgSrc}" alt="Camera Feed" />
              ` : `
                <div style="width:100%; height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; color:var(--d-subtext); font-size:12px; gap:6px;">
                  <ha-icon icon="mdi:camera-off" style="--mdc-icon-size:28px; opacity:0.6;"></ha-icon>
                  <span>Aucune caméra liée</span>
                </div>
              `}
            </div>

            <div class="camera-footer-status">
              <span>${currentCamEntity ? this.escapeHtml(camFriendlyName).toUpperCase() : 'CAMÉRAS'}</span>
              ${currentCamEntity ? `
                <button class="btn-live-stream" id="btn-open-live-stream" style="background:rgba(239, 68, 68, 0.15); border:1px solid rgba(239,68,68,0.4); color:#ef4444; padding:3px 10px; border-radius:8px; font-size:10px; font-weight:800; cursor:pointer; display:flex; align-items:center; gap:5px; transition:all 0.2s ease;">
                  <span class="live-red-dot" style="width:5px; height:5px;"></span> FORCER LE LIVE
                </button>
              ` : `
                <span style="color:var(--d-subtext); font-size:11px;">Non configurée</span>
              `}
            </div>
          </div>

          <!-- Widget 2: Appareils -->
          <div class="glass-card widget-card" id="widget-nav-equip" style="cursor:pointer;" title="Voir les équipements">
            <div class="widget-header">
              <span>Appareils</span>
              <ha-icon icon="mdi:chevron-right" style="--mdc-icon-size:18px;"></ha-icon>
            </div>
            <div class="stat-big-value">${totalSensorsCount} Capteur${totalSensorsCount > 1 ? 's' : ''}</div>
            <div class="stat-sub-label">${activeTriggers.length > 0 ? `<span style="color:#ef4444; font-weight:700;">${activeTriggers.length} Ouvert(s)</span>` : 'Tous sécurisés'}</div>
          </div>

          <!-- Widget 3: Journal / Activité -->
          <div class="glass-card widget-card" id="widget-nav-log" style="cursor:pointer;" title="Voir le journal des événements">
            <div class="widget-header">
              <span>Journal</span>
              <ha-icon icon="mdi:chevron-right" style="--mdc-icon-size:18px;"></ha-icon>
            </div>
            <div style="font-size:12px; font-weight:700; color:var(--d-text); margin-bottom:2px;">Activité</div>
            <div class="recent-events-list">
              <div class="recent-event-row">${recentEvent1}</div>
              <div class="recent-event-row">${recentEvent2}</div>
            </div>
          </div>

          <!-- Widget 4: Santé -->
          <div class="glass-card widget-card" id="widget-nav-health" style="cursor:pointer;" title="Voir la santé des équipements">
            <div class="widget-header">
              <span>Santé</span>
              <ha-icon icon="mdi:chevron-right" style="--mdc-icon-size:18px;"></ha-icon>
            </div>
            <div class="health-stats-row">
              <div class="health-item-stat">
                <span style="font-size:11px; color:var(--d-subtext); font-weight:600;">Pile min.</span>
                <span style="font-size:16px; font-weight:800; color:${battColor};">${battLabel}</span>
              </div>
              <div class="health-item-stat" style="text-align:right;">
                <span style="font-size:11px; color:var(--d-subtext); font-weight:600;">Réseau</span>
                <span style="font-size:16px; font-weight:800; color:${netColor};">${netLabel}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- ─── Center Column (Neon Hero Encadrés) ─── -->
        <div class="center-hero-col">
          <!-- Top Encadré Arrondi (SÉCURISÉ / ARMÉ) -->
          <div class="neon-pill-card ${heroClass}">
            <div class="pill-icon-badge">
              <ha-icon icon="${heroIcon}"></ha-icon>
            </div>
            <div class="pill-text-content">
              <div class="pill-main-title">${heroTitle}</div>
              <div class="pill-sub-desc">${this.escapeHtml(heroDesc)}</div>
            </div>
          </div>

          <!-- Real Subsystem Badges Grid -->
          <div class="room-badges-grid">
            <div class="room-badge-item ${openDoors.length === 0 ? 'ok' : 'danger'}">
              <span class="room-badge-name">OUVERTURES</span>
              <span class="room-badge-status">${openDoors.length === 0 ? 'SÉCURISÉ' : `${openDoors.length} OUVERT`}</span>
            </div>
            <div class="room-badge-item ${activeMotions.length === 0 ? 'ok' : 'danger'}">
              <span class="room-badge-name">MOUVEMENTS</span>
              <span class="room-badge-status">${activeMotions.length === 0 ? 'REPOS' : 'DÉTECTÉ'}</span>
            </div>
            <div class="room-badge-item ${activeSabotages.length === 0 ? 'ok' : 'danger'}">
              <span class="room-badge-name">SÉCURITÉ 24/7</span>
              <span class="room-badge-status">${activeSabotages.length === 0 ? 'PROTÉGÉ' : 'ALERTE'}</span>
            </div>
            <div class="room-badge-item ${isArmed ? 'info' : 'ok'}">
              <span class="room-badge-name">OCCUPATION</span>
              <span class="room-badge-status">${totalPersons > 0 ? `${homePersons.length}/${totalPersons} PRÉSENT(S)` : (isArmed ? 'ARMÉ' : 'SURVEILLANCE')}</span>
            </div>
          </div>

          <!-- Bottom Encadré Arrondi (ALERTE) -->
          <div class="neon-pill-card ${alertClass}">
            <div class="pill-icon-badge">
              <ha-icon icon="${alertIcon}"></ha-icon>
            </div>
            <div class="pill-text-content">
              <div class="pill-main-title">${alertTitle}</div>
              <div class="pill-sub-desc">${this.escapeHtml(alertDesc)}</div>
            </div>
          </div>

          <!-- Carousel Dots Indicator -->
          <div class="carousel-dots">
            <div class="dot active"></div>
            <div class="dot"></div>
          </div>

          <!-- Center Mode Switcher Pills -->
          <div class="center-modes-row">
            <button class="center-mode-btn ${state === 'armed_away' ? 'active' : ''}" data-service="alarm_arm_away">
              <ha-icon icon="mdi:shield-lock"></ha-icon> Armement
            </button>
            <button class="center-mode-btn ${state === 'armed_home' ? 'active' : ''}" data-service="alarm_arm_home">
              <ha-icon icon="mdi:shield-home"></ha-icon> Partiel
            </button>
            <button class="center-mode-btn ${isDisarmed ? 'active' : ''}" data-service="alarm_disarm">
              <ha-icon icon="mdi:shield-off"></ha-icon> Désarmé
            </button>
          </div>
          
          <!-- Cloud & Cameras Status (Red Box Area) -->
          <div style="display:flex; gap:12px; margin-top:24px;">
            <!-- Telegram -->
            <div style="flex:1; background:var(--d-sec-bg); border-radius:14px; border:1px solid var(--d-border); padding:10px 12px; display:flex; align-items:center; gap:10px; box-shadow:0 2px 10px rgba(0,0,0,0.02);">
              <div style="width:36px; height:36px; border-radius:10px; background:${telegramStatus === 'Désactivé' ? 'var(--d-border)' : (telegramStatus === 'Connecté' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)')}; display:flex; align-items:center; justify-content:center; color:${telegramStatus === 'Désactivé' ? 'var(--d-subtext)' : (telegramStatus === 'Connecté' ? '#10b981' : '#ef4444')};">
                <ha-icon icon="mdi:send-circle"></ha-icon>
              </div>
              <div style="flex-grow:1; min-width:0;">
                <div style="font-size:10px; font-weight:800; color:var(--d-subtext); text-transform:uppercase; letter-spacing:0.5px;">Telegram</div>
                <div style="font-size:12px; font-weight:800; color:var(--d-text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${telegramStatus}</div>
              </div>
            </div>
            
            <!-- FTP -->
            <div style="flex:1; background:var(--d-sec-bg); border-radius:14px; border:1px solid var(--d-border); padding:10px 12px; display:flex; align-items:center; gap:10px; box-shadow:0 2px 10px rgba(0,0,0,0.02);">
              <div style="width:36px; height:36px; border-radius:10px; background:${ftpStatus === 'Désactivé' ? 'var(--d-border)' : (ftpStatus === 'Connecté' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)')}; display:flex; align-items:center; justify-content:center; color:${ftpStatus === 'Désactivé' ? 'var(--d-subtext)' : (ftpStatus === 'Connecté' ? '#10b981' : '#ef4444')};">
                <ha-icon icon="mdi:folder-network"></ha-icon>
              </div>
              <div style="flex-grow:1; min-width:0;">
                <div style="font-size:10px; font-weight:800; color:var(--d-subtext); text-transform:uppercase; letter-spacing:0.5px;">Cloud FTP</div>
                <div style="font-size:12px; font-weight:800; color:var(--d-text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${ftpStatus}</div>
              </div>
            </div>
            
            <!-- Cameras -->
            <div style="flex:1; background:var(--d-sec-bg); border-radius:14px; border:1px solid var(--d-border); padding:10px 12px; display:flex; align-items:center; gap:10px; box-shadow:0 2px 10px rgba(0,0,0,0.02);">
              <div style="width:36px; height:36px; border-radius:10px; background:${camerasArmed ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)'}; display:flex; align-items:center; justify-content:center; color:${camerasArmed ? '#ef4444' : '#10b981'};">
                <ha-icon icon="mdi:cctv"></ha-icon>
              </div>
              <div style="flex-grow:1; min-width:0;">
                <div style="font-size:10px; font-weight:800; color:var(--d-subtext); text-transform:uppercase; letter-spacing:0.5px;">Caméras</div>
                <div style="font-size:12px; font-weight:800; color:var(--d-text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${camerasArmed ? 'Armées' : 'Désactivées'}</div>
              </div>
            </div>
          </div>
          
        </div>

        <!-- ─── Right Column (PIN Keypad) ─────────── -->
        <div class="glass-card keypad-glass-card">
          <div class="keypad-title">ENTRER LE PIN</div>

          <div class="keypad-feedback-box">
            <div class="pin-indicators-row">
              <div class="pin-dot-light"></div>
              <div class="pin-dot-light"></div>
              <div class="pin-dot-light"></div>
              <div class="pin-dot-light"></div>
              <div class="pin-dot-light"></div>
              <div class="pin-dot-light"></div>
            </div>
          </div>

          <div class="keypad-buttons-grid">
            ${[1, 2, 3, 4, 5, 6, 7, 8, 9].map(n => `
              <button class="keypad-circle-btn" data-key="${n}">
                ${n}
                <div class="key-led-dot"></div>
              </button>
            `).join('')}
            <button class="keypad-circle-btn" data-key="clear" style="font-size:18px; font-weight:800;">#</button>
            <button class="keypad-circle-btn" data-key="0">
              0
              <div class="key-led-dot"></div>
            </button>
            <button class="keypad-circle-btn" data-key="back" style="font-size:20px; font-weight:800;">*</button>
          </div>

          <div class="keypad-bottom-actions">
            <button class="keypad-action-pill ${state === 'armed_away' ? 'primary' : ''}" data-service="alarm_arm_away">
              Armement Total
            </button>
            <button class="keypad-action-pill ${state === 'armed_home' ? 'primary' : ''}" data-service="alarm_arm_home">
              Partiel
            </button>
            <button class="keypad-action-pill ${isDisarmed ? 'primary' : ''}" data-service="alarm_disarm">
              Désarmé
            </button>
          </div>

          <button class="btn-sos-danger" id="btn-panic-sos">
            <ha-icon icon="mdi:alert-decagram" style="--mdc-icon-size:18px;"></ha-icon>
            SOS PANIQUE IMMÉDIAT
          </button>
        </div>
      </div>
    `;

    const armCacheKey = `${state}_${attrs.last_user}_${attrs.triggered_by}_${this._selectedCameraIndex}_${totalSensorsCount}_${activeTriggers.length}_${isArmed}`;
    if (this._lastArmKey !== armCacheKey) {
      this._lastArmKey = armCacheKey;
      container.innerHTML = html;

      // Keypad Touch Listeners with tactile feedback
      container.querySelectorAll('.keypad-circle-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          if (window.navigator && window.navigator.vibrate) {
            try { window.navigator.vibrate(15); } catch(e) {}
          }
          const k = btn.getAttribute('data-key');
          if (k === 'clear') this._codeValue = '';
          else if (k === 'back') this._codeValue = this._codeValue.slice(0, -1);
          else if (this._codeValue.length < 6) this._codeValue += k;
          this._updatePinDisplay();
        });
      });

      // Service Buttons
      container.querySelectorAll('[data-service]').forEach(btn => {
        btn.addEventListener('click', () => this.callAlarmService(btn.getAttribute('data-service')));
      });

      // Camera Live Stream Trigger (Reliably opens Home Assistant live stream player)
      const triggerLiveStream = () => {
        if (!currentCamEntity) return;

        const liveBtn = container.querySelector('#btn-open-live-stream');
        if (liveBtn) {
          const origHtml = liveBtn.innerHTML;
          liveBtn.innerHTML = '<span class="live-red-dot"></span> LIVE...';
          setTimeout(() => { if (liveBtn) liveBtn.innerHTML = origHtml; }, 2500);
        }

        const fireMoreInfo = (target) => {
          const ev = new Event('hass-more-info', {
            bubbles: true,
            cancelable: false,
            composed: true,
          });
          ev.detail = { entityId: currentCamEntity };
          target.dispatchEvent(ev);
        };

        fireMoreInfo(this);
        const haRoot = document.querySelector('home-assistant');
        if (haRoot) fireMoreInfo(haRoot);
        window.dispatchEvent(new CustomEvent('hass-more-info', { detail: { entityId: currentCamEntity }, bubbles: true, composed: true }));
      };

      const camBox = container.querySelector('#camera-preview-box');
      if (camBox && currentCamEntity) {
        camBox.addEventListener('click', triggerLiveStream);
      }

      const liveBtn = container.querySelector('#btn-open-live-stream');
      if (liveBtn && currentCamEntity) {
        liveBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          triggerLiveStream();
        });
      }

      // Clickable Widgets for Quick Navigation
      const navEquip = container.querySelector('#widget-nav-equip');
      if (navEquip) {
        navEquip.addEventListener('click', () => {
          this._activeTab = 'equip';
          this.querySelectorAll('.nav-tab').forEach(t => t.classList.toggle('active', t.getAttribute('data-tab') === 'equip'));
          this.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('active', p.id === 'pane-equip'));
          this.render();
        });
      }
      const navLog = container.querySelector('#widget-nav-log');
      if (navLog) {
        navLog.addEventListener('click', () => {
          this._activeTab = 'log';
          this.querySelectorAll('.nav-tab').forEach(t => t.classList.toggle('active', t.getAttribute('data-tab') === 'log'));
          this.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('active', p.id === 'pane-log'));
          this.render();
        });
      }
      const navHealth = container.querySelector('#widget-nav-health');
      if (navHealth) {
        navHealth.addEventListener('click', () => {
          this._activeTab = 'health';
          this.querySelectorAll('.nav-tab').forEach(t => t.classList.toggle('active', t.getAttribute('data-tab') === 'health'));
          this.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('active', p.id === 'pane-health'));
          this.render();
        });
      }

      // Camera Switcher
      const camSwitchBtn = container.querySelector('#btn-switch-camera');
      if (camSwitchBtn && cameraList.length > 1) {
        camSwitchBtn.addEventListener('click', () => {
          this._selectedCameraIndex = (this._selectedCameraIndex + 1) % cameraList.length;
          this.render();
        });
      }

      // SOS Panic Button
      const panicBtn = container.querySelector('#btn-panic-sos');
      if (panicBtn) {
        panicBtn.addEventListener('click', () => {
          if (confirm("🚨 DÉCLENCHER L'ALERTE SOS IMMÉDIATE ?")) {
            this._hass.callService('domolink_alarm', 'panic', { activate_sirens: true });
          }
        });
      }
    }
  }

  // ─── Tab 2: Équipements ─────────────────────────

  _renderEquipTab(attrs) {
    const container = this.querySelector('#pane-equip');
    if (!container) return;
    const bypassedSensors = attrs.bypassed_sensors || [];

    const categories = [
      { key: "opening_sensors", icon: "mdi:door-open", name: "Capteurs d'ouverture" },
      { key: "motion_sensors", icon: "mdi:motion-sensor", name: "Capteurs de mouvement" },
      { key: "tamper_sensors", icon: "mdi:shield-alert", name: "Capteurs de sabotage (24/7)" },
      { key: "safety_sensors", icon: "mdi:fire-alert", name: "Capteurs Techniques (Fumée, Gaz, Inondation)" },
      { key: "night_sensors", icon: "mdi:weather-night", name: "Capteurs Mode Nuit" },
      { key: "sirens", icon: "mdi:bullhorn", name: "Sirènes d'alarme" },
      { key: "lights", icon: "mdi:alarm-light", name: "Éclairages d'urgence" },
      { key: "cameras", icon: "mdi:cctv", name: "Caméras de sécurité" },
      { key: "media_players", icon: "mdi:speaker", name: "Haut-parleurs & Annonces vocales" },
      { key: "persons", icon: "mdi:account", name: "Personnes & Géolocalisation" }
    ];

    let html = '<div class="glass-card"><div style="display:flex; flex-direction:column; gap:24px;">';
    let count = 0;

    for (const cat of categories) {
      const entityIds = attrs[cat.key];
      if (!entityIds || entityIds.length === 0) continue;
      count++;

      html += `<div><div style="font-size:15px; font-weight:800; color:var(--d-text); margin-bottom:12px; display:flex; align-items:center; gap:8px;"><ha-icon icon="${cat.icon}" style="color:#f59e0b;"></ha-icon> ${cat.name}</div><div class="equip-matrix">`;
      for (const entityId of entityIds) {
        const entityState = this._hass.states[entityId];
        let friendlyName = entityId, stateStr = "Inconnu", activeClass = "";
        let isUnavailable = false, isOpenOrFaulty = false;
        const isBypassed = bypassedSensors.includes(entityId);

        if (!entityState || entityState.state === 'unavailable' || entityState.state === 'unknown') {
          isUnavailable = true;
          friendlyName = entityState ? (entityState.attributes.friendly_name || entityId) : entityId;
          stateStr = entityState && entityState.state === 'unknown' ? "Inconnu" : "Hors ligne";
          activeClass = "active";
        } else {
          friendlyName = entityState.attributes.friendly_name || entityId;
          stateStr = this._hass.formatEntityState ? this._hass.formatEntityState(entityState) : entityState.state;
          activeClass = this.getActiveClass(entityState);
          if (activeClass === "active") isOpenOrFaulty = true;
        }

        let actionBtn = "";
        if (isBypassed) {
          actionBtn = `<button class="btn-action-pill restore" data-action="unbypass" data-entity="${entityId}">Rétablir</button>`;
        } else if (isUnavailable || isOpenOrFaulty) {
          actionBtn = `<button class="btn-action-pill bypass" data-action="bypass" data-entity="${entityId}">Ignorer</button>`;
        }

        let iconDiscClass = isBypassed ? "bypassed" : (activeClass === "active" ? "active" : (activeClass === "active-success" ? "success" : ""));

        html += `
          <div class="equip-item-card">
            <div class="equip-icon-disc ${iconDiscClass}">
              <ha-icon icon="${isBypassed ? 'mdi:shield-off' : cat.icon}"></ha-icon>
            </div>
            <div style="flex-grow:1; min-width:0;">
              <div style="font-size:14px; font-weight:700; color:var(--d-text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${this.escapeHtml(friendlyName)}</div>
              <div style="font-size:12px; color:${isBypassed ? '#f59e0b' : (activeClass === 'active' ? '#ef4444' : 'var(--d-subtext)')}; margin-top:2px; font-weight:600;">
                ${isBypassed ? '⚠️ Exclu de la surveillance' : this.escapeHtml(stateStr)}
              </div>
            </div>
            ${actionBtn}
          </div>
        `;
      }
      html += '</div></div>';
    }

    if (count === 0) {
      html += '<div class="empty-placeholder"><ha-icon icon="mdi:devices" style="--mdc-icon-size:40px;margin-bottom:8px"></ha-icon><br>Aucun équipement configuré.</div>';
    }
    html += '</div></div>';

    if (this._lastEquipHtml !== html) {
      container.innerHTML = html;
      this._lastEquipHtml = html;

      // Event delegation for bypass
      container.querySelectorAll('.btn-action-pill').forEach(btn => {
        btn.addEventListener('click', () => {
          const entityId = btn.getAttribute('data-entity');
          const action = btn.getAttribute('data-action');
          if (action === 'bypass') {
            this._hass.callService('domolink_alarm', 'bypass_sensor', { entity_id: entityId });
          } else if (action === 'unbypass') {
            this._hass.callService('domolink_alarm', 'unbypass_sensor', { entity_id: entityId });
          }
        });
      });
    }
  }

  // ─── Tab 3: Journal ─────────────────────────────

  _renderLogTab() {
    const container = this.querySelector('#pane-log');
    if (!container) return;

    const alarmEntity = this._getAlarmEntity();
    const attrs = alarmEntity ? alarmEntity.attributes : {};
    const armHistory = attrs.arm_history || [];
    const systemEvents = attrs.system_events || [];

    const html = `
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">
        <div class="glass-card">
          <div style="font-size:15px; font-weight:800; color:var(--d-text); margin-bottom:16px; display:flex; align-items:center; gap:8px;">
            <ha-icon icon="mdi:shield-account" style="color:#10b981;"></ha-icon>
            Activations & Utilisateurs
          </div>
          <div class="log-timeline">
            ${armHistory.length > 0 ? armHistory.map(ev => {
              const isArm = ev.action === "arm";
              let dotClass = isArm ? "arm" : "disarm";
              let title = isArm ? `Armement (${ev.mode || 'Absent'})` : "Désarmement";
              return `
                <div class="log-entry">
                  <div class="log-dot ${dotClass}">
                    <ha-icon icon="${isArm ? 'mdi:shield-lock' : 'mdi:shield-off'}" style="--mdc-icon-size:18px;"></ha-icon>
                  </div>
                  <div style="flex-grow:1; min-width:0;">
                    <div style="font-size:13px; font-weight:700; color:var(--d-text);">${title} par <strong style="color:#f59e0b;">${this.escapeHtml(ev.user || "Inconnu")}</strong></div>
                    <div style="font-size:11px; color:var(--d-subtext); margin-top:2px; font-weight:500;">${this.formatDate(ev.time)}</div>
                  </div>
                </div>
              `;
            }).join('') : '<div class="empty-placeholder">Aucun historique d\'activation.</div>'}
          </div>
        </div>

        <div class="glass-card">
          <div style="font-size:15px; font-weight:800; color:var(--d-text); margin-bottom:16px; display:flex; align-items:center; gap:8px;">
            <ha-icon icon="mdi:format-list-bulleted" style="color:#3b82f6;"></ha-icon>
            Événements récents
          </div>
          <div class="log-timeline">
            ${systemEvents.length > 0 ? systemEvents.map(ev => {
              let icon = 'mdi:information-variant';
              let iconColor = 'var(--d-subtext)';
              let dotClass = 'info';
              
              let entryClass = '';
              if (ev.message.includes('DÉCLENCHÉE') || ev.message.includes('ALERTE') || ev.message.includes('Sabotage') || ev.message.includes('Sirène prolongée') || ev.message.includes('Double détection confirmée') || ev.message.includes('PANIQUE')) {
                icon = 'mdi:alert';
                iconColor = '#ef4444';
                dotClass = 'alert';
                entryClass = 'row-alert';
              } else if (ev.message.includes('Pré-détection') || ev.message.includes("pendant le délai d'entrée") || ev.message.includes("pendant délai d'entrée") || ev.message.includes('Message envoyé') || ev.message.includes("SMS d'alerte envoyé")) {
                icon = 'mdi:alert-outline';
                iconColor = '#f97316'; // Orange
                dotClass = 'warning';
                entryClass = 'row-warning';
              } else if (ev.message.includes('Armée')) {
                icon = 'mdi:shield-lock';
                iconColor = '#f59e0b';
                dotClass = 'warning';
              } else if (ev.message.includes('Désarmée')) {
                icon = 'mdi:shield-check';
                iconColor = '#10b981';
                dotClass = 'event';
              }
              
              return `
                <div class="log-entry ${entryClass}">
                  <div class="log-dot ${dotClass}" style="color: ${iconColor};">
                    <ha-icon icon="${icon}" style="--mdc-icon-size:18px;"></ha-icon>
                  </div>
                  <div style="flex-grow:1; min-width:0;">
                    <div style="font-size:13px; font-weight:600; color:var(--d-text); line-height:1.4;">${ev.message}</div>
                    <div style="font-size:11px; color:var(--d-subtext); margin-top:2px; font-weight:500;">${this.formatDate(ev.time)}</div>
                  </div>
                </div>
              `;
            }).join('') : '<div class="empty-placeholder">Aucun événement système.</div>'}
          </div>
        </div>
      </div>
    `;

    if (this._lastLogHtml !== html) {
      container.innerHTML = html;
      this._lastLogHtml = html;
    }
  }

  // ─── Tab 4: Santé ───────────────────────────────

  _renderHealthTab() {
    const container = this.querySelector('#pane-health');
    if (!container) return;

    const alarmEntity = this._getAlarmEntity();
    const attrs = alarmEntity ? alarmEntity.attributes : {};
    const healthData = attrs.sensor_health || {};
    const keys = Object.keys(healthData).sort();

    let html = '<div class="glass-card">';

    if (keys.length > 0) {
      let onlineCount = 0;
      let lowBattCount = 0;

      for (const entityId of keys) {
        const item = healthData[entityId];
        if (!item.offline) onlineCount++;
        if (item.battery !== null && item.battery <= 15) lowBattCount++;
      }

      const score = Math.round((onlineCount / keys.length) * 100);
      let scoreColor = score >= 95 ? "#10b981" : (score >= 80 ? "#f59e0b" : "#ef4444");

      html += `
        <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:16px; margin-bottom:24px;">
          <div style="background:var(--d-sec-bg); border:1px solid var(--d-border); border-radius:16px; padding:18px; text-align:center;">
            <div style="font-size:28px; font-weight:900; color:${scoreColor};">${score}%</div>
            <div style="font-size:12px; color:var(--d-subtext); font-weight:700; margin-top:4px;">Disponibilité Globale</div>
          </div>
          <div style="background:var(--d-sec-bg); border:1px solid var(--d-border); border-radius:16px; padding:18px; text-align:center;">
            <div style="font-size:28px; font-weight:900; color:var(--d-text);">${keys.length}</div>
            <div style="font-size:12px; color:var(--d-subtext); font-weight:700; margin-top:4px;">Équipements Liés</div>
          </div>
          <div style="background:var(--d-sec-bg); border:1px solid var(--d-border); border-radius:16px; padding:18px; text-align:center;">
            <div style="font-size:28px; font-weight:900; color:${lowBattCount > 0 ? '#ef4444' : '#10b981'};">${lowBattCount}</div>
            <div style="font-size:12px; color:var(--d-subtext); font-weight:700; margin-top:4px;">Piles Faibles (&le;15%)</div>
          </div>
        </div>

        <div style="font-size:15px; font-weight:800; color:var(--d-text); margin-bottom:14px; display:flex; align-items:center; gap:8px;">
          <ha-icon icon="mdi:check-network-outline" style="color:#f59e0b;"></ha-icon> État individuel des équipements
        </div>
        <div style="display:flex; flex-direction:column; gap:10px;">
      `;

      for (const entityId of keys) {
        const item = healthData[entityId];
        const lastSeen = item.last_changed ? this.formatDate(item.last_changed) : "Inconnu";

        let battHtml = '<span style="font-size:12px; color:var(--d-subtext); font-weight:700;">N/A</span>';
        if (item.battery !== null) {
          const b = item.battery;
          const bColor = b > 50 ? '#10b981' : (b > 15 ? '#f59e0b' : '#ef4444');
          battHtml = `
            <div style="display:flex; align-items:center; gap:8px;">
              <div style="width:70px; height:6px; background:var(--d-border); border-radius:3px; overflow:hidden;">
                <div style="width:${b}%; height:100%; background:${bColor};"></div>
              </div>
              <span style="font-size:12px; font-weight:800; color:${bColor}; min-width:36px; text-align:right;">${b}%</span>
            </div>
          `;
        }

        html += `
          <div style="display:flex; align-items:center; padding:12px 16px; background:var(--d-sec-bg); border:1px solid var(--d-border); border-radius:14px; gap:14px;">
            <div style="width:10px; height:10px; border-radius:50%; background:${item.offline ? '#ef4444' : '#10b981'};"></div>
            <div style="flex-grow:1; min-width:0;">
              <div style="font-size:14px; font-weight:700; color:var(--d-text);">${this.escapeHtml(item.name)}</div>
              <div style="font-size:12px; color:var(--d-subtext); margin-top:2px; font-weight:500;">
                ${item.offline ? '⚠️ Hors ligne' : 'En ligne'} • Vu ${lastSeen}
              </div>
            </div>
            ${battHtml}
          </div>
        `;
      }
      html += '</div>';
    } else {
      html += '<div class="empty-placeholder"><ha-icon icon="mdi:stethoscope" style="--mdc-icon-size:40px;margin-bottom:8px"></ha-icon><br>Diagnostic de santé actif.<br>Supervision automatique toutes les 4 heures.</div>';
    }

    html += '</div>';

    if (this._lastHealthHtml !== html) {
      container.innerHTML = html;
      this._lastHealthHtml = html;
    }
  }

  // ─── Tab 5: Simulation de Présence ──────────────

  _renderSimTab(attrs) {
    const container = this.querySelector('#pane-sim');
    if (!container) return;

    const isRunning = attrs.presence_simulation_active;
    const historyDays = attrs.presence_simulation_history_days || 7;
    const entities = attrs.presence_simulation_entities || [];

    const html = `
      <div class="glass-card" style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:20px; margin-bottom:20px;">
        <div style="display:flex; align-items:center; gap:16px;">
          <div style="width:52px; height:52px; border-radius:14px; background:rgba(139, 92, 246, 0.15); color:#8b5cf6; display:flex; align-items:center; justify-content:center;">
            <ha-icon icon="mdi:home-clock" style="--mdc-icon-size:30px;"></ha-icon>
          </div>
          <div>
            <div style="font-size:18px; font-weight:800; color:var(--d-text);">
              Simulation de Présence : ${isRunning ? '<span style="color:#10b981">ACTIVE</span>' : '<span style="color:var(--d-subtext)">EN PAUSE</span>'}
            </div>
            <div style="font-size:13px; color:var(--d-subtext); margin-top:4px;">
              ${isRunning ? `Rejeu automatique de vos habitudes d'il y a ${historyDays} jours sur ${entities.length} appareils` : "Prête à s'activer lors de vos absences ou sur demande"}
            </div>
          </div>
        </div>

        <button id="btn-toggle-sim" style="padding:14px 24px; border-radius:9999px; border:none; font-size:13px; font-weight:800; cursor:pointer; background:${isRunning ? '#ef4444' : '#10b981'}; color:#ffffff; box-shadow:0 4px 14px rgba(0,0,0,0.2);">
          ${isRunning ? 'ARRÊTER LA SIMULATION' : 'DÉMARRER MAINTENANT'}
        </button>
      </div>

      <div class="glass-card">
        <div style="font-size:15px; font-weight:800; color:var(--d-text); margin-bottom:16px; display:flex; align-items:center; gap:8px;">
          <ha-icon icon="mdi:lightbulb-multiple" style="color:#f59e0b;"></ha-icon>
          Appareils supervisés (${entities.length})
        </div>
        <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(240px, 1fr)); gap:10px;">
          ${entities.length > 0 ? entities.map(entityId => {
            const stateObj = this._hass.states[entityId];
            const name = stateObj ? (stateObj.attributes.friendly_name || entityId) : entityId;
            const isOn = stateObj && stateObj.state === 'on';
            return `
              <div style="display:flex; align-items:center; justify-content:space-between; padding:12px 14px; background:var(--d-sec-bg); border-radius:12px; border:1px solid var(--d-border);">
                <div style="display:flex; align-items:center; gap:10px; min-width:0;">
                  <ha-icon icon="${isOn ? 'mdi:lightbulb-on' : 'mdi:lightbulb-outline'}" style="color:${isOn ? '#f59e0b' : 'var(--d-subtext)'};"></ha-icon>
                  <span style="font-size:13px; font-weight:700; color:var(--d-text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${this.escapeHtml(name)}</span>
                </div>
                <span style="font-size:11px; font-weight:800; text-transform:uppercase; color:${isOn ? '#10b981' : 'var(--d-subtext)'};">
                  ${isOn ? 'Allumé' : 'Éteint'}
                </span>
              </div>
            `;
          }).join('') : '<div class="empty-placeholder">Aucun appareil configuré pour la simulation.</div>'}
        </div>
      </div>
    `;

    if (this._lastSimHtml !== html) {
      container.innerHTML = html;
      this._lastSimHtml = html;

      const btn = container.querySelector('#btn-toggle-sim');
      if (btn) {
        btn.addEventListener('click', () => {
          this._hass.callService('domolink_alarm', 'toggle_presence_simulation', {});
        });
      }
    }
  }

  // ─── Tab 6: Paramètres ──────────────────────────

  _renderParamTab(alarmEntity) {
    const container = this.querySelector('#pane-param');
    if (!container) return;

    const attrs = alarmEntity ? alarmEntity.attributes : {};
    const chime = attrs.chime_active || false;
    const history_days = attrs.presence_simulation_history_days || 7;

    const html = `
      <div class="glass-card" style="display:flex; flex-direction:column; gap:20px;">
        <div style="font-size:17px; font-weight:800; color:var(--d-text); display:flex; align-items:center; gap:8px;">
          <ha-icon icon="mdi:tune" style="color:#f59e0b;"></ha-icon> Paramètres Rapides
        </div>

        <div style="display:flex; align-items:center; justify-content:space-between; padding:14px 16px; background:var(--d-sec-bg); border-radius:14px; border:1px solid var(--d-border);">
          <div>
            <div style="font-size:14px; font-weight:700; color:var(--d-text);">Mode Carillon (Chime)</div>
            <div style="font-size:12px; color:var(--d-subtext); margin-top:2px;">Bip court à l'ouverture d'une porte quand l'alarme est désarmée</div>
          </div>
          <input type="checkbox" id="param-chime" ${chime ? 'checked' : ''} style="width:20px; height:20px; cursor:pointer;" />
        </div>

        <div style="display:flex; align-items:center; justify-content:space-between; padding:14px 16px; background:var(--d-sec-bg); border-radius:14px; border:1px solid var(--d-border);">
          <div>
            <div style="font-size:14px; font-weight:700; color:var(--d-text);">Jours d'historique de simulation</div>
            <div style="font-size:12px; color:var(--d-subtext); margin-top:2px;">Plage de rejeu des habitudes de présence</div>
          </div>
          <select id="param-history" style="padding:8px 12px; border-radius:8px; background:var(--d-surface); color:var(--d-text); border:1px solid var(--d-border); font-weight:700;">
            <option value="7" ${history_days==7?"selected":""}>7 jours</option>
            <option value="14" ${history_days==14?"selected":""}>14 jours</option>
            <option value="21" ${history_days==21?"selected":""}>21 jours</option>
            <option value="28" ${history_days==28?"selected":""}>28 jours</option>
          </select>
        </div>

        <div style="text-align:center; padding-top:10px;">
          <button id="btn-save-params" style="padding:12px 32px; border-radius:9999px; border:none; background:#f59e0b; color:#ffffff; font-weight:800; font-size:13px; cursor:pointer; box-shadow:0 4px 16px rgba(245,158,11,0.4);">
            Sauvegarder les Paramètres
          </button>
        </div>
      </div>
    `;

    if (this._lastParamHtml !== html) {
      container.innerHTML = html;
      this._lastParamHtml = html;

      const btnSave = container.querySelector('#btn-save-params');
      if (btnSave) {
        btnSave.addEventListener('click', () => {
          const chimeVal = container.querySelector('#param-chime').checked;
          const historyVal = parseInt(container.querySelector('#param-history').value, 10);
          this._hass.callService('domolink_alarm', 'update_settings', {
            chime_mode: chimeVal,
            presence_simulation_history_days: historyVal
          }).then(() => {
            btnSave.innerText = "✓ Sauvegardé !";
            btnSave.style.backgroundColor = "#10b981";
            setTimeout(() => {
              btnSave.innerText = "Sauvegarder les Paramètres";
              btnSave.style.backgroundColor = "#f59e0b";
            }, 2000);
          }).catch(e => alert("Erreur: " + e.message));
        });
      }
    }
  }

  // ─── Main Render ────────────────────────────────

  render() {
    const alarmEntity = this._getAlarmEntity();
    const attrs = alarmEntity ? alarmEntity.attributes : {};

    if (this._activeTab === 'arm') this._renderArmTab(alarmEntity);
    else if (this._activeTab === 'equip') this._renderEquipTab(attrs);
    else if (this._activeTab === 'log') this._renderLogTab();
    else if (this._activeTab === 'health') this._renderHealthTab();
    else if (this._activeTab === 'sim') this._renderSimTab(attrs);
    else if (this._activeTab === 'param') this._renderParamTab(alarmEntity);
  }

  // ─── Helpers ────────────────────────────────────

  getActiveClass(entityState) {
    const domain = entityState.entity_id.split('.')[0];
    const state = entityState.state;
    if (domain === "binary_sensor") return state === "on" ? "active" : "";
    if (domain === "person") return state === "home" ? "active-success" : "";
    if (domain === "switch" || domain === "light") return state === "on" ? "active" : "";
    return "";
  }
}

customElements.define('domolink-panel', DomolinkPanel);
