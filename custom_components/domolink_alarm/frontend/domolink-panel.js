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
    this.render();
  }

  _buildShell() {
    this.innerHTML = `
      <style>
        :host {
          background-color: var(--primary-background-color);
          display: block;
          height: 100%;
          overflow: auto;
          padding: 16px;
          box-sizing: border-box;
        }
        .panel-wrap { max-width: 1000px; margin: 0 auto; }
        ha-card { margin-bottom: 16px; }

        /* ─── Header ──────────────────────────────── */
        .header {
          display: flex; align-items: center; justify-content: space-between;
          flex-wrap: wrap; gap: 16px;
        }
        .title { font-size: 24px; font-weight: 400; }
        .state-badge {
          padding: 8px 16px; border-radius: 20px; font-weight: bold;
          color: white; text-transform: uppercase; font-size: 13px;
        }
        .state-disarmed { background-color: var(--success-color, #4caf50); }
        .state-armed   { background-color: var(--error-color, #f44336); }
        .state-pending  { background-color: var(--warning-color, #ff9800); }

        /* ─── Status indicators ───────────────────── */
        .status-row {
          display: flex; gap: 10px; margin-top: 12px; flex-wrap: wrap;
        }
        .status-chip {
          display: inline-flex; align-items: center; gap: 4px;
          padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;
          background: var(--secondary-background-color, #f5f5f5);
          color: var(--secondary-text-color);
        }
        .status-chip.active { background: rgba(76,175,80,0.15); color: #2e7d32; }
        .status-chip ha-icon { --mdc-icon-size: 14px; }

        /* ─── Tabs ────────────────────────────────── */
        .tabs {
          display: flex; border-bottom: 2px solid var(--divider-color);
          margin: 0 -16px; padding: 0 16px;
        }
        .tab {
          padding: 12px 20px; cursor: pointer; font-weight: 500; font-size: 14px;
          color: var(--secondary-text-color); border-bottom: 3px solid transparent;
          transition: all 0.2s; display: flex; align-items: center; gap: 6px;
          user-select: none;
        }
        .tab:hover { color: var(--primary-text-color); }
        .tab.active {
          color: var(--primary-color, #03a9f4);
          border-bottom-color: var(--primary-color, #03a9f4);
        }
        .tab ha-icon { --mdc-icon-size: 20px; }
        .tab-content { display: none; padding-top: 16px; }
        .tab-content.active { display: block; }

        /* ─── Keypad (Arm tab) ────────────────────── */
        .keypad-wrap {
          display: flex; flex-direction: column; align-items: center; padding: 20px 0;
        }
        .code-display {
          font-size: 32px; letter-spacing: 8px; font-weight: 300;
          min-height: 48px; text-align: center;
          color: var(--primary-text-color); margin-bottom: 20px;
        }
        .keypad-grid {
          display: grid; grid-template-columns: repeat(3, 72px); gap: 12px;
        }
        .key {
          width: 72px; height: 72px; border-radius: 50%; border: 2px solid var(--divider-color);
          background: var(--card-background-color); color: var(--primary-text-color);
          font-size: 24px; font-weight: 400; cursor: pointer;
          display: flex; align-items: center; justify-content: center;
          transition: all 0.15s;
        }
        .key:active { background: var(--primary-color, #03a9f4); color: white; border-color: var(--primary-color); }
        .key.clear { font-size: 14px; font-weight: 600; color: var(--error-color, #f44336); border-color: var(--error-color, #f44336); }
        .key.clear:active { background: var(--error-color); color: white; }

        .arm-buttons {
          display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;
          margin-top: 24px; width: 100%; max-width: 320px;
        }
        .arm-btn {
          padding: 14px 8px; border: none; border-radius: 12px; font-weight: 600;
          cursor: pointer; color: white; text-transform: uppercase; font-size: 13px;
          display: flex; flex-direction: column; align-items: center; gap: 6px;
          transition: opacity 0.15s;
        }
        .arm-btn:active { opacity: 0.75; }
        .arm-btn ha-icon { --mdc-icon-size: 28px; }
        .arm-btn.disarm   { background: var(--success-color, #4caf50); grid-column: 1 / -1; }
        .arm-btn.away     { background: var(--error-color, #f44336); }
        .arm-btn.home     { background: #2196f3; }
        .arm-btn.night    { background: #673ab7; }
        .arm-btn.simulate { background: #ff9800; }

        /* ─── Sensor categories (Équipements tab) ── */
        .category-title {
          font-size: 18px; font-weight: 500; margin-top: 24px; margin-bottom: 12px;
          color: var(--primary-text-color);
        }
        .sensor-grid {
          display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px;
        }
        .sensor-item {
          display: flex; align-items: center; padding: 12px; border-radius: 8px;
          background: var(--card-background-color);
          box-shadow: 0px 2px 4px rgba(0,0,0,0.1);
          transition: all 0.2s; position: relative;
        }
        .sensor-item.bypassed { border: 1px dashed #ff9800; background: rgba(255,152,0,0.05); opacity: 0.85; }
        .sensor-item.unavailable { border: 1px solid rgba(244,67,54,0.4); background: rgba(244,67,54,0.04); }
        .sensor-icon { margin-right: 14px; color: var(--state-icon-color, #44739e); --mdc-icon-size: 28px; }
        .sensor-icon.active { color: var(--error-color, #f44336); }
        .sensor-icon.active-success { color: var(--success-color, #4caf50); }
        .sensor-icon.bypassed { color: #ff9800; }
        .sensor-info { flex-grow: 1; overflow: hidden; margin-right: 8px; }
        .sensor-name-row { display: flex; align-items: center; gap: 6px; }
        .sensor-name {
          font-size: 14px; font-weight: 500; white-space: nowrap;
          overflow: hidden; text-overflow: ellipsis; color: var(--primary-text-color);
        }
        .badge-bypassed {
          background-color: #ff9800; color: white; border-radius: 4px;
          padding: 2px 6px; font-size: 10px; font-weight: bold;
          text-transform: uppercase; letter-spacing: 0.5px;
        }
        .sensor-state {
          font-size: 12px; color: var(--secondary-text-color);
          text-transform: capitalize; display: flex; justify-content: space-between; margin-top: 4px;
        }
        .sensor-state.active .state-text { color: var(--error-color, #f44336); font-weight: bold; }
        .sensor-state.active-success .state-text { color: var(--success-color, #4caf50); font-weight: bold; }
        .sensor-time { font-size: 11px; color: var(--secondary-text-color); opacity: 0.8; }
        .btn-action-bypass {
          padding: 5px 10px; border-radius: 4px; border: none; font-size: 11px;
          font-weight: 600; cursor: pointer; white-space: nowrap;
          display: flex; align-items: center; gap: 4px; transition: background-color 0.2s;
        }
        .btn-ignore { background-color: #ff9800; color: white; }
        .btn-ignore:hover { background-color: #f57c00; }
        .btn-restore { background-color: var(--secondary-background-color, #546e7a); color: white; }
        .btn-restore:hover { background-color: #455a64; }

        /* ─── Event Log (Journal tab) ─────────────── */
        .history-title {
          font-size: 18px; font-weight: 500; display: flex; align-items: center;
          margin-bottom: 16px; color: var(--primary-text-color);
        }
        .history-list { display: flex; flex-direction: column; gap: 8px; }
        .history-item {
          display: flex; align-items: baseline; padding: 8px 12px;
          background: var(--card-background-color);
          border-left: 3px solid var(--primary-color, #03a9f4); border-radius: 4px; font-size: 13px;
        }
        .history-time {
          font-size: 11px; color: var(--secondary-text-color); min-width: 140px;
          flex-shrink: 0; font-weight: 600;
        }
        .history-msg { color: var(--primary-text-color); word-break: break-word; }
        .history-empty {
          text-align: center; padding: 40px 20px;
          color: var(--secondary-text-color); font-size: 14px;
        }

        /* ─── Counter badge on tabs ───────────────── */
        .tab-badge {
          background: var(--primary-color, #03a9f4); color: white;
          border-radius: 10px; padding: 1px 7px; font-size: 11px; font-weight: 700;
          margin-left: 2px;
        }
        /* ─── Health Tab ──────────────────────────── */
        .health-grid { display: flex; flex-direction: column; gap: 8px; }
        .health-item {
          display: flex; align-items: center; padding: 12px; border-radius: 8px;
          background: var(--card-background-color); border: 1px solid var(--divider-color);
        }
        .health-icon { margin-right: 16px; --mdc-icon-size: 24px; color: var(--secondary-text-color); }
        .health-info { flex-grow: 1; }
        .health-name { font-size: 14px; font-weight: 500; color: var(--primary-text-color); }
        .health-status { font-size: 12px; margin-top: 4px; display: flex; align-items: center; gap: 8px; }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; }
        .status-dot.online { background-color: var(--success-color, #4caf50); }
        .status-dot.offline { background-color: var(--error-color, #f44336); }
        
        .battery-bar-container { width: 80px; height: 6px; background: rgba(0,0,0,0.1); border-radius: 3px; overflow: hidden; margin-left: auto; }
        .battery-bar { height: 100%; border-radius: 3px; }
        .batt-high { background-color: var(--success-color, #4caf50); }
        .batt-med { background-color: #ff9800; }
        .batt-low { background-color: var(--error-color, #f44336); }
        .battery-text { font-size: 12px; font-weight: bold; width: 40px; text-align: right; margin-left: 8px; }
      </style>

      <div class="panel-wrap">
        <ha-card>
          <div class="card-content">
            <div class="header">
              <div class="title">DomoLink Alarm</div>
              <div id="alarm-state" class="state-badge">Chargement...</div>
            </div>
            <div id="status-row" class="status-row"></div>
          </div>
        </ha-card>

        <ha-card>
          <div class="card-content" style="padding-bottom:0">
            <div class="tabs">
              <div class="tab active" data-tab="arm">
                <ha-icon icon="mdi:shield-lock"></ha-icon> Armement
              </div>
              <div class="tab" data-tab="equip">
                <ha-icon icon="mdi:devices"></ha-icon> Équipements <span id="badge-equip" class="tab-badge" style="display:none"></span>
              </div>
              <div class="tab" data-tab="log">
                <ha-icon icon="mdi:history"></ha-icon> Journal
              </div>
              <div class="tab" data-tab="health">
                <ha-icon icon="mdi:medical-bag"></ha-icon> Santé
              </div>
            </div>
          </div>
          <div class="card-content">
            <div id="tab-arm" class="tab-content active"></div>
            <div id="tab-equip" class="tab-content"></div>
            <div id="tab-log" class="tab-content"></div>
            <div id="tab-health" class="tab-content"></div>
          </div>
        </ha-card>
      </div>
    `;

    // Tab switching
    this.querySelectorAll('.tab').forEach(tab => {
      tab.addEventListener('click', () => {
        this._activeTab = tab.getAttribute('data-tab');
        this.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        this.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        this.querySelector('#tab-' + this._activeTab).classList.add('active');
      });
    });

    // Event delegation for bypass / restore buttons
    this.querySelector('#tab-equip').addEventListener('click', (e) => {
      const target = e.target.closest('.btn-action-bypass');
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

  // ─── Service calls ──────────────────────────────

  callAlarmService(service) {
    const alarmEntity = Object.values(this._hass.states).find(s => s.entity_id.startsWith('alarm_control_panel.domolink'));
    if (!alarmEntity) return;
    const data = { entity_id: alarmEntity.entity_id };
    if (this._codeValue) data.code = this._codeValue;
    this._hass.callService('alarm_control_panel', service, data);
    this._codeValue = '';
  }

  formatDate(dateStr) {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    return date.toLocaleString('fr-FR', {
      day: '2-digit', month: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
  }

  escapeHtml(text) {
    if (!text) return "";
    return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // ─── Tab 3: Journal ─────────────────────────────

  _renderLogTab() {
    const container = this.querySelector('#tab-log');
    const logEntity = Object.values(this._hass.states).find(s =>
      s.entity_id.includes('domolink_event_log') ||
      (s.attributes && Array.isArray(s.attributes.events) && s.entity_id.startsWith('sensor.'))
    );
    const alarmEntity = Object.values(this._hass.states).find(s => s.entity_id.startsWith('alarm_control_panel.domolink'));
    
    const events = (logEntity && logEntity.attributes && Array.isArray(logEntity.attributes.events)) ? logEntity.attributes.events : [];
    const armHistory = (alarmEntity && alarmEntity.attributes && Array.isArray(alarmEntity.attributes.arm_history)) ? alarmEntity.attributes.arm_history : [];

    let html = '';
    
    // Split into 2 columns if screen is wide enough, else stack
    html += '<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px;">';

    // Arm History Block
    html += '<div><div class="history-title">'
      + '<ha-icon icon="mdi:shield-lock-outline" style="margin-right:10px;color:var(--primary-color,#03a9f4);--mdc-icon-size:24px"></ha-icon>'
      + 'Historique des activations'
      + '</div>';
    
    if (armHistory.length > 0) {
      html += '<div class="history-list">'
        + armHistory.map(ev => {
            const isArm = ev.action === "arm";
            const icon = isArm ? (ev.mode === "AWAY" ? "mdi:shield-lock" : ev.mode === "HOME" ? "mdi:shield-home" : "mdi:shield-moon") : "mdi:shield-off";
            const color = isArm ? (ev.mode === "AWAY" ? "var(--error-color, #f44336)" : ev.mode === "HOME" ? "#2196f3" : "#673ab7") : "var(--success-color, #4caf50)";
            return '<div class="history-item" style="border-left-color: ' + color + '">'
              + '<ha-icon icon="' + icon + '" style="color:' + color + '; margin-right: 12px; --mdc-icon-size:20px;"></ha-icon>'
              + '<div style="flex-grow:1">'
              + '<div style="font-weight:600; font-size:14px;">' + (isArm ? "Armement (" + ev.mode + ")" : "Désarmement") + '</div>'
              + '<div style="font-size:12px; color:var(--secondary-text-color)">' + this.escapeHtml(ev.user) + ' • ' + this.formatDate(ev.time) + '</div>'
              + '</div></div>';
        }).join('')
        + '</div>';
    } else {
      html += '<div class="history-empty"><ha-icon icon="mdi:shield-alert-outline" style="--mdc-icon-size:40px;margin-bottom:12px"></ha-icon><br>Aucun historique.</div>';
    }
    html += '</div>';

    // Event Log Block
    html += '<div><div class="history-title">'
      + '<ha-icon icon="mdi:format-list-bulleted" style="margin-right:10px;color:var(--primary-color,#03a9f4);--mdc-icon-size:24px"></ha-icon>'
      + 'Événements divers'
      + '</div>';
      
    if (events.length > 0) {
      html += '<div class="history-list">'
        + events.map(ev =>
            '<div class="history-item">'
            + '<div class="history-time">' + this.formatDate(ev.time) + '</div>'
            + '<div class="history-msg">' + this.escapeHtml(ev.message) + '</div>'
            + '</div>'
          ).join('')
        + '</div>';
    } else {
      html += '<div class="history-empty"><ha-icon icon="mdi:calendar-blank" style="--mdc-icon-size:40px;margin-bottom:12px"></ha-icon><br>Aucun événement récent.</div>';
    }
    html += '</div>';
    
    html += '</div>';

    if (this._lastLogHtml !== html) {
      container.innerHTML = html;
      this._lastLogHtml = html;
    }
  }

  // ─── Tab 4: Santé ───────────────────────────────

  _renderHealthTab() {
    const container = this.querySelector('#tab-health');
    const alarmEntity = Object.values(this._hass.states).find(s => s.entity_id.startsWith('alarm_control_panel.domolink'));
    if (!alarmEntity) return;

    const healthData = alarmEntity.attributes.sensor_health || {};
    const keys = Object.keys(healthData).sort();

    let html = '';
    
    if (keys.length > 0) {
      let onlineCount = 0;
      let lowBattCount = 0;
      
      let listHtml = '<div class="health-grid">';
      
      for (const entityId of keys) {
        const item = healthData[entityId];
        if (!item.offline) onlineCount++;
        if (item.battery !== null && item.battery <= 15) lowBattCount++;
        
        const stateColorClass = item.offline ? "offline" : "online";
        const stateText = item.offline ? "Hors ligne" : "En ligne";
        const lastSeen = item.last_changed ? this.formatDate(item.last_changed) : "Inconnu";
        
        let battHtml = '';
        if (item.battery !== null) {
            const b = item.battery;
            const bClass = b > 50 ? "batt-high" : (b > 15 ? "batt-med" : "batt-low");
            battHtml = '<div class="battery-bar-container" title="' + b + '%"><div class="battery-bar ' + bClass + '" style="width:' + b + '%"></div></div>'
                     + '<div class="battery-text">' + b + '%</div>';
        } else {
            battHtml = '<div class="battery-text" style="color:var(--secondary-text-color)">N/A</div>';
        }
        
        listHtml += '<div class="health-item">'
                  + '<ha-icon class="health-icon" icon="' + (item.offline ? 'mdi:wifi-off' : 'mdi:wifi-check') + '"></ha-icon>'
                  + '<div class="health-info">'
                  + '<div class="health-name">' + this.escapeHtml(item.name) + '</div>'
                  + '<div class="health-status"><div class="status-dot ' + stateColorClass + '"></div> ' + stateText + ' &nbsp;•&nbsp; ' + lastSeen + '</div>'
                  + '</div>'
                  + battHtml
                  + '</div>';
      }
      listHtml += '</div>';
      
      // Global stats
      const score = Math.round((onlineCount / keys.length) * 100);
      let scoreColor = score >= 95 ? "#4caf50" : (score >= 80 ? "#ff9800" : "#f44336");
      
      html += '<div style="display:flex; justify-content:space-around; background:var(--card-background-color); border-radius:8px; padding:16px; margin-bottom:20px; text-align:center; box-shadow:0px 2px 4px rgba(0,0,0,0.1);">'
            + '<div><div style="font-size:24px; font-weight:bold; color:' + scoreColor + '">' + score + '%</div><div style="font-size:12px; color:var(--secondary-text-color)">Disponibilité</div></div>'
            + '<div><div style="font-size:24px; font-weight:bold; color:var(--primary-text-color)">' + keys.length + '</div><div style="font-size:12px; color:var(--secondary-text-color)">Total Équip.</div></div>'
            + '<div><div style="font-size:24px; font-weight:bold; color:' + (lowBattCount > 0 ? '#f44336' : 'var(--success-color,#4caf50)') + '">' + lowBattCount + '</div><div style="font-size:12px; color:var(--secondary-text-color)">Piles Faibles</div></div>'
            + '</div>';
            
      html += listHtml;
      
    } else {
      html = '<div class="history-empty"><ha-icon icon="mdi:stethoscope" style="--mdc-icon-size:40px;margin-bottom:12px"></ha-icon><br>Données de santé non disponibles.<br>La vérification tourne toutes les 4h.</div>';
    }

    if (this._lastHealthHtml !== html) {
      container.innerHTML = html;
      this._lastHealthHtml = html;
    }
  }

  // ─── Main render (suite) ────────────────────────

  render() {
    const alarmEntity = Object.values(this._hass.states).find(s => s.entity_id.startsWith('alarm_control_panel.domolink'));
    if (!alarmEntity) {
      this.querySelector('#alarm-state').textContent = "Alarme non trouvée";
      this.querySelector('#alarm-state').className = "state-badge";
      return;
    }

    const state = alarmEntity.state;
    const attrs = alarmEntity.attributes;
    const badge = this.querySelector('#alarm-state');

    // State badge text
    const stateLabels = {
      disarmed: 'Désarmée', armed_home: 'Présence', armed_away: 'Absence',
      armed_night: 'Nuit', arming: 'Armement...', pending: 'En attente...', triggered: 'DÉCLENCHÉE'
    };
    badge.textContent = stateLabels[state] || state;
    if (state === 'disarmed') badge.className = 'state-badge state-disarmed';
    else if (state.startsWith('armed') || state === 'triggered') badge.className = 'state-badge state-armed';
    else badge.className = 'state-badge state-pending';

    // Status chips
    const statusRow = this.querySelector('#status-row');
    let chips = '';
    if (attrs.chime_active) chips += '<span class="status-chip active"><ha-icon icon="mdi:bell-ring"></ha-icon> Carillon</span>';
    if (attrs.cross_zoning_active) chips += '<span class="status-chip active"><ha-icon icon="mdi:shield-check"></ha-icon> Cross-Zone</span>';
    if (attrs.geofence_active) chips += '<span class="status-chip active"><ha-icon icon="mdi:map-marker-radius"></ha-icon> Géo Auto</span>';
    if (attrs.geofence_reminder_active) chips += '<span class="status-chip active"><ha-icon icon="mdi:bell-alert"></ha-icon> Rappel</span>';
    if (attrs.health_check_active) chips += '<span class="status-chip active"><ha-icon icon="mdi:heart-pulse"></ha-icon> Santé</span>';
    if (attrs.presence_simulation_active) chips += '<span class="status-chip active"><ha-icon icon="mdi:home-clock"></ha-icon> Simulation</span>';
    
    // Custom chips for scheduling & sirens
    const scheduleEnabled = false; // We can't access config directly from attributes for schedule state unless exported, but let's assume it's part of config
    
    if (attrs.last_user) chips += '<span class="status-chip"><ha-icon icon="mdi:account"></ha-icon> ' + this.escapeHtml(attrs.last_user) + '</span>';
    statusRow.innerHTML = chips;

    // Equipment count badge on tab
    const allEquip = ['opening_sensors','motion_sensors','tamper_sensors','safety_sensors','night_sensors',
                      'sirens','lights','cameras','presence_simulation_entities','media_players','persons'];
    const total = allEquip.reduce((n, k) => n + ((attrs[k] || []).length), 0);
    const badgeEquip = this.querySelector('#badge-equip');
    if (total > 0) { badgeEquip.textContent = total; badgeEquip.style.display = ''; }
    else { badgeEquip.style.display = 'none'; }

    // Render active tab only
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
