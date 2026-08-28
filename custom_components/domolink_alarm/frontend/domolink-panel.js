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
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 12px;
          }
          .sensor-item {
            display: flex;
            align-items: center;
            padding: 12px;
            border-radius: 8px;
            background: var(--card-background-color);
            box-shadow: 0px 2px 4px rgba(0,0,0,0.1);
          }
          .sensor-icon {
            margin-right: 16px;
            color: var(--state-icon-color, #44739e);
            --mdc-icon-size: 28px;
          }
          .sensor-icon.active {
            color: var(--error-color, #f44336);
          }
          .sensor-icon.active-success {
            color: var(--success-color, #4caf50);
          }
          .sensor-info {
            flex-grow: 1;
            overflow: hidden;
          }
          .sensor-name {
            font-size: 15px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            color: var(--primary-text-color);
          }
          .sensor-state {
            font-size: 13px;
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
          
          if (entityState) {
             friendlyName = entityState.attributes.friendly_name || entityId;
             stateStr = this._hass.formatEntityState ? this._hass.formatEntityState(entityState) : entityState.state;
             activeClass = this.getActiveClass(entityState);
             // Use last_changed for contact time
             timeStr = this.formatDate(entityState.last_changed);
          } else {
             stateStr = "Introuvable";
             activeClass = "active";
          }
          
          html += `
            <div class="sensor-item">
              <ha-icon class="sensor-icon ${activeClass}" icon="${cat.icon}"></ha-icon>
              <div class="sensor-info">
                <div class="sensor-name">${friendlyName}</div>
                <div class="sensor-state ${activeClass}">
                  <span class="state-text">${stateStr}</span>
                  <span class="sensor-time">${timeStr}</span>
                </div>
              </div>
            </div>
          `;
       }
       
       html += `</div>`;
    }
    
    if (html === "") {
       html = "<ha-card><div class='card-content'>Aucun équipement configuré dans les entités. (Rechargez l'intégration si nécessaire).</div></ha-card>";
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
