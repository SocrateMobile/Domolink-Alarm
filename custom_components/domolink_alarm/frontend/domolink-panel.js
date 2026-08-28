class DomolinkPanel extends HTMLElement {
  set panel(panel) {
    this._panel = panel;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this.content) {
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
          ha-card {
            max-width: 1000px;
            margin: 0 auto 16px auto;
          }
          .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
          }
          .title {
            font-size: 24px;
            font-weight: 400;
          }
          .state-badge {
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            color: white;
            text-transform: uppercase;
          }
          .state-disarmed { background-color: var(--success-color, #4caf50); }
          .state-armed { background-color: var(--error-color, #f44336); }
          .state-pending { background-color: var(--warning-color, #ff9800); }
          
          .controls {
            display: flex;
            gap: 8px;
            align-items: center;
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid var(--divider-color);
            flex-wrap: wrap;
          }
          .controls input {
            padding: 8px 12px;
            border: 1px solid var(--divider-color);
            border-radius: 4px;
            background: var(--card-background-color);
            color: var(--primary-text-color);
            outline: none;
          }
          .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            font-weight: 500;
            cursor: pointer;
            color: white;
            text-transform: uppercase;
          }
          .btn-disarm { background-color: var(--success-color, #4caf50); }
          .btn-arm { background-color: var(--error-color, #f44336); }
          .btn:active { opacity: 0.8; }
          
          .main-content {
            max-width: 1000px;
            margin: 0 auto;
          }
          .category-title {
            font-size: 18px;
            font-weight: 500;
            margin-top: 24px;
            margin-bottom: 12px;
            color: var(--primary-text-color);
          }
          .sensor-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 12px;
          }
          .sensor-item {
            display: flex;
            align-items: center;
            padding: 12px;
            border-radius: 8px;
            background: var(--card-background-color);
            box-shadow: 0px 2px 4px rgba(0,0,0,0.1);
            transition: all 0.2s ease-in-out;
            position: relative;
          }
          .sensor-item.bypassed {
            border: 1px dashed #ff9800;
            background: rgba(255, 152, 0, 0.05);
            opacity: 0.85;
          }
          .sensor-item.unavailable {
            border: 1px solid rgba(244, 67, 54, 0.4);
            background: rgba(244, 67, 54, 0.04);
          }
          .sensor-icon {
            margin-right: 14px;
            color: var(--state-icon-color, #44739e);
            --mdc-icon-size: 28px;
          }
          .sensor-icon.active {
            color: var(--error-color, #f44336);
          }
          .sensor-icon.active-success {
            color: var(--success-color, #4caf50);
          }
          .sensor-icon.bypassed {
            color: #ff9800;
          }
          .sensor-info {
            flex-grow: 1;
            overflow: hidden;
            margin-right: 8px;
          }
          .sensor-name-row {
            display: flex;
            align-items: center;
            gap: 6px;
          }
          .sensor-name {
            font-size: 14px;
            font-weight: 500;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            color: var(--primary-text-color);
          }
          .badge-bypassed {
            background-color: #ff9800;
            color: white;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.5px;
          }
          .sensor-state {
            font-size: 12px;
            color: var(--secondary-text-color);
            text-transform: capitalize;
            display: flex;
            justify-content: space-between;
            margin-top: 4px;
          }
          .sensor-state.active .state-text {
            color: var(--error-color, #f44336);
            font-weight: bold;
          }
          .sensor-state.active-success .state-text {
            color: var(--success-color, #4caf50);
            font-weight: bold;
          }
          .sensor-time {
            font-size: 11px;
            color: var(--secondary-text-color);
            opacity: 0.8;
          }
          .btn-action-bypass {
            padding: 5px 10px;
            border-radius: 4px;
            border: none;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
            display: flex;
            align-items: center;
            gap: 4px;
            transition: background-color 0.2s;
          }
          .btn-ignore {
            background-color: #ff9800;
            color: white;
          }
          .btn-ignore:hover {
            background-color: #f57c00;
          }
          .btn-restore {
            background-color: var(--secondary-background-color, #546e7a);
            color: white;
          }
          .btn-restore:hover {
            background-color: #455a64;
          }
          
          /* Event Log Section */
          .history-title {
            font-size: 18px;
            font-weight: 500;
            display: flex;
            align-items: center;
            margin-bottom: 16px;
            color: var(--primary-text-color);
          }
          .history-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
            max-height: 320px;
            overflow-y: auto;
          }
          .history-item {
            display: flex;
            align-items: baseline;
            padding: 8px 12px;
            background: var(--card-background-color);
            border-left: 3px solid var(--primary-color, #03a9f4);
            border-radius: 4px;
            font-size: 13px;
          }
          .history-time {
            font-size: 11px;
            color: var(--secondary-text-color);
            min-width: 140px;
            flex-shrink: 0;
            font-weight: 600;
          }
          .history-msg {
            color: var(--primary-text-color);
            word-break: break-word;
          }
        </style>
        <ha-card>
          <div class="card-content">
            <div class="header">
              <div class="title">DomoLink Alarm</div>
              <div id="alarm-state" class="state-badge">Chargement...</div>
            </div>
            <div class="controls">
              <input type="password" id="alarm-code" placeholder="Code (si requis)">
              <button class="btn btn-disarm" id="btn-disarm">Désactiver</button>
              <button class="btn btn-arm" id="btn-arm-away">Absence</button>
              <button class="btn btn-arm" id="btn-arm-home">Présence</button>
              <button class="btn btn-arm" id="btn-arm-night">Nuit</button>
            </div>
          </div>
        </ha-card>
        <div class="main-content" id="categories"></div>
      `;
      this.content = this.querySelector('#categories');
      this.alarmStateBadge = this.querySelector('#alarm-state');
      
      // Event listeners for controls
      this.querySelector('#btn-disarm').addEventListener('click', () => this.callAlarmService('alarm_disarm'));
      this.querySelector('#btn-arm-away').addEventListener('click', () => this.callAlarmService('alarm_arm_away'));
      this.querySelector('#btn-arm-home').addEventListener('click', () => this.callAlarmService('alarm_arm_home'));
      this.querySelector('#btn-arm-night').addEventListener('click', () => this.callAlarmService('alarm_arm_night'));

      // Event delegation for Bypass / Restore buttons
      this.content.addEventListener('click', (e) => {
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
    
    this.render();
  }
  
  callAlarmService(service) {
    const alarmEntity = Object.values(this._hass.states).find(s => s.entity_id.startsWith('alarm_control_panel.domolink'));
    if (!alarmEntity) return;
    
    const codeInput = this.querySelector('#alarm-code');
    const data = { entity_id: alarmEntity.entity_id };
    if (codeInput.value) {
      data.code = codeInput.value;
    }
    
    this._hass.callService('alarm_control_panel', service, data);
    codeInput.value = ''; // Clear code after sending
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

  render() {
    // Find domolink alarm entity
    const alarmEntity = Object.values(this._hass.states).find(s => s.entity_id.startsWith('alarm_control_panel.domolink'));
    if (!alarmEntity) {
       this.alarmStateBadge.textContent = "Alarme non trouvée";
       this.alarmStateBadge.className = "state-badge";
       return;
    }
    
    // Update header
    const state = alarmEntity.state;
    this.alarmStateBadge.textContent = this._hass.localize ? this._hass.localize(`component.alarm_control_panel.entity_component._.state.${state}`) || state : state;
    if (state === "disarmed") {
      this.alarmStateBadge.className = "state-badge state-disarmed";
    } else if (state.startsWith("armed") || state === "triggered") {
      this.alarmStateBadge.className = "state-badge state-armed";
    } else {
      this.alarmStateBadge.className = "state-badge state-pending";
    }

    // Categories mapping
    const attrs = alarmEntity.attributes;
    const bypassedSensors = attrs.bypassed_sensors || [];
    
    const categories = [
      { key: "opening_sensors", icon: "mdi:door-open", name: "Capteurs d'ouverture" },
      { key: "motion_sensors", icon: "mdi:motion-sensor", name: "Capteurs de mouvement" },
      { key: "tamper_sensors", icon: "mdi:shield-alert", name: "Capteurs de sabotage (24/7)" },
      { key: "night_sensors", icon: "mdi:weather-night", name: "Capteurs Mode Nuit" },
      { key: "sirens", icon: "mdi:bullhorn", name: "Sirènes" },
      { key: "lights", icon: "mdi:alarm-light", name: "Lumières d'urgence" },
      { key: "cameras", icon: "mdi:cctv", name: "Caméras" },
      { key: "media_players", icon: "mdi:speaker", name: "Lecteurs multimédia (TTS)" },
      { key: "persons", icon: "mdi:account", name: "Personnes (Géoloc)" }
    ];
    
    let html = "";
    
    for (const cat of categories) {
       const entityIds = attrs[cat.key];
       if (!entityIds || entityIds.length === 0) continue;
       
       html += `<div class="category-title">${cat.name}</div>`;
       html += `<div class="sensor-grid">`;
       
       for (const entityId of entityIds) {
          const entityState = this._hass.states[entityId];
          let friendlyName = entityId;
          let stateStr = "Inconnu";
          let activeClass = "";
          let timeStr = "";
          let isUnavailable = false;
          let isOpenOrFaulty = false;
          
          const isBypassed = bypassedSensors.includes(entityId);
          
          if (!entityState || entityState.state === 'unavailable' || entityState.state === 'unknown') {
             isUnavailable = true;
             friendlyName = entityState ? (entityState.attributes.friendly_name || entityId) : entityId;
             stateStr = entityState && entityState.state === 'unknown' ? "Inconnu" : "Non joignable";
             activeClass = "active";
             if (entityState && entityState.last_changed) {
                timeStr = this.formatDate(entityState.last_changed);
             }
          } else {
             friendlyName = entityState.attributes.friendly_name || entityId;
             stateStr = this._hass.formatEntityState ? this._hass.formatEntityState(entityState) : entityState.state;
             activeClass = this.getActiveClass(entityState);
             timeStr = this.formatDate(entityState.last_changed);
             if (activeClass === "active") {
                isOpenOrFaulty = true;
             }
          }
          
          // Action button (Ignorer / Rétablir)
          let actionButtonHtml = "";
          if (isBypassed) {
             actionButtonHtml = `
               <button class="btn-action-bypass btn-restore" data-action="unbypass" data-entity="${entityId}">
                 <ha-icon icon="mdi:undo" style="--mdc-icon-size: 14px;"></ha-icon> Rétablir
               </button>
             `;
          } else if (isUnavailable || isOpenOrFaulty) {
             actionButtonHtml = `
               <button class="btn-action-bypass btn-ignore" data-action="bypass" data-entity="${entityId}">
                 <ha-icon icon="mdi:eye-off" style="--mdc-icon-size: 14px;"></ha-icon> Ignorer
               </button>
             `;
          }
          
          // Additional card classes
          let cardClasses = "sensor-item";
          if (isBypassed) {
             cardClasses += " bypassed";
          } else if (isUnavailable) {
             cardClasses += " unavailable";
          }
          
          let iconClass = activeClass;
          if (isBypassed) {
             iconClass = "bypassed";
          }
          
          html += `
            <div class="${cardClasses}">
              <ha-icon class="sensor-icon ${iconClass}" icon="${isBypassed ? 'mdi:shield-off' : cat.icon}"></ha-icon>
              <div class="sensor-info">
                <div class="sensor-name-row">
                  <span class="sensor-name" title="${friendlyName}">${friendlyName}</span>
                  ${isBypassed ? '<span class="badge-bypassed">Ignoré</span>' : ''}
                </div>
                <div class="sensor-state ${isBypassed ? '' : activeClass}">
                  <span class="state-text">${isBypassed ? 'Exclu de surveillance' : stateStr}</span>
                  <span class="sensor-time">${timeStr}</span>
                </div>
              </div>
              ${actionButtonHtml}
            </div>
          `;
       }
       
       html += `</div>`;
    }
    
    if (html === "") {
       html = "<ha-card><div class='card-content'>Aucun équipement configuré dans les entités. (Rechargez l'intégration si nécessaire).</div></ha-card>";
    }

    // Event Log Section
    const logEntity = Object.values(this._hass.states).find(s => 
      s.entity_id.includes('domolink_event_log') || 
      (s.attributes && Array.isArray(s.attributes.events) && s.entity_id.startsWith('sensor.'))
    );
    const events = (logEntity && logEntity.attributes && Array.isArray(logEntity.attributes.events)) ? logEntity.attributes.events : [];
    
    if (events.length > 0) {
      html += `
        <ha-card style="margin-top: 28px; margin-bottom: 24px;">
          <div class="card-content">
            <div class="history-title">
              <ha-icon icon="mdi:history" style="margin-right: 10px; color: var(--primary-color, #03a9f4); --mdc-icon-size: 24px;"></ha-icon>
              Journal des événements récents
            </div>
            <div class="history-list">
              ${events.map(ev => `
                <div class="history-item">
                  <div class="history-time">${this.formatDate(ev.time)}</div>
                  <div class="history-msg">${this.escapeHtml(ev.message)}</div>
                </div>
              `).join('')}
            </div>
          </div>
        </ha-card>
      `;
    }
    
    if (this._lastHtml !== html) {
       this.content.innerHTML = html;
       this._lastHtml = html;
    }
  }
  
  getActiveClass(entityState) {
     const domain = entityState.entity_id.split('.')[0];
     const state = entityState.state;
     if (domain === "binary_sensor") return state === "on" ? "active" : "";
     if (domain === "person") return state === "home" ? "active-success" : ""; // Home is green
     if (domain === "switch" || domain === "light") return state === "on" ? "active" : "";
     return "";
  }
}

customElements.define('domolink-panel', DomolinkPanel);
