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
          --d-bg: var(--primary-background-color, #f8fafc);
          --d-card-bg: var(--card-background-color, #ffffff);
          --d-sec-bg: var(--secondary-background-color, rgba(148, 163, 184, 0.1));
          --d-border: var(--divider-color, rgba(148, 163, 184, 0.2));
          --d-text: var(--primary-text-color, #0f172a);
          --d-subtext: var(--secondary-text-color, #64748b);
          --d-primary: var(--primary-color, #0284c7);
          --d-success: #10b981;
          --d-danger: #ef4444;
          --d-warning: #f59e0b;
          --d-night: #8b5cf6;
          --d-home: #3b82f6;

          background-color: var(--d-bg);
          display: block;
          min-height: 100%;
          overflow-y: auto;
          padding: 20px 16px 48px;
          box-sizing: border-box;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          color: var(--d-text);
        }

        .panel-wrap {
          max-width: 1040px;
          margin: 0 auto;
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        /* ─── Adaptive Modern Glass Card ─────────── */
        .glass-card {
          background: var(--d-card-bg);
          border: 1px solid var(--d-border);
          border-radius: 20px;
          box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05), 0 2px 6px -1px rgba(0, 0, 0, 0.02);
          padding: 24px;
          position: relative;
          color: var(--d-text);
        }

        /* ─── Top Bar Navigation ─────────────────── */
        .top-bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 16px;
        }

        .brand-box {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .brand-icon {
          width: 42px;
          height: 42px;
          border-radius: 12px;
          background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
          display: flex;
          align-items: center;
          justify-content: center;
          color: #ffffff;
          box-shadow: 0 4px 14px rgba(245, 158, 11, 0.35);
        }
        .brand-icon ha-icon { --mdc-icon-size: 24px; }
        .brand-name { font-size: 20px; font-weight: 800; color: var(--d-text); letter-spacing: -0.3px; }

        .nav-capsule {
          display: inline-flex;
          background: var(--d-sec-bg);
          padding: 4px;
          border-radius: 9999px;
          border: 1px solid var(--d-border);
          gap: 4px;
          user-select: none;
        }

        .nav-item {
          padding: 8px 16px;
          border-radius: 9999px;
          font-size: 13px;
          font-weight: 600;
          color: var(--d-subtext);
          cursor: pointer;
          transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .nav-item:hover { color: var(--d-text); }
        .nav-item.active {
          background: var(--d-card-bg);
          color: var(--d-primary);
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
          font-weight: 700;
        }
        .nav-item ha-icon { --mdc-icon-size: 17px; }

        /* ─── Dashboard Grid ──────────────────────── */
        .dashboard-grid {
          display: grid;
          grid-template-columns: 1.15fr 0.85fr;
          gap: 20px;
          align-items: stretch;
        }
        @media (max-width: 860px) {
          .dashboard-grid { grid-template-columns: 1fr; }
        }

        /* ─── Status Hero Neon Banners ────────────── */
        .status-hero {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .neon-banner {
          display: flex;
          align-items: center;
          gap: 20px;
          padding: 24px 28px;
          border-radius: 20px;
          position: relative;
          transition: all 0.3s ease;
        }

        .neon-banner.secure {
          background: rgba(16, 185, 129, 0.08);
          border: 2px solid rgba(16, 185, 129, 0.5);
          box-shadow: 0 0 30px rgba(16, 185, 129, 0.15);
        }
        .neon-banner.alert {
          background: rgba(239, 68, 68, 0.1);
          border: 2px solid rgba(239, 68, 68, 0.6);
          box-shadow: 0 0 35px rgba(239, 68, 68, 0.25);
          animation: pulse-border 2s infinite;
        }
        .neon-banner.pending {
          background: rgba(245, 158, 11, 0.1);
          border: 2px solid rgba(245, 158, 11, 0.5);
          box-shadow: 0 0 30px rgba(245, 158, 11, 0.2);
        }

        @keyframes pulse-border {
          0% { box-shadow: 0 0 15px rgba(239, 68, 68, 0.25); }
          50% { box-shadow: 0 0 35px rgba(239, 68, 68, 0.45); }
          100% { box-shadow: 0 0 15px rgba(239, 68, 68, 0.25); }
        }

        .banner-icon-circle {
          width: 60px;
          height: 60px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }
        .neon-banner.secure .banner-icon-circle {
          background: rgba(16, 185, 129, 0.2);
          color: var(--d-success);
        }
        .neon-banner.alert .banner-icon-circle {
          background: rgba(239, 68, 68, 0.25);
          color: var(--d-danger);
        }
        .neon-banner.pending .banner-icon-circle {
          background: rgba(245, 158, 11, 0.25);
          color: var(--d-warning);
        }
        .banner-icon-circle ha-icon { --mdc-icon-size: 34px; }

        .banner-title { font-size: 24px; font-weight: 800; color: var(--d-text); letter-spacing: 0.5px; }
        .banner-sub { font-size: 13px; color: var(--d-subtext); margin-top: 4px; }

        /* ─── Room / Quick Status Chips ───────────── */
        .chips-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 10px;
        }
        @media (max-width: 600px) {
          .chips-grid { grid-template-columns: repeat(2, 1fr); }
        }

        .room-chip {
          padding: 10px 8px;
          border-radius: 12px;
          text-align: center;
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          border: 1px solid transparent;
        }
        .room-chip.ok {
          background: rgba(16, 185, 129, 0.1);
          border-color: rgba(16, 185, 129, 0.3);
          color: #059669;
        }
        .room-chip.armed {
          background: rgba(239, 68, 68, 0.1);
          border-color: rgba(239, 68, 68, 0.3);
          color: var(--d-danger);
        }
        .room-chip.info {
          background: var(--d-sec-bg);
          border-color: var(--d-border);
          color: var(--d-subtext);
        }

        /* ─── Fast Mode Selectors ─────────────────── */
        .mode-capsules {
          display: flex;
          background: var(--d-sec-bg);
          padding: 6px;
          border-radius: 16px;
          border: 1px solid var(--d-border);
          gap: 6px;
        }

        .mode-capsule-btn {
          flex: 1;
          padding: 12px 8px;
          border-radius: 12px;
          border: none;
          background: transparent;
          color: var(--d-subtext);
          font-size: 12px;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.2s ease;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
        }
        .mode-capsule-btn:hover { color: var(--d-text); background: rgba(148, 163, 184, 0.15); }
        .mode-capsule-btn.active {
          background: var(--d-card-bg);
          color: var(--d-primary);
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
        .mode-capsule-btn ha-icon { --mdc-icon-size: 20px; }

        /* ─── Keypad Box ──────────────────────────── */
        .keypad-box {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 24px 20px;
        }

        .keypad-header-title {
          font-size: 13px;
          font-weight: 800;
          letter-spacing: 1.5px;
          text-transform: uppercase;
          color: var(--d-text);
          margin-bottom: 4px;
        }

        .keypad-feedback {
          font-size: 12px;
          color: var(--d-subtext);
          margin-bottom: 16px;
          min-height: 18px;
        }

        .pin-indicators {
          display: flex;
          gap: 10px;
          margin-bottom: 20px;
        }
        .pin-light {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          background: var(--d-sec-bg);
          border: 1px solid var(--d-border);
          transition: all 0.15s ease;
        }
        .pin-light.active {
          background: #f59e0b;
          box-shadow: 0 0 10px rgba(245, 158, 11, 0.6);
          border-color: #f59e0b;
          transform: scale(1.2);
        }

        .keypad-matrix {
          display: grid;
          grid-template-columns: repeat(3, 68px);
          gap: 12px;
          margin-bottom: 20px;
        }

        .keypad-touch {
          width: 68px;
          height: 68px;
          border-radius: 50%;
          background: var(--d-sec-bg);
          border: 1px solid var(--d-border);
          color: var(--d-text);
          font-size: 22px;
          font-weight: 600;
          cursor: pointer;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
          position: relative;
        }
        .keypad-touch:hover {
          background: var(--d-card-bg);
          border-color: var(--d-primary);
        }
        .keypad-touch:active {
          transform: scale(0.92);
          background: #f59e0b;
          color: #ffffff;
          box-shadow: 0 0 16px rgba(245, 158, 11, 0.5);
        }
        .key-dot {
          width: 4px;
          height: 4px;
          border-radius: 50%;
          background: #f59e0b;
          margin-top: 2px;
        }

        .keypad-footer-modes {
          display: flex;
          gap: 8px;
          width: 100%;
        }
        .keypad-mode-pill {
          flex: 1;
          padding: 10px 6px;
          border-radius: 9999px;
          border: 1px solid var(--d-border);
          background: var(--d-sec-bg);
          color: var(--d-text);
          font-size: 11px;
          font-weight: 700;
          cursor: pointer;
          text-align: center;
          transition: all 0.2s ease;
        }
        .keypad-mode-pill:hover { border-color: var(--d-primary); }
        .keypad-mode-pill.primary {
          background: var(--d-primary);
          color: #ffffff;
          border-color: var(--d-primary);
          box-shadow: 0 2px 10px rgba(2, 132, 199, 0.3);
        }

        /* SOS Panic Trigger */
        .btn-sos-glow {
          margin-top: 14px;
          padding: 14px 20px;
          border-radius: 16px;
          background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(220, 38, 38, 0.3) 100%);
          border: 1px solid rgba(239, 68, 68, 0.4);
          color: var(--d-danger);
          font-weight: 800;
          font-size: 13px;
          letter-spacing: 1px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          transition: all 0.2s ease;
        }
        .btn-sos-glow:active { transform: scale(0.97); }

        /* ─── Tab Content Views ───────────────────── */
        .view-pane { display: none; }
        .view-pane.active { display: block; animation: fadeIn 0.25s ease; }

        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }

        /* ─── Simulation Tab Styles ───────────────── */
        .sim-header-card {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 20px;
          margin-bottom: 20px;
          background: linear-gradient(135deg, rgba(139, 92, 246, 0.08) 0%, rgba(2, 132, 199, 0.05) 100%);
          border: 1px solid rgba(139, 92, 246, 0.25);
        }

        .sim-toggle-btn {
          padding: 14px 24px;
          border-radius: 9999px;
          border: none;
          font-size: 13px;
          font-weight: 800;
          letter-spacing: 0.5px;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 8px;
          transition: all 0.2s ease;
        }
        .sim-toggle-btn.start {
          background: var(--d-success);
          color: #ffffff;
          box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35);
        }
        .sim-toggle-btn.stop {
          background: var(--d-danger);
          color: #ffffff;
          box-shadow: 0 4px 14px rgba(239, 68, 68, 0.35);
        }

        .sim-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
        }
        @media (max-width: 768px) {
          .sim-grid { grid-template-columns: 1fr; }
        }

        /* ─── Equipments Grid ─────────────────────── */
        .equip-matrix {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
          gap: 12px;
        }
        .equip-item-card {
          background: var(--d-sec-bg);
          border: 1px solid var(--d-border);
          border-radius: 14px;
          padding: 12px 16px;
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .equip-icon-disc {
          width: 40px;
          height: 40px;
          border-radius: 10px;
          background: var(--d-card-bg);
          border: 1px solid var(--d-border);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--d-subtext);
          flex-shrink: 0;
        }
        .equip-icon-disc.active { background: rgba(239, 68, 68, 0.15); color: var(--d-danger); border-color: rgba(239, 68, 68, 0.3); }
        .equip-icon-disc.success { background: rgba(16, 185, 129, 0.15); color: var(--d-success); border-color: rgba(16, 185, 129, 0.3); }
        .equip-icon-disc.bypassed { background: rgba(245, 158, 11, 0.15); color: var(--d-warning); border-color: rgba(245, 158, 11, 0.3); }

        .btn-action-pill {
          padding: 6px 12px;
          border-radius: 8px;
          border: none;
          font-size: 11px;
          font-weight: 700;
          cursor: pointer;
          margin-left: auto;
        }
        .btn-action-pill.bypass { background: rgba(245, 158, 11, 0.15); color: #b45309; }
        .btn-action-pill.restore { background: var(--d-card-bg); color: var(--d-subtext); border: 1px solid var(--d-border); }

        /* ─── Timeline Logs ───────────────────────── */
        .log-timeline {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        .log-entry {
          display: flex;
          align-items: center;
          gap: 14px;
          padding: 12px 16px;
          background: var(--d-sec-bg);
          border-radius: 12px;
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
        .log-dot.disarm { background: var(--d-success); }
        .log-dot.arm { background: var(--d-danger); }
        .log-dot.sim { background: var(--d-night); }
        .log-dot.event { background: var(--d-primary); }

        .empty-placeholder {
          text-align: center;
          padding: 30px 20px;
          color: var(--d-subtext);
          font-size: 13px;
        }
      </style>

      <div class="panel-wrap">
        <!-- Top Bar Navigation -->
        <div class="top-bar">
          <div class="brand-box">
            <div class="brand-icon">
              <ha-icon icon="mdi:shield-lock-outline"></ha-icon>
            </div>
            <div class="brand-name">DomoLink Alarm</div>
          </div>

          <div class="nav-capsule">
            <div class="nav-item active" data-tab="arm">
              <ha-icon icon="mdi:shield-check"></ha-icon> Armement
            </div>
            <div class="nav-item" data-tab="equip">
              <ha-icon icon="mdi:devices"></ha-icon> Équipements
            </div>
            <div class="nav-item" data-tab="sim">
              <ha-icon icon="mdi:home-clock"></ha-icon> Simulation
            </div>
            <div class="nav-item" data-tab="log">
              <ha-icon icon="mdi:history"></ha-icon> Journal
            </div>
            <div class="nav-item" data-tab="health">
              <ha-icon icon="mdi:heart-pulse"></ha-icon> Santé
            </div>
          </div>
        </div>

        <!-- View 1: Armement -->
        <div id="tab-arm" class="view-pane active"></div>

        <!-- View 2: Équipements -->
        <div id="tab-equip" class="view-pane"></div>

        <!-- View 3: Simulation de Présence -->
        <div id="tab-sim" class="view-pane"></div>

        <!-- View 4: Journal -->
        <div id="tab-log" class="view-pane"></div>

        <!-- View 5: Santé -->
        <div id="tab-health" class="view-pane"></div>
        <div id="tab-param" class="view-pane"></div>
      </div>
    `;

    // Tab Navigation Event
    this.querySelectorAll('.nav-item').forEach(tab => {
      tab.addEventListener('click', () => {
        this._activeTab = tab.getAttribute('data-tab');
        this.querySelectorAll('.nav-item').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        this.querySelectorAll('.view-pane').forEach(c => c.classList.remove('active'));
        const pane = this.querySelector('#tab-' + this._activeTab);
        if (pane) pane.classList.add('active');
      });
    });

    // Bypass buttons delegation
    const equipTab = this.querySelector('#tab-equip');
    if (equipTab) {
      equipTab.addEventListener('click', (e) => {
        const target = e.target.closest('.btn-action-pill');
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

    // Simulation toggle button delegation
    const simTab = this.querySelector('#tab-sim');
    if (simTab) {
      simTab.addEventListener('click', (e) => {
        const btn = e.target.closest('.sim-toggle-btn');
        if (!btn) return;
        this._hass.callService('domolink_alarm', 'toggle_presence_simulation', {});
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
    const dots = this.querySelectorAll('.pin-light');
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

  // ─── Tab 1: Armement ────────────────────────────

  _renderArmTab(state, attrs) {
    const container = this.querySelector('#tab-arm');
    if (!container) return;

    const isSecure = state === 'disarmed';
    const isAlert = state === 'triggered' || state.startsWith('armed');
    const isPending = state === 'pending' || state === 'arming';

    let bannerClass = 'secure';
    let bannerIcon = 'mdi:shield-check';
    let bannerTitle = 'SÉCURISÉ';
    let bannerSub = attrs.last_user ? `Désarmée par ${attrs.last_user}` : 'Système au repos • Périmètre libre';

    if (state.startsWith('armed')) {
      bannerClass = 'alert';
      bannerIcon = 'mdi:shield-lock';
      bannerTitle = state === 'armed_away' ? 'ARMÉ (ABSENCE)' : (state === 'armed_night' ? 'ARMÉ (NUIT)' : 'ARMÉ (PRÉSENCE)');
      bannerSub = attrs.last_user ? `Armée par ${attrs.last_user}` : 'Surveillance active';
    } else if (state === 'triggered') {
      bannerClass = 'alert';
      bannerIcon = 'mdi:bell-alert';
      bannerTitle = 'ALERTE INTRUSION';
      bannerSub = attrs.triggered_by ? `Déclenchée par ${attrs.triggered_by}` : 'Sirènes et alertes actives !';
    } else if (isPending) {
      bannerClass = 'pending';
      bannerIcon = 'mdi:timer-sand';
      bannerTitle = 'EN COURS...';
      bannerSub = 'Temporisation active';
    }

    const html = `
      <div class="dashboard-grid">
        <!-- Left Side: Status & Hero Banners -->
        <div class="status-hero">
          <div class="neon-banner ${bannerClass}">
            <div class="banner-icon-circle">
              <ha-icon icon="${bannerIcon}"></ha-icon>
            </div>
            <div>
              <div class="banner-title">${bannerTitle}</div>
              <div class="banner-sub">${this.escapeHtml(bannerSub)}</div>
            </div>
          </div>

          <!-- Quick Room Chips -->
          <div class="glass-card" style="padding: 16px;">
            <div class="chips-grid">
              <div class="room-chip ${attrs.chime_active ? 'ok' : 'info'}">Carillon</div>
              <div class="room-chip ${attrs.cross_zoning_active ? 'ok' : 'info'}">Double Détect.</div>
              <div class="room-chip ${attrs.geofence_active ? 'ok' : 'info'}">Géo Auto</div>
              <div class="room-chip ${attrs.presence_simulation_active ? 'ok' : 'info'}">Simulation</div>
            </div>
          </div>

          <!-- Mode Selectors Strip -->
          <div class="mode-capsules">
            <button class="mode-capsule-btn ${state === 'armed_away' ? 'active' : ''}" data-service="alarm_arm_away">
              <ha-icon icon="mdi:shield-lock"></ha-icon> Armement Total
            </button>
            <button class="mode-capsule-btn ${state === 'armed_home' ? 'active' : ''}" data-service="alarm_arm_home">
              <ha-icon icon="mdi:shield-home"></ha-icon> Partiel
            </button>
            <button class="mode-capsule-btn ${state === 'armed_night' ? 'active' : ''}" data-service="alarm_arm_night">
              <ha-icon icon="mdi:shield-moon"></ha-icon> Nuit
            </button>
            <button class="mode-capsule-btn ${state === 'disarmed' ? 'active' : ''}" data-service="alarm_disarm">
              <ha-icon icon="mdi:shield-off"></ha-icon> Désarmé
            </button>
          </div>

          <!-- SOS Panic Button -->
          <button class="btn-sos-glow" id="btn-panic">
            <ha-icon icon="mdi:alert-decagram"></ha-icon> SOS PANIQUE IMMÉDIAT
          </button>
        </div>

        <!-- Right Side: Keypad Box -->
        <div class="glass-card keypad-box">
          <div class="keypad-header-title">ENTRER LE PIN</div>
          <div class="keypad-feedback">Code de sécurité à 4 ou 6 chiffres</div>

          <div class="pin-indicators">
            <div class="pin-light"></div>
            <div class="pin-light"></div>
            <div class="pin-light"></div>
            <div class="pin-light"></div>
            <div class="pin-light"></div>
            <div class="pin-light"></div>
          </div>

          <div class="keypad-matrix">
            ${[1, 2, 3, 4, 5, 6, 7, 8, 9].map(n => `
              <button class="keypad-touch" data-key="${n}">
                ${n}
                <div class="key-dot"></div>
              </button>
            `).join('')}
            <button class="keypad-touch" data-key="clear" style="font-size:16px; font-weight:700;">#</button>
            <button class="keypad-touch" data-key="0">
              0
              <div class="key-dot"></div>
            </button>
            <button class="keypad-touch" data-key="back" style="font-size:18px;">*</button>
          </div>

          <div class="keypad-footer-modes">
            <button class="keypad-mode-pill primary" data-service="alarm_disarm">Désarmer</button>
            <button class="keypad-mode-pill" data-service="alarm_arm_away">Absent</button>
            <button class="keypad-mode-pill" data-service="alarm_arm_home">Présent</button>
          </div>
        </div>
      </div>
    `;

    if (this._lastArmHtml !== html) {
      container.innerHTML = html;
      this._lastArmHtml = html;

      // Keypad touches
      container.querySelectorAll('.keypad-touch').forEach(btn => {
        btn.addEventListener('click', () => {
          const k = btn.getAttribute('data-key');
          if (k === 'clear') this._codeValue = '';
          else if (k === 'back') this._codeValue = this._codeValue.slice(0, -1);
          else if (this._codeValue.length < 6) this._codeValue += k;
          this._updatePinDisplay();
        });
      });

      // Service buttons
      container.querySelectorAll('[data-service]').forEach(btn => {
        btn.addEventListener('click', () => this.callAlarmService(btn.getAttribute('data-service')));
      });

      // Panic button
      const panicBtn = container.querySelector('#btn-panic');
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
    const container = this.querySelector('#tab-equip');
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

      html += `<div><div style="font-size:15px; font-weight:800; color:var(--d-text); margin-bottom:12px; display:flex; align-items:center; gap:8px;"><ha-icon icon="${cat.icon}" style="color:var(--d-primary);"></ha-icon> ${cat.name}</div><div class="equip-matrix">`;
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
              <div style="font-size:12px; color:${isBypassed ? 'var(--d-warning)' : (activeClass === 'active' ? 'var(--d-danger)' : 'var(--d-subtext)')}; margin-top:2px; font-weight:600;">
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
    }
  }

  // ─── Tab 3: Simulation de Présence ──────────────

  _renderSimTab(attrs) {
    const container = this.querySelector('#tab-sim');
    if (!container) return;

    const isRunning = attrs.presence_simulation_active;
    const historyDays = attrs.presence_simulation_history_days || 7;
    const entities = attrs.presence_simulation_entities || [];
    const simEvents = attrs.presence_simulation_events || [];

    const html = `
      <!-- Simulation Status Banner -->
      <div class="glass-card sim-header-card">
        <div style="display:flex; align-items:center; gap:16px;">
          <div style="width:52px; height:52px; border-radius:14px; background:rgba(139, 92, 246, 0.15); color:var(--d-night); display:flex; align-items:center; justify-content:center;">
            <ha-icon icon="mdi:home-clock" style="--mdc-icon-size:30px;"></ha-icon>
          </div>
          <div>
            <div style="font-size:18px; font-weight:800; color:var(--d-text);">
              Simulation de Présence : ${isRunning ? '<span style="color:var(--d-success)">ACTIVE</span>' : '<span style="color:var(--d-subtext)">EN PAUSE</span>'}
            </div>
            <div style="font-size:13px; color:var(--d-subtext); margin-top:4px;">
              ${isRunning ? `Rejeu automatique de vos habitudes d'il y a ${historyDays} jours sur ${entities.length} appareils` : 'Prête à s\'activer lors de vos absences ou sur demande'}
            </div>
          </div>
        </div>

        <button class="sim-toggle-btn ${isRunning ? 'stop' : 'start'}">
          <ha-icon icon="${isRunning ? 'mdi:stop-circle-outline' : 'mdi:play-circle-outline'}"></ha-icon>
          ${isRunning ? 'ARRÊTER LA SIMULATION' : 'DÉMARRER MAINTENANT'}
        </button>
      </div>

      <!-- Simulation Layout (Entities & Logs) -->
      <div class="sim-grid">
        <!-- Entities included in simulation -->
        <div class="glass-card">
          <div style="font-size:15px; font-weight:800; color:var(--d-text); margin-bottom:16px; display:flex; align-items:center; gap:8px;">
            <ha-icon icon="mdi:lightbulb-multiple" style="color:var(--d-warning);"></ha-icon>
            Appareils supervisés (${entities.length})
          </div>

          <div style="display:flex; flex-direction:column; gap:10px;">
            ${entities.length > 0 ? entities.map(entityId => {
              const stateObj = this._hass.states[entityId];
              const name = stateObj ? (stateObj.attributes.friendly_name || entityId) : entityId;
              const isOn = stateObj && stateObj.state === 'on';
              return `
                <div style="display:flex; align-items:center; justify-content:space-between; padding:12px 14px; background:var(--d-sec-bg); border-radius:12px; border:1px solid var(--d-border);">
                  <div style="display:flex; align-items:center; gap:10px;">
                    <ha-icon icon="${isOn ? 'mdi:lightbulb-on' : 'mdi:lightbulb-outline'}" style="color:${isOn ? '#f59e0b' : 'var(--d-subtext)'};"></ha-icon>
                    <span style="font-size:13px; font-weight:700; color:var(--d-text);">${this.escapeHtml(name)}</span>
                  </div>
                  <span style="font-size:11px; font-weight:800; text-transform:uppercase; color:${isOn ? 'var(--d-success)' : 'var(--d-subtext)'};">
                    ${isOn ? 'Allumé' : 'Éteint'}
                  </span>
                </div>
              `;
            }).join('') : '<div class="empty-placeholder">Aucun appareil configuré pour la simulation.</div>'}
          </div>
        </div>

        <!-- Simulation Events Log -->
        <div class="glass-card">
          <div style="font-size:15px; font-weight:800; color:var(--d-text); margin-bottom:16px; display:flex; align-items:center; gap:8px;">
            <ha-icon icon="mdi:history" style="color:var(--d-night);"></ha-icon>
            Historique des actions déclenchées
          </div>

          <div class="log-timeline">
            ${simEvents.length > 0 ? simEvents.map(ev => `
              <div class="log-entry">
                <div class="log-dot sim">
                  <ha-icon icon="${ev.state === 'on' ? 'mdi:lightbulb' : 'mdi:lightbulb-off'}" style="--mdc-icon-size:18px;"></ha-icon>
                </div>
                <div style="flex-grow:1; min-width:0;">
                  <div style="font-size:13px; font-weight:700; color:var(--d-text);">
                    ${this.escapeHtml(ev.name)} <span style="color:${ev.state === 'on' ? 'var(--d-success)' : 'var(--d-subtext)'}; font-weight:800;">${ev.state === 'on' ? 'ALLUMÉ' : 'ÉTEINT'}</span>
                  </div>
                  <div style="font-size:11px; color:var(--d-subtext); margin-top:2px; font-weight:500;">
                    ${this.formatDate(ev.time)} • Rejeu J-${ev.history_days || 7}
                  </div>
                </div>
              </div>
            `).join('') : '<div class="empty-placeholder">Aucune action de simulation enregistrée récemment.</div>'}
          </div>
        </div>
      </div>
    `;

    if (this._lastSimHtml !== html) {
      container.innerHTML = html;
      this._lastSimHtml = html;
    }
  }

  // ─── Tab 4: Journal ─────────────────────────────

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

    const html = `
      <div class="sim-grid">
        <!-- Activations / Disarm History -->
        <div class="glass-card">
          <div style="font-size:15px; font-weight:800; color:var(--d-text); margin-bottom:16px; display:flex; align-items:center; gap:8px;">
            <ha-icon icon="mdi:shield-account" style="color:var(--d-success);"></ha-icon>
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
                    <div style="font-size:13px; font-weight:700; color:var(--d-text);">${title} par <strong style="color:var(--d-primary);">${this.escapeHtml(ev.user || "Inconnu")}</strong></div>
                    <div style="font-size:11px; color:var(--d-subtext); margin-top:2px; font-weight:500;">${this.formatDate(ev.time)}</div>
                  </div>
                </div>
              `;
            }).join('') : '<div class="empty-placeholder">Aucun historique d\'activation.</div>'}
          </div>
        </div>

        <!-- System Events -->
        <div class="glass-card">
          <div style="font-size:15px; font-weight:800; color:var(--d-text); margin-bottom:16px; display:flex; align-items:center; gap:8px;">
            <ha-icon icon="mdi:format-list-bulleted" style="color:var(--d-primary);"></ha-icon>
            Événements du système
          </div>

          <div class="log-timeline">
            ${events.length > 0 ? events.slice(0, 30).map(ev => `
              <div class="log-entry">
                <div class="log-dot event">
                  <ha-icon icon="mdi:bell-outline" style="--mdc-icon-size:18px;"></ha-icon>
                </div>
                <div style="flex-grow:1; min-width:0;">
                  <div style="font-size:13px; font-weight:600; color:var(--d-text);">${this.escapeHtml(ev.message)}</div>
                  <div style="font-size:11px; color:var(--d-subtext); margin-top:2px; font-weight:500;">${this.formatDate(ev.time)}</div>
                </div>
              </div>
            `).join('') : '<div class="empty-placeholder">Aucun événement récent.</div>'}
          </div>
        </div>
      </div>
    `;

    if (this._lastLogHtml !== html) {
      container.innerHTML = html;
      this._lastLogHtml = html;
    }
  }

  // ─── Tab 5: Santé ───────────────────────────────

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
            <div style="font-size:28px; font-weight:900; color:${lowBattCount > 0 ? 'var(--d-danger)' : 'var(--d-success)'};">${lowBattCount}</div>
            <div style="font-size:12px; color:var(--d-subtext); font-weight:700; margin-top:4px;">Piles Faibles (&le;15%)</div>
          </div>
        </div>

        <div style="font-size:15px; font-weight:800; color:var(--d-text); margin-bottom:14px; display:flex; align-items:center; gap:8px;">
          <ha-icon icon="mdi:check-network-outline" style="color:var(--d-primary);"></ha-icon> État individuel des équipements
        </div>
        <div style="display:flex; flex-direction:column; gap:10px;">
      `;

      for (const entityId of keys) {
        const item = healthData[entityId];
        const lastSeen = item.last_changed ? this.formatDate(item.last_changed) : "Inconnu";

        let battHtml = '<span style="font-size:12px; color:var(--d-subtext); font-weight:700;">N/A</span>';
        if (item.battery !== null) {
          const b = item.battery;
          const bColor = b > 50 ? 'var(--d-success)' : (b > 15 ? 'var(--d-warning)' : 'var(--d-danger)');
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
          <div style="display:flex; align-items:center; padding:12px 16px; background:var(--d-sec-bg); border:1px solid var(--d-border); border-radius:12px; gap:14px;">
            <div style="width:10px; height:10px; border-radius:50%; background:${item.offline ? 'var(--d-danger)' : 'var(--d-success)'};"></div>
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
      html += '<div class="empty-placeholder"><ha-icon icon="mdi:stethoscope" style="--mdc-icon-size:40px;margin-bottom:8px"></ha-icon><br>Synchronisation des données de santé...<br>Le diagnostic s\'exécute automatiquement toutes les 4 heures.</div>';
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
    if (!alarmEntity) return;

    const state = alarmEntity.state;
    const attrs = alarmEntity.attributes;

    if (this._activeTab === 'arm') this._renderArmTab(state, attrs);
    else if (this._activeTab === 'equip') this._renderEquipTab(attrs);
    else if (this._activeTab === 'sim') this._renderSimTab(attrs);
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

  _renderParamTab(entity) {
    const container = this.querySelector('#tab-param');
    if (!container) return;
    
    if (!entity || !entity.attributes) {
        container.innerHTML = '<div class="empty-state">Données indisponibles</div>';
        return;
    }

    const chime = entity.attributes.chime_active || false;
    const history_days = entity.attributes.presence_simulation_history_days || 7;

    container.innerHTML = `
      <div class="list-section">
        <div class="list-header">Paramètres Rapides</div>
        <div class="param-row">
            <div class="param-label">
                <div class="param-title">Mode Carillon (Chime)</div>
                <div class="param-desc">Bip court à l'ouverture d'une porte (alarme désarmée)</div>
            </div>
            <div class="param-input">
                <input type="checkbox" id="param-chime" ${chime ? 'checked' : ''} />
            </div>
        </div>
        
        <div class="param-row">
            <div class="param-label">
                <div class="param-title">Jours Historique Simulation</div>
                <div class="param-desc">Base de données pour rejeu de la simulation de présence</div>
            </div>
            <div class="param-input">
                <select id="param-history">
                    <option value="7" ${history_days==7?"selected":""}>7 jours</option>
                    <option value="14" ${history_days==14?"selected":""}>14 jours</option>
                    <option value="21" ${history_days==21?"selected":""}>21 jours</option>
                    <option value="28" ${history_days==28?"selected":""}>28 jours</option>
                    <option value="35" ${history_days==35?"selected":""}>35 jours</option>
                    <option value="42" ${history_days==42?"selected":""}>42 jours</option>
                </select>
            </div>
        </div>
        
        <div class="param-row" style="justify-content: center; padding-top: 24px; padding-bottom: 24px;">
            <button id="btn-save-params" class="btn-primary" style="padding: 12px 32px; border-radius: 20px;">
              Sauvegarder les Paramètres
            </button>
        </div>
      </div>
      
      <div class="list-section">
          <div class="list-header">Caméras (Captures)</div>
          <div style="padding: 16px; color: var(--d-subtext); font-size: 0.9em; line-height: 1.5;">
             Les caméras configurées dans l'intégration sont automatiquement utilisées pour capturer une photo (snapshot) et enregistrer un clip (30s) lors du déclenchement de l'alarme. <br/><br/>
             <strong>Dernière Capture:</strong> <code>/local/domolink_alarm_alert.jpg</code><br/><br/>
             <em>Note: Assurez-vous d'avoir sélectionné des entités de domaine "camera" dans la configuration (et non uniquement les détecteurs de mouvement des caméras).</em>
          </div>
      </div>
    `;

    // Bind event
    const btnSave = container.querySelector('#btn-save-params');
    if (btnSave) {
        btnSave.addEventListener('click', () => {
            const chimeVal = container.querySelector('#param-chime').checked;
            const historyVal = parseInt(container.querySelector('#param-history').value, 10);
            
            this._hass.callService('domolink_alarm', 'update_settings', {
                chime_mode: chimeVal,
                presence_simulation_history_days: historyVal
            }).then(() => {
                const btn = container.querySelector('#btn-save-params');
                const orig = btn.innerText;
                btn.innerText = "✓ Sauvegardé !";
                btn.style.backgroundColor = "var(--d-success)";
                setTimeout(() => {
                    btn.innerText = orig;
                    btn.style.backgroundColor = "";
                }, 2000);
            }).catch(e => {
                alert("Erreur lors de la sauvegarde: " + e.message);
            });
        });
    }
  }
}
