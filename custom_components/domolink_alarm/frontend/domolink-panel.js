class DomolinkPanel extends HTMLElement {
  set panel(panel) {
    this._panel = panel;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._activeTab = 'arm';
      this._codeValue = '';
      this._buildShell();
      this._initialized = true;
    }
    try {
      this.render();
    } catch (err) {
      console.error("Domolink Alarm render error:", err);
    }
  }

  _buildShell() {
    this.innerHTML = `
      <style>
        :host {
          --d-primary: var(--primary-color, #0284c7);
          --d-success: #10b981;
          --d-danger: #ef4444;
          --d-warning: #f59e0b;
          --d-night: #8b5cf6;
          --d-home: #3b82f6;
          --d-card-bg: var(--card-background-color, #ffffff);
          --d-bg: var(--primary-background-color, #f8fafc);
          --d-text: var(--primary-text-color, #1e293b);
          --d-subtext: var(--secondary-text-color, #64748b);
          --d-border: var(--divider-color, rgba(148, 163, 184, 0.15));

          background-color: var(--d-bg);
          display: block;
          height: 100%;
          overflow-y: auto;
          padding: 20px 16px 40px;
          box-sizing: border-box;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        .panel-wrap {
          max-width: 960px;
          margin: 0 auto;
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        /* ─── Modern Cards ────────────────────────── */
        .glass-card {
          background: var(--d-card-bg);
          border-radius: 20px;
          border: 1px solid var(--d-border);
          box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05), 0 2px 6px -1px rgba(0, 0, 0, 0.02);
          padding: 20px;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        /* ─── Hero Header & Status Banner ─────────── */
        .hero-banner {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 16px;
          padding: 20px 24px;
          background: linear-gradient(135deg, var(--d-card-bg) 0%, rgba(255,255,255,0.02) 100%);
          border-radius: 20px;
          border: 1px solid var(--d-border);
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
        }

        .brand-section {
          display: flex;
          align-items: center;
          gap: 14px;
        }

        .brand-logo {
          width: 48px;
          height: 48px;
          border-radius: 14px;
          background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          box-shadow: 0 4px 12px rgba(2, 132, 199, 0.25);
        }
        .brand-logo ha-icon { --mdc-icon-size: 28px; }

        .brand-title {
          font-size: 20px;
          font-weight: 700;
          color: var(--d-text);
          letter-spacing: -0.3px;
        }
        .brand-subtitle {
          font-size: 13px;
          color: var(--d-subtext);
          margin-top: 2px;
        }

        .state-pill {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 10px 20px;
          border-radius: 9999px;
          font-weight: 700;
          font-size: 13px;
          text-transform: uppercase;
          letter-spacing: 0.8px;
          color: white;
          box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12);
          transition: all 0.3s ease;
        }

        .state-disarmed {
          background: linear-gradient(135deg, #10b981 0%, #059669 100%);
          box-shadow: 0 4px 16px rgba(16, 185, 129, 0.35);
        }
        .state-armed {
          background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
          box-shadow: 0 4px 16px rgba(239, 68, 68, 0.35);
          animation: pulse-glow 2s infinite;
        }
        .state-pending {
          background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
          box-shadow: 0 4px 16px rgba(245, 158, 11, 0.35);
        }

        @keyframes pulse-glow {
          0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.5); }
          70% { box-shadow: 0 0 0 12px rgba(239, 68, 68, 0); }
          100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }

        /* ─── Status Chips (Active Features) ──────── */
        .status-chips-row {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          margin-top: 12px;
        }

        .status-pill {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 6px 12px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 600;
          background: rgba(148, 163, 184, 0.08);
          color: var(--d-subtext);
          border: 1px solid var(--d-border);
          transition: all 0.2s ease;
        }
        .status-pill ha-icon { --mdc-icon-size: 15px; }

        .status-pill.active {
          background: rgba(16, 185, 129, 0.1);
          color: #059669;
          border-color: rgba(16, 185, 129, 0.25);
        }
        .status-pill.user-badge {
          background: rgba(2, 132, 199, 0.1);
          color: #0284c7;
          border-color: rgba(2, 132, 199, 0.2);
        }

        /* ─── Segmented Navigation Bar ────────────── */
        .nav-segmented {
          display: flex;
          background: rgba(148, 163, 184, 0.12);
          padding: 5px;
          border-radius: 16px;
          gap: 4px;
          user-select: none;
        }

        .nav-tab {
          flex: 1;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 10px 14px;
          border-radius: 12px;
          font-size: 13px;
          font-weight: 600;
          color: var(--d-subtext);
          cursor: pointer;
          transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .nav-tab:hover {
          color: var(--d-text);
        }

        .nav-tab.active {
          background: var(--d-card-bg);
          color: var(--d-primary);
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }
        .nav-tab ha-icon { --mdc-icon-size: 18px; }

        .tab-badge {
          background: var(--d-primary);
          color: white;
          border-radius: 10px;
          padding: 1px 7px;
          font-size: 11px;
          font-weight: 700;
        }

        /* ─── Tab Content Panes ───────────────────── */
        .tab-pane {
          display: none;
          animation: fadeIn 0.25s ease;
        }
        .tab-pane.active { display: block; }

        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }

        /* ─── Tab 1: Armement & Modern Keypad ─────── */
        .arm-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 24px;
          align-items: start;
        }

        @media (max-width: 768px) {
          .arm-grid { grid-template-columns: 1fr; }
        }

        .keypad-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 12px 0;
        }

        .pin-display {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 12px;
          min-height: 48px;
          margin-bottom: 24px;
        }

        .pin-dot {
          width: 14px;
          height: 14px;
          border-radius: 50%;
          border: 2px solid var(--d-border);
          background: transparent;
          transition: all 0.15s ease;
        }
        .pin-dot.filled {
          background: var(--d-primary);
          border-color: var(--d-primary);
          box-shadow: 0 0 10px rgba(2, 132, 199, 0.4);
          transform: scale(1.1);
        }

        .keypad-dial {
          display: grid;
          grid-template-columns: repeat(3, 72px);
          gap: 14px;
        }

        .dial-key {
          width: 72px;
          height: 72px;
          border-radius: 50%;
          border: 1px solid var(--d-border);
          background: var(--d-card-bg);
          color: var(--d-text);
          font-size: 24px;
          font-weight: 500;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
          box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
        }

        .dial-key:hover {
          background: rgba(148, 163, 184, 0.08);
          border-color: var(--d-primary);
        }
        .dial-key:active {
          transform: scale(0.92);
          background: var(--d-primary);
          color: white;
        }

        .dial-key.action-key {
          font-size: 15px;
          font-weight: 600;
          color: var(--d-subtext);
        }
        .dial-key.action-key:active {
          background: var(--d-danger);
          color: white;
        }

        /* Mode Action Buttons */
        .mode-actions {
          display: flex;
          flex-direction: column;
          gap: 12px;
          justify-content: center;
        }

        .btn-mode {
          display: flex;
          align-items: center;
          gap: 16px;
          padding: 16px 20px;
          border-radius: 16px;
          border: none;
          color: white;
          font-size: 15px;
          font-weight: 700;
          letter-spacing: 0.3px;
          cursor: pointer;
          transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
          box-shadow: 0 4px 12px rgba(0,0,0,0.08);
          text-align: left;
        }
        .btn-mode:active { transform: scale(0.98); }
        .btn-mode ha-icon { --mdc-icon-size: 28px; }

        .btn-mode-content {
          display: flex;
          flex-direction: column;
        }
        .btn-mode-title { font-size: 15px; font-weight: 700; }
        .btn-mode-desc { font-size: 12px; opacity: 0.85; font-weight: 400; margin-top: 2px; }

        .btn-disarm {
          background: linear-gradient(135deg, #10b981 0%, #059669 100%);
          box-shadow: 0 4px 16px rgba(16, 185, 129, 0.25);
        }
        .btn-away {
          background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
          box-shadow: 0 4px 16px rgba(239, 68, 68, 0.25);
        }
        .btn-home {
          background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
          box-shadow: 0 4px 16px rgba(59, 130, 246, 0.25);
        }
        .btn-night {
          background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
          box-shadow: 0 4px 16px rgba(139, 92, 246, 0.25);
        }

        .btn-panic-sos {
          background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%);
          color: white;
          padding: 16px;
          border-radius: 16px;
          border: 1px solid rgba(239, 68, 68, 0.3);
          font-weight: 800;
          font-size: 14px;
          letter-spacing: 1px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 10px;
          box-shadow: 0 4px 16px rgba(220, 38, 38, 0.3);
          transition: all 0.2s ease;
          margin-top: 8px;
        }
        .btn-panic-sos:active { transform: scale(0.97); }
        .btn-panic-sos ha-icon { --mdc-icon-size: 24px; }

        /* ─── Tab 2: Équipements Grid ─────────────── */
        .section-header {
          font-size: 15px;
          font-weight: 700;
          color: var(--d-text);
          margin: 20px 0 10px;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .equip-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
          gap: 12px;
        }

        .equip-card {
          display: flex;
          align-items: center;
          padding: 12px 14px;
          background: var(--d-card-bg);
          border: 1px solid var(--d-border);
          border-radius: 14px;
          gap: 12px;
          transition: all 0.2s ease;
        }

        .equip-card.bypassed {
          border-style: dashed;
          border-color: var(--d-warning);
          background: rgba(245, 158, 11, 0.03);
          opacity: 0.85;
        }
        .equip-card.unavailable {
          border-color: rgba(239, 68, 68, 0.3);
          background: rgba(239, 68, 68, 0.03);
        }

        .equip-icon-wrap {
          width: 40px;
          height: 40px;
          border-radius: 10px;
          background: rgba(148, 163, 184, 0.1);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--d-subtext);
          flex-shrink: 0;
        }
        .equip-icon-wrap.active { background: rgba(239, 68, 68, 0.15); color: var(--d-danger); }
        .equip-icon-wrap.active-success { background: rgba(16, 185, 129, 0.15); color: var(--d-success); }
        .equip-icon-wrap.bypassed { background: rgba(245, 158, 11, 0.15); color: var(--d-warning); }

        .equip-info {
          flex-grow: 1;
          min-width: 0;
        }
        .equip-name {
          font-size: 14px;
          font-weight: 600;
          color: var(--d-text);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .equip-sub {
          font-size: 12px;
          color: var(--d-subtext);
          display: flex;
          align-items: center;
          gap: 6px;
          margin-top: 2px;
        }
        .equip-sub.active { color: var(--d-danger); font-weight: 600; }

        .btn-bypass {
          padding: 6px 12px;
          border-radius: 8px;
          border: none;
          font-size: 11px;
          font-weight: 700;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 4px;
          transition: opacity 0.2s ease;
          flex-shrink: 0;
        }
        .btn-bypass:active { opacity: 0.7; }
        .btn-bypass.ignore { background: rgba(245, 158, 11, 0.15); color: #b45309; }
        .btn-bypass.restore { background: rgba(148, 163, 184, 0.15); color: var(--d-subtext); }

        /* ─── Tab 3: Journal & Timeline ───────────── */
        .journal-layout {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
        }
        @media (max-width: 768px) {
          .journal-layout { grid-template-columns: 1fr; }
        }

        .timeline-list {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .timeline-item {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 12px 14px;
          background: var(--d-card-bg);
          border-radius: 12px;
          border: 1px solid var(--d-border);
        }

        .timeline-icon {
          width: 36px;
          height: 36px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          flex-shrink: 0;
        }
        .timeline-icon.arm-away { background: var(--d-danger); }
        .timeline-icon.arm-home { background: var(--d-home); }
        .timeline-icon.arm-night { background: var(--d-night); }
        .timeline-icon.disarm { background: var(--d-success); }
        .timeline-icon.event { background: var(--d-primary); }

        .timeline-body { flex-grow: 1; min-width: 0; }
        .timeline-title { font-size: 13px; font-weight: 700; color: var(--d-text); }
        .timeline-meta { font-size: 12px; color: var(--d-subtext); margin-top: 2px; }

        /* ─── Tab 4: Health Dashboard ─────────────── */
        .kpi-row {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px;
          margin-bottom: 20px;
        }

        .kpi-card {
          background: var(--d-card-bg);
          border: 1px solid var(--d-border);
          border-radius: 16px;
          padding: 16px;
          text-align: center;
        }
        .kpi-val { font-size: 26px; font-weight: 800; letter-spacing: -0.5px; }
        .kpi-label { font-size: 12px; color: var(--d-subtext); font-weight: 600; margin-top: 4px; }

        .health-row {
          display: flex;
          align-items: center;
          padding: 12px 16px;
          background: var(--d-card-bg);
          border: 1px solid var(--d-border);
          border-radius: 12px;
          margin-bottom: 8px;
          gap: 14px;
        }

        .health-dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
          flex-shrink: 0;
        }
        .health-dot.online { background: var(--d-success); box-shadow: 0 0 8px rgba(16, 185, 129, 0.4); }
        .health-dot.offline { background: var(--d-danger); box-shadow: 0 0 8px rgba(239, 68, 68, 0.4); }

        .batt-container {
          width: 80px;
          height: 8px;
          background: rgba(148, 163, 184, 0.2);
          border-radius: 4px;
          overflow: hidden;
          margin-left: auto;
        }
        .batt-fill { height: 100%; border-radius: 4px; }
        .batt-fill.high { background: var(--d-success); }
        .batt-fill.med { background: var(--d-warning); }
        .batt-fill.low { background: var(--d-danger); }
        .batt-label { font-size: 12px; font-weight: 700; width: 44px; text-align: right; color: var(--d-text); }

        .empty-hint {
          text-align: center;
          padding: 40px 20px;
          color: var(--d-subtext);
          font-size: 13px;
        }
      </style>

      <div class="panel-wrap">
        <!-- Hero Header -->
        <div class="hero-banner">
          <div class="brand-section">
            <div class="brand-logo">
              <ha-icon icon="mdi:shield-lock-outline"></ha-icon>
            </div>
            <div>
              <div class="brand-title">DomoLink Alarm</div>
              <div id="brand-subtitle" class="brand-subtitle">Chargement de l'état...</div>
            </div>
          </div>
          <div id="alarm-state" class="state-pill state-disarmed">Chargement...</div>
        </div>

        <!-- Active Options Row -->
        <div id="status-row" class="status-chips-row"></div>

        <!-- Segmented Navigation -->
        <div class="nav-segmented">
          <div class="nav-tab active" data-tab="arm">
            <ha-icon icon="mdi:shield-check"></ha-icon> Armement
          </div>
          <div class="nav-tab" data-tab="equip">
            <ha-icon icon="mdi:devices"></ha-icon> Équipements <span id="badge-equip" class="tab-badge" style="display:none"></span>
          </div>
          <div class="nav-tab" data-tab="log">
            <ha-icon icon="mdi:history"></ha-icon> Journal
          </div>
          <div class="nav-tab" data-tab="health">
            <ha-icon icon="mdi:heart-pulse"></ha-icon> Santé
          </div>
        </div>

        <!-- Tab 1: Armement -->
        <div id="tab-arm" class="tab-pane active"></div>

        <!-- Tab 2: Équipements -->
        <div id="tab-equip" class="tab-pane"></div>

        <!-- Tab 3: Journal -->
        <div id="tab-log" class="tab-pane"></div>

        <!-- Tab 4: Santé -->
        <div id="tab-health" class="tab-pane"></div>
      </div>
    `;

    // Tab switching event
    this.querySelectorAll('.nav-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        this._activeTab = tab.getAttribute('data-tab');
        this.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        this.querySelectorAll('.tab-pane').forEach(c => c.classList.remove('active'));
        const pane = this.querySelector('#tab-' + this._activeTab);
        if (pane) pane.classList.add('active');
      });
    });

    // Bypass buttons event delegation
    const equipTab = this.querySelector('#tab-equip');
    if (equipTab) {
      equipTab.addEventListener('click', (e) => {
        const target = e.target.closest('.btn-bypass');
        if (!target) return;
        const entityId = target.getAttribute('data-entity');
        const action = target.getAttribute('data-action');
        if (!entityId || !action) return;
        if (action === 'bypass') {
          this._hass.callService('domolink_alarm', 'bypass_sensor', { entity_id: entityId });
        } else if (action === 'unbypass') {
          this._hass.callService('domolink_alarm', 'unbypass_sensor', { entity_id: entityId });
        }
      });
    }
  }

  // ─── Service Calls ──────────────────────────────

  callAlarmService(service) {
    const alarmEntity = Object.values(this._hass.states).find(s => s.entity_id.startsWith('alarm_control_panel.domolink'));
    if (!alarmEntity) return;
    const data = { entity_id: alarmEntity.entity_id };
    if (this._codeValue) data.code = this._codeValue;
    this._hass.callService('alarm_control_panel', service, data);
    this._codeValue = '';
    this._updatePinDisplay();
  }

  _updatePinDisplay() {
    const dots = this.querySelectorAll('.pin-dot');
    dots.forEach((dot, index) => {
      if (index < this._codeValue.length) dot.classList.add('filled');
      else dot.classList.remove('filled');
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

  // ─── Tab 1: Armement ────────────────────────────

  _renderArmTab(state, attrs) {
    const container = this.querySelector('#tab-arm');
    if (!container) return;

    const html = `
      <div class="glass-card">
        <div class="arm-grid">
          <!-- Keypad Column -->
          <div class="keypad-container">
            <div class="pin-display">
              <div class="pin-dot"></div>
              <div class="pin-dot"></div>
              <div class="pin-dot"></div>
              <div class="pin-dot"></div>
              <div class="pin-dot"></div>
              <div class="pin-dot"></div>
            </div>
            <div class="keypad-dial">
              ${[1, 2, 3, 4, 5, 6, 7, 8, 9].map(n => `<button class="dial-key" data-key="${n}">${n}</button>`).join('')}
              <button class="dial-key action-key" data-key="clear">C</button>
              <button class="dial-key" data-key="0">0</button>
              <button class="dial-key action-key" data-key="back">⌫</button>
            </div>
          </div>

          <!-- Actions Column -->
          <div class="mode-actions">
            <button class="btn-mode btn-disarm" data-service="alarm_disarm">
              <ha-icon icon="mdi:shield-off"></ha-icon>
              <div class="btn-mode-content">
                <span class="btn-mode-title">Désactiver l'alarme</span>
                <span class="btn-mode-desc">Désarmer l'ensemble des zones</span>
              </div>
            </button>

            <button class="btn-mode btn-away" data-service="alarm_arm_away">
              <ha-icon icon="mdi:shield-lock"></ha-icon>
              <div class="btn-mode-content">
                <span class="btn-mode-title">Mode Absence</span>
                <span class="btn-mode-desc">Armement total (Intérieur & Périmètre)</span>
              </div>
            </button>

            <button class="btn-mode btn-home" data-service="alarm_arm_home">
              <ha-icon icon="mdi:shield-home"></ha-icon>
              <div class="btn-mode-content">
                <span class="btn-mode-title">Mode Présence</span>
                <span class="btn-mode-desc">Périmètre uniquement (Portes & Fenêtres)</span>
              </div>
            </button>

            <button class="btn-mode btn-night" data-service="alarm_arm_night">
              <ha-icon icon="mdi:shield-moon"></ha-icon>
              <div class="btn-mode-content">
                <span class="btn-mode-title">Mode Nuit</span>
                <span class="btn-mode-desc">Capteurs nocturnes & Périmètre</span>
              </div>
            </button>

            <button class="btn-panic-sos" id="btn-panic">
              <ha-icon icon="mdi:alert-decagram"></ha-icon> SOS PANIQUE IMMÉDIAT
            </button>
          </div>
        </div>
      </div>
    `;

    if (this._lastArmHtml !== html) {
      container.innerHTML = html;
      this._lastArmHtml = html;

      // Keypad event listeners
      container.querySelectorAll('.dial-key').forEach(btn => {
        btn.addEventListener('click', () => {
          const k = btn.getAttribute('data-key');
          if (k === 'clear') this._codeValue = '';
          else if (k === 'back') this._codeValue = this._codeValue.slice(0, -1);
          else if (this._codeValue.length < 6) this._codeValue += k;
          this._updatePinDisplay();
        });
      });

      // Arm buttons
      container.querySelectorAll('.btn-mode[data-service]').forEach(btn => {
        btn.addEventListener('click', () => this.callAlarmService(btn.getAttribute('data-service')));
      });

      // Panic button
      const panicBtn = container.querySelector('#btn-panic');
      if (panicBtn) {
        panicBtn.addEventListener('click', () => {
          if (confirm("🚨 DÉCLENCHER UNE ALERTE SOS PANIQUE IMMÉDIATE ?")) {
            this._hass.callService('domolink_alarm', 'panic', { activate_sirens: true });
          }
        });
      }
    }
  }

  // ─── Tab 2: Équipements ─────────────────────────

  _renderEquipTab(attrs) {
    const container = this.querySelector('#tab-equip');
    if (!container) return;
    const bypassedSensors = attrs.bypassed_sensors || [];

    const categories = [
      { key: "opening_sensors", icon: "mdi:door-open", name: "Capteurs d'ouverture" },
      { key: "motion_sensors", icon: "mdi:motion-sensor", name: "Capteurs de mouvement" },
      { key: "tamper_sensors", icon: "mdi:shield-alert", name: "Capteurs de sabotage (24/7)" },
      { key: "safety_sensors", icon: "mdi:fire-alert", name: "Capteurs Techniques 24/7" },
      { key: "night_sensors", icon: "mdi:weather-night", name: "Capteurs Mode Nuit" },
      { key: "sirens", icon: "mdi:bullhorn", name: "Sirènes d'alerte" },
      { key: "lights", icon: "mdi:alarm-light", name: "Lumières d'urgence" },
      { key: "cameras", icon: "mdi:cctv", name: "Caméras" },
      { key: "presence_simulation_entities", icon: "mdi:home-clock", name: "Simulation de Présence" },
      { key: "media_players", icon: "mdi:speaker", name: "Haut-parleurs & TTS" },
      { key: "persons", icon: "mdi:account", name: "Personnes & Géoloc" }
    ];

    let html = '<div class="glass-card">';
    let count = 0;

    for (const cat of categories) {
      const entityIds = attrs[cat.key];
      if (!entityIds || entityIds.length === 0) continue;
      count++;

      html += `<div class="section-header"><ha-icon icon="${cat.icon}"></ha-icon> ${cat.name}</div><div class="equip-grid">`;
      for (const entityId of entityIds) {
        const entityState = this._hass.states[entityId];
        let friendlyName = entityId, stateStr = "Inconnu", activeClass = "", timeStr = "";
        let isUnavailable = false, isOpenOrFaulty = false;
        const isBypassed = bypassedSensors.includes(entityId);

        if (!entityState || entityState.state === 'unavailable' || entityState.state === 'unknown') {
          isUnavailable = true;
          friendlyName = entityState ? (entityState.attributes.friendly_name || entityId) : entityId;
          stateStr = entityState && entityState.state === 'unknown' ? "Inconnu" : "Hors ligne";
          activeClass = "active";
          if (entityState && entityState.last_changed) timeStr = this.formatDate(entityState.last_changed);
        } else {
          friendlyName = entityState.attributes.friendly_name || entityId;
          stateStr = this._hass.formatEntityState ? this._hass.formatEntityState(entityState) : entityState.state;
          activeClass = this.getActiveClass(entityState);
          timeStr = this.formatDate(entityState.last_changed);
          if (activeClass === "active") isOpenOrFaulty = true;
        }

        let actionButtonHtml = "";
        if (isBypassed) {
          actionButtonHtml = `<button class="btn-bypass restore" data-action="unbypass" data-entity="${entityId}"><ha-icon icon="mdi:undo" style="--mdc-icon-size:14px"></ha-icon> Rétablir</button>`;
        } else if (isUnavailable || isOpenOrFaulty) {
          actionButtonHtml = `<button class="btn-bypass ignore" data-action="bypass" data-entity="${entityId}"><ha-icon icon="mdi:eye-off" style="--mdc-icon-size:14px"></ha-icon> Ignorer</button>`;
        }

        let cardClasses = "equip-card";
        if (isBypassed) cardClasses += " bypassed";
        else if (isUnavailable) cardClasses += " unavailable";
        let iconWrapClass = isBypassed ? "bypassed" : activeClass;

        html += `
          <div class="${cardClasses}">
            <div class="equip-icon-wrap ${iconWrapClass}">
              <ha-icon icon="${isBypassed ? 'mdi:shield-off' : cat.icon}"></ha-icon>
            </div>
            <div class="equip-info">
              <div class="equip-name" title="${this.escapeHtml(friendlyName)}">${this.escapeHtml(friendlyName)}</div>
              <div class="equip-sub ${isBypassed ? '' : activeClass}">
                <span>${isBypassed ? 'Exclu de la surveillance' : this.escapeHtml(stateStr)}</span>
                ${timeStr ? `<span>• ${timeStr}</span>` : ''}
              </div>
            </div>
            ${actionButtonHtml}
          </div>
        `;
      }
      html += '</div>';
    }

    if (count === 0) {
      html += '<div class="empty-hint"><ha-icon icon="mdi:devices" style="--mdc-icon-size:40px;margin-bottom:8px"></ha-icon><br>Aucun équipement configuré.</div>';
    }
    html += '</div>';

    if (this._lastEquipHtml !== html) {
      container.innerHTML = html;
      this._lastEquipHtml = html;
    }
  }

  // ─── Tab 3: Journal & Timeline ──────────────────

  _renderLogTab() {
    const container = this.querySelector('#tab-log');
    if (!container) return;

    const logEntity = Object.values(this._hass.states).find(s =>
      s.entity_id.includes('domolink_event_log') ||
      (s.attributes && Array.isArray(s.attributes.events) && s.entity_id.startsWith('sensor.'))
    );
    const alarmEntity = Object.values(this._hass.states).find(s => s.entity_id.startsWith('alarm_control_panel.domolink'));

    const events = (logEntity && logEntity.attributes && Array.isArray(logEntity.attributes.events)) ? logEntity.attributes.events : [];
    const armHistory = (alarmEntity && alarmEntity.attributes && Array.isArray(alarmEntity.attributes.arm_history)) ? alarmEntity.attributes.arm_history : [];

    let html = '<div class="journal-layout">';

    // Column 1: Arm/Disarm Timeline with User Attribution
    html += `
      <div class="glass-card">
        <div class="section-header" style="margin-top:0"><ha-icon icon="mdi:shield-account"></ha-icon> Activations & Utilisateurs</div>
        <div class="timeline-list">
    `;

    if (armHistory.length > 0) {
      html += armHistory.map(ev => {
        const isArm = ev.action === "arm";
        let icon = "mdi:shield-off", iconClass = "disarm", actionTitle = "Désarmement";
        if (isArm) {
          if (ev.mode === "AWAY") { icon = "mdi:shield-lock"; iconClass = "arm-away"; actionTitle = "Armement Absent"; }
          else if (ev.mode === "HOME") { icon = "mdi:shield-home"; iconClass = "arm-home"; actionTitle = "Armement Présent"; }
          else { icon = "mdi:shield-moon"; iconClass = "arm-night"; actionTitle = "Armement Nuit"; }
        }

        return `
          <div class="timeline-item">
            <div class="timeline-icon ${iconClass}">
              <ha-icon icon="${icon}" style="--mdc-icon-size:20px;"></ha-icon>
            </div>
            <div class="timeline-body">
              <div class="timeline-title">${actionTitle} par <strong style="color:var(--d-primary)">${this.escapeHtml(ev.user || "Inconnu")}</strong></div>
              <div class="timeline-meta">${this.formatDate(ev.time)}</div>
            </div>
          </div>
        `;
      }).join('');
    } else {
      html += '<div class="empty-hint"><ha-icon icon="mdi:shield-outline" style="--mdc-icon-size:36px;margin-bottom:8px"></ha-icon><br>Aucun historique d\'activation enregistré.</div>';
    }
    html += '</div></div>';

    // Column 2: System Event Logs
    html += `
      <div class="glass-card">
        <div class="section-header" style="margin-top:0"><ha-icon icon="mdi:format-list-bulleted"></ha-icon> Événements du système</div>
        <div class="timeline-list">
    `;

    if (events.length > 0) {
      html += events.slice(0, 30).map(ev => `
        <div class="timeline-item">
          <div class="timeline-icon event">
            <ha-icon icon="mdi:bell-outline" style="--mdc-icon-size:18px;"></ha-icon>
          </div>
          <div class="timeline-body">
            <div class="timeline-title">${this.escapeHtml(ev.message)}</div>
            <div class="timeline-meta">${this.formatDate(ev.time)}</div>
          </div>
        </div>
      `).join('');
    } else {
      html += '<div class="empty-hint"><ha-icon icon="mdi:calendar-blank" style="--mdc-icon-size:36px;margin-bottom:8px"></ha-icon><br>Aucun événement récent.</div>';
    }
    html += '</div></div>';

    html += '</div>';

    if (this._lastLogHtml !== html) {
      container.innerHTML = html;
      this._lastLogHtml = html;
    }
  }

  // ─── Tab 4: Santé ───────────────────────────────

  _renderHealthTab() {
    const container = this.querySelector('#tab-health');
    if (!container) return;

    const alarmEntity = Object.values(this._hass.states).find(s => s.entity_id.startsWith('alarm_control_panel.domolink'));
    if (!alarmEntity) return;

    const healthData = alarmEntity.attributes.sensor_health || {};
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
      let scoreColor = score >= 95 ? "var(--d-success)" : (score >= 80 ? "var(--d-warning)" : "var(--d-danger)");

      html += `
        <div class="kpi-row">
          <div class="kpi-card">
            <div class="kpi-val" style="color:${scoreColor}">${score}%</div>
            <div class="kpi-label">Disponibilité globale</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-val" style="color:var(--d-text)">${keys.length}</div>
            <div class="kpi-label">Équipements liés</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-val" style="color:${lowBattCount > 0 ? 'var(--d-danger)' : 'var(--d-success)'}">${lowBattCount}</div>
            <div class="kpi-label">Piles faibles (&le;15%)</div>
          </div>
        </div>
        <div class="section-header"><ha-icon icon="mdi:check-network-outline"></ha-icon> État de connectivité et batteries</div>
      `;

      for (const entityId of keys) {
        const item = healthData[entityId];
        const lastSeen = item.last_changed ? this.formatDate(item.last_changed) : "Inconnu";

        let battHtml = '<div class="batt-label" style="color:var(--d-subtext)">N/A</div>';
        if (item.battery !== null) {
          const b = item.battery;
          const bClass = b > 50 ? "high" : (b > 15 ? "med" : "low");
          battHtml = `
            <div class="batt-container" title="${b}%">
              <div class="batt-fill ${bClass}" style="width:${b}%"></div>
            </div>
            <div class="batt-label">${b}%</div>
          `;
        }

        html += `
          <div class="health-row">
            <div class="health-dot ${item.offline ? 'offline' : 'online'}"></div>
            <div style="flex-grow:1; min-width:0;">
              <div style="font-size:14px; font-weight:600; color:var(--d-text)">${this.escapeHtml(item.name)}</div>
              <div style="font-size:12px; color:var(--d-subtext); margin-top:2px;">
                ${item.offline ? '⚠️ Hors ligne' : 'En ligne'} • Vu ${lastSeen}
              </div>
            </div>
            ${battHtml}
          </div>
        `;
      }
    } else {
      html += '<div class="empty-hint"><ha-icon icon="mdi:stethoscope" style="--mdc-icon-size:40px;margin-bottom:8px"></ha-icon><br>Données de santé en cours de synchronisation.<br>La vérification périodique s\'exécute toutes les 4 heures.</div>';
    }

    html += '</div>';

    if (this._lastHealthHtml !== html) {
      container.innerHTML = html;
      this._lastHealthHtml = html;
    }
  }

  // ─── Main Render ────────────────────────────────

  render() {
    const alarmEntity = Object.values(this._hass.states).find(s => s.entity_id.startsWith('alarm_control_panel.domolink'));
    if (!alarmEntity) {
      const stateBadge = this.querySelector('#alarm-state');
      if (stateBadge) {
        stateBadge.textContent = "Alarme non trouvée";
        stateBadge.className = "state-pill";
      }
      return;
    }

    const state = alarmEntity.state;
    const attrs = alarmEntity.attributes;
    const badge = this.querySelector('#alarm-state');
    const subtitle = this.querySelector('#brand-subtitle');

    // State Badge & Subtitle
    const stateLabels = {
      disarmed: 'Désarmée', armed_home: 'Présence', armed_away: 'Absence',
      armed_night: 'Nuit', arming: 'Armement...', pending: 'En attente...', triggered: 'DÉCLENCHÉE'
    };

    if (badge) {
      badge.textContent = stateLabels[state] || state;
      if (state === 'disarmed') badge.className = 'state-pill state-disarmed';
      else if (state.startsWith('armed') || state === 'triggered') badge.className = 'state-pill state-armed';
      else badge.className = 'state-pill state-pending';
    }

    if (subtitle) {
      if (state === 'disarmed') {
        subtitle.textContent = attrs.last_user ? `Désarmée par ${attrs.last_user}` : "Système au repos • Périmètre libre";
      } else if (state === 'triggered') {
        subtitle.textContent = attrs.triggered_by ? `Alerte intrusion : ${attrs.triggered_by}` : "🚨 ALARME ACTIVÉE";
      } else {
        subtitle.textContent = attrs.last_user ? `Armée par ${attrs.last_user}` : "Surveillance active";
      }
    }

    // Active Feature Chips
    const statusRow = this.querySelector('#status-row');
    if (statusRow) {
      let chips = '';
      if (attrs.chime_active) chips += '<span class="status-pill active"><ha-icon icon="mdi:bell-ring"></ha-icon> Carillon</span>';
      if (attrs.cross_zoning_active) chips += '<span class="status-pill active"><ha-icon icon="mdi:shield-check"></ha-icon> Double Détection</span>';
      if (attrs.geofence_active) chips += '<span class="status-pill active"><ha-icon icon="mdi:map-marker-radius"></ha-icon> Géo Auto</span>';
      if (attrs.geofence_reminder_active) chips += '<span class="status-pill active"><ha-icon icon="mdi:bell-alert"></ha-icon> Rappel d\'armement</span>';
      if (attrs.presence_simulation_active) chips += '<span class="status-pill active"><ha-icon icon="mdi:home-clock"></ha-icon> Simulation Présence</span>';
      if (attrs.health_check_active) chips += '<span class="status-pill active"><ha-icon icon="mdi:heart-pulse"></ha-icon> Diagnostic OK</span>';
      if (attrs.last_user) chips += `<span class="status-pill user-badge"><ha-icon icon="mdi:account-check"></ha-icon> ${this.escapeHtml(attrs.last_user)}</span>`;
      statusRow.innerHTML = chips;
    }

    // Badge count on equipments tab
    const allEquip = ['opening_sensors','motion_sensors','tamper_sensors','safety_sensors','night_sensors',
                      'sirens','lights','cameras','presence_simulation_entities','media_players','persons'];
    const total = allEquip.reduce((n, k) => n + ((attrs[k] || []).length), 0);
    const badgeEquip = this.querySelector('#badge-equip');
    if (badgeEquip) {
      if (total > 0) { badgeEquip.textContent = total; badgeEquip.style.display = ''; }
      else { badgeEquip.style.display = 'none'; }
    }

    // Render active tab content
    if (this._activeTab === 'arm') this._renderArmTab(state, attrs);
    else if (this._activeTab === 'equip') this._renderEquipTab(attrs);
    else if (this._activeTab === 'log') this._renderLogTab();
    else if (this._activeTab === 'health') this._renderHealthTab();
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
