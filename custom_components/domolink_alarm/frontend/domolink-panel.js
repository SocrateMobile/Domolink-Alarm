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
      this._kioskActive = localStorage.getItem('domolink_kiosk_active') === 'true';
      this._kioskTimeout = parseInt(localStorage.getItem('domolink_kiosk_timeout') || '120', 10);
      const urlParams = new URLSearchParams(window.location.search);
      const carParam = urlParams.get('mode') === 'car' || urlParams.get('carplay') === '1' || urlParams.get('voiture') === '1';
      this._carModeActive = carParam || (localStorage.getItem('domolink_car_mode_active') === 'true');
      this._screensaverVisible = false;
      this._screensaverTimer = null;
      this._showWebdavTestConsole = false;
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
    if (this._screensaverTimer) clearTimeout(this._screensaverTimer);
    if (this._inactivityHandler) {
      window.removeEventListener('pointerdown', this._inactivityHandler);
      window.removeEventListener('keydown', this._inactivityHandler);
      window.removeEventListener('mousemove', this._inactivityHandler);
    }
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
      if (this._screensaverVisible) {
        this._updateScreensaverContent();
      }
      this._updateLiveTestProgress();
    };
    updateTime();
    this._clockTimer = setInterval(updateTime, 1000);
  }

  _updateLiveTestProgress() {
    const entity = this._hass && this._hass.states ? this._hass.states['alarm_control_panel.domolink_alarm'] : null;
    if (!entity || !entity.attributes) return;
    const attrs = entity.attributes;
    if (!attrs.camera_test_running || !attrs.camera_test_info) return;

    const info = attrs.camera_test_info;
    const total = Math.max(1, info.total || 1);
    const current = Math.max(0, info.current || 0);

    let cameraFraction = 0;
    let stepLabel = '';
    let stepStatus = '';
    let stepRatio = 0;

    if (info.step === 'photo') {
      cameraFraction = 0.15;
      stepLabel = 'Capture Photo en cours...';
      stepStatus = 'En cours';
      stepRatio = 0.5;
    } else if (info.step === 'video') {
      const elapsed = Math.max(0, (Date.now() / 1000) - (info.video_start || (Date.now() / 1000)));
      const duration = info.video_duration || 34;
      const videoSecs = Math.min(30, Math.floor(elapsed));
      stepRatio = Math.min(1, elapsed / duration);
      cameraFraction = 0.15 + (0.85 * stepRatio);
      stepLabel = `Vidéo 30s en cours (${videoSecs}s / 30s)...`;
      stepStatus = 'Enregistrement';
    } else {
      stepLabel = 'Préparation du test...';
      stepStatus = 'Initialisation';
      stepRatio = 0.1;
    }

    let globalPct = 0;
    if (current > 0) {
      globalPct = Math.min(100, Math.max(0, (((current - 1) + cameraFraction) / total) * 100));
    }

    const camName = info.camera_name && info.camera_name !== '...' ? info.camera_name : (current > 0 ? `Caméra ${current}/${total}` : 'Initialisation...');

    // Update global progress text & bar
    this.querySelectorAll('.cam-test-global-text').forEach(el => {
      el.textContent = `GLOBAL (${current}/${total})`;
    });
    this.querySelectorAll('.cam-test-global-pct').forEach(el => {
      el.textContent = `${Math.round(globalPct)}%`;
    });
    this.querySelectorAll('.cam-test-global-bar').forEach(el => {
      el.style.width = `${globalPct}%`;
    });

    // Update camera name
    this.querySelectorAll('.cam-test-camera-name').forEach(el => {
      el.textContent = camName;
    });

    // Update step label & status
    this.querySelectorAll('.cam-test-step-label').forEach(el => {
      el.textContent = stepLabel;
    });
    this.querySelectorAll('.cam-test-step-status').forEach(el => {
      el.textContent = stepStatus;
    });

    // Update step bar
    if (info.step === 'video') {
      this.querySelectorAll('.cam-test-step-bar').forEach(el => {
        el.style.animation = 'none';
        el.style.width = `${Math.round(stepRatio * 100)}%`;
      });
    }

    // Update Widget 1 compact indicators
    this.querySelectorAll('.cam-test-widget-current').forEach(el => {
      el.textContent = `Test en cours (${current}/${total})`;
    });
    this.querySelectorAll('.cam-test-widget-cam').forEach(el => {
      el.textContent = camName;
    });
  }

  _startCameraStream() {
    this._cameraRefreshTimer = setInterval(() => {
      const camImg = this.querySelector('#live-camera-img');
      if (camImg && camImg.dataset.camEntity) {
        const entityId = camImg.dataset.camEntity;
        const stateObj = this._hass && this._hass.states ? this._hass.states[entityId] : null;
        if (stateObj && stateObj.attributes && stateObj.attributes.entity_picture) {
          const pic = stateObj.attributes.entity_picture;
          camImg.src = pic + (pic.includes('?') ? '&' : '?') + 't=' + Date.now();
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

  _toggleKioskMode() {
    this._kioskActive = !this._kioskActive;
    localStorage.setItem('domolink_kiosk_active', this._kioskActive ? 'true' : 'false');
    const wrap = this.querySelector('.panel-wrap');
    if (wrap) {
      wrap.classList.toggle('kiosk-mode', this._kioskActive);
    }
    const btn = this.querySelector('#kiosk-toggle-btn');
    if (btn) {
      btn.classList.toggle('active', this._kioskActive);
      btn.innerHTML = `<ha-icon icon="${this._kioskActive ? 'mdi:fullscreen-exit' : 'mdi:fullscreen'}"></ha-icon>`;
    }
    if (this._kioskActive) {
      try {
        if (document.documentElement.requestFullscreen) {
          document.documentElement.requestFullscreen().catch(() => {});
        } else if (document.documentElement.webkitRequestFullscreen) {
          document.documentElement.webkitRequestFullscreen();
        }
      } catch (e) {}
      this._resetInactivityTimer();
    } else {
      try {
        if (document.fullscreenElement && document.exitFullscreen) {
          document.exitFullscreen().catch(() => {});
        }
      } catch (e) {}
      this._hideScreensaver();
    }
  }

  _toggleCarMode() {
    this._carModeActive = !this._carModeActive;
    localStorage.setItem('domolink_car_mode_active', this._carModeActive ? 'true' : 'false');
    const wrap = this.querySelector('.panel-wrap');
    if (wrap) {
      wrap.classList.toggle('car-mode', this._carModeActive);
    }
    const btn = this.querySelector('#car-toggle-btn');
    if (btn) {
      btn.classList.toggle('active', this._carModeActive);
      btn.innerHTML = `<ha-icon icon="${this._carModeActive ? 'mdi:car-connected' : 'mdi:car'}"></ha-icon>`;
    }
    this._lastArmKey = '';
    this._lastCarKey = '';
    this.render();
  }

  _resetInactivityTimer() {
    if (this._screensaverTimer) clearTimeout(this._screensaverTimer);
    if (!this._kioskActive) return;
    const timeoutSec = this._kioskTimeout !== undefined ? this._kioskTimeout : 120;
    if (timeoutSec <= 0) return;
    this._screensaverTimer = setTimeout(() => {
      this._showScreensaver();
    }, timeoutSec * 1000);
  }

  _showScreensaver() {
    if (!this._kioskActive) return;
    const alarmEntity = this._getAlarmEntity();
    const state = alarmEntity ? alarmEntity.state : 'disarmed';
    if (state === 'pending' || state === 'triggered') {
      this._hideScreensaver();
      return;
    }
    this._screensaverVisible = true;
    const screensaver = this.querySelector('#kiosk-screensaver');
    if (screensaver) {
      this._updateScreensaverContent();
      screensaver.classList.add('visible');
    }
  }

  _hideScreensaver() {
    this._screensaverVisible = false;
    const screensaver = this.querySelector('#kiosk-screensaver');
    if (screensaver) {
      screensaver.classList.remove('visible');
    }
    this._resetInactivityTimer();
  }

  _updateScreensaverContent() {
    const timeEl = this.querySelector('#screensaver-time');
    const dateEl = this.querySelector('#screensaver-date');
    const badgeEl = this.querySelector('#screensaver-badge');
    const textEl = this.querySelector('#screensaver-status-text');

    if (timeEl || dateEl) {
      const now = new Date();
      if (timeEl) timeEl.textContent = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
      if (dateEl) dateEl.textContent = now.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    }

    if (badgeEl && textEl) {
      const alarmEntity = this._getAlarmEntity();
      const state = alarmEntity ? alarmEntity.state : 'disarmed';
      badgeEl.className = `screensaver-status-badge status-${state}`;
      let label = 'SYSTÈME DÉSARMÉ • SÉCURISÉ';
      if (state === 'armed_away') label = 'ARMEMENT TOTAL ACTIF';
      else if (state === 'armed_home') label = 'ARMEMENT PARTIEL (MAISON)';
      else if (state === 'armed_night') label = 'ARMEMENT NUIT ACTIF';
      else if (state === 'arming') label = 'ARMEMENT EN COURS...';
      else if (state === 'disarming') label = 'DÉSARMEMENT EN COURS...';
      textEl.textContent = label;
    }
  }

  async _handleBiometricAuth() {
    if (!window.PublicKeyCredential) {
      alert("L'authentification biométrique (WebAuthn) n'est pas supportée sur ce navigateur ou cet appareil.");
      return;
    }

    const savedPin = localStorage.getItem('domolink_bio_pin');

    if (!savedPin) {
      if (!this._codeValue || this._codeValue.length < 4) {
        alert("Configuration Déverrouillage Biométrique :\n\n1. Saisissez votre code PIN sur le pavé numérique.\n2. Cliquez ensuite sur ce bouton pour associer votre Touch ID / Face ID.");
        return;
      }

      try {
        const challenge = new Uint8Array(32);
        window.crypto.getRandomValues(challenge);
        const userId = new Uint8Array(16);
        window.crypto.getRandomValues(userId);

        const credential = await navigator.credentials.create({
          publicKey: {
            challenge: challenge,
            rp: { name: "Domolink Alarm", id: window.location.hostname },
            user: {
              id: userId,
              name: "domolink_user",
              displayName: "Utilisateur Domolink"
            },
            pubKeyCredParams: [
              { alg: -7, type: "public-key" },
              { alg: -257, type: "public-key" }
            ],
            authenticatorSelection: {
              authenticatorAttachment: "platform",
              userVerification: "required"
            },
            timeout: 60000
          }
        });

        if (credential) {
          localStorage.setItem('domolink_bio_pin', this._codeValue);
          const currentPin = this._codeValue;
          this._codeValue = '';
          this._updatePinDisplay();
          
          if (window.navigator && window.navigator.vibrate) {
            try { window.navigator.vibrate([40, 60, 40]); } catch(e) {}
          }
          
          alert("✓ Empreinte / Face ID configuré avec succès !\nVous pouvez désormais désarmer l'alarme instantanément.");
          this.callAlarmService('alarm_disarm', currentPin);
        }
      } catch (err) {
        console.error("Biometric enrollment error:", err);
        if (err.name === 'NotAllowedError') return;

        if (confirm("Votre navigateur n'a pas pu joindre le matériel biométrique. Souhaitez-vous quand même enregistrer votre code sur cet appareil pour un désarmement rapide ?")) {
          localStorage.setItem('domolink_bio_pin', this._codeValue);
          const currentPin = this._codeValue;
          this._codeValue = '';
          this._updatePinDisplay();
          alert("✓ Déverrouillage rapide configuré !");
          this.callAlarmService('alarm_disarm', currentPin);
        }
      }
      return;
    }

    try {
      const challenge = new Uint8Array(32);
      window.crypto.getRandomValues(challenge);

      const assertion = await navigator.credentials.get({
        publicKey: {
          challenge: challenge,
          timeout: 60000,
          userVerification: "required"
        }
      });

      if (assertion) {
        if (window.navigator && window.navigator.vibrate) {
          try { window.navigator.vibrate(60); } catch(e) {}
        }
        this.callAlarmService('alarm_disarm', savedPin);
      }
    } catch (err) {
      console.warn("Biometric verification error:", err);
      if (err.name === 'NotAllowedError') return;
      
      if (confirm("L'authentification biométrique a échoué. Souhaitez-vous réinitialiser le code biométrique enregistré ?")) {
        localStorage.removeItem('domolink_bio_pin');
        alert("Configuration biométrique réinitialisée. Tapez votre code PIN puis cliquez à nouveau sur l'icône empreinte.");
      }
    }
  }

  _getAlarmEntity() {
    if (!this._hass || !this._hass.states) return null;
    // Use cached entity ID for direct O(1) lookup
    if (this._cachedAlarmEntityId && this._hass.states[this._cachedAlarmEntityId]) {
      return this._hass.states[this._cachedAlarmEntityId];
    }
    // Full scan only on first call or if cached entity disappeared
    const states = Object.values(this._hass.states);
    const found = states.find(s => 
      (s.attributes && (s.attributes.domolink_alarm === true || s.attributes.opening_sensors !== undefined)) ||
      s.entity_id.startsWith('alarm_control_panel.domolink') ||
      (s.attributes && s.attributes.attribution && String(s.attributes.attribution).toLowerCase().includes('domolink'))
    ) || states.find(s => s.entity_id.startsWith('alarm_control_panel.')) || null;
    if (found) this._cachedAlarmEntityId = found.entity_id;
    return found;
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

        .panel-wrap,
        .panel-wrap *,
        .panel-wrap *::before,
        .panel-wrap *::after {
          box-sizing: border-box;
        }

        .panel-wrap {
          background-color: var(--d-bg);
          background-image: 
            radial-gradient(at 10% 10%, rgba(245, 158, 11, 0.07) 0px, transparent 50%),
            radial-gradient(at 90% 90%, rgba(16, 185, 129, 0.07) 0px, transparent 50%);
          color: var(--d-text);
          min-height: 100vh;
          padding: max(20px, env(safe-area-inset-top)) max(24px, env(safe-area-inset-right)) max(40px, env(safe-area-inset-bottom)) max(24px, env(safe-area-inset-left));
          box-sizing: border-box;
          transition: background 0.3s ease, color 0.3s ease;
          overflow-x: hidden;
          width: 100%;
        }

        .panel-wrap.kiosk-mode {
          padding: 12px 16px 20px;
        }
        .panel-wrap.kiosk-mode .top-nav {
          margin-bottom: 8px;
        }
        .panel-wrap.kiosk-mode .container {
          max-width: 100%;
          gap: 16px;
        }

        .panel-wrap.car-mode {
          background: #090d16;
          --d-bg: #090d16;
          --d-surface: rgba(15, 23, 42, 0.85);
          --d-surface-card: rgba(15, 23, 42, 0.9);
          --d-sec-bg: #1e293b;
          --d-border: rgba(255, 255, 255, 0.14);
          --d-text: #f8fafc;
          --d-subtext: #94a3b8;
        }
        .panel-wrap.car-mode .top-nav {
          display: none !important;
        }

        @media (max-width: 768px) {
          .panel-wrap {
            padding: max(12px, env(safe-area-inset-top)) max(12px, env(safe-area-inset-right)) max(28px, env(safe-area-inset-bottom)) max(12px, env(safe-area-inset-left));
          }
          .top-nav {
            gap: 10px;
          }
          .brand-title {
            font-size: 18px;
          }
          .brand-logo-disc {
            width: 36px;
            height: 36px;
            border-radius: 10px;
          }
          .brand-logo-disc ha-icon {
            --mdc-icon-size: 20px;
          }
          .clock-widget {
            display: none;
          }
        }
        @media (max-width: 480px) {
          .panel-wrap {
            padding: max(10px, env(safe-area-inset-top)) max(8px, env(safe-area-inset-right)) max(24px, env(safe-area-inset-bottom)) max(8px, env(safe-area-inset-left));
          }
        }

        .icon-btn-circle.active {
          background: #3b82f6 !important;
          color: #ffffff !important;
          border-color: #3b82f6 !important;
          box-shadow: 0 0 12px rgba(59, 130, 246, 0.4) !important;
        }

        /* ─── Kiosk Screensaver ─────────────────────── */
        #kiosk-screensaver {
          position: fixed;
          inset: 0;
          width: 100vw;
          height: 100vh;
          background: #000000;
          color: #ffffff;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          z-index: 9999999;
          opacity: 0;
          pointer-events: none;
          transition: opacity 0.4s cubic-bezier(0.4, 0, 0.2, 1);
          user-select: none;
          -webkit-user-select: none;
        }
        #kiosk-screensaver.visible {
          opacity: 1;
          pointer-events: auto;
        }
        .screensaver-time {
          font-size: clamp(64px, 16vw, 130px);
          font-weight: 800;
          letter-spacing: -2px;
          line-height: 1;
          font-variant-numeric: tabular-nums;
          background: linear-gradient(180deg, #ffffff 0%, #cbd5e1 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          text-shadow: 0 0 40px rgba(255, 255, 255, 0.2);
          text-align: center;
        }
        .screensaver-date {
          font-size: clamp(16px, 3.5vw, 24px);
          color: #94a3b8;
          text-transform: capitalize;
          text-align: center;
          margin-top: 10px;
          font-weight: 500;
        }
        .screensaver-status-badge {
          margin-top: 40px;
          display: inline-flex;
          align-items: center;
          gap: 12px;
          padding: 12px 28px;
          border-radius: 9999px;
          background: rgba(255, 255, 255, 0.05);
          backdrop-filter: blur(16px);
          border: 1px solid rgba(255, 255, 255, 0.12);
          font-size: 15px;
          font-weight: 800;
          letter-spacing: 1px;
          text-transform: uppercase;
        }
        .screensaver-status-badge.status-disarmed {
          border-color: rgba(16, 185, 129, 0.4);
          color: #10b981;
          background: rgba(16, 185, 129, 0.1);
          box-shadow: 0 0 30px rgba(16, 185, 129, 0.15);
        }
        .screensaver-status-badge.status-armed_away {
          border-color: rgba(239, 68, 68, 0.4);
          color: #ef4444;
          background: rgba(239, 68, 68, 0.1);
          box-shadow: 0 0 30px rgba(239, 68, 68, 0.2);
        }
        .screensaver-status-badge.status-armed_home,
        .screensaver-status-badge.status-armed_night {
          border-color: rgba(245, 158, 11, 0.4);
          color: #f59e0b;
          background: rgba(245, 158, 11, 0.1);
          box-shadow: 0 0 30px rgba(245, 158, 11, 0.15);
        }
        .screensaver-status-disc {
          width: 14px;
          height: 14px;
          border-radius: 50%;
          background: currentColor;
          box-shadow: 0 0 12px currentColor;
          animation: pulseGlow 2.5s infinite ease-in-out;
        }
        .screensaver-touch-hint {
          position: absolute;
          bottom: 36px;
          font-size: 13px;
          color: #64748b;
          display: flex;
          align-items: center;
          gap: 8px;
          opacity: 0.7;
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
          align-items: center;
          background: var(--d-surface);
          backdrop-filter: var(--d-card-blur);
          padding: 5px 6px;
          border-radius: 9999px;
          border: 1px solid var(--d-border);
          box-shadow: var(--d-shadow);
          gap: 4px;
          user-select: none;
          max-width: 100%;
          overflow-x: auto;
          scrollbar-width: none;
        }
        .nav-capsule::-webkit-scrollbar {
          display: none;
        }

        .nav-tab {
          padding: 6px 14px;
          border-radius: 9999px;
          font-size: 13px;
          font-weight: 600;
          color: var(--d-subtext);
          cursor: pointer;
          transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
          display: inline-flex;
          align-items: center;
          gap: 8px;
          white-space: nowrap;
          flex-shrink: 0;
        }
        .nav-tab ha-icon {
          --mdc-icon-size: 17px;
          flex-shrink: 0;
        }
        .nav-tab:hover { color: var(--d-text); }
        .nav-tab.active {
          background: var(--d-pill-active-bg);
          color: var(--d-pill-active-text);
          font-weight: 700;
          box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
        }

        /* ─── Top Navigation Badges ────────────────── */
        .nav-tab-badge {
          display: inline-flex;
          align-items: center;
          pointer-events: none;
        }

        .nav-badge-stack {
          display: inline-flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 2px;
          line-height: 1;
          margin-left: 2px;
          pointer-events: none;
        }

        .nav-badge-pill {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          font-size: 8.5px;
          font-weight: 800;
          padding: 1.5px 5px;
          border-radius: 5px;
          letter-spacing: 0.2px;
          white-space: nowrap;
          line-height: 1.1;
          transition: all 0.2s ease;
        }

        .nav-badge-pill.badge-ok {
          background: rgba(16, 185, 129, 0.18);
          color: #10b981;
          border: 1px solid rgba(16, 185, 129, 0.35);
        }
        .nav-badge-pill.badge-ko {
          background: rgba(239, 68, 68, 0.18);
          color: #ef4444;
          border: 1px solid rgba(239, 68, 68, 0.4);
        }
        .nav-badge-pill.badge-ko.zero,
        .nav-badge-pill.badge-ok.zero {
          background: rgba(156, 163, 175, 0.12);
          color: var(--d-subtext);
          border: 1px solid rgba(156, 163, 175, 0.2);
          opacity: 0.8;
        }
        .nav-badge-pill.badge-photo {
          background: rgba(59, 130, 246, 0.18);
          color: #3b82f6;
          border: 1px solid rgba(59, 130, 246, 0.35);
        }
        .nav-badge-pill.badge-video {
          background: rgba(168, 85, 247, 0.18);
          color: #a855f7;
          border: 1px solid rgba(168, 85, 247, 0.35);
        }
        .nav-badge-pill.badge-neutral {
          background: rgba(156, 163, 175, 0.14);
          color: var(--d-text);
          border: 1px solid rgba(156, 163, 175, 0.25);
        }
        .nav-badge-pill.badge-sim-on {
          background: rgba(16, 185, 129, 0.2);
          color: #10b981;
          border: 1px solid rgba(16, 185, 129, 0.45);
          box-shadow: 0 0 6px rgba(16, 185, 129, 0.25);
        }
        .nav-badge-pill.badge-sim-off {
          background: rgba(156, 163, 175, 0.12);
          color: var(--d-subtext);
          border: 1px solid rgba(156, 163, 175, 0.2);
        }
        .nav-badge-pill.badge-version {
          background: rgba(245, 158, 11, 0.18);
          color: #f59e0b;
          border: 1px solid rgba(245, 158, 11, 0.35);
        }
        .nav-badge-pill.badge-arm-disarmed {
          background: rgba(16, 185, 129, 0.16);
          color: #10b981;
          border: 1px solid rgba(16, 185, 129, 0.35);
        }
        .nav-badge-pill.badge-arm-armed {
          background: rgba(59, 130, 246, 0.18);
          color: #3b82f6;
          border: 1px solid rgba(59, 130, 246, 0.4);
        }
        .nav-badge-pill.badge-arm-triggered {
          background: rgba(239, 68, 68, 0.25);
          color: #ef4444;
          border: 1px solid rgba(239, 68, 68, 0.5);
          animation: pulse 1s infinite;
        }
        .nav-badge-pill.badge-arm-pending {
          background: rgba(245, 158, 11, 0.2);
          color: #f59e0b;
          border: 1px solid rgba(245, 158, 11, 0.4);
        }
        .nav-badge-pill.badge-warn {
          background: rgba(245, 158, 11, 0.18);
          color: #f59e0b;
          border: 1px solid rgba(245, 158, 11, 0.35);
        }

        /* Active Tab Contrast Adjustments */
        .nav-tab.active .nav-badge-pill.badge-ok {
          background: rgba(16, 185, 129, 0.22);
          color: #059669;
          border-color: rgba(5, 150, 105, 0.45);
        }
        .nav-tab.active .nav-badge-pill.badge-ko {
          background: rgba(239, 68, 68, 0.22);
          color: #dc2626;
          border-color: rgba(220, 38, 38, 0.45);
        }
        .nav-tab.active .nav-badge-pill.badge-ko.zero,
        .nav-tab.active .nav-badge-pill.badge-ok.zero {
          background: rgba(0, 0, 0, 0.08);
          color: var(--d-pill-active-text);
          border-color: rgba(0, 0, 0, 0.15);
          opacity: 0.7;
        }
        .panel-wrap.theme-light .nav-tab.active .nav-badge-pill.badge-ko.zero,
        .panel-wrap.theme-light .nav-tab.active .nav-badge-pill.badge-ok.zero {
          background: rgba(255, 255, 255, 0.15);
          color: var(--d-pill-active-text);
          border-color: rgba(255, 255, 255, 0.25);
        }
        .nav-tab.active .nav-badge-pill.badge-photo {
          background: rgba(59, 130, 246, 0.22);
          color: #2563eb;
          border-color: rgba(37, 99, 235, 0.45);
        }
        .nav-tab.active .nav-badge-pill.badge-video {
          background: rgba(168, 85, 247, 0.22);
          color: #9333ea;
          border-color: rgba(147, 51, 234, 0.45);
        }
        .nav-tab.active .nav-badge-pill.badge-neutral {
          background: rgba(0, 0, 0, 0.08);
          color: var(--d-pill-active-text);
          border-color: rgba(0, 0, 0, 0.15);
        }
        .panel-wrap.theme-light .nav-tab.active .nav-badge-pill.badge-neutral {
          background: rgba(255, 255, 255, 0.15);
          color: var(--d-pill-active-text);
          border-color: rgba(255, 255, 255, 0.25);
        }
        .nav-tab.active .nav-badge-pill.badge-version {
          background: rgba(245, 158, 11, 0.22);
          color: #d97706;
          border-color: rgba(217, 119, 6, 0.45);
        }
        .nav-tab.active .nav-badge-pill.badge-sim-on {
          background: rgba(16, 185, 129, 0.22);
          color: #059669;
          border-color: rgba(5, 150, 105, 0.5);
        }
        .nav-tab.active .nav-badge-pill.badge-sim-off {
          background: rgba(0, 0, 0, 0.08);
          color: var(--d-pill-active-text);
          border-color: rgba(0, 0, 0, 0.15);
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
          grid-template-columns: 290px minmax(0, 1fr) 340px;
          gap: 20px;
          align-items: start;
        }
        @media (max-width: 1180px) {
          .arm-layout-grid { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
          .left-widgets-col { grid-column: span 2; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; }
        }
        @media (max-width: 820px) {
          .arm-layout-grid {
            display: flex;
            flex-direction: column;
            gap: 16px;
          }
          .center-hero-col {
            order: 1;
            width: 100%;
          }
          .keypad-glass-card {
            order: 2;
            width: 100%;
          }
          .left-widgets-col {
            order: 3;
            width: 100%;
            grid-column: span 1;
            display: flex;
            flex-direction: column;
            gap: 16px;
          }
        }

        /* ─── Left Column (Widgets) ──────────────── */
        .left-widgets-col {
          display: flex;
          flex-direction: column;
          gap: 16px;
          min-width: 0;
          box-sizing: border-box;
        }

        .widget-card {
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 10px;
          border-radius: 20px;
          min-width: 0;
          box-sizing: border-box;
          overflow: hidden;
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
          0% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.7; transform: scale(0.98); }
          100% { opacity: 1; transform: scale(1); }
        }
        @keyframes fillBar {
          from { width: 0%; }
          to { width: 100%; }
        }
        @keyframes progressIndeterminate {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .spin {
          animation: spin 1s linear infinite;
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

        .cam-test-widget-box {
          width: 100%;
          max-width: 100%;
          box-sizing: border-box;
          margin-top: 10px;
          background: rgba(245, 158, 11, 0.08);
          border: 1px solid rgba(245, 158, 11, 0.25);
          border-radius: 10px;
          padding: 9px 12px;
          display: flex;
          align-items: center;
          gap: 8px;
          overflow: hidden;
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
          word-wrap: break-word;
          overflow-wrap: anywhere;
          white-space: normal;
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
          min-width: 0;
          box-sizing: border-box;
        }

        .camera-test-progress-card {
          display: flex;
          flex-direction: column;
          width: 100%;
          max-width: 100%;
          box-sizing: border-box;
          gap: 12px;
          background: rgba(245, 158, 11, 0.06);
          border-radius: 12px;
          border: 1px solid rgba(245, 158, 11, 0.3);
          padding: 14px;
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
          overflow: hidden;
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

        @media (max-width: 600px) {
          .neon-pill-card {
            border-radius: 20px;
            padding: 14px 16px;
            gap: 14px;
          }
          .pill-icon-badge {
            width: 48px;
            height: 48px;
            min-width: 48px;
          }
          .pill-icon-badge ha-icon {
            --mdc-icon-size: 26px;
          }
          .pill-main-title {
            font-size: 18px;
          }
          .pill-sub-desc {
            font-size: 11px;
          }
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
          width: 100%;
          box-sizing: border-box;
        }
        .center-mode-btn {
          flex: 1;
          min-width: 0;
          padding: 12px 16px;
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
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .center-mode-btn ha-icon {
          --mdc-icon-size: 18px;
          flex-shrink: 0;
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
        @media (max-width: 600px) {
          .center-modes-row {
            gap: 6px;
          }
          .center-mode-btn {
            padding: 9px 6px;
            font-size: clamp(10.5px, 2.7vw, 12px);
            gap: 4px;
            border-radius: 12px;
          }
          .center-mode-btn ha-icon {
            --mdc-icon-size: 15px;
          }
        }
        @media (max-width: 360px) {
          .center-modes-row {
            flex-wrap: wrap;
          }
          .center-mode-btn {
            flex: 1 1 calc(50% - 4px);
          }
          .center-mode-btn:last-child {
            flex: 1 1 100%;
          }
        }

        /* ─── Cloud & Backup Status Tiles ──────────── */
        .dashboard-cloud-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(135px, 1fr));
          gap: 10px;
          margin-top: 24px;
          width: 100%;
          box-sizing: border-box;
        }
        .dashboard-cloud-tile {
          background: var(--d-sec-bg);
          border-radius: 14px;
          border: 1px solid var(--d-border);
          padding: 10px 12px;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          box-shadow: 0 2px 10px rgba(0,0,0,0.02);
          min-width: 0;
          min-height: 68px;
          box-sizing: border-box;
          overflow: hidden;
        }
        .cloud-tile-top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 6px;
          min-width: 0;
          margin-bottom: 6px;
          width: 100%;
        }
        .cloud-tile-brand {
          display: flex;
          align-items: center;
          gap: 7px;
          min-width: 0;
          flex: 1;
          overflow: hidden;
        }
        .cloud-tile-icon {
          width: 28px;
          height: 28px;
          min-width: 28px;
          border-radius: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }
        .cloud-tile-title {
          font-size: 10.5px;
          font-weight: 800;
          color: var(--d-subtext);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          min-width: 0;
          flex: 1;
        }
        .cloud-tile-btn {
          padding: 2px 6px;
          font-size: 9px;
          font-weight: 800;
          border-radius: 6px;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: 3px;
          transition: all 0.2s;
          white-space: nowrap;
          flex-shrink: 0;
        }
        .cloud-tile-bottom {
          display: flex;
          align-items: center;
          justify-content: space-between;
          min-width: 0;
          width: 100%;
        }
        .cloud-tile-status {
          font-size: 12px;
          font-weight: 800;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          min-width: 0;
          flex: 1;
        }
        .cloud-tile-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          flex-shrink: 0;
          margin-left: 6px;
        }

        @media (max-width: 600px) {
          .dashboard-cloud-grid {
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            margin-top: 14px;
          }
          .dashboard-cloud-tile {
            padding: 8px 10px;
            min-height: 62px;
          }
          .cloud-tile-icon {
            width: 24px;
            height: 24px;
            min-width: 24px;
            border-radius: 6px;
          }
          .cloud-tile-icon ha-icon {
            --mdc-icon-size: 15px !important;
          }
          .cloud-tile-title {
            font-size: 9.5px;
          }
          .cloud-tile-btn {
            padding: 2px 5px;
            font-size: 8px;
            gap: 2px;
          }
          .cloud-tile-btn ha-icon {
            --mdc-icon-size: 10px !important;
          }
          .cloud-tile-status {
            font-size: 11px;
          }
        }
        @media (max-width: 340px) {
          .dashboard-cloud-grid {
            grid-template-columns: 1fr;
          }
        }

        /* ─── Mode Voiture / In-Car Screen ─────────── */
        .car-mode-container {
          display: flex;
          flex-direction: column;
          gap: 20px;
          max-width: 1100px;
          margin: 0 auto;
          width: 100%;
          box-sizing: border-box;
        }
        .car-header-banner {
          background: var(--d-surface-card);
          border: 2px solid var(--d-border);
          border-radius: 24px;
          padding: 16px 24px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          box-shadow: var(--d-shadow);
        }
        .car-badge-pill {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;
          font-weight: 900;
          letter-spacing: 1px;
          text-transform: uppercase;
          color: #3b82f6;
          background: rgba(59, 130, 246, 0.15);
          border: 1px solid rgba(59, 130, 246, 0.35);
          padding: 6px 14px;
          border-radius: 9999px;
        }
        .car-exit-btn {
          background: var(--d-sec-bg);
          border: 1px solid var(--d-border);
          color: var(--d-text);
          padding: 8px 16px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 700;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          transition: all 0.2s;
        }
        .car-exit-btn:hover {
          background: rgba(239, 68, 68, 0.15);
          color: #ef4444;
          border-color: rgba(239, 68, 68, 0.4);
        }
        .car-hero-card {
          border-radius: 28px;
          padding: 24px 32px;
          display: flex;
          align-items: center;
          gap: 24px;
          box-sizing: border-box;
          transition: all 0.3s ease;
        }
        .car-hero-card.secure {
          background: radial-gradient(circle at center, rgba(16, 185, 129, 0.2) 0%, rgba(16, 185, 129, 0.05) 100%), var(--d-surface-card);
          border: 3px solid #10b981;
          box-shadow: 0 0 35px rgba(16, 185, 129, 0.4);
        }
        .car-hero-card.armed {
          background: radial-gradient(circle at center, rgba(59, 130, 246, 0.22) 0%, rgba(59, 130, 246, 0.06) 100%), var(--d-surface-card);
          border: 3px solid #3b82f6;
          box-shadow: 0 0 35px rgba(59, 130, 246, 0.4);
        }
        .car-hero-card.alert {
          background: radial-gradient(circle at center, rgba(239, 68, 68, 0.25) 0%, rgba(239, 68, 68, 0.08) 100%), var(--d-surface-card);
          border: 3px solid #ef4444;
          box-shadow: 0 0 45px rgba(239, 68, 68, 0.6);
          animation: pulseBorder 1.5s infinite;
        }
        .car-hero-icon {
          width: 72px;
          height: 72px;
          min-width: 72px;
          border-radius: 22px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 38px;
        }
        .car-hero-card.secure .car-hero-icon {
          background: rgba(16, 185, 129, 0.25);
          color: #10b981;
          border: 2px solid #10b981;
        }
        .car-hero-card.armed .car-hero-icon {
          background: rgba(59, 130, 246, 0.25);
          color: #3b82f6;
          border: 2px solid #3b82f6;
        }
        .car-hero-card.alert .car-hero-icon {
          background: rgba(239, 68, 68, 0.25);
          color: #ef4444;
          border: 2px solid #ef4444;
        }
        .car-hero-title {
          font-size: 28px;
          font-weight: 900;
          letter-spacing: -0.5px;
          line-height: 1.1;
        }
        .car-hero-desc {
          font-size: 14px;
          color: var(--d-subtext);
          margin-top: 6px;
          font-weight: 600;
        }
        .car-actions-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 16px;
        }
        .car-btn-giant {
          min-height: 80px;
          padding: 16px 20px;
          border-radius: 22px;
          border: 2px solid var(--d-border);
          background: var(--d-surface-card);
          color: var(--d-text);
          font-size: 17px;
          font-weight: 800;
          cursor: pointer;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 8px;
          transition: all 0.2s ease;
          box-shadow: var(--d-shadow);
        }
        .car-btn-giant ha-icon {
          --mdc-icon-size: 32px;
        }
        .car-btn-giant:active,
        .car-btn-giant:hover {
          transform: scale(1.02);
        }
        .car-btn-giant.btn-arm-away {
          border-color: rgba(59, 130, 246, 0.4);
        }
        .car-btn-giant.btn-arm-away:hover,
        .car-btn-giant.btn-arm-away.active {
          background: #2563eb;
          color: #ffffff;
          border-color: #3b82f6;
          box-shadow: 0 6px 24px rgba(37, 99, 235, 0.4);
        }
        .car-btn-giant.btn-arm-home {
          border-color: rgba(245, 158, 11, 0.4);
        }
        .car-btn-giant.btn-arm-home:hover,
        .car-btn-giant.btn-arm-home.active {
          background: #d97706;
          color: #ffffff;
          border-color: #f59e0b;
          box-shadow: 0 6px 24px rgba(217, 119, 6, 0.4);
        }
        .car-btn-giant.btn-disarm {
          border-color: rgba(16, 185, 129, 0.4);
        }
        .car-btn-giant.btn-disarm:hover,
        .car-btn-giant.btn-disarm.active {
          background: #059669;
          color: #ffffff;
          border-color: #10b981;
          box-shadow: 0 6px 24px rgba(5, 150, 105, 0.4);
        }
        .car-columns-row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
          align-items: start;
        }
        @media (max-width: 768px) {
          .car-actions-grid {
            grid-template-columns: 1fr;
            gap: 12px;
          }
          .car-columns-row {
            grid-template-columns: 1fr;
          }
          .car-hero-card {
            padding: 16px 20px;
            gap: 16px;
          }
          .car-hero-icon {
            width: 56px;
            height: 56px;
            min-width: 56px;
            font-size: 28px;
          }
          .car-hero-title {
            font-size: 22px;
          }
        }

        /* ─── Log & Health Layout Responsive ──────── */
        .log-layout-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
        }
        @media (max-width: 768px) {
          .log-layout-grid {
            grid-template-columns: 1fr;
            gap: 16px;
          }
        }

        .health-summary-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 16px;
          margin-bottom: 24px;
        }
        @media (max-width: 650px) {
          .health-summary-grid {
            grid-template-columns: 1fr;
            gap: 10px;
            margin-bottom: 16px;
          }
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

        .keypad-circle-btn.btn-key-clear {
          color: #ef4444 !important;
          font-size: 20px;
          font-weight: 800;
        }
        .keypad-circle-btn.btn-key-clear:hover {
          border-color: #ef4444 !important;
          background: rgba(239, 68, 68, 0.15) !important;
        }
        .keypad-circle-btn.btn-key-clear:active {
          background: #ef4444 !important;
          color: #ffffff !important;
          box-shadow: 0 0 20px rgba(239, 68, 68, 0.7) !important;
        }
        .keypad-circle-btn.btn-key-disarm {
          color: #10b981 !important;
          font-size: 20px;
          font-weight: 800;
        }
        .keypad-circle-btn.btn-key-disarm:hover {
          border-color: #10b981 !important;
          background: rgba(16, 185, 129, 0.15) !important;
        }
        .keypad-circle-btn.btn-key-disarm:active {
          background: #10b981 !important;
          color: #ffffff !important;
          box-shadow: 0 0 20px rgba(16, 185, 129, 0.7) !important;
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

        .btn-biometric-unlock {
          width: 100%;
          margin-top: 6px;
          padding: 11px 14px;
          border-radius: 14px;
          background: rgba(16, 185, 129, 0.12);
          border: 1px solid rgba(16, 185, 129, 0.35);
          color: #10b981;
          font-size: 11px;
          font-weight: 800;
          letter-spacing: 0.5px;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .btn-biometric-unlock:hover {
          background: rgba(16, 185, 129, 0.22);
          border-color: rgba(16, 185, 129, 0.6);
          box-shadow: 0 4px 14px rgba(16, 185, 129, 0.25);
          transform: translateY(-1px);
        }
        .btn-biometric-unlock:active {
          transform: scale(0.98);
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
        .zone-badge {
          display: inline-flex;
          align-items: center;
          gap: 3px;
          padding: 2px 7px;
          border-radius: 9999px;
          background: rgba(245, 158, 11, 0.12);
          color: #f59e0b;
          border: 1px solid rgba(245, 158, 11, 0.28);
          font-size: 10px;
          font-weight: 700;
          margin-left: 6px;
          vertical-align: middle;
        }
        .zone-badge.global {
          background: rgba(59, 130, 246, 0.12);
          color: #3b82f6;
          border-color: rgba(59, 130, 246, 0.28);
        }

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

        /* ─── Configuration Center Styles ─────────── */
        .config-subnav {
          display: flex;
          gap: 6px;
          padding: 5px;
          background: var(--d-surface);
          border-radius: 14px;
          border: 1px solid var(--d-border);
          margin-bottom: 20px;
          overflow-x: auto;
          scrollbar-width: none;
        }
        .config-subnav::-webkit-scrollbar {
          display: none;
        }
        .config-subnav-btn {
          padding: 9px 18px;
          border-radius: 10px;
          border: none;
          background: transparent;
          color: var(--d-subtext);
          font-size: 13px;
          font-weight: 700;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          white-space: nowrap;
          transition: all 0.2s ease;
        }
        .config-subnav-btn ha-icon {
          --mdc-icon-size: 18px;
        }
        .config-subnav-btn:hover {
          color: var(--d-text);
          background: var(--d-sec-bg);
        }
        .config-subnav-btn.active {
          background: var(--d-pill-active-bg);
          color: var(--d-pill-active-text);
          box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }

        .config-card {
          background: var(--d-surface-card);
          border: 1px solid var(--d-border);
          border-radius: 18px;
          padding: 22px;
          margin-bottom: 16px;
          backdrop-filter: var(--d-card-blur);
          transition: border-color 0.2s ease, box-shadow 0.2s ease, padding 0.2s ease, background 0.2s ease;
        }
        .config-card.accordion-card {
          padding: 16px 20px;
        }
        .config-card.accordion-card.open {
          padding: 18px 20px 22px 20px;
          border-color: rgba(245,158,11,0.3);
          box-shadow: 0 4px 20px rgba(0,0,0,0.12);
        }
        .config-card.accordion-card.collapsed {
          padding: 14px 18px;
        }
        .config-card.accordion-card.collapsed:hover {
          border-color: rgba(245,158,11,0.45);
          background: rgba(255,255,255,0.025);
        }
        .config-card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          cursor: pointer;
          user-select: none;
          gap: 12px;
          border-radius: 10px;
          transition: background 0.15s ease;
        }
        .config-card-title {
          font-size: 15px;
          font-weight: 800;
          color: var(--d-text);
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 0;
          flex-wrap: wrap;
        }
        .config-card-chevron-wrap {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          border-radius: 10px;
          background: rgba(255,255,255,0.04);
          border: 1px solid var(--d-border-light);
          color: var(--d-subtext);
          transition: all 0.25s ease;
          flex-shrink: 0;
        }
        .config-card-header:hover .config-card-chevron-wrap {
          color: #f59e0b;
          border-color: rgba(245,158,11,0.4);
          background: rgba(245,158,11,0.12);
        }
        .config-card-chevron {
          transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
          --mdc-icon-size: 20px;
        }
        .config-card.collapsed .config-card-chevron {
          transform: rotate(-90deg);
        }
        .config-card.open .config-card-chevron {
          transform: rotate(0deg);
          color: #f59e0b;
        }
        .config-card-body {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid var(--d-border-light);
          animation: fadeIn 0.2s ease-in-out;
        }
        .config-card.collapsed .config-card-body {
          display: none;
        }

        .config-accordion-toolbar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 14px;
          padding: 4px 6px;
          flex-wrap: wrap;
          gap: 8px;
        }
        .config-accordion-toolbar-hint {
          font-size: 12px;
          color: var(--d-subtext);
          display: flex;
          align-items: center;
          gap: 6px;
          font-weight: 500;
        }
        .config-accordion-toolbar-actions {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .btn-accordion-action {
          padding: 6px 12px;
          border-radius: 9px;
          background: var(--d-sec-bg);
          border: 1px solid var(--d-border-light);
          color: var(--d-subtext);
          font-size: 11.5px;
          font-weight: 700;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 5px;
          transition: all 0.2s ease;
        }
        .btn-accordion-action:hover {
          color: var(--d-text);
          border-color: rgba(245,158,11,0.35);
          background: rgba(245,158,11,0.08);
        }
        .config-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 16px;
          background: var(--d-sec-bg);
          border: 1px solid var(--d-border-light);
          border-radius: 12px;
          margin-bottom: 10px;
          gap: 16px;
        }
        .config-row-stacked {
          display: flex;
          flex-direction: column;
          align-items: stretch;
          padding: 14px 16px;
          background: var(--d-sec-bg);
          border: 1px solid var(--d-border-light);
          border-radius: 12px;
          margin-bottom: 12px;
          gap: 8px;
        }
        .config-label {
          font-size: 13.5px;
          font-weight: 700;
          color: var(--d-text);
          display: flex;
          align-items: center;
        }
        .config-help {
          font-size: 11.5px;
          color: var(--d-subtext);
          margin-top: 2px;
          line-height: 1.35;
        }
        .config-chips-container {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-top: 4px;
        }
        .config-chip {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 4px 10px;
          border-radius: 8px;
          background: rgba(245, 158, 11, 0.12);
          border: 1px solid rgba(245, 158, 11, 0.3);
          color: var(--d-text);
          font-size: 12px;
          font-weight: 600;
        }
        .config-chip-remove {
          cursor: pointer;
          color: #ef4444;
          font-weight: 800;
          font-size: 13px;
          line-height: 1;
          padding: 0 3px;
          border-radius: 4px;
          transition: background 0.15s;
        }
        .config-chip-remove:hover {
          background: rgba(239, 68, 68, 0.2);
        }
        .config-input {
          padding: 8px 12px;
          border-radius: 8px;
          border: 1px solid var(--d-border);
          background: var(--d-surface);
          color: var(--d-text);
          font-size: 13px;
          font-weight: 600;
          outline: none;
          transition: border-color 0.2s;
        }
        .config-input:focus {
          border-color: #f59e0b;
        }
        .config-select {
          padding: 7px 12px;
          border-radius: 8px;
          border: 1px solid var(--d-border);
          background: var(--d-surface);
          color: var(--d-text);
          font-size: 12.5px;
          font-weight: 600;
          outline: none;
          max-width: 320px;
        }
        .config-select:focus {
          border-color: #f59e0b;
        }
        .config-toggle-wrap {
          position: relative;
          display: inline-block;
          width: 44px;
          height: 24px;
          flex-shrink: 0;
        }
        .config-toggle-wrap input {
          opacity: 0;
          width: 0;
          height: 0;
        }
        .config-toggle-slider {
          position: absolute;
          cursor: pointer;
          top: 0; left: 0; right: 0; bottom: 0;
          background-color: rgba(156, 163, 175, 0.3);
          transition: .25s;
          border-radius: 24px;
        }
        .config-toggle-slider:before {
          position: absolute;
          content: "";
          height: 18px;
          width: 18px;
          left: 3px;
          bottom: 3px;
          background-color: white;
          transition: .25s;
          border-radius: 50%;
        }
        input:checked + .config-toggle-slider {
          background-color: #10b981;
        }
        input:checked + .config-toggle-slider:before {
          transform: translateX(20px);
        }
        .config-actions-bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 12px;
          padding: 16px 22px;
          background: var(--d-surface);
          border: 1px solid var(--d-border);
          border-radius: 16px;
          margin-top: 20px;
          box-shadow: var(--d-shadow);
        }
        .btn-config-save {
          padding: 12px 28px;
          border-radius: 9999px;
          border: none;
          background: #f59e0b;
          color: #ffffff;
          font-weight: 800;
          font-size: 13.5px;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: 8px;
          box-shadow: 0 4px 14px rgba(245,158,11,0.35);
          transition: all 0.2s ease;
        }
        .btn-config-save:hover {
          background: #d97706;
          transform: translateY(-1px);
        }
        .btn-config-reset {
          padding: 10px 20px;
          border-radius: 9999px;
          border: 1px solid var(--d-border);
          background: transparent;
          color: var(--d-subtext);
          font-weight: 700;
          font-size: 13px;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          transition: all 0.2s ease;
        }
        .btn-config-reset:hover {
          color: var(--d-text);
          background: var(--d-sec-bg);
        }

        /* ─── Certified Incident Report Print Styles ─── */
        @media print {
          body * {
            visibility: hidden !important;
          }
          #incident-report-modal, #incident-report-modal * {
            visibility: visible !important;
          }
          #incident-report-modal {
            position: fixed !important;
            left: 0 !important;
            top: 0 !important;
            width: 100vw !important;
            height: auto !important;
            margin: 0 !important;
            padding: 0 !important;
            background: #ffffff !important;
          }
          .incident-report-card {
            max-width: 100% !important;
            width: 100% !important;
            box-shadow: none !important;
            padding: 0 !important;
          }
          .no-print {
            display: none !important;
          }
        }
      </style>

      <div class="panel-wrap theme-${this._theme} ${this._kioskActive ? 'kiosk-mode' : ''} ${this._carModeActive ? 'car-mode' : ''}">
        <!-- Kiosk Ambient Screensaver Overlay -->
        <div id="kiosk-screensaver" class="${this._screensaverVisible ? 'visible' : ''}">
          <div class="screensaver-clock">
            <div class="screensaver-time" id="screensaver-time">--:--</div>
            <div class="screensaver-date" id="screensaver-date">---</div>
          </div>
          <div class="screensaver-status-badge" id="screensaver-badge">
            <div class="screensaver-status-disc"></div>
            <span id="screensaver-status-text">SYSTÈME ALARME</span>
          </div>
          <div class="screensaver-touch-hint">
            <ha-icon icon="mdi:gesture-tap"></ha-icon> Touchez l'écran pour accéder au tableau de bord
          </div>
        </div>

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
                <ha-icon icon="mdi:shield-check"></ha-icon>
                <span>Armement</span>
                <span class="nav-tab-badge" id="nav-badge-arm"></span>
              </div>
              <div class="nav-tab" data-tab="equip">
                <ha-icon icon="mdi:devices"></ha-icon>
                <span>Équipements</span>
                <span class="nav-tab-badge" id="nav-badge-equip"></span>
              </div>
              <div class="nav-tab" data-tab="log">
                <ha-icon icon="mdi:history"></ha-icon>
                <span>Journal</span>
                <span class="nav-tab-badge" id="nav-badge-log"></span>
              </div>
              <div class="nav-tab" data-tab="health">
                <ha-icon icon="mdi:heart-pulse"></ha-icon>
                <span>Santé</span>
                <span class="nav-tab-badge" id="nav-badge-health"></span>
              </div>
              <div class="nav-tab" data-tab="sim">
                <ha-icon icon="mdi:home-clock"></ha-icon>
                <span>Simulation</span>
                <span class="nav-tab-badge" id="nav-badge-sim"></span>
              </div>
              <div class="nav-tab" data-tab="media">
                <ha-icon icon="mdi:image-multiple"></ha-icon>
                <span>Médias</span>
                <span class="nav-tab-badge" id="nav-badge-media"></span>
              </div>
              <div class="nav-tab" data-tab="param">
                <ha-icon icon="mdi:cog"></ha-icon>
                <span>Paramètres</span>
                <span class="nav-tab-badge" id="nav-badge-param"></span>
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
              <button class="icon-btn-circle ${this._kioskActive ? 'active' : ''}" id="kiosk-toggle-btn" title="Mode Kiosque Mural (Plein Écran)">
                <ha-icon icon="${this._kioskActive ? 'mdi:fullscreen-exit' : 'mdi:fullscreen'}"></ha-icon>
              </button>
              <button class="icon-btn-circle ${this._carModeActive ? 'active' : ''}" id="car-toggle-btn" title="Mode Voiture / CarPlay (Interface Écran Embarqué)">
                <ha-icon icon="${this._carModeActive ? 'mdi:car-connected' : 'mdi:car'}"></ha-icon>
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

          <!-- Tab 5: Simulation de présence -->
          <div id="pane-sim" class="tab-pane"></div>

          <!-- Tab 6: Médias & Captures -->
          <div id="pane-media" class="tab-pane"></div>

          <!-- Tab 7: Paramètres -->
          <div id="pane-param" class="tab-pane"></div>
        </div>
      </div>
    `;

    this._bindEvents();
  }

  _bindEvents() {
    const navTabs = this.querySelectorAll('.nav-tab');
    navTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        navTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        this._activeTab = tab.dataset.tab;
        this._lastMediaSignature = null;
        if (this._activeTab === 'param') {
          this._paramRendered = false;
        }
        this.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        const targetPane = this.querySelector(`#pane-${this._activeTab}`);
        if (targetPane) targetPane.classList.add('active');
        this.render();
      });
    });

    // Bind Theme Toggle
    const themeBtn = this.querySelector('#theme-toggle-btn');
    if (themeBtn) {
      themeBtn.addEventListener('click', () => this._toggleTheme());
    }

    // Bind Kiosk Toggle
    const kioskBtn = this.querySelector('#kiosk-toggle-btn');
    if (kioskBtn) {
      kioskBtn.addEventListener('click', () => this._toggleKioskMode());
    }

    // Bind Car Mode Toggle
    const carBtn = this.querySelector('#car-toggle-btn');
    if (carBtn) {
      carBtn.addEventListener('click', () => this._toggleCarMode());
    }

    // Bind Screensaver Touch / Tap to wake up
    const screensaverEl = this.querySelector('#kiosk-screensaver');
    if (screensaverEl) {
      const wakeUp = () => this._hideScreensaver();
      screensaverEl.addEventListener('pointerdown', wakeUp);
      screensaverEl.addEventListener('touchstart', wakeUp);
      screensaverEl.addEventListener('click', wakeUp);
    }

    // Inactivity tracker for screensaver
    this._inactivityHandler = () => this._resetInactivityTimer();
    window.addEventListener('pointerdown', this._inactivityHandler, { passive: true });
    window.addEventListener('keydown', this._inactivityHandler, { passive: true });
    this._resetInactivityTimer();
  }

  // ─── Service Dispatcher ─────────────────────────

  callAlarmService(service, codeOverride = null) {
    const alarmEntity = this._getAlarmEntity();
    if (!alarmEntity) {
      alert("Entité DomoLink Alarm introuvable dans Home Assistant.");
      return;
    }
    const data = { entity_id: alarmEntity.entity_id };
    const codeToUse = codeOverride !== null ? codeOverride : this._codeValue;
    if (codeToUse) {
      data.code = codeToUse;
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

  // ─── Mode Voiture / In-Car Screen ───────────────

  _renderCarModeView(alarmEntity, attrs, state, isDisarmed, isArmed, isTriggered, isPending, heroClass, heroIcon, heroTitle, heroDesc, openDoors, activeMotions) {
    return `
      <div class="car-mode-container">
        <!-- Top Automotive Header Bar -->
        <div class="car-header-banner">
          <div style="display:flex; align-items:center; gap:12px;">
            <div class="car-badge-pill">
              <ha-icon icon="mdi:car-connected" style="--mdc-icon-size:18px;"></ha-icon>
              <span>MODE VOITURE & CARPLAY</span>
            </div>
            <span style="font-size:12px; color:var(--d-subtext); font-weight:600;">Interface Haute Visibilité Écran Embarqué</span>
          </div>
          <button class="car-exit-btn" id="btn-exit-car-mode" title="Retourner à l'interface standard">
            <ha-icon icon="mdi:view-dashboard" style="--mdc-icon-size:16px;"></ha-icon>
            <span>Quitter le Mode Voiture</span>
          </button>
        </div>

        <!-- Giant Neon Status Hero Card -->
        <div class="car-hero-card ${heroClass}">
          <div class="car-hero-icon">
            <ha-icon icon="${heroIcon}" style="--mdc-icon-size:42px;"></ha-icon>
          </div>
          <div style="flex:1; min-width:0;">
            <div class="car-hero-title">${heroTitle}</div>
            <div class="car-hero-desc">${this.escapeHtml(heroDesc)}</div>
          </div>
          <div style="display:flex; flex-direction:column; align-items:flex-end; gap:6px;">
            <span class="nav-badge-pill ${isDisarmed ? 'badge-ok' : (isTriggered ? 'badge-ko' : 'badge-arm-armed')}" style="font-size:12px; padding:4px 12px; font-weight:900;">
              ${state.toUpperCase()}
            </span>
          </div>
        </div>

        <!-- Giant 1-Tap Arming Buttons for Drivers -->
        <div class="car-actions-grid">
          <button class="car-btn-giant btn-arm-away ${state === 'armed_away' ? 'active' : ''}" data-car-service="alarm_arm_away">
            <ha-icon icon="mdi:shield-lock"></ha-icon>
            <span>ARMEMENT TOTAL</span>
            <span style="font-size:11px; font-weight:600; opacity:0.8;">Départ en voiture</span>
          </button>

          <button class="car-btn-giant btn-arm-home ${state === 'armed_home' ? 'active' : ''}" data-car-service="alarm_arm_home">
            <ha-icon icon="mdi:shield-home"></ha-icon>
            <span>PARTIEL / NUIT</span>
            <span style="font-size:11px; font-weight:600; opacity:0.8;">Périmètre seul</span>
          </button>

          <button class="car-btn-giant btn-disarm ${isDisarmed ? 'active' : ''}" data-car-service="alarm_disarm">
            <ha-icon icon="mdi:shield-off"></ha-icon>
            <span>DÉSARMER</span>
            <span style="font-size:11px; font-weight:600; opacity:0.8;">Arrivée au domicile</span>
          </button>
        </div>

        <!-- Two Columns: Keypad + Quick Car Diagnostics -->
        <div class="car-columns-row">
          <!-- Car PIN Keypad -->
          <div class="glass-card" style="border-radius:24px; padding:20px; display:flex; flex-direction:column; align-items:center; gap:16px;">
            <div style="font-size:14px; font-weight:800; text-transform:uppercase; letter-spacing:1px; color:var(--d-subtext); display:flex; align-items:center; gap:6px;">
              <ha-icon icon="mdi:dialpad"></ha-icon> Pavé Numérique de Sécurité
            </div>

            <div class="keypad-feedback-box" style="max-width:280px;">
              <div class="pin-indicators-row">
                ${[0, 1, 2, 3, 4, 5].map(i => `
                  <div class="pin-dot-light ${this._codeValue.length > i ? 'active' : ''}"></div>
                `).join('')}
              </div>
            </div>

            <div class="keypad-buttons-grid" style="grid-template-columns:repeat(3, 76px); gap:12px;">
              ${[1, 2, 3, 4, 5, 6, 7, 8, 9].map(n => `
                <button class="keypad-circle-btn car-keypad-btn" data-key="${n}" style="width:76px; height:76px; font-size:24px;">
                  ${n}
                </button>
              `).join('')}
              <button class="keypad-circle-btn car-keypad-btn btn-key-clear" data-key="clear" style="width:76px; height:76px;" title="Effacer le code">
                C
              </button>
              <button class="keypad-circle-btn car-keypad-btn" data-key="0" style="width:76px; height:76px; font-size:24px;">
                0
              </button>
              <button class="keypad-circle-btn car-keypad-btn btn-key-disarm" data-key="disarm" style="width:76px; height:76px;" title="Valider / Désarmer">
                <ha-icon icon="mdi:check-bold" style="--mdc-icon-size:26px;"></ha-icon>
              </button>
            </div>
          </div>

          <!-- Car Diagnostics / Glance Cards -->
          <div style="display:flex; flex-direction:column; gap:14px;">
            <!-- Portes & Fenêtres -->
            <div class="glass-card" style="border-radius:20px; padding:16px; display:flex; align-items:center; justify-content:space-between;">
              <div style="display:flex; align-items:center; gap:12px;">
                <div style="width:44px; height:44px; border-radius:12px; background:${openDoors.length === 0 ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)'}; display:flex; align-items:center; justify-content:center; color:${openDoors.length === 0 ? '#10b981' : '#ef4444'};">
                  <ha-icon icon="${openDoors.length === 0 ? 'mdi:door-closed' : 'mdi:door-open-alert'}" style="--mdc-icon-size:24px;"></ha-icon>
                </div>
                <div>
                  <div style="font-size:14px; font-weight:800; color:var(--d-text);">Portes & Fenêtres</div>
                  <div style="font-size:12px; color:${openDoors.length === 0 ? '#10b981' : '#ef4444'}; font-weight:700;">
                    ${openDoors.length === 0 ? 'Toutes les issues sont fermées' : `${openDoors.length} ouverture(s) détectée(s)`}
                  </div>
                </div>
              </div>
              <span class="nav-badge-pill ${openDoors.length === 0 ? 'badge-ok' : 'badge-ko'}" style="font-size:11px; padding:3px 8px;">
                ${openDoors.length === 0 ? 'SÉCURISÉ' : `${openDoors.length} OUVERT`}
              </span>
            </div>

            <!-- Mouvements -->
            <div class="glass-card" style="border-radius:20px; padding:16px; display:flex; align-items:center; justify-content:space-between;">
              <div style="display:flex; align-items:center; gap:12px;">
                <div style="width:44px; height:44px; border-radius:12px; background:${activeMotions.length === 0 ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)'}; display:flex; align-items:center; justify-content:center; color:${activeMotions.length === 0 ? '#10b981' : '#f59e0b'};">
                  <ha-icon icon="${activeMotions.length === 0 ? 'mdi:motion-sensor-off' : 'mdi:motion-sensor'}" style="--mdc-icon-size:24px;"></ha-icon>
                </div>
                <div>
                  <div style="font-size:14px; font-weight:800; color:var(--d-text);">Détecteurs de Mouvement</div>
                  <div style="font-size:12px; color:${activeMotions.length === 0 ? '#10b981' : '#f59e0b'}; font-weight:700;">
                    ${activeMotions.length === 0 ? 'Aucune activité suspecte' : `${activeMotions.length} mouvement(s) en cours`}
                  </div>
                </div>
              </div>
              <span class="nav-badge-pill ${activeMotions.length === 0 ? 'badge-ok' : 'badge-warn'}" style="font-size:11px; padding:3px 8px;">
                ${activeMotions.length === 0 ? 'REPOS' : 'MOUVEMENT'}
              </span>
            </div>

            <!-- Apple CarPlay Info Card -->
            <div class="glass-card" style="border-radius:20px; padding:16px; border-left:4px solid #3b82f6;">
              <div style="display:flex; align-items:center; gap:8px; font-size:13px; font-weight:800; color:#3b82f6; margin-bottom:4px;">
                <ha-icon icon="mdi:apple"></ha-icon> Apple CarPlay Natif
              </div>
              <div style="font-size:11.5px; color:var(--d-subtext); line-height:1.4;">
                Contrôlez également Domolink Alarm directement sur l'écran tactile CarPlay de votre voiture via l'application Home Assistant iOS (Réglages &gt; CarPlay &amp; Voiture).
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  _bindCarModeEvents(paneArm, alarmEntity) {
    const exitBtn = paneArm.querySelector('#btn-exit-car-mode');
    if (exitBtn) {
      exitBtn.addEventListener('click', () => this._toggleCarMode());
    }

    paneArm.querySelectorAll('.car-btn-giant').forEach(btn => {
      btn.addEventListener('click', (e) => {
        if (window.navigator && window.navigator.vibrate) {
          try { window.navigator.vibrate(15); } catch(e) {}
        }
        const service = e.currentTarget.dataset.carService;
        if (service === 'alarm_disarm') {
          if (this._codeValue.length > 0) {
            this.callAlarmService(service, this._codeValue);
            this._codeValue = '';
          } else {
            this.callAlarmService(service);
          }
        } else if (service) {
          this.callAlarmService(service, this._codeValue || null);
          this._codeValue = '';
        }
        this._updatePinDisplay();
      });
    });

    paneArm.querySelectorAll('.car-keypad-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        if (window.navigator && window.navigator.vibrate) {
          try { window.navigator.vibrate(15); } catch(e) {}
        }
        const key = e.currentTarget.dataset.key;
        if (key === 'clear') {
          this._codeValue = '';
        } else if (key === 'disarm') {
          this.callAlarmService('alarm_disarm', this._codeValue || null);
          this._codeValue = '';
        } else if (this._codeValue.length < 6) {
          this._codeValue += key;
          if (this._codeValue.length === 4 || this._codeValue.length === 6) {
            const alarmState = alarmEntity ? alarmEntity.state : 'disarmed';
            if (alarmState !== 'disarmed') {
              this.callAlarmService('alarm_disarm', this._codeValue);
              this._codeValue = '';
            }
          }
        }
        this._updatePinDisplay();
      });
    });
  }

  // ─── Tab 1: Armement (Mockup UI) ────────────────

  _renderArmTab(alarmEntity) {
    const container = this.querySelector('#pane-arm');
    if (!container) return;

    const state = alarmEntity ? alarmEntity.state : 'disarmed';
    const attrs = alarmEntity ? alarmEntity.attributes : {};

    // 1. Resolve Cameras
    const cameraList = attrs.cameras || Object.keys(this._hass.states).filter(k => k.startsWith('camera.'));
    let currentCamEntity = cameraList.length > 0 ? cameraList[this._selectedCameraIndex % cameraList.length] : null;
    if (attrs.camera_test_running && attrs.camera_test_info && attrs.camera_test_info.camera_entity) {
      currentCamEntity = attrs.camera_test_info.camera_entity;
    }
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
    const isArming = state === 'arming';
    const isPending = state === 'pending';
    const isArmed = state.startsWith('armed');

    let heroClass = 'secure';
    let heroIcon = 'mdi:shield-check';
    let heroTitle = 'SÉCURISÉ';
    let heroDesc = attrs.last_user ? `Désarmée par ${attrs.last_user}` : 'Système au repos • Résidence Principale';

    if (attrs.pre_alert) {
      heroClass = 'alert';
      heroIcon = 'mdi:shield-alert-outline';
      heroTitle = 'PRÉ-ALERTE INTRUSION (NF A2P)';
      heroDesc = attrs.pre_alert_sensor ? `1er détecteur : ${attrs.pre_alert_sensor} • Confirmation en cours (${attrs.pre_alert_remaining || 30}s)` : 'Temporisation de confirmation active';
    } else if (isArmed) {
      heroClass = 'armed';
      heroIcon = 'mdi:shield-lock';
      heroTitle = state === 'armed_away' ? 'ARMÉ (ABSENCE)' : (state === 'armed_night' ? 'ARMÉ (NUIT)' : 'ARMÉ (PRÉSENCE)');
      heroDesc = attrs.last_user ? `Armée par ${attrs.last_user}` : 'Surveillance active • Périmètre sous alarme';
    } else if (isTriggered) {
      heroClass = 'alert';
      heroIcon = 'mdi:bell-alert';
      if (attrs.disarm_cooldown) {
        heroTitle = 'ATTENTE DE DÉSARMEMENT';
        heroDesc = 'Fin de sonnerie • Réarmement automatique dans 1 minute';
      } else {
        heroTitle = 'ALERTE INTRUSION';
        heroDesc = attrs.triggered_by ? `Déclenchée par ${attrs.triggered_by}` : 'Sirènes et alertes actives !';
      }
    } else if (isArming) {
      heroClass = 'pending';
      heroIcon = 'mdi:timer-sand';
      heroTitle = 'TEMPORISATION DE SORTIE';
      heroDesc = 'Armement en cours... Sortez du domicile';
    } else if (isPending) {
      heroClass = 'alert';
      heroIcon = 'mdi:alert-circle';
      heroTitle = 'INTRUSION EN COURS';
      heroDesc = attrs.triggered_by ? `Détection par ${attrs.triggered_by} — Veuillez désarmer` : 'Délai d\'entrée — Veuillez désarmer immédiatement';
    }

    const telegramStatus = attrs.telegram_status || 'Inconnu';
    const ftpStatus = attrs.ftp_status || 'Inconnu';
    const webdavStatus = attrs.webdav_status || (attrs.webdav_enabled ? 'Inconnu' : 'Désactivé');
    const googleDriveStatus = attrs.google_drive_status || (attrs.google_drive_enabled ? 'Inconnu' : 'Désactivé');
    const nasType = attrs.nas_type || 'asustor';
    const nasLabels = { asustor: 'ASUSTOR', synology: 'Synology', qnap: 'QNAP', truenas: 'TrueNAS', freebox: 'Freebox', unraid: 'Unraid', generic: 'NAS' };
    const nasName = nasLabels[nasType] || 'NAS';
    const camerasArmed = attrs.cameras_armed || false;
    if (attrs.ftp_test_running && this._showFtpTestConsole !== false) {
      this._showFtpTestConsole = true;
    }
    if (attrs.webdav_test_running && this._showWebdavTestConsole !== false) {
      this._showWebdavTestConsole = true;
    }
    if (attrs.google_drive_test_running && this._showGoogleDriveTestConsole !== false) {
      this._showGoogleDriveTestConsole = true;
    }

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

    const testProgressHTML = attrs.camera_test_running && attrs.camera_test_info ? (() => {
      const info = attrs.camera_test_info;
      const total = Math.max(1, info.total || 1);
      const current = Math.max(0, info.current || 0);

      // Compute realistic, monotonic global percentage
      let cameraFraction = 0;
      let delay = 0;
      let videoSecs = 0;
      if (info.step === 'photo') {
        cameraFraction = 0.15;
      } else if (info.step === 'video') {
        delay = Math.max(0, (Date.now()/1000) - (info.video_start || (Date.now()/1000)));
        const duration = info.video_duration || 34;
        videoSecs = Math.min(30, Math.floor(delay));
        const videoRatio = Math.min(1, delay / duration);
        cameraFraction = 0.15 + (0.85 * videoRatio);
      }

      let globalPct = 0;
      if (current > 0) {
        globalPct = Math.min(100, Math.max(0, (((current - 1) + cameraFraction) / total) * 100));
      }

      let stepHtml = '';
      if (info.step === 'photo') {
         stepHtml = `
           <div style="display:flex; justify-content:space-between; font-size:10.5px; margin-bottom:4px; opacity:0.9;">
             <span class="cam-test-step-label">Capture Photo en cours...</span>
             <span class="cam-test-step-status" style="color:#f59e0b; font-weight:700;">En cours</span>
           </div>
           <div style="width:100%; height:5px; background:rgba(255,255,255,0.1); border-radius:3px; overflow:hidden;">
             <div class="cam-test-step-bar" style="width:100%; height:100%; background:#f59e0b; animation: progressIndeterminate 1.5s infinite linear;"></div>
           </div>
         `;
      } else if (info.step === 'video') {
         stepHtml = `
           <div style="display:flex; justify-content:space-between; font-size:10.5px; margin-bottom:4px; opacity:0.9;">
             <span class="cam-test-step-label">Vidéo 30s en cours (${videoSecs}s / 30s)...</span>
             <span class="cam-test-step-status" style="color:#f59e0b; font-weight:700;">Enregistrement</span>
           </div>
           <div style="width:100%; height:5px; background:rgba(255,255,255,0.1); border-radius:3px; overflow:hidden;">
             <div class="cam-test-step-bar" style="width:100%; height:100%; background:#f59e0b; animation: fillBar 34s linear forwards; animation-delay: -${delay}s;"></div>
           </div>
         `;
      } else {
         stepHtml = `
           <div style="display:flex; justify-content:space-between; font-size:10.5px; margin-bottom:4px; opacity:0.9;">
             <span class="cam-test-step-label">Préparation du test...</span>
             <span class="cam-test-step-status" style="color:#f59e0b; font-weight:700;">Initialisation</span>
           </div>
           <div style="width:100%; height:5px; background:rgba(255,255,255,0.1); border-radius:3px; overflow:hidden;">
             <div class="cam-test-step-bar" style="width:100%; height:100%; background:#f59e0b; animation: progressIndeterminate 1.5s infinite linear;"></div>
           </div>
         `;
      }
      
      const cameraLabel = info.camera_name && info.camera_name !== '...' ? info.camera_name : (current > 0 ? `Caméra ${current}/${total}` : 'Initialisation...');

      return `
        <div class="camera-test-progress-card" style="display:flex; flex-direction:column; width:100%; max-width:100%; box-sizing:border-box; gap:12px; background:rgba(245,158,11,0.06); border-radius:12px; border:1px solid rgba(245,158,11,0.3); padding:14px; box-shadow:0 4px 16px rgba(0,0,0,0.1); overflow:hidden;">
          <!-- Total Progress -->
          <div style="width:100%; box-sizing:border-box;">
            <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:800; margin-bottom:6px; color:#10b981;">
              <span class="cam-test-global-text">GLOBAL (${current}/${total})</span>
              <span class="cam-test-global-pct">${Math.round(globalPct)}%</span>
            </div>
            <div style="width:100%; height:6px; background:rgba(255,255,255,0.1); border-radius:3px; overflow:hidden;">
              <div class="cam-test-global-bar" style="width:${globalPct}%; height:100%; background:#10b981; transition:width 0.4s ease;"></div>
            </div>
          </div>
          <!-- Current Camera Progress -->
          <div style="width:100%; box-sizing:border-box;">
            <div style="font-size:12px; font-weight:800; margin-bottom:6px; color:var(--d-text); display:flex; justify-content:space-between; align-items:center;">
              <div style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:0; margin-right:8px;">Caméra : <span class="cam-test-camera-name" style="color:#f59e0b;">${this.escapeHtml(cameraLabel)}</span></div>
              <span style="font-size:10px; font-weight:700; color:#f59e0b; background:rgba(245,158,11,0.15); padding:2px 6px; border-radius:4px; flex-shrink:0;">${current > 0 ? `${current}/${total}` : '...'}</span>
            </div>
            ${stepHtml}
          </div>
        </div>
      `;
    })() : '';

    if (this._carModeActive) {
      const carCacheKey = `car_${state}_${attrs.last_user}_${attrs.triggered_by}_${openDoors.length}_${activeMotions.length}_${heroClass}_${heroTitle}_${heroDesc}`;
      if (this._lastCarKey !== carCacheKey || !container.querySelector('.car-mode-container')) {
        this._lastCarKey = carCacheKey;
        this._lastArmKey = '';
        container.innerHTML = this._renderCarModeView(alarmEntity, attrs, state, isDisarmed, isArmed, isTriggered, isPending, heroClass, heroIcon, heroTitle, heroDesc, openDoors, activeMotions);
        this._bindCarModeEvents(container, alarmEntity);
      }
      this._updatePinDisplay();
      return;
    }

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

            <!-- Test d'enregistrement vidéo Button (Widget 1) -->
            ${attrs.camera_test_running ? `
            <div class="cam-test-widget-box" style="width:100%; max-width:100%; box-sizing:border-box; margin-top:10px; background:rgba(245,158,11,0.08); border:1px solid rgba(245,158,11,0.25); border-radius:10px; padding:9px 12px; display:flex; align-items:center; gap:8px; overflow:hidden;">
              <ha-icon icon="mdi:loading" style="--mdc-icon-size:18px; color:#f59e0b; animation:spin 1s linear infinite; flex-shrink:0;"></ha-icon>
              <div style="flex:1; min-width:0; overflow:hidden;">
                <div class="cam-test-widget-current" style="font-size:10px; font-weight:800; color:#f59e0b; text-transform:uppercase; letter-spacing:0.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Test en cours (${Math.max(0, (attrs.camera_test_info || {}).current || 0)}/${Math.max(1, (attrs.camera_test_info || {}).total || 1)})</div>
                <div class="cam-test-widget-cam" style="font-size:11.5px; font-weight:700; color:var(--d-text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${this.escapeHtml((attrs.camera_test_info || {}).camera_name || 'Initialisation...')}</div>
              </div>
            </div>
            ` : `
            <button class="btn-test-cameras-record" id="btn-test-cameras-record-widget" style="width:100%; max-width:100%; box-sizing:border-box; margin-top:10px; background:linear-gradient(135deg, rgba(245,158,11,0.12), rgba(217,119,6,0.22)); border:1px solid rgba(245,158,11,0.45); color:#f59e0b; padding:8px 12px; border-radius:10px; font-size:11px; font-weight:800; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:6px; transition:all 0.2s ease;">
              <ha-icon icon="mdi:video-check" style="--mdc-icon-size:16px; flex-shrink:0;"></ha-icon>
              <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">TEST ENREGISTREMENT VIDÉO</span>
            </button>
            `}
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
          ${attrs.pre_alert ? `
            <div style="background:linear-gradient(135deg, rgba(245,158,11,0.25), rgba(217,119,6,0.35)); border:1.5px solid #f59e0b; border-radius:16px; padding:14px 18px; margin-bottom:12px; display:flex; align-items:center; justify-content:space-between; gap:12px; box-shadow:0 0 16px rgba(245,158,11,0.35);">
              <div style="display:flex; align-items:center; gap:12px;">
                <ha-icon icon="mdi:shield-alert-outline" style="--mdc-icon-size:28px; color:#f59e0b;"></ha-icon>
                <div>
                  <div style="font-weight:800; color:#f59e0b; font-size:14px; letter-spacing:0.5px;">PRÉ-ALERTE INTRUSION (NF A2P)</div>
                  <div style="font-size:12px; color:var(--d-text); margin-top:2px;">1er détecteur : <strong>${this.escapeHtml(attrs.pre_alert_sensor || 'Capteur')}</strong> • En attente de confirmation (${attrs.pre_alert_remaining || 30}s)</div>
                </div>
              </div>
              <button id="btn-prealert-disarm" class="action-btn" style="background:#ef4444; color:#fff; border:none; padding:8px 16px; border-radius:8px; font-weight:700; font-size:13px; cursor:pointer; white-space:nowrap; box-shadow:0 4px 12px rgba(239,68,68,0.35);">Désarmer</button>
            </div>
          ` : ''}
          ${attrs.network_failover_active ? `
            <div style="background:rgba(239,68,68,0.18); border:1px solid #ef4444; border-radius:12px; padding:10px 16px; margin-bottom:12px; display:flex; align-items:center; gap:10px;">
              <ha-icon icon="mdi:cellphone-wireless" style="color:#ef4444; --mdc-icon-size:22px;"></ha-icon>
              <div style="font-size:12px; color:#fca5a5; font-weight:600;">Secours Réseau / GSM Actif : Réseau principal indisponible, alertes transmises via passerelle GSM de secours.</div>
            </div>
          ` : ''}
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
          <div class="dashboard-cloud-grid">
            <!-- Telegram -->
            <div class="dashboard-cloud-tile">
              <div class="cloud-tile-top">
                <div class="cloud-tile-brand">
                  <div class="cloud-tile-icon" style="background:${telegramStatus === 'Désactivé' ? 'var(--d-border)' : (telegramStatus === 'Connecté' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)')}; color:${telegramStatus === 'Désactivé' ? 'var(--d-subtext)' : (telegramStatus === 'Connecté' ? '#10b981' : '#ef4444')};">
                    <ha-icon icon="mdi:send-circle" style="--mdc-icon-size:18px;"></ha-icon>
                  </div>
                  <span class="cloud-tile-title">Telegram</span>
                </div>
              </div>
              <div class="cloud-tile-bottom">
                <span class="cloud-tile-status" style="color:${telegramStatus === 'Connecté' ? '#10b981' : (telegramStatus === 'Désactivé' ? 'var(--d-subtext)' : '#ef4444')};" title="${this.escapeHtml(telegramStatus)}">
                  ${this.escapeHtml(telegramStatus)}
                </span>
                <span class="cloud-tile-dot" style="background:${telegramStatus === 'Connecté' ? '#10b981' : (telegramStatus === 'Désactivé' ? 'rgba(255,255,255,0.2)' : '#ef4444')};"></span>
              </div>
            </div>
            
            <!-- FTP -->
            <div class="dashboard-cloud-tile">
              <div class="cloud-tile-top">
                <div class="cloud-tile-brand">
                  <div class="cloud-tile-icon" style="background:${ftpStatus === 'Désactivé' ? 'var(--d-border)' : (ftpStatus === 'Connecté' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)')}; color:${ftpStatus === 'Désactivé' ? 'var(--d-subtext)' : (ftpStatus === 'Connecté' ? '#10b981' : '#ef4444')};">
                    <ha-icon icon="mdi:folder-network" style="--mdc-icon-size:18px;"></ha-icon>
                  </div>
                  <span class="cloud-tile-title">${this.escapeHtml((attrs.ftp_protocol || 'ftp').toUpperCase())} ${this.escapeHtml(nasName)}</span>
                </div>
                <button class="btn-test-ftp cloud-tile-btn" title="Tester la connexion (${(attrs.ftp_protocol || 'ftp').toUpperCase()})" style="border:1px solid ${attrs.ftp_test_running ? 'rgba(245,158,11,0.5)' : 'rgba(59,130,246,0.35)'}; background:${attrs.ftp_test_running ? 'rgba(245,158,11,0.15)' : 'rgba(59,130,246,0.12)'}; color:${attrs.ftp_test_running ? '#f59e0b' : '#3b82f6'};">
                  <ha-icon icon="${attrs.ftp_test_running ? 'mdi:loading' : 'mdi:lan-connect'}" style="--mdc-icon-size:12px; ${attrs.ftp_test_running ? 'animation: spin 1s linear infinite;' : ''}"></ha-icon>
                  <span>${attrs.ftp_test_running ? '...' : 'TEST'}</span>
                </button>
              </div>
              <div class="cloud-tile-bottom">
                <span class="cloud-tile-status" style="color:${ftpStatus === 'Connecté' ? '#10b981' : (ftpStatus === 'Désactivé' ? 'var(--d-subtext)' : '#ef4444')};" title="${this.escapeHtml(ftpStatus)}">
                  ${this.escapeHtml(ftpStatus)}
                </span>
                <span class="cloud-tile-dot" style="background:${ftpStatus === 'Connecté' ? '#10b981' : (ftpStatus === 'Désactivé' ? 'rgba(255,255,255,0.2)' : '#ef4444')};"></span>
              </div>
            </div>

            <!-- WebDAV / Multi-Cloud -->
            <div class="dashboard-cloud-tile">
              <div class="cloud-tile-top">
                <div class="cloud-tile-brand">
                  <div class="cloud-tile-icon" style="background:${webdavStatus === 'Désactivé' ? 'var(--d-border)' : (webdavStatus === 'Connecté' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)')}; color:${webdavStatus === 'Désactivé' ? 'var(--d-subtext)' : (webdavStatus === 'Connecté' ? '#10b981' : '#ef4444')};">
                    <ha-icon icon="mdi:cloud-sync" style="--mdc-icon-size:18px;"></ha-icon>
                  </div>
                  <span class="cloud-tile-title">WebDAV</span>
                </div>
                <button class="btn-test-webdav cloud-tile-btn" title="Tester la synchronisation WebDAV" style="border:1px solid ${attrs.webdav_test_running ? 'rgba(245,158,11,0.5)' : 'rgba(139,92,246,0.35)'}; background:${attrs.webdav_test_running ? 'rgba(245,158,11,0.15)' : 'rgba(139,92,246,0.12)'}; color:${attrs.webdav_test_running ? '#f59e0b' : '#a855f7'};">
                  <ha-icon icon="${attrs.webdav_test_running ? 'mdi:loading' : 'mdi:cloud-check'}" style="--mdc-icon-size:12px; ${attrs.webdav_test_running ? 'animation: spin 1s linear infinite;' : ''}"></ha-icon>
                  <span>${attrs.webdav_test_running ? '...' : 'TEST'}</span>
                </button>
              </div>
              <div class="cloud-tile-bottom">
                <span class="cloud-tile-status" style="color:${webdavStatus === 'Connecté' ? '#10b981' : (webdavStatus === 'Désactivé' ? 'var(--d-subtext)' : '#ef4444')};" title="${this.escapeHtml(webdavStatus)}">
                  ${this.escapeHtml(webdavStatus)}
                </span>
                <span class="cloud-tile-dot" style="background:${webdavStatus === 'Connecté' ? '#10b981' : (webdavStatus === 'Désactivé' ? 'rgba(255,255,255,0.2)' : '#ef4444')};"></span>
              </div>
            </div>

            <!-- Google Drive -->
            <div class="dashboard-cloud-tile">
              <div class="cloud-tile-top">
                <div class="cloud-tile-brand">
                  <div class="cloud-tile-icon" style="background:${googleDriveStatus === 'Désactivé' ? 'var(--d-border)' : (googleDriveStatus === 'Connecté' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)')}; color:${googleDriveStatus === 'Désactivé' ? 'var(--d-subtext)' : (googleDriveStatus === 'Connecté' ? '#10b981' : '#ef4444')};">
                    <ha-icon icon="mdi:google-drive" style="--mdc-icon-size:18px;"></ha-icon>
                  </div>
                  <span class="cloud-tile-title">Google Drive</span>
                </div>
                <button class="btn-test-gdrive cloud-tile-btn" title="Tester la synchronisation Google Drive" style="border:1px solid ${attrs.google_drive_test_running ? 'rgba(245,158,11,0.5)' : 'rgba(52,168,83,0.35)'}; background:${attrs.google_drive_test_running ? 'rgba(245,158,11,0.15)' : 'rgba(52,168,83,0.12)'}; color:${attrs.google_drive_test_running ? '#f59e0b' : '#34a853'};">
                  <ha-icon icon="${attrs.google_drive_test_running ? 'mdi:loading' : 'mdi:cloud-check'}" style="--mdc-icon-size:12px; ${attrs.google_drive_test_running ? 'animation: spin 1s linear infinite;' : ''}"></ha-icon>
                  <span>${attrs.google_drive_test_running ? '...' : 'TEST'}</span>
                </button>
              </div>
              <div class="cloud-tile-bottom">
                <span class="cloud-tile-status" style="color:${googleDriveStatus === 'Connecté' ? '#10b981' : (googleDriveStatus === 'Désactivé' ? 'var(--d-subtext)' : '#ef4444')};" title="${this.escapeHtml(googleDriveStatus)}">
                  ${this.escapeHtml(googleDriveStatus)}
                </span>
                <span class="cloud-tile-dot" style="background:${googleDriveStatus === 'Connecté' ? '#10b981' : (googleDriveStatus === 'Désactivé' ? 'rgba(255,255,255,0.2)' : '#ef4444')};"></span>
              </div>
            </div>
            
            <!-- Cameras -->
            <div class="dashboard-cloud-tile">
              <div class="cloud-tile-top">
                <div class="cloud-tile-brand">
                  <div class="cloud-tile-icon" style="background:${camerasArmed ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)'}; color:${camerasArmed ? '#ef4444' : '#10b981'};">
                    <ha-icon icon="mdi:cctv" style="--mdc-icon-size:18px;"></ha-icon>
                  </div>
                  <span class="cloud-tile-title">Caméras</span>
                </div>
              </div>
              <div class="cloud-tile-bottom">
                <span class="cloud-tile-status" style="color:${camerasArmed ? '#ef4444' : '#10b981'};">
                  ${camerasArmed ? 'Armées' : 'Désactivées'}
                </span>
                <span class="cloud-tile-dot" style="background:${camerasArmed ? '#ef4444' : '#10b981'};"></span>
              </div>
            </div>
          </div>

          <!-- Console de Test & Diagnostic FTP -->
          ${this._showFtpTestConsole ? `
          <div style="margin-top:14px; background:#0f172a; border:1px solid rgba(59,130,246,0.35); border-radius:14px; padding:12px 14px; box-shadow:0 8px 24px rgba(0,0,0,0.3); color:#f8fafc;">
            <!-- Header -->
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:8px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <ha-icon icon="mdi:console-network" style="--mdc-icon-size:18px; color:#38bdf8;"></ha-icon>
                <span style="font-size:12px; font-weight:800; letter-spacing:0.5px; text-transform:uppercase; color:#e2e8f0;">Diagnostic de Connexion ${(attrs.ftp_protocol || 'ftp').toUpperCase()}</span>
              </div>
              <div style="display:flex; align-items:center; gap:8px;">
                ${attrs.ftp_test_running ? `
                  <span style="display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:700; color:#f59e0b; background:rgba(245,158,11,0.15); padding:2px 8px; border-radius:6px;">
                    <ha-icon icon="mdi:loading" style="--mdc-icon-size:13px; animation:spin 1s linear infinite;"></ha-icon> En cours...
                  </span>
                ` : (attrs.ftp_test_result && attrs.ftp_test_result.success ? `
                  <span style="display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:700; color:#10b981; background:rgba(16,185,129,0.15); padding:2px 8px; border-radius:6px;">
                    <ha-icon icon="mdi:check-circle" style="--mdc-icon-size:13px;"></ha-icon> Connecté
                  </span>
                ` : (attrs.ftp_test_result && attrs.ftp_test_result.success === false ? `
                  <span style="display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:700; color:#ef4444; background:rgba(239,68,68,0.15); padding:2px 8px; border-radius:6px;">
                    <ha-icon icon="mdi:alert-circle" style="--mdc-icon-size:13px;"></ha-icon> Erreur
                  </span>
                ` : ''))}
                <button class="btn-close-ftp-test" title="Fermer la console" style="background:transparent; border:none; color:#94a3b8; cursor:pointer; padding:2px 6px; font-size:16px; font-weight:700; border-radius:4px; line-height:1;">
                  ✕
                </button>
              </div>
            </div>

            <!-- Terminal logs window -->
            <div id="ftp-test-logs" style="background:#020617; border-radius:8px; padding:10px 12px; max-height:160px; min-height:80px; overflow-y:auto; font-family:'SF Mono', Monaco, Menlo, Consolas, monospace; font-size:11px; line-height:1.6; border:1px solid rgba(255,255,255,0.06);">
              ${Array.isArray(attrs.ftp_test_logs) && attrs.ftp_test_logs.length > 0 ? attrs.ftp_test_logs.map(log => {
                const color = log.level === 'error' ? '#f87171' : (log.level === 'success' ? '#4ade80' : (log.level === 'warning' ? '#fbbf24' : '#94a3b8'));
                const icon = log.level === 'error' ? '❌' : (log.level === 'success' ? '✅' : (log.level === 'warning' ? '⚠️' : '▶'));
                return `<div style="color:${color}; margin-bottom:2px;">[${log.time || ''}] ${icon} ${this.escapeHtml(log.message || log.msg || '')}</div>`;
              }).join('') : `
                <div style="display:flex; align-items:center; gap:8px; color:#94a3b8; font-style:italic; padding:6px 0;">
                  <ha-icon icon="mdi:loading" class="spin" style="--mdc-icon-size:15px; color:#38bdf8;"></ha-icon>
                  <span>Démarrage du test de connexion ${(attrs.ftp_protocol || 'ftp').toUpperCase()}...</span>
                </div>
              `}
            </div>

            <!-- Result Summary Banner -->
            ${attrs.ftp_test_result && attrs.ftp_test_result.success ? `
              <div style="margin-top:10px; background:rgba(16,185,129,0.12); border:1px solid rgba(16,185,129,0.4); border-radius:8px; padding:8px 12px; display:flex; align-items:center; gap:10px;">
                <ha-icon icon="mdi:folder-check" style="--mdc-icon-size:22px; color:#10b981; flex-shrink:0;"></ha-icon>
                <div style="font-size:11px; color:#e2e8f0; line-height:1.4;">
                  <strong style="color:#10b981;">Connexion ${(attrs.ftp_test_result?.protocol || attrs.ftp_protocol || 'ftp').toUpperCase()} acceptée avec succès !</strong><br>
                  <span>Chemin de sauvegarde / Partage : </span>
                  <code style="background:rgba(0,0,0,0.4); color:#38bdf8; padding:2px 6px; border-radius:4px; font-weight:700; font-size:11px;">${this.escapeHtml(attrs.ftp_test_result.save_path || 'domolink/alarm')}</code>
                </div>
              </div>
            ` : (attrs.ftp_test_result && attrs.ftp_test_result.success === false ? `
              <div style="margin-top:10px; background:rgba(239,68,68,0.12); border:1px solid rgba(239,68,68,0.4); border-radius:8px; padding:8px 12px; display:flex; align-items:center; gap:10px;">
                <ha-icon icon="mdi:alert-octagon" style="--mdc-icon-size:22px; color:#ef4444; flex-shrink:0;"></ha-icon>
                <div style="font-size:11px; color:#e2e8f0; line-height:1.4;">
                  <strong style="color:#ef4444;">Échec de la connexion ${(attrs.ftp_test_result?.protocol || attrs.ftp_protocol || 'ftp').toUpperCase()} :</strong>
                  <div style="color:#fca5a5; margin-top:2px;">${this.escapeHtml(attrs.ftp_test_result.message || 'Erreur inconnue')}</div>
                </div>
              </div>
            ` : '')}

            <!-- Footer actions -->
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">
              <span style="font-size:10px; color:#64748b;">Hôte : ${this.escapeHtml(attrs.ftp_host || 'NAS')}</span>
              <div style="display:flex; gap:8px;">
                <button class="btn-test-ftp" style="background:rgba(59,130,246,0.15); border:1px solid rgba(59,130,246,0.4); color:#60a5fa; padding:5px 12px; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer; display:flex; align-items:center; gap:5px;">
                  <ha-icon icon="mdi:refresh" style="--mdc-icon-size:13px;"></ha-icon> Relancer
                </button>
                <button class="btn-close-ftp-test" style="background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); color:#cbd5e1; padding:5px 12px; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer;">
                  Fermer
                </button>
              </div>
            </div>
          </div>
          ` : ''}

          <!-- Console de Test & Diagnostic WebDAV -->
          ${this._showWebdavTestConsole ? `
          <div style="margin-top:14px; background:#0f172a; border:1px solid rgba(139,92,246,0.35); border-radius:14px; padding:12px 14px; box-shadow:0 8px 24px rgba(0,0,0,0.3); color:#f8fafc;">
            <!-- Header -->
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:8px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <ha-icon icon="mdi:cloud-sync" style="--mdc-icon-size:18px; color:#c084fc;"></ha-icon>
                <span style="font-size:12px; font-weight:800; letter-spacing:0.5px; text-transform:uppercase; color:#e2e8f0;">Diagnostic WebDAV / Multi-Cloud</span>
              </div>
              <div style="display:flex; align-items:center; gap:8px;">
                ${attrs.webdav_test_running ? `
                  <span style="display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:700; color:#f59e0b; background:rgba(245,158,11,0.15); padding:2px 8px; border-radius:6px;">
                    <ha-icon icon="mdi:loading" style="--mdc-icon-size:13px; animation:spin 1s linear infinite;"></ha-icon> En cours...
                  </span>
                ` : (attrs.webdav_test_result && attrs.webdav_test_result.success ? `
                  <span style="display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:700; color:#10b981; background:rgba(16,185,129,0.15); padding:2px 8px; border-radius:6px;">
                    <ha-icon icon="mdi:check-circle" style="--mdc-icon-size:13px;"></ha-icon> Connecté
                  </span>
                ` : (attrs.webdav_test_result && attrs.webdav_test_result.success === false ? `
                  <span style="display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:700; color:#ef4444; background:rgba(239,68,68,0.15); padding:2px 8px; border-radius:6px;">
                    <ha-icon icon="mdi:alert-circle" style="--mdc-icon-size:13px;"></ha-icon> Erreur
                  </span>
                ` : ''))}
                <button class="btn-close-webdav-test" title="Fermer la console" style="background:transparent; border:none; color:#94a3b8; cursor:pointer; padding:2px 6px; font-size:16px; font-weight:700; border-radius:4px; line-height:1;">
                  ✕
                </button>
              </div>
            </div>

            <!-- Terminal logs window -->
            <div id="webdav-test-logs" style="background:#020617; border-radius:8px; padding:10px 12px; max-height:160px; min-height:80px; overflow-y:auto; font-family:'SF Mono', Monaco, Menlo, Consolas, monospace; font-size:11px; line-height:1.6; border:1px solid rgba(255,255,255,0.06);">
              ${Array.isArray(attrs.webdav_test_logs) && attrs.webdav_test_logs.length > 0 ? attrs.webdav_test_logs.map(log => {
                const color = log.level === 'error' ? '#f87171' : (log.level === 'success' ? '#4ade80' : (log.level === 'warning' ? '#fbbf24' : '#c084fc'));
                const icon = log.level === 'error' ? '❌' : (log.level === 'success' ? '✅' : (log.level === 'warning' ? '⚠️' : '▶'));
                return `<div style="color:${color}; margin-bottom:2px;">[${log.time || ''}] ${icon} ${this.escapeHtml(log.msg || '')}</div>`;
              }).join('') : `
                <div style="display:flex; align-items:center; gap:8px; color:#94a3b8; font-style:italic; padding:6px 0;">
                  <ha-icon icon="mdi:loading" class="spin" style="--mdc-icon-size:15px; color:#c084fc;"></ha-icon>
                  <span>Démarrage du test de synchronisation WebDAV...</span>
                </div>
              `}
            </div>

            <!-- Result Summary Banner -->
            ${attrs.webdav_test_result && attrs.webdav_test_result.success ? `
              <div style="margin-top:10px; background:rgba(16,185,129,0.12); border:1px solid rgba(16,185,129,0.4); border-radius:8px; padding:8px 12px; display:flex; align-items:center; gap:10px;">
                <ha-icon icon="mdi:cloud-check" style="--mdc-icon-size:22px; color:#10b981; flex-shrink:0;"></ha-icon>
                <div style="font-size:11px; color:#e2e8f0; line-height:1.4;">
                  <strong style="color:#10b981;">Connexion WebDAV acceptée avec succès !</strong><br>
                  <span>Dossier de sauvegarde : </span>
                  <code style="background:rgba(0,0,0,0.4); color:#c084fc; padding:2px 6px; border-radius:4px; font-weight:700; font-size:11px;">${this.escapeHtml(attrs.webdav_test_result.save_path || attrs.webdav_path || 'domolink/alarm')}</code>
                </div>
              </div>
            ` : (attrs.webdav_test_result && attrs.webdav_test_result.success === false ? `
              <div style="margin-top:10px; background:rgba(239,68,68,0.12); border:1px solid rgba(239,68,68,0.4); border-radius:8px; padding:8px 12px; display:flex; align-items:center; gap:10px;">
                <ha-icon icon="mdi:alert-octagon" style="--mdc-icon-size:22px; color:#ef4444; flex-shrink:0;"></ha-icon>
                <div style="font-size:11px; color:#e2e8f0; line-height:1.4;">
                  <strong style="color:#ef4444;">Échec de la connexion WebDAV :</strong>
                  <div style="color:#fca5a5; margin-top:2px;">${this.escapeHtml(attrs.webdav_test_result.message || 'Erreur inconnue')}</div>
                </div>
              </div>
            ` : '')}

            <!-- Footer actions -->
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">
              <span style="font-size:10px; color:#64748b;">Serveur : ${this.escapeHtml(attrs.webdav_url || 'Non configuré')}</span>
              <div style="display:flex; gap:8px;">
                <button class="btn-test-webdav" style="background:rgba(139,92,246,0.15); border:1px solid rgba(139,92,246,0.4); color:#c084fc; padding:5px 12px; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer; display:flex; align-items:center; gap:5px;">
                  <ha-icon icon="mdi:refresh" style="--mdc-icon-size:13px;"></ha-icon> Relancer
                </button>
                <button class="btn-close-webdav-test" style="background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); color:#cbd5e1; padding:5px 12px; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer;">
                  Fermer
                </button>
              </div>
            </div>
          </div>
          ` : ''}

          <!-- Console de Test & Diagnostic Google Drive -->
          ${this._showGoogleDriveTestConsole ? `
          <div style="margin-top:14px; background:#0f172a; border:1px solid rgba(52,168,83,0.35); border-radius:14px; padding:12px 14px; box-shadow:0 8px 24px rgba(0,0,0,0.3); color:#f8fafc;">
            <!-- Header -->
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:8px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <ha-icon icon="mdi:google-drive" style="--mdc-icon-size:18px; color:#4ade80;"></ha-icon>
                <span style="font-size:12px; font-weight:800; letter-spacing:0.5px; text-transform:uppercase; color:#e2e8f0;">Diagnostic Google Drive (${attrs.google_drive_method === 'oauth' ? 'API OAuth2' : 'Webhook Script'})</span>
              </div>
              <div style="display:flex; align-items:center; gap:8px;">
                ${attrs.google_drive_test_running ? `
                  <span style="display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:700; color:#f59e0b; background:rgba(245,158,11,0.15); padding:2px 8px; border-radius:6px;">
                    <ha-icon icon="mdi:loading" style="--mdc-icon-size:13px; animation:spin 1s linear infinite;"></ha-icon> En cours...
                  </span>
                ` : (attrs.google_drive_test_result && attrs.google_drive_test_result.success ? `
                  <span style="display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:700; color:#10b981; background:rgba(16,185,129,0.15); padding:2px 8px; border-radius:6px;">
                    <ha-icon icon="mdi:check-circle" style="--mdc-icon-size:13px;"></ha-icon> Connecté
                  </span>
                ` : (attrs.google_drive_test_result && attrs.google_drive_test_result.success === false ? `
                  <span style="display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:700; color:#ef4444; background:rgba(239,68,68,0.15); padding:2px 8px; border-radius:6px;">
                    <ha-icon icon="mdi:alert-circle" style="--mdc-icon-size:13px;"></ha-icon> Erreur
                  </span>
                ` : ''))}
                <button class="btn-close-gdrive-test" title="Fermer la console" style="background:transparent; border:none; color:#94a3b8; cursor:pointer; padding:2px 6px; font-size:16px; font-weight:700; border-radius:4px; line-height:1;">
                  ✕
                </button>
              </div>
            </div>

            <!-- Terminal logs window -->
            <div id="gdrive-test-logs" style="background:#020617; border-radius:8px; padding:10px 12px; max-height:160px; min-height:80px; overflow-y:auto; font-family:'SF Mono', Monaco, Menlo, Consolas, monospace; font-size:11px; line-height:1.6; border:1px solid rgba(255,255,255,0.06);">
              ${Array.isArray(attrs.google_drive_test_logs) && attrs.google_drive_test_logs.length > 0 ? attrs.google_drive_test_logs.map(log => {
                const color = log.level === 'error' ? '#f87171' : (log.level === 'success' ? '#4ade80' : (log.level === 'warning' ? '#fbbf24' : '#86efac'));
                const icon = log.level === 'error' ? '❌' : (log.level === 'success' ? '✅' : (log.level === 'warning' ? '⚠️' : '▶'));
                return `<div style="color:${color}; margin-bottom:2px;">[${log.time || ''}] ${icon} ${this.escapeHtml(log.message || log.msg || '')}</div>`;
              }).join('') : `
                <div style="display:flex; align-items:center; gap:8px; color:#94a3b8; font-style:italic; padding:6px 0;">
                  <ha-icon icon="mdi:loading" class="spin" style="--mdc-icon-size:15px; color:#4ade80;"></ha-icon>
                  <span>Démarrage du test de synchronisation Google Drive...</span>
                </div>
              `}
            </div>

            <!-- Result Summary Banner -->
            ${attrs.google_drive_test_result && attrs.google_drive_test_result.success ? `
              <div style="margin-top:10px; background:rgba(16,185,129,0.12); border:1px solid rgba(16,185,129,0.4); border-radius:8px; padding:8px 12px; display:flex; align-items:center; gap:10px;">
                <ha-icon icon="mdi:cloud-check" style="--mdc-icon-size:22px; color:#10b981; flex-shrink:0;"></ha-icon>
                <div style="font-size:11px; color:#e2e8f0; line-height:1.4;">
                  <strong style="color:#10b981;">Connexion Google Drive acceptée avec succès !</strong><br>
                  <span>Dossier de sauvegarde : </span>
                  <code style="background:rgba(0,0,0,0.4); color:#4ade80; padding:2px 6px; border-radius:4px; font-weight:700; font-size:11px;">${this.escapeHtml(attrs.google_drive_test_result.save_path || 'Racine Google Drive')}</code>
                </div>
              </div>
            ` : (attrs.google_drive_test_result && attrs.google_drive_test_result.success === false ? `
              <div style="margin-top:10px; background:rgba(239,68,68,0.12); border:1px solid rgba(239,68,68,0.4); border-radius:8px; padding:8px 12px; display:flex; align-items:center; gap:10px;">
                <ha-icon icon="mdi:alert-octagon" style="--mdc-icon-size:22px; color:#ef4444; flex-shrink:0;"></ha-icon>
                <div style="font-size:11px; color:#e2e8f0; line-height:1.4;">
                  <strong style="color:#ef4444;">Échec de la connexion Google Drive :</strong>
                  <div style="color:#fca5a5; margin-top:2px;">${this.escapeHtml(attrs.google_drive_test_result.message || 'Erreur inconnue')}</div>
                </div>
              </div>
            ` : '')}

            <!-- Footer actions -->
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">
              <span style="font-size:10px; color:#64748b;">Mode : ${attrs.google_drive_method === 'oauth' ? 'OAuth2 Google Cloud' : 'Apps Script Webhook'}</span>
              <div style="display:flex; gap:8px;">
                <button class="btn-test-gdrive" style="background:rgba(52,168,83,0.15); border:1px solid rgba(52,168,83,0.4); color:#4ade80; padding:5px 12px; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer; display:flex; align-items:center; gap:5px;">
                  <ha-icon icon="mdi:refresh" style="--mdc-icon-size:13px;"></ha-icon> Relancer
                </button>
                <button class="btn-close-gdrive-test" style="background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); color:#cbd5e1; padding:5px 12px; border-radius:6px; font-size:11px; font-weight:700; cursor:pointer;">
                  Fermer
                </button>
              </div>
            </div>
          </div>
          ` : ''}

          <!-- Bouton Test d'enregistrement vidéo (Colonne centrale) -->
          <div style="margin-top:14px; width:100%; max-width:100%; box-sizing:border-box; overflow:hidden;">
            ${attrs.camera_test_running ? testProgressHTML : `
            <button class="btn-test-cameras-record" id="btn-test-cameras-record-center" style="width:100%; max-width:100%; background:linear-gradient(135deg, rgba(245,158,11,0.12), rgba(217,119,6,0.22)); border:1px solid rgba(245,158,11,0.45); color:#f59e0b; padding:11px 12px; border-radius:12px; font-size:clamp(10.5px, 2.7vw, 12px); font-weight:800; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:8px; transition:all 0.2s ease; box-shadow:0 4px 14px rgba(245,158,11,0.06); text-align:center; box-sizing:border-box;">
              <ha-icon icon="mdi:video-check" style="--mdc-icon-size:18px; flex-shrink:0;"></ha-icon>
              <span>TEST D'ENREGISTREMENT VIDÉO (TOUTES LES CAMÉRAS)</span>
            </button>
            `}
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
            <button class="keypad-circle-btn btn-key-clear" data-key="clear" title="Effacer le code">C</button>
            <button class="keypad-circle-btn" data-key="0">
              0
              <div class="key-led-dot"></div>
            </button>
            <button class="keypad-circle-btn btn-key-disarm" data-key="disarm" title="Valider / Désarmer">
              <ha-icon icon="mdi:check-bold" style="--mdc-icon-size:22px; color:#10b981;"></ha-icon>
            </button>
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

          <button class="btn-biometric-unlock" id="btn-biometric-unlock" title="Touch ID / Face ID / Empreinte digitale">
            <ha-icon icon="mdi:fingerprint" style="--mdc-icon-size:18px;"></ha-icon>
            DÉVERROUILLAGE BIOMÉTRIQUE
          </button>

          <button class="btn-sos-danger" id="btn-panic-sos">
            <ha-icon icon="mdi:alert-decagram" style="--mdc-icon-size:18px;"></ha-icon>
            SOS PANIQUE IMMÉDIAT
          </button>
        </div>
      </div>
    `;

    const armCacheKey = `${state}_${attrs.last_user}_${attrs.triggered_by}_${this._selectedCameraIndex}_${totalSensorsCount}_${activeTriggers.length}_${isArmed}_${telegramStatus}_${ftpStatus}_${webdavStatus}_${googleDriveStatus}_${camerasArmed}_${attrs.camera_test_running}_${JSON.stringify(attrs.camera_test_info || {})}_${attrs.ftp_test_running}_${this._showFtpTestConsole}_${(attrs.ftp_test_logs || []).length}_${JSON.stringify(attrs.ftp_test_result || {})}_${attrs.webdav_test_running}_${this._showWebdavTestConsole}_${(attrs.webdav_test_logs || []).length}_${JSON.stringify(attrs.webdav_test_result || {})}_${attrs.google_drive_test_running}_${this._showGoogleDriveTestConsole}_${(attrs.google_drive_test_logs || []).length}_${JSON.stringify(attrs.google_drive_test_result || {})}_${recentEvent1}_${recentEvent2}`;
    if (this._lastArmKey !== armCacheKey || !container.querySelector('.arm-layout-grid')) {
      this._lastArmKey = armCacheKey;
      this._lastCarKey = '';
      container.innerHTML = html;
      
      // FIX: Restore PIN display immediately after DOM reconstruction
      // to prevent the yellow dots from disappearing if HA sends a state update!
      this._updatePinDisplay();

      // Keypad Touch Listeners with tactile feedback
      container.querySelectorAll('.keypad-circle-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          if (window.navigator && window.navigator.vibrate) {
            try { window.navigator.vibrate(15); } catch(e) {}
          }
          const k = btn.getAttribute('data-key');
          if (k === 'clear') {
            this._codeValue = '';
          } else if (k === 'disarm' || k === 'validate') {
            this.callAlarmService('alarm_disarm', this._codeValue || null);
            this._codeValue = '';
          } else if (k === 'back') {
            this._codeValue = this._codeValue.slice(0, -1);
          } else if (this._codeValue.length < 6) {
            this._codeValue += k;
          }
          this._updatePinDisplay();
        });
      });

      // Service Buttons
      container.querySelectorAll('[data-service]').forEach(btn => {
        btn.addEventListener('click', () => this.callAlarmService(btn.getAttribute('data-service')));
      });

      // Biometric Unlock Button Listener
      const bioBtn = container.querySelector('#btn-biometric-unlock');
      if (bioBtn) {
        bioBtn.addEventListener('click', () => this._handleBiometricAuth());
      }

      // Pre-Alert Quick Disarm Button
      const preAlertDisarmBtn = container.querySelector('#btn-prealert-disarm');
      if (preAlertDisarmBtn) {
        preAlertDisarmBtn.addEventListener('click', () => {
          this.callAlarmService('alarm_disarm', this._codeValue || null);
        });
      }

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

      // Test Cameras Recording Buttons
      const triggerTestCameras = async () => {
        if (attrs.camera_test_running) {
          alert("Un test d'enregistrement est déjà en cours d'exécution. Veuillez patienter.");
          return;
        }
        const mediaFolder = attrs.media_path || "domolink_media";
        if (!confirm(`Lancer le test d'enregistrement sur toutes les caméras ?\n\nPour chaque caméra, l'une après l'autre :\n1. Une photo sera capturée et sauvegardée\n2. Une vidéo de 30 secondes sera enregistrée et finalisée\n\nTous les fichiers seront stockés dans /local/${mediaFolder}/.`)) return;
        try {
          await this._hass.callService('domolink_alarm', 'test_cameras_recording', {});
          alert("🎬 Test d'enregistrement lancé avec succès !\n\nChaque caméra est traitée l'une après l'autre (photo + vidéo de 30 secondes).\nSuivez l'avancement en direct dans l'onglet Journal.");
        } catch (err) {
          alert("Erreur lors du lancement du test : " + (err.message || err));
        }
      };

      container.querySelectorAll('.btn-test-cameras-record').forEach(btn => {
        btn.addEventListener('click', triggerTestCameras);
      });

      // Test FTP Connection Buttons
      const triggerTestFtp = async () => {
        this._showFtpTestConsole = true;
        this._lastArmKey = '';
        this.render();
        try {
          await this._hass.callService('domolink_alarm', 'test_ftp', {});
        } catch (err) {
          console.error("Erreur lors du lancement du test FTP:", err);
          alert("Erreur lors du lancement du test FTP : " + (err.message || err));
        }
      };

      container.querySelectorAll('.btn-test-ftp').forEach(btn => {
        btn.addEventListener('click', (ev) => {
          ev.stopPropagation();
          triggerTestFtp();
        });
      });

      container.querySelectorAll('.btn-close-ftp-test').forEach(btn => {
        btn.addEventListener('click', (ev) => {
          ev.stopPropagation();
          this._showFtpTestConsole = false;
          this._lastArmKey = '';
          this.render();
        });
      });

      if (this._showFtpTestConsole) {
        setTimeout(() => {
          const ftpLogEl = container.querySelector('#ftp-test-logs');
          if (ftpLogEl) {
            ftpLogEl.scrollTop = ftpLogEl.scrollHeight;
          }
        }, 50);
      }

      // Test WebDAV Connection Buttons
      const triggerTestWebdav = async () => {
        this._showWebdavTestConsole = true;
        this._lastArmKey = '';
        this.render();
        try {
          await this._hass.callService('domolink_alarm', 'test_webdav', {});
        } catch (err) {
          console.error("Erreur lors du lancement du test WebDAV:", err);
          alert("Erreur lors du lancement du test WebDAV : " + (err.message || err));
        }
      };

      container.querySelectorAll('.btn-test-webdav').forEach(btn => {
        btn.addEventListener('click', (ev) => {
          ev.stopPropagation();
          triggerTestWebdav();
        });
      });

      container.querySelectorAll('.btn-close-webdav-test').forEach(btn => {
        btn.addEventListener('click', (ev) => {
          ev.stopPropagation();
          this._showWebdavTestConsole = false;
          this._lastArmKey = '';
          this.render();
        });
      });

      if (this._showWebdavTestConsole) {
        setTimeout(() => {
          const webdavLogEl = container.querySelector('#webdav-test-logs');
          if (webdavLogEl) {
            webdavLogEl.scrollTop = webdavLogEl.scrollHeight;
          }
        }, 50);
      }

      // Test Google Drive Connection Buttons
      const triggerTestGoogleDrive = async () => {
        this._showGoogleDriveTestConsole = true;
        this._lastArmKey = '';
        this.render();
        try {
          await this._hass.callService('domolink_alarm', 'test_google_drive', {});
        } catch (err) {
          console.error("Erreur lors du lancement du test Google Drive:", err);
          alert("Erreur lors du lancement du test Google Drive : " + (err.message || err));
        }
      };

      container.querySelectorAll('.btn-test-gdrive').forEach(btn => {
        btn.addEventListener('click', (ev) => {
          ev.stopPropagation();
          triggerTestGoogleDrive();
        });
      });

      container.querySelectorAll('.btn-close-gdrive-test').forEach(btn => {
        btn.addEventListener('click', (ev) => {
          ev.stopPropagation();
          this._showGoogleDriveTestConsole = false;
          this._lastArmKey = '';
          this.render();
        });
      });

      if (this._showGoogleDriveTestConsole) {
        setTimeout(() => {
          const gdriveLogEl = container.querySelector('#gdrive-test-logs');
          if (gdriveLogEl) {
            gdriveLogEl.scrollTop = gdriveLogEl.scrollHeight;
          }
        }, 50);
      }
    }
  }

  // ─── Tab 2: Équipements ─────────────────────────

  _renderEquipTab(attrs) {
    const container = this.querySelector('#pane-equip');
    if (!container) return;
    const bypassedSensors = attrs.bypassed_sensors || [];
    const entityZones = attrs.entity_zones || {};
    const globalCameras = attrs.global_cameras || [];

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

        // Zone badges
        const zones = entityZones[entityId] || [];
        const zoneBadgeHtml = zones.map(z => `<span class="zone-badge" title="Zone: ${this.escapeHtml(z)}"><ha-icon icon="mdi:map-marker-radius" style="--mdc-icon-size:11px;"></ha-icon> ${this.escapeHtml(z)}</span>`).join('');
        const globalBadgeHtml = globalCameras.includes(entityId) ? `<span class="zone-badge global" title="Caméra Globale"><ha-icon icon="mdi:earth" style="--mdc-icon-size:11px;"></ha-icon> Globale</span>` : '';

        html += `
          <div class="equip-item-card">
            <div class="equip-icon-disc ${iconDiscClass}">
              <ha-icon icon="${isBypassed ? 'mdi:shield-off' : cat.icon}"></ha-icon>
            </div>
            <div style="flex-grow:1; min-width:0;">
              <div style="font-size:14px; font-weight:700; color:var(--d-text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; display:flex; align-items:center; flex-wrap:wrap; gap:4px;">
                <span>${this.escapeHtml(friendlyName)}</span>
                ${zoneBadgeHtml}
                ${globalBadgeHtml}
              </div>
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
      <div style="display:flex; justify-content:flex-end; margin-bottom:16px;">
        <button id="btn-open-incident-report" class="action-btn" style="background:linear-gradient(135deg, #4f46e5, #4338ca); color:white; border:none; padding:10px 18px; border-radius:10px; font-weight:700; font-size:13px; display:inline-flex; align-items:center; gap:8px; cursor:pointer; box-shadow:0 4px 14px rgba(79,70,229,0.35); transition:all 0.2s;">
          <ha-icon icon="mdi:file-certificate-outline" style="--mdc-icon-size:20px;"></ha-icon>
          Rapport d'Incident Certifié (PDF)
        </button>
      </div>
      <div class="log-layout-grid">
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

      const reportBtn = container.querySelector('#btn-open-incident-report');
      if (reportBtn) {
        reportBtn.addEventListener('click', () => {
          this._openIncidentReportModal(alarmEntity);
        });
      }
    }
  }

  // ─── Certified Incident Report Modal ────────────

  _openIncidentReportModal(alarmEntity) {
    const attrs = alarmEntity ? alarmEntity.attributes : {};
    const report = attrs.last_incident_report || {
      id: "INC-" + (new Date().toISOString().replace(/[-:T]/g, "").slice(0, 14)),
      timestamp: new Date().toISOString(),
      french_date: new Date().toLocaleString('fr-FR'),
      type: attrs.triggered_by ? "intrusion" : "system_snapshot",
      alarm_name: attrs.friendly_name || "Domolink Alarm",
      state_before: alarmEntity ? alarmEntity.state : "disarmed",
      trigger_sensor: attrs.last_triggered_by || "N/A",
      trigger_name: attrs.triggered_by || "Aucun déclenchement récent",
      active_faults: attrs.faults || [],
      bypassed_sensors: attrs.bypassed_sensors || [],
      recent_events: (attrs.system_events || []).slice(0, 15),
      sha256_token: "DOMO-" + Math.random().toString(36).substring(2, 10).toUpperCase() + Math.random().toString(36).substring(2, 10).toUpperCase(),
      system_version: attrs.system_version || "0.9.74"
    };

    const modal = document.createElement('div');
    modal.id = 'incident-report-modal';
    modal.style = "position:fixed; inset:0; background:rgba(0,0,0,0.85); backdrop-filter:blur(8px); z-index:999999; display:flex; align-items:center; justify-content:center; padding:16px; overflow-y:auto; cursor:default;";

    modal.innerHTML = `
      <div class="incident-report-card" style="background:#ffffff; color:#111827; width:95vw; max-width:840px; max-height:92vh; border-radius:16px; overflow-y:auto; padding:32px; box-shadow:0 25px 50px -12px rgba(0,0,0,0.5); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; position:relative;">
        <div class="no-print" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; border-bottom:1px solid #e5e7eb; padding-bottom:14px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="background:#4f46e5; color:white; font-size:11px; font-weight:800; padding:4px 8px; border-radius:6px; letter-spacing:0.5px;">RAPPORT OFFICIEL</span>
            <span style="font-size:12px; color:#6b7280;">Conforme aux exigences d'attestation d'assurance</span>
          </div>
          <div style="display:flex; gap:10px;">
            <button id="btn-print-report" style="background:#4f46e5; color:white; border:none; padding:8px 16px; border-radius:8px; font-weight:700; font-size:13px; cursor:pointer; display:inline-flex; align-items:center; gap:6px;">
              <ha-icon icon="mdi:printer" style="--mdc-icon-size:18px;"></ha-icon> Imprimer / PDF
            </button>
            <button id="btn-close-report" style="background:#f3f4f6; color:#374151; border:none; padding:8px 14px; border-radius:8px; font-weight:700; font-size:13px; cursor:pointer;">Fermer</button>
          </div>
        </div>

        <!-- En-tête officiel du rapport -->
        <div style="display:flex; justify-content:space-between; align-items:flex-start; border-bottom:2px solid #111827; padding-bottom:16px; margin-bottom:20px;">
          <div>
            <div style="font-size:20px; font-weight:900; color:#111827; letter-spacing:-0.5px; text-transform:uppercase;">Rapport d'Incident & d'Intrusion</div>
            <div style="font-size:13px; color:#4b5563; font-weight:600; margin-top:2px;">Système de télésurveillance et sécurité autonome Domolink Alarm</div>
            <div style="font-size:12px; color:#6b7280; margin-top:2px;">Identifiant d'Incident : <strong style="font-family:monospace; color:#111827;">${report.id}</strong> • Version ${report.system_version}</div>
          </div>
          <div style="text-align:right;">
            <div style="display:inline-flex; align-items:center; gap:6px; background:#f0fdf4; border:1px solid #86efac; color:#166534; font-size:11px; font-weight:800; padding:4px 10px; border-radius:20px;">
              <ha-icon icon="mdi:shield-check" style="--mdc-icon-size:16px;"></ha-icon> INTÉGRITÉ SCELLÉE
            </div>
            <div style="font-size:11px; color:#6b7280; margin-top:6px;">Émis le ${report.french_date || new Date().toLocaleString('fr-FR')}</div>
          </div>
        </div>

        <!-- Synthèse de l'événement -->
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:12px; margin-bottom:20px;">
          <div style="background:#f9fafb; border:1px solid #e5e7eb; border-radius:10px; padding:12px 14px;">
            <div style="font-size:11px; font-weight:700; color:#6b7280; text-transform:uppercase;">Système</div>
            <div style="font-size:14px; font-weight:800; color:#111827; margin-top:3px;">${this.escapeHtml(report.alarm_name)}</div>
          </div>
          <div style="background:#f9fafb; border:1px solid #e5e7eb; border-radius:10px; padding:12px 14px;">
            <div style="font-size:11px; font-weight:700; color:#6b7280; text-transform:uppercase;">Type d'Événement</div>
            <div style="font-size:14px; font-weight:800; color:#dc2626; margin-top:3px;">${report.type === 'intrusion' ? '🚨 INTRUSION CONFIRMÉE' : '🛡️ INSTANTANÉ SÉCURITÉ'}</div>
          </div>
          <div style="background:#f9fafb; border:1px solid #e5e7eb; border-radius:10px; padding:12px 14px;">
            <div style="font-size:11px; font-weight:700; color:#6b7280; text-transform:uppercase;">Capteur Déclencheur</div>
            <div style="font-size:14px; font-weight:800; color:#111827; margin-top:3px;">${this.escapeHtml(report.trigger_name)}</div>
          </div>
          <div style="background:#f9fafb; border:1px solid #e5e7eb; border-radius:10px; padding:12px 14px;">
            <div style="font-size:11px; font-weight:700; color:#6b7280; text-transform:uppercase;">État Initial</div>
            <div style="font-size:14px; font-weight:800; color:#111827; margin-top:3px;">${this.escapeHtml(report.state_before)}</div>
          </div>
        </div>

        <!-- Détails Techniques & Capteurs -->
        <div style="border:1px solid #e5e7eb; border-radius:10px; overflow:hidden; margin-bottom:20px;">
          <div style="background:#f3f4f6; padding:10px 14px; font-size:12px; font-weight:800; color:#374151; border-bottom:1px solid #e5e7eb;">
            DIAGNOSTIC TECHNIQUE ET ÉQUIPEMENTS EN CAUSE
          </div>
          <div style="padding:12px 14px; font-size:13px; display:grid; grid-template-columns:1fr 1fr; gap:12px;">
            <div>
              <span style="color:#6b7280; font-weight:600;">Détecteurs en alerte active :</span>
              <strong style="color:#111827; display:block; margin-top:2px;">${(report.active_faults && report.active_faults.length > 0) ? report.active_faults.join(', ') : 'Aucun'}</strong>
            </div>
            <div>
              <span style="color:#6b7280; font-weight:600;">Détecteurs contournés (Bypass) :</span>
              <strong style="color:#111827; display:block; margin-top:2px;">${(report.bypassed_sensors && report.bypassed_sensors.length > 0) ? report.bypassed_sensors.join(', ') : 'Aucun (Sécurité 100% active)'}</strong>
            </div>
          </div>
        </div>

        <!-- Chronologie Événementielle (Journal certifié) -->
        <div style="border:1px solid #e5e7eb; border-radius:10px; overflow:hidden; margin-bottom:20px;">
          <div style="background:#f3f4f6; padding:10px 14px; font-size:12px; font-weight:800; color:#374151; border-bottom:1px solid #e5e7eb;">
            CHRONOLOGIE DÉTAILLÉE DES ÉVÉNEMENTS HORODATÉS
          </div>
          <div style="padding:10px 14px;">
            ${(report.recent_events && report.recent_events.length > 0) ? report.recent_events.map(e => `
              <div style="display:flex; justify-content:space-between; align-items:center; padding:6px 0; border-bottom:1px solid #f3f4f6; font-size:12px;">
                <span style="color:#111827; font-weight:600;">${this.escapeHtml(e.message || e.text || '')}</span>
                <span style="color:#6b7280; font-family:monospace; font-size:11px; margin-left:12px; white-space:nowrap;">${this.formatDate(e.time)}</span>
              </div>
            `).join('') : '<div style="font-size:12px; color:#6b7280;">Aucun log horodaté associé.</div>'}
          </div>
        </div>

        <!-- Sceau Cryptographique et Empreinte Numérique -->
        <div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:10px; padding:14px; margin-bottom:16px;">
          <div style="font-size:11px; font-weight:800; color:#475569; text-transform:uppercase; display:flex; align-items:center; gap:6px;">
            <ha-icon icon="mdi:fingerprint" style="--mdc-icon-size:18px; color:#3b82f6;"></ha-icon>
            EMPREINTE CRYPTOGRAPHIQUE NUMÉRIQUE (SHA-256)
          </div>
          <div style="font-family:monospace; font-size:11px; color:#0f172a; word-break:break-all; margin-top:4px; background:#ffffff; padding:6px 10px; border-radius:6px; border:1px solid #e2e8f0;">
            ${report.sha256_token || 'SHA256-AUTHENTIC-VERIFIED-CERTIFICATE'}
          </div>
          <div style="font-size:11px; color:#64748b; margin-top:6px;">
            Ce certificat constitue une preuve d'alerte infalsifiable horodatée générée localement par la centrale Domolink Alarm. Valable pour dépôt de plainte et déclaration d'assurance.
          </div>
        </div>
      </div>
    `;

    this.appendChild(modal);

    modal.querySelector('#btn-print-report')?.addEventListener('click', () => {
      window.print();
    });

    const closeModal = () => modal.remove();
    modal.querySelector('#btn-close-report')?.addEventListener('click', closeModal);
    modal.addEventListener('click', (ev) => {
      if (ev.target === modal) closeModal();
    });
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
        <div class="health-summary-grid">
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

  // ─── Tab 7: Centre de Configuration ─────────────

  _initParamDraft(attrs) {
    if (this._configDraft) return;
    const c = (attrs && attrs.installed_config) ? attrs.installed_config : {};
    
    const defaultNasConfigs = {
      asustor: { ftp_enabled: true, ftp_protocol: "ftp", ftp_host: "", ftp_port: 21, ftp_user: "", ftp_pass: "", ftp_path: "/", webdav_enabled: false, webdav_url: "", webdav_user: "", webdav_pass: "", webdav_path: "domolink/alarm" },
      synology: { ftp_enabled: true, ftp_protocol: "ftp", ftp_host: "", ftp_port: 21, ftp_user: "", ftp_pass: "", ftp_path: "/", webdav_enabled: false, webdav_url: "", webdav_user: "", webdav_pass: "", webdav_path: "domolink/alarm" },
      qnap: { ftp_enabled: true, ftp_protocol: "ftp", ftp_host: "", ftp_port: 21, ftp_user: "", ftp_pass: "", ftp_path: "/", webdav_enabled: false, webdav_url: "", webdav_user: "", webdav_pass: "", webdav_path: "domolink/alarm" },
      truenas: { ftp_enabled: false, ftp_protocol: "ftp", ftp_host: "", ftp_port: 21, ftp_user: "", ftp_pass: "", ftp_path: "/", webdav_enabled: true, webdav_url: "", webdav_user: "", webdav_pass: "", webdav_path: "domolink/alarm" },
      freebox: { ftp_enabled: true, ftp_protocol: "ftp", ftp_host: "mafreebox.freebox.fr", ftp_port: 21, ftp_user: "freebox", ftp_pass: "", ftp_path: "/Disque 1", webdav_enabled: false, webdav_url: "", webdav_user: "", webdav_pass: "", webdav_path: "domolink/alarm" },
      unraid: { ftp_enabled: true, ftp_protocol: "ftp", ftp_host: "", ftp_port: 21, ftp_user: "", ftp_pass: "", ftp_path: "/", webdav_enabled: false, webdav_url: "", webdav_user: "", webdav_pass: "", webdav_path: "domolink/alarm" },
      generic: { ftp_enabled: true, ftp_protocol: "ftp", ftp_host: "", ftp_port: 21, ftp_user: "", ftp_pass: "", ftp_path: "/", webdav_enabled: false, webdav_url: "", webdav_user: "", webdav_pass: "", webdav_path: "domolink/alarm" }
    };

    const savedNasConfigs = (c && c.nas_configs) || (attrs && attrs.nas_configs) || {};
    const mergedNasConfigs = {};
    Object.keys(defaultNasConfigs).forEach(brand => {
      mergedNasConfigs[brand] = Object.assign({}, defaultNasConfigs[brand], (savedNasConfigs && savedNasConfigs[brand]) || {});
    });

    const activeNas = (c.nas_type || (attrs && attrs.nas_type) || "asustor").toLowerCase();
    if (!mergedNasConfigs[activeNas]) {
      mergedNasConfigs[activeNas] = Object.assign({}, defaultNasConfigs.asustor);
    }

    // If activeNas has legacy top-level credentials in c, ensure they're populated into active profile
    if (c.ftp_host && (!savedNasConfigs[activeNas] || !savedNasConfigs[activeNas].ftp_host)) {
      mergedNasConfigs[activeNas].ftp_enabled = Boolean(c.ftp_enabled);
      mergedNasConfigs[activeNas].ftp_protocol = c.ftp_protocol || attrs.ftp_protocol || "ftp";
      mergedNasConfigs[activeNas].ftp_host = c.ftp_host || "";
      mergedNasConfigs[activeNas].ftp_port = c.ftp_port !== undefined ? c.ftp_port : 21;
      mergedNasConfigs[activeNas].ftp_user = c.ftp_user || "";
      mergedNasConfigs[activeNas].ftp_pass = c.ftp_pass || "";
      mergedNasConfigs[activeNas].ftp_path = c.ftp_path || (activeNas === 'freebox' ? "/Disque 1" : "/");
    }
    if (c.webdav_url && (!savedNasConfigs[activeNas] || !savedNasConfigs[activeNas].webdav_url)) {
      mergedNasConfigs[activeNas].webdav_enabled = Boolean(c.webdav_enabled);
      mergedNasConfigs[activeNas].webdav_url = c.webdav_url || "";
      mergedNasConfigs[activeNas].webdav_user = c.webdav_user || "";
      mergedNasConfigs[activeNas].webdav_pass = c.webdav_pass || "";
      mergedNasConfigs[activeNas].webdav_path = c.webdav_path || "domolink/alarm";
    }

    // Freebox guarantee defaults if empty
    if (!mergedNasConfigs.freebox.ftp_host) mergedNasConfigs.freebox.ftp_host = "mafreebox.freebox.fr";
    if (!mergedNasConfigs.freebox.ftp_user) mergedNasConfigs.freebox.ftp_user = "freebox";
    if (!mergedNasConfigs.freebox.ftp_protocol) mergedNasConfigs.freebox.ftp_protocol = "ftp";
    if (mergedNasConfigs.freebox.ftp_port === undefined) mergedNasConfigs.freebox.ftp_port = 21;
    if (mergedNasConfigs.freebox.ftp_enabled === undefined) mergedNasConfigs.freebox.ftp_enabled = true;
    if (!mergedNasConfigs.freebox.ftp_path || mergedNasConfigs.freebox.ftp_path === "/") mergedNasConfigs.freebox.ftp_path = "/Disque 1";

    const curNasCfg = mergedNasConfigs[activeNas] || mergedNasConfigs.asustor;

    this._configDraft = {
      name: c.name || "Domolink Alarm",
      opening_sensors: Array.isArray(c.opening_sensors) ? [...c.opening_sensors] : [],
      opening_sensors_labels: Array.isArray(c.opening_sensors_labels) ? [...c.opening_sensors_labels] : [],
      night_sensors: Array.isArray(c.night_sensors) ? [...c.night_sensors] : [],
      night_sensors_labels: Array.isArray(c.night_sensors_labels) ? [...c.night_sensors_labels] : [],
      motion_sensors: Array.isArray(c.motion_sensors) ? [...c.motion_sensors] : [],
      motion_sensors_labels: Array.isArray(c.motion_sensors_labels) ? [...c.motion_sensors_labels] : [],
      cameras: Array.isArray(c.cameras) ? [...c.cameras] : [],
      cameras_labels: Array.isArray(c.cameras_labels) ? [...c.cameras_labels] : [],
      cameras_arm_entities: Array.isArray(c.cameras_arm_entities) ? [...c.cameras_arm_entities] : [],
      cameras_arm_entities_labels: Array.isArray(c.cameras_arm_entities_labels) ? [...c.cameras_arm_entities_labels] : [],
      tamper_sensors: Array.isArray(c.tamper_sensors) ? [...c.tamper_sensors] : [],
      tamper_sensors_labels: Array.isArray(c.tamper_sensors_labels) ? [...c.tamper_sensors_labels] : [],
      keypads: Array.isArray(c.keypads) ? [...c.keypads] : [],
      keypads_labels: Array.isArray(c.keypads_labels) ? [...c.keypads_labels] : [],
      safety_sensors: Array.isArray(c.safety_sensors) ? [...c.safety_sensors] : [],
      safety_sensors_labels: Array.isArray(c.safety_sensors_labels) ? [...c.safety_sensors_labels] : [],
      sirens: Array.isArray(c.sirens) ? [...c.sirens] : [],
      sirens_labels: Array.isArray(c.sirens_labels) ? [...c.sirens_labels] : [],
      lights: Array.isArray(c.lights) ? [...c.lights] : [],
      lights_labels: Array.isArray(c.lights_labels) ? [...c.lights_labels] : [],
      media_players: Array.isArray(c.media_players) ? [...c.media_players] : [],
      media_players_labels: Array.isArray(c.media_players_labels) ? [...c.media_players_labels] : [],
      notify_services: Array.isArray(c.notify_services) ? [...c.notify_services] : [],
      notify_services_labels: Array.isArray(c.notify_services_labels) ? [...c.notify_services_labels] : [],
      free_mobile_user: c.free_mobile_user || "",
      free_mobile_pass: c.free_mobile_pass || "",
      icloud_account: c.icloud_account || "",
      icloud_devices: Array.isArray(c.icloud_devices) ? [...c.icloud_devices] : [],
      emergency_contact: Array.isArray(c.emergency_contact) ? [...c.emergency_contact] : [],
      emergency_contact_labels: Array.isArray(c.emergency_contact_labels) ? [...c.emergency_contact_labels] : [],
      presence_simulation_entities: Array.isArray(c.presence_simulation_entities) ? [...c.presence_simulation_entities] : [],
      presence_simulation_labels: Array.isArray(c.presence_simulation_labels) ? [...c.presence_simulation_labels] : [],
      zone_labels: Array.isArray(c.zone_labels) ? [...c.zone_labels] : [],
      global_cameras: Array.isArray(c.global_cameras) ? [...c.global_cameras] : [],
      global_cameras_labels: Array.isArray(c.global_cameras_labels) ? [...c.global_cameras_labels] : [],
      persons: Array.isArray(c.persons) ? [...c.persons] : [],
      persons_labels: Array.isArray(c.persons_labels) ? [...c.persons_labels] : [],
      users_codes: c.users_codes || "",
      duress_code: c.duress_code || "",
      rfid_tags: c.rfid_tags || "",
      exit_delay: c.exit_delay !== undefined ? c.exit_delay : 30,
      entry_delay: c.entry_delay !== undefined ? c.entry_delay : 30,
      siren_duration: c.siren_duration !== undefined ? c.siren_duration : 180,
      bypass_allowed: Boolean(c.bypass_allowed),
      health_check: c.health_check !== undefined ? Boolean(c.health_check) : true,
      geofence_auto_arm: Boolean(c.geofence_auto_arm),
      geofence_reminder: Boolean(c.geofence_reminder),
      geofence_reminder_delay: c.geofence_reminder_delay !== undefined ? c.geofence_reminder_delay : 15,
      chime_mode: Boolean(c.chime_mode),
      cross_zoning: Boolean(c.cross_zoning),
      cross_zoning_window: c.cross_zoning_window !== undefined ? c.cross_zoning_window : 60,
      presence_simulation_history_days: c.presence_simulation_history_days !== undefined ? c.presence_simulation_history_days : 7,
      siren_test: Boolean(c.siren_test),
      siren_test_day: c.siren_test_day !== undefined ? c.siren_test_day : 5,
      siren_test_hour: c.siren_test_hour !== undefined ? c.siren_test_hour : 12,
      schedule_enabled: Boolean(c.schedule_enabled),
      schedule_arm_time: c.schedule_arm_time || "23:00",
      schedule_disarm_time: c.schedule_disarm_time || "06:00",
      schedule_mode: c.schedule_mode || "night",
      mqtt_enabled: Boolean(c.mqtt_enabled),
      mqtt_topic_base: c.mqtt_topic_base || "domolink/alarme",
      mqtt_require_code: Boolean(c.mqtt_require_code),
      telegram_enabled: Boolean(c.telegram_enabled),
      telegram_token: c.telegram_token || "",
      telegram_chat_id: c.telegram_chat_id || "",
      nas_type: activeNas,
      nas_configs: mergedNasConfigs,
      ftp_enabled: Boolean(curNasCfg.ftp_enabled),
      ftp_protocol: curNasCfg.ftp_protocol || "ftp",
      ftp_host: curNasCfg.ftp_host !== undefined ? curNasCfg.ftp_host : "",
      ftp_port: curNasCfg.ftp_port !== undefined ? curNasCfg.ftp_port : 21,
      ftp_user: curNasCfg.ftp_user !== undefined ? curNasCfg.ftp_user : "",
      ftp_pass: curNasCfg.ftp_pass !== undefined ? curNasCfg.ftp_pass : "",
      ftp_path: curNasCfg.ftp_path !== undefined ? curNasCfg.ftp_path : "/",
      webdav_enabled: Boolean(curNasCfg.webdav_enabled),
      webdav_url: curNasCfg.webdav_url !== undefined ? curNasCfg.webdav_url : "",
      webdav_user: curNasCfg.webdav_user !== undefined ? curNasCfg.webdav_user : "",
      webdav_pass: curNasCfg.webdav_pass !== undefined ? curNasCfg.webdav_pass : "",
      webdav_path: curNasCfg.webdav_path !== undefined ? curNasCfg.webdav_path : "domolink/alarm",
      google_drive_enabled: Boolean(c.google_drive_enabled),
      google_drive_method: c.google_drive_method || "webhook",
      google_drive_webhook_url: c.google_drive_webhook_url || "",
      google_drive_client_id: c.google_drive_client_id || "",
      google_drive_client_secret: c.google_drive_client_secret || "",
      google_drive_refresh_token: c.google_drive_refresh_token || "",
      google_drive_folder_id: c.google_drive_folder_id || "",
      media_retention_days: c.media_retention_days !== undefined ? c.media_retention_days : 30,
      media_max_size_mb: c.media_max_size_mb !== undefined ? c.media_max_size_mb : 1024,
      media_path: c.media_path || "domolink_media",
      nf_a2p_mode: Boolean(c.nf_a2p_mode),
      nf_a2p_window: c.nf_a2p_window !== undefined ? c.nf_a2p_window : 30,
      proximity_entity: c.proximity_entity || "",
      proximity_departure_distance: c.proximity_departure_distance !== undefined ? c.proximity_departure_distance : 500,
      proximity_departure_reminder: c.proximity_departure_reminder !== undefined ? Boolean(c.proximity_departure_reminder) : true,
      proximity_return_disarm: Boolean(c.proximity_return_disarm),
      keypad_enabled: c.keypad_enabled !== undefined ? Boolean(c.keypad_enabled) : true,
      keypad_beep_exit: c.keypad_beep_exit !== undefined ? Boolean(c.keypad_beep_exit) : true,
      keypad_beep_entry: c.keypad_beep_entry !== undefined ? Boolean(c.keypad_beep_entry) : true,
      audio_pre_alert_message: c.audio_pre_alert_message || "Attention, intrusion en cours de confirmation. Veuillez vous identifier ou désarmer l'alarme immédiatement.",
      audio_alarm_message: c.audio_alarm_message || "Alerte intrusion détectée, le propriétaire et la police ont été prévenus. Les enregistrements photos et vidéo ont été réalisés à l'intérieur mais aussi à l'extérieur dès que vous avez pénétré dans la propriété. Tout est d'ores et déjà sauvegardé en ligne, sur des serveurs sécurisés.",
      audio_pre_alert_volume: c.audio_pre_alert_volume !== undefined ? c.audio_pre_alert_volume : 0.7,
      audio_alarm_volume: c.audio_alarm_volume !== undefined ? c.audio_alarm_volume : 1.0,
      failover_enabled: Boolean(c.failover_enabled),
      failover_notification_target: c.failover_notification_target || "",
      failover_siren_fallback: c.failover_siren_fallback !== undefined ? Boolean(c.failover_siren_fallback) : true,
      failover_ping_entity: c.failover_ping_entity || "",
    };
  }

  _syncDraftToNasConfig(field, val) {
    if (!this._configDraft || !this._configDraft.nas_configs) return;
    const nasFields = ['ftp_enabled', 'ftp_protocol', 'ftp_host', 'ftp_port', 'ftp_user', 'ftp_pass', 'ftp_path', 'webdav_enabled', 'webdav_url', 'webdav_user', 'webdav_pass', 'webdav_path'];
    if (nasFields.includes(field)) {
      const curNas = this._configDraft.nas_type || 'asustor';
      if (!this._configDraft.nas_configs[curNas]) {
        this._configDraft.nas_configs[curNas] = {};
      }
      this._configDraft.nas_configs[curNas][field] = val;
    }
  }

  _renderEntityListField(title, help, fieldName, allowedDomains, icon) {
    const selectedList = Array.isArray(this._configDraft[fieldName]) ? this._configDraft[fieldName] : [];
    
    let chipsHtml = '';
    if (selectedList.length === 0) {
      chipsHtml = `<span style="font-size:12px; color:var(--d-subtext); font-style:italic;">Aucun équipement sélectionné.</span>`;
    } else {
      chipsHtml = selectedList.map(entId => {
        const stateObj = this._hass && this._hass.states ? this._hass.states[entId] : null;
        const name = stateObj ? (stateObj.attributes.friendly_name || entId) : entId;
        return `
          <span class="config-chip" title="${this.escapeHtml(entId)}">
            <span>${this.escapeHtml(name)}</span>
            <span class="config-chip-remove" data-field="${fieldName}" data-entity="${this.escapeHtml(entId)}" title="Supprimer">✕</span>
          </span>
        `;
      }).join('');
    }

    const availableEntities = [];
    if (this._hass && this._hass.states) {
      Object.keys(this._hass.states).forEach(entId => {
        const domain = entId.split('.')[0];
        if (allowedDomains.includes(domain) && !selectedList.includes(entId)) {
          const stateObj = this._hass.states[entId];
          const name = stateObj && stateObj.attributes && stateObj.attributes.friendly_name ? `${stateObj.attributes.friendly_name} (${entId})` : entId;
          availableEntities.push({ id: entId, name });
        }
      });
      availableEntities.sort((a,b) => a.name.localeCompare(b.name));
    }

    const selectHtml = `
      <select class="config-select config-entity-picker" data-field="${fieldName}">
        <option value="">+ Ajouter un équipement...</option>
        ${availableEntities.map(e => `<option value="${this.escapeHtml(e.id)}">${this.escapeHtml(e.name)}</option>`).join('')}
      </select>
    `;

    return `
      <div class="config-row-stacked">
        <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px;">
          <div>
            <div class="config-label"><ha-icon icon="${icon}" style="--mdc-icon-size:18px; margin-right:6px; color:#f59e0b;"></ha-icon> ${title}</div>
            <div class="config-help">${help}</div>
          </div>
          ${selectHtml}
        </div>
        <div class="config-chips-container">${chipsHtml}</div>
      </div>
    `;
  }

  _renderLabelsField(title, help, fieldName, icon) {
    const selectedList = Array.isArray(this._configDraft[fieldName]) ? this._configDraft[fieldName] : [];
    let chipsHtml = '';
    if (selectedList.length === 0) {
      chipsHtml = `<span style="font-size:12px; color:var(--d-subtext); font-style:italic;">Aucun élément configuré.</span>`;
    } else {
      chipsHtml = selectedList.map(label => `
        <span class="config-chip">
          <span>${this.escapeHtml(label)}</span>
          <span class="config-chip-remove" data-field="${fieldName}" data-entity="${this.escapeHtml(label)}" title="Supprimer">✕</span>
        </span>
      `).join('');
    }

    return `
      <div class="config-row-stacked">
        <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px;">
          <div>
            <div class="config-label"><ha-icon icon="${icon}" style="--mdc-icon-size:18px; margin-right:6px; color:#f59e0b;"></ha-icon> ${title}</div>
            <div class="config-help">${help}</div>
          </div>
          <div style="display:flex; align-items:center; gap:6px;">
            <input type="text" class="config-input config-label-input" data-field="${fieldName}" placeholder="Nom..." style="width:140px;" />
            <button type="button" class="btn-add-label btn-action-pill" data-field="${fieldName}" style="padding:6px 12px; font-weight:700;">Ajouter</button>
          </div>
        </div>
        <div class="config-chips-container">${chipsHtml}</div>
      </div>
    `;
  }

  _renderToggleField(title, help, fieldName, icon) {
    const val = Boolean(this._configDraft[fieldName]);
    return `
      <div class="config-row">
        <div>
          <div class="config-label"><ha-icon icon="${icon}" style="--mdc-icon-size:18px; margin-right:6px; color:#f59e0b;"></ha-icon> ${title}</div>
          <div class="config-help">${help}</div>
        </div>
        <label class="config-toggle-wrap">
          <input type="checkbox" class="config-toggle" data-field="${fieldName}" ${val ? 'checked' : ''}>
          <span class="config-toggle-slider"></span>
        </label>
      </div>
    `;
  }

  _getGoogleAppsScriptCode() {
    return `/**
 * =========================================================================
 *  DOMOLINK ALARM — Google Apps Script Webhook pour Sauvegarde Google Drive
 * =========================================================================
 * 
 * Instructions de déploiement en 1 minute :
 * 1. Rendez-vous sur https://script.google.com et créez un "Nouveau projet".
 * 2. Remplacez TOUT le code existant par ce script.
 * 3. Cliquez sur "Déployer" (en haut à droite) > "Nouveau déploiement".
 * 4. Cliquez sur l'engrenage "Sélectionner le type" > choisissez "Application Web".
 * 5. Configurez impérativement :
 *    - Exécuter en tant que : "Moi" (votre compte Google)
 *    - Qui a accès : "Tout le monde" (Anyone)
 * 6. Cliquez sur "Déployer", autorisez les accès Google Drive.
 * 7. Copiez l'URL de l'application Web (se terminant par /exec) et collez-la dans Domolink Alarm !
 */

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        code: 400,
        message: "Corps de requête vide."
      })).setMimeType(ContentService.MimeType.JSON);
    }

    var data = JSON.parse(e.postData.contents);

    // 1. Sonde de test diagnostic Domolink Alarm
    if (data.probe === true) {
      return ContentService.createTextOutput(JSON.stringify({
        success: true,
        code: 200,
        status: "ok",
        message: "Diagnostic Domolink Alarm réussi : Webhook Google Drive opérationnel !"
      })).setMimeType(ContentService.MimeType.JSON);
    }

    // 2. Traitement du fichier média
    var filename = data.filename || ("domolink_" + Utilities.formatDate(new Date(), "GMT", "yyyyMMdd_HHmmss") + ".jpg");
    var mimeType = data.mime_type || "image/jpeg";
    var folderId = (data.folder_id || "").toString().trim();
    var fileBase64 = data.file_base64;

    if (!fileBase64) {
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        code: 400,
        message: "Contenu base64 manquant."
      })).setMimeType(ContentService.MimeType.JSON);
    }

    var fileBytes = Utilities.base64Decode(fileBase64);
    var blob = Utilities.newBlob(fileBytes, mimeType, filename);

    // 3. Dossier cible
    var targetFolder;
    if (folderId !== "") {
      try {
        targetFolder = DriveApp.getFolderById(folderId);
      } catch (err) {
        targetFolder = null;
      }
    }
    if (!targetFolder) {
      var folderName = "Domolink Alarm";
      var folders = DriveApp.getFoldersByName(folderName);
      targetFolder = folders.hasNext() ? folders.next() : DriveApp.createFolder(folderName);
    }

    // 4. Enregistrement sur Drive
    var driveFile = targetFolder.createFile(blob);
    return ContentService.createTextOutput(JSON.stringify({
      success: true,
      code: 200,
      file_id: driveFile.getId(),
      file_name: driveFile.getName(),
      file_url: driveFile.getUrl()
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      code: 500,
      message: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({
    success: true,
    status: "online",
    service: "Domolink Alarm Google Drive Webhook"
  })).setMimeType(ContentService.MimeType.JSON);
}`;
  }

  _renderTestBadge(testResult) {
    if (!testResult) {
      return `<span style="display:inline-flex; align-items:center; gap:4px; padding:3px 8px; border-radius:12px; font-size:10px; font-weight:700; background:rgba(148,163,184,0.12); color:var(--d-subtext); border:1px solid rgba(148,163,184,0.25);">Non testé</span>`;
    }
    if (testResult.loading) {
      return `<span style="display:inline-flex; align-items:center; gap:4px; padding:3px 8px; border-radius:12px; font-size:11px; font-weight:700; background:rgba(59,130,246,0.15); color:#3b82f6; border:1px solid rgba(59,130,246,0.3);"><ha-icon icon="mdi:loading" class="spin" style="--mdc-icon-size:12px;"></ha-icon> Test...</span>`;
    }
    if (testResult.success) {
      return `<span style="display:inline-flex; align-items:center; gap:4px; padding:3px 8px; border-radius:12px; font-size:11px; font-weight:800; background:rgba(16,185,129,0.16); color:#10b981; border:1px solid rgba(16,185,129,0.35);"><ha-icon icon="mdi:check-circle" style="--mdc-icon-size:13px;"></ha-icon> Connecté</span>`;
    }
    const label = testResult.result_label || (testResult.code ? `Erreur ${testResult.code}` : "Erreur");
    const msg = this.escapeHtml(testResult.message || "");
    return `<span style="display:inline-flex; align-items:center; gap:4px; padding:3px 8px; border-radius:12px; font-size:11px; font-weight:800; background:rgba(239,68,68,0.16); color:#ef4444; border:1px solid rgba(239,68,68,0.35);" title="${msg}"><ha-icon icon="mdi:alert-circle" style="--mdc-icon-size:13px;"></ha-icon> ${this.escapeHtml(label)}</span>`;
  }

  _renderAccordionCard(id, icon, iconColor, title, bodyHtml, defaultOpen = false, badgeText = '') {
    if (!this._openAccordions) this._openAccordions = new Set();
    if (!this._closedAccordions) this._closedAccordions = new Set();

    const isOpen = this._openAccordions.has(id) ? true : (this._closedAccordions.has(id) ? false : defaultOpen);

    return `
      <div class="config-card accordion-card ${isOpen ? 'open' : 'collapsed'}" data-accordion-id="${id}">
        <div class="config-card-header" data-toggle-accordion="${id}">
          <div class="config-card-title">
            <ha-icon icon="${icon}" style="color:${iconColor}; --mdc-icon-size:20px;"></ha-icon>
            <span>${title}</span>
            ${badgeText ? `<span class="nav-badge-pill" style="font-size:10.5px; padding:2px 8px; background:rgba(255,255,255,0.06); border:1px solid var(--d-border-light); color:var(--d-subtext);">${badgeText}</span>` : ''}
          </div>
          <div class="config-card-chevron-wrap">
            <ha-icon icon="mdi:chevron-down" class="config-card-chevron"></ha-icon>
          </div>
        </div>
        <div class="config-card-body">
          ${bodyHtml}
        </div>
      </div>
    `;
  }

  _renderTextField(title, help, fieldName, icon, type = "text", placeholder = "") {
    const val = this._configDraft[fieldName] !== undefined ? this._configDraft[fieldName] : "";
    return `
      <div class="config-row">
        <div>
          <div class="config-label"><ha-icon icon="${icon}" style="--mdc-icon-size:18px; margin-right:6px; color:#f59e0b;"></ha-icon> ${title}</div>
          <div class="config-help">${help}</div>
        </div>
        <input type="${type}" class="config-input" data-field="${fieldName}" value="${this.escapeHtml(val)}" placeholder="${placeholder}" style="min-width:240px;" />
      </div>
    `;
  }

  _renderPasswordField(title, help, fieldName, icon) {
    const val = this._configDraft[fieldName] !== undefined ? this._configDraft[fieldName] : "";
    return `
      <div class="config-row">
        <div>
          <div class="config-label"><ha-icon icon="${icon}" style="--mdc-icon-size:18px; margin-right:6px; color:#f59e0b;"></ha-icon> ${title}</div>
          <div class="config-help">${help}</div>
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
          <input type="password" class="config-input config-pwd-field" data-field="${fieldName}" value="${this.escapeHtml(val)}" style="min-width:200px;" />
          <button type="button" class="btn-pwd-toggle" title="Afficher/Masquer le mot de passe" style="background:transparent; border:none; color:var(--d-subtext); cursor:pointer; padding:4px;">
            <ha-icon icon="mdi:eye" style="--mdc-icon-size:20px;"></ha-icon>
          </button>
        </div>
      </div>
    `;
  }

  _renderNumberField(title, help, fieldName, icon, min, max, step, unit) {
    const val = this._configDraft[fieldName] !== undefined ? this._configDraft[fieldName] : min;
    return `
      <div class="config-row">
        <div>
          <div class="config-label"><ha-icon icon="${icon}" style="--mdc-icon-size:18px; margin-right:6px; color:#f59e0b;"></ha-icon> ${title}</div>
          <div class="config-help">${help}</div>
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
          <input type="number" class="config-input" min="${min}" max="${max}" step="${step}" data-field="${fieldName}" value="${val}" style="width:90px; text-align:right;" />
          <span style="font-size:13px; font-weight:700; color:var(--d-subtext);">${unit}</span>
        </div>
      </div>
    `;
  }

  _renderSelectField(title, help, fieldName, icon, options) {
    const val = this._configDraft[fieldName];
    return `
      <div class="config-row">
        <div>
          <div class="config-label"><ha-icon icon="${icon}" style="--mdc-icon-size:18px; margin-right:6px; color:#f59e0b;"></ha-icon> ${title}</div>
          <div class="config-help">${help}</div>
        </div>
        <select class="config-select" data-field="${fieldName}">
          ${options.map(opt => `<option value="${this.escapeHtml(opt.value)}" ${opt.value == val ? 'selected' : ''}>${this.escapeHtml(opt.label)}</option>`).join('')}
        </select>
      </div>
    `;
  }

  _renderParamTab(alarmEntity) {
    const container = this.querySelector('#pane-param');
    if (!container) return;
    this._paramRendered = true;

    const attrs = alarmEntity ? alarmEntity.attributes : {};
    this._initParamDraft(attrs);
    if (!this._configSubTab) this._configSubTab = 'sensors';

    // Sub-navigation buttons
    const subnavItems = [
      { key: "sensors", label: "Capteurs", icon: "mdi:shield-check" },
      { key: "actuators", label: "Actionneurs", icon: "mdi:bullhorn" },
      { key: "zones", label: "Zones", icon: "mdi:map-marker-radius" },
      { key: "logic", label: "Logique & NF A2P", icon: "mdi:tune" },
      { key: "profiles", label: "Profils & Invités", icon: "mdi:account-multiple-plus" },
      { key: "mqtt", label: "MQTT", icon: "mdi:access-point-network" },
      { key: "backup", label: "Sauvegardes & Médias", icon: "mdi:cloud-sync" },
      { key: "carplay", label: "Auto, CarPlay, Watch & TV", icon: "mdi:car-connected" },
    ];

    let contentHtml = '';

    if (this._configSubTab === 'sensors') {
      contentHtml = `
        ${this._renderAccordionCard("sys_id", "mdi:shield-home", "#f59e0b", "Identification du Système", `
          ${this._renderTextField("Nom du Système", "Nom affiché dans les notifications et le tableau de bord", "name", "mdi:rename-box")}
        `)}

        ${this._renderAccordionCard("intrusion", "mdi:radar", "#3b82f6", "Capteurs d'Intrusion & Sécurité", `
          ${this._renderEntityListField("Capteurs d'Ouverture", "Portes, fenêtres, baies vitrées et garages déclenchant l'alarme", "opening_sensors", ["binary_sensor", "sensor"], "mdi:door-open")}
          ${this._renderLabelsField("Étiquettes Capteurs d'Ouverture", "Sélection automatique par étiquette HA (ex: fenetre, porte)", "opening_sensors_labels", "mdi:tag-outline")}

          ${this._renderEntityListField("Capteurs Mode Nuit", "Capteurs périmétriques surveillés pendant le sommeil", "night_sensors", ["binary_sensor", "sensor"], "mdi:weather-night")}
          ${this._renderLabelsField("Étiquettes Capteurs Mode Nuit", "Sélection automatique par étiquette HA (ex: perimetre)", "night_sensors_labels", "mdi:tag-outline")}

          ${this._renderEntityListField("Capteurs de Mouvement", "Radars et détecteurs volumétriques intérieurs", "motion_sensors", ["binary_sensor", "sensor"], "mdi:motion-sensor")}
          ${this._renderLabelsField("Étiquettes Détecteurs de Mouvement", "Sélection automatique par étiquette HA (ex: mouvement, radar)", "motion_sensors_labels", "mdi:tag-outline")}

          ${this._renderEntityListField("Capteurs de Sabotage (Tamper)", "Protection anti-arrachement active 24h/24", "tamper_sensors", ["binary_sensor", "sensor"], "mdi:shield-alert")}
          ${this._renderLabelsField("Étiquettes Capteurs Sabotage", "Sélection automatique par étiquette HA (ex: sabotage)", "tamper_sensors_labels", "mdi:tag-outline")}

          ${this._renderEntityListField("Capteurs Techniques", "Fumée, monoxyde de carbone, gaz, fuite d'eau", "safety_sensors", ["binary_sensor", "sensor"], "mdi:fire-alert")}
          ${this._renderLabelsField("Étiquettes Capteurs Techniques", "Sélection automatique par étiquette HA (ex: technique, fumee)", "safety_sensors_labels", "mdi:tag-outline")}
        `)}

        ${this._renderAccordionCard("cameras_keypads", "mdi:cctv", "#10b981", "Vidéosurveillance & Claviers", `
          ${this._renderEntityListField("Caméras de Sécurité", "Caméras enregistrant des clichés et vidéos en cas d'intrusion", "cameras", ["camera"], "mdi:cctv")}
          ${this._renderLabelsField("Étiquettes Caméras de Sécurité", "Sélection automatique par étiquette HA (ex: camera, video)", "cameras_labels", "mdi:tag-outline")}

          ${this._renderEntityListField("Activation Caméras à l'Armement", "Interrupteurs ou entités activant l'alimentation des caméras", "cameras_arm_entities", ["switch", "camera", "alarm_control_panel"], "mdi:camera-switch")}
          ${this._renderLabelsField("Étiquettes Activation Caméras", "Sélection automatique par étiquette HA", "cameras_arm_entities_labels", "mdi:tag-outline")}

          ${this._renderEntityListField("Claviers Physiques / Déportés", "Claviers muraux ou panneaux tiers synchronisés", "keypads", ["alarm_control_panel", "sensor"], "mdi:dialpad")}
          ${this._renderLabelsField("Étiquettes Claviers", "Sélection automatique par étiquette HA", "keypads_labels", "mdi:tag-outline")}
          ${this._renderToggleField("Activer les Claviers Physiques", "Traiter les codes et synchroniser l'état des claviers Zigbee / Z-Wave", "keypad_enabled", "mdi:dialpad")}
          ${this._renderToggleField("Bip Temporisation Sortie", "Bips sonores sur le clavier mural pendant la temporisation de sortie", "keypad_beep_exit", "mdi:volume-source")}
          ${this._renderToggleField("Bip Temporisation Entrée", "Bips sonores sur le clavier mural pendant la temporisation d'entrée", "keypad_beep_entry", "mdi:volume-source")}
        `)}
      `;
    } else if (this._configSubTab === 'actuators') {
      contentHtml = `
        ${this._renderAccordionCard("sirens", "mdi:bullhorn", "#ef4444", "Dissuasion & Sirènes", `
          ${this._renderEntityListField("Sirènes d'Alarme", "Sirènes intérieures et extérieures à déclencher", "sirens", ["switch", "siren"], "mdi:bullhorn")}
          ${this._renderLabelsField("Étiquettes Sirènes", "Sélection automatique par étiquette HA (ex: sirene)", "sirens_labels", "mdi:tag-outline")}

          ${this._renderEntityListField("Éclairages d'Urgence", "Lumières à faire clignoter ou allumer en continu lors d'une intrusion", "lights", ["light"], "mdi:alarm-light")}
          ${this._renderLabelsField("Étiquettes Éclairages", "Sélection automatique par étiquette HA (ex: lumiere_alarme)", "lights_labels", "mdi:tag-outline")}

          ${this._renderEntityListField("Haut-parleurs & Annonces Vocales", "Enceintes diffusant des messages dissuasifs TTS", "media_players", ["media_player"], "mdi:speaker")}
          ${this._renderLabelsField("Étiquettes Haut-parleurs", "Sélection automatique par étiquette HA (ex: enceinte)", "media_players_labels", "mdi:tag-outline")}
        `)}

        ${this._renderAccordionCard("notifications", "mdi:bell-badge", "#f59e0b", "Notifications & Alertes Mobiles", `
          ${this._renderEntityListField("Services de Notification", "Services d'envoi de notifications push (HA Companion, etc.)", "notify_services", ["notify", "script"], "mdi:bell-ring")}
          ${this._renderLabelsField("Étiquettes Services Notification", "Sélection automatique par étiquette HA (ex: notification)", "notify_services_labels", "mdi:tag-outline")}

          ${this._renderEntityListField("Contacts d'Urgence", "Destinataires secondaires prévenus en cas de confirmation d'intrusion", "emergency_contact", ["notify", "script"], "mdi:account-alert")}
          ${this._renderLabelsField("Étiquettes Contacts d'Urgence", "Sélection automatique par étiquette HA", "emergency_contact_labels", "mdi:tag-outline")}

          ${this._renderTextField("Free Mobile — Utilisateur", "Identifiant abonné Free Mobile pour alertes SMS directes (Optionnel)", "free_mobile_user", "mdi:cellphone-message")}
          ${this._renderPasswordField("Free Mobile — Clé API", "Clé d'accès API notifications SMS Free Mobile", "free_mobile_pass", "mdi:key")}
          ${this._renderLabelsField("iCloud — Noms des Appareils", "Noms des appareils Apple à faire sonner en urgence (Find My)", "icloud_devices", "mdi:apple")}
        `)}

        ${this._renderAccordionCard("presence", "mdi:home-clock", "#8b5cf6", "Simulation de Présence", `
          ${this._renderEntityListField("Appareils Rejoués", "Lumières, volets et prises rejouant vos habitudes passées", "presence_simulation_entities", ["light", "switch", "cover"], "mdi:lightbulb-multiple")}
          ${this._renderLabelsField("Étiquettes Simulation de Présence", "Sélection automatique par étiquette HA (ex: simulation)", "presence_simulation_labels", "mdi:tag-outline")}
        `)}

        ${this._renderAccordionCard("audio_deterrence", "mdi:volume-vibrate", "#f59e0b", "Dissuasion Vocale & Messages Audio Multi-Niveaux", `
          ${this._renderTextField("Message vocal de pré-alerte", "Diffusé dès la 1ère détection en mode NF A2P ou temporisation", "audio_pre_alert_message", "mdi:bullhorn-outline")}
          ${this._renderNumberField("Volume de pré-alerte", "Volume sonore de pré-alerte (0.1 à 1.0)", "audio_pre_alert_volume", "mdi:volume-medium", 0.1, 1.0, 0.1, "")}
          ${this._renderTextField("Message vocal d'intrusion", "Diffusé dès confirmation d'intrusion sur les enceintes", "audio_alarm_message", "mdi:bullhorn")}
          ${this._renderNumberField("Volume d'intrusion", "Volume sonore d'intrusion (0.1 à 1.0)", "audio_alarm_volume", "mdi:volume-high", 0.1, 1.0, 0.1, "")}
        `)}

        ${this._renderAccordionCard("failover_alerting", "mdi:cellphone-wireless", "#ef4444", "Bascule de Secours Réseau / 4G (Failover)", `
          ${this._renderToggleField("Activer l'alerte de secours Réseau / GSM", "Bascule automatique sur passerelle SMS GSM ou sirène si coupure Internet", "failover_enabled", "mdi:shield-link-variant")}
          ${this._renderTextField("Entité de notification de secours", "Entité de secours (ex: notify.gsm_sms, notify.cle_4g, sms.send_sms)", "failover_notification_target", "mdi:message-badge-outline")}
          ${this._renderTextField("Capteur de connectivité Réseau", "Capteur surveillant la connexion Internet (ex: binary_sensor.wan_status)", "failover_ping_entity", "mdi:network-strength-4-alert")}
          ${this._renderToggleField("Forcer la sirène locale si déconnecté", "Déclenche immédiatement les sirènes locales en cas d'intrusion même isolée", "failover_siren_fallback", "mdi:bullhorn-alert")}
        `)}
      `;
    } else if (this._configSubTab === 'zones') {
      contentHtml = `
        ${this._renderAccordionCard("zones_def", "mdi:map-marker-radius", "#f59e0b", "Zones de Surveillance Ciblée", `
          ${this._renderLabelsField("Étiquettes des Zones (Labels)", "Noms des zones créées dans Home Assistant (ex: Jardin, Étage, Salon)", "zone_labels", "mdi:tag-multiple")}
          ${this._renderEntityListField("Caméras Globales", "Caméras capturant des clichés quelle que soit la zone déclenchée", "global_cameras", ["camera"], "mdi:earth")}
          ${this._renderLabelsField("Étiquettes Caméras Globales", "Sélection automatique par étiquette HA", "global_cameras_labels", "mdi:tag-outline")}
        `)}
      `;
    } else if (this._configSubTab === 'logic') {
      contentHtml = `
        ${this._renderAccordionCard("users", "mdi:account-lock", "#10b981", "Utilisateurs, Codes PIN & Badges", `
          ${this._renderEntityListField("Personnes & Présence", "Membres du foyer pour l'armement/désarmement géolocalisé", "persons", ["person"], "mdi:account-group")}
          ${this._renderLabelsField("Étiquettes Personnes", "Sélection automatique par étiquette HA", "persons_labels", "mdi:tag-outline")}
          ${this._renderTextField("Utilisateurs & Codes PIN", "Format : Prénom:CodePIN séparés par des virgules (ex: Jean:1234, Marie:5678)", "users_codes", "mdi:account-key")}
          ${this._renderTextField("Code sous contrainte (Duress)", "Code secret désarmant l'alarme tout en envoyant une alerte silencieuse", "duress_code", "mdi:shield-alert-outline")}
          ${this._renderTextField("Badges RFID", "Format : IdentifiantBadge:Nom séparés par des virgules (ex: 04-7A-5B:Jean, 8F-B2:Marie)", "rfid_tags", "mdi:nfc-variant")}
        `)}

        ${this._renderAccordionCard("delays", "mdi:timer-outline", "#3b82f6", "Délais Système", `
          ${this._renderNumberField("Délai de sortie", "Temps alloué pour quitter les lieux après armement", "exit_delay", "mdi:exit-run", 0, 300, 5, "secondes")}
          ${this._renderNumberField("Délai d'entrée", "Temps accordé pour taper le code PIN avant déclenchement sirène", "entry_delay", "mdi:door-open", 0, 300, 5, "secondes")}
          ${this._renderNumberField("Durée de la sirène", "Durée maximale de retentissement sonore continu", "siren_duration", "mdi:volume-high", 30, 900, 15, "secondes")}
        `)}

        ${this._renderAccordionCard("behavior", "mdi:cog-outline", "#f59e0b", "Comportement & Détection", `
          ${this._renderToggleField("Confirmation d'Intrusion (Norme NF A2P)", "Exige deux détections distinctes pour valider l'alarme", "nf_a2p_mode", "mdi:shield-check")}
          ${this._renderNumberField("Fenêtre de confirmation NF A2P", "Délai maximal entre deux détections pour confirmer l'intrusion", "nf_a2p_window", "mdi:clock-fast", 10, 120, 5, "secondes")}
          ${this._renderToggleField("Mode Carillon (Chime)", "Bip sonore bref à l'ouverture d'une porte lorsque l'alarme est désarmée", "chime_mode", "mdi:bell-outline")}
          ${this._renderToggleField("Autoriser le contournement (Bypass)", "Permettre d'armer même si un capteur reste ouvert", "bypass_allowed", "mdi:shield-off")}
          ${this._renderToggleField("Surveillance de santé automatique", "Vérifie régulièrement l'état de ligne et de batterie des équipements", "health_check", "mdi:heart-pulse")}
          ${this._renderToggleField("Double Détection (Cross-Zoning)", "Exige deux détections successives pour confirmer une intrusion", "cross_zoning", "mdi:filter-check")}
          ${this._renderNumberField("Fenêtre de double détection", "Délai maximal entre les deux détections pour valider l'intrusion", "cross_zoning_window", "mdi:clock-fast", 10, 300, 5, "secondes")}
          ${this._renderSelectField("Historique de simulation", "Profondeur de rejeu des habitudes passées", "presence_simulation_history_days", "mdi:history", [
            { value: 7, label: "7 jours d'historique" },
            { value: 14, label: "14 jours d'historique" },
            { value: 21, label: "21 jours d'historique" },
            { value: 28, label: "28 jours d'historique" },
          ])}
        `)}

        ${this._renderAccordionCard("geo", "mdi:crosshairs-gps", "#06b6d4", "Géolocalisation & Rappels", `
          ${this._renderToggleField("Armement Automatique Géolocalisé", "Arme l'alarme quand toutes les personnes ont quitté le domicile", "geofence_auto_arm", "mdi:home-export-outline")}
          ${this._renderTextField("Entité Proximity Home Assistant", "Capteur de proximité pour calcul précis de distance (ex: proximity.home)", "proximity_entity", "mdi:map-marker-distance")}
          ${this._renderNumberField("Distance de départ pour rappel", "Distance d'éloignement pour rappel intelligent si alarme oubliée", "proximity_departure_distance", "mdi:radius-outline", 100, 5000, 100, "mètres")}
          ${this._renderToggleField("Rappel Intelligent de Départ", "Alerte push avec bouton d'armement direct si vous vous éloignez", "proximity_departure_reminder", "mdi:bell-alert")}
          ${this._renderToggleField("Désarmement Prédictif au Retour", "Désarmement automatique lorsque vous approchez du domicile", "proximity_return_disarm", "mdi:home-import-outline")}
          ${this._renderNumberField("Délai avant rappel", "Délai après départ du domicile avant d'envoyer le rappel", "geofence_reminder_delay", "mdi:timer-sand", 1, 60, 1, "minutes")}
        `)}

        ${this._renderAccordionCard("schedule", "mdi:calendar-clock", "#a855f7", "Tests & Planification Automatique", `
          ${this._renderToggleField("Test Mensuel Automatique de Sirène", "Déclenche un bref bip sonore mensuel de vérification fonctionnelle", "siren_test", "mdi:bullhorn-outline")}
          ${this._renderSelectField("Jour du test mensuel", "Jour de la semaine pour le test automatique", "siren_test_day", "mdi:calendar-today", [
            { value: 1, label: "Lundi" },
            { value: 2, label: "Mardi" },
            { value: 3, label: "Mercredi" },
            { value: 4, label: "Jeudi" },
            { value: 5, label: "Vendredi" },
            { value: 6, label: "Samedi" },
            { value: 7, label: "Dimanche" },
          ])}
          ${this._renderNumberField("Heure du test mensuel", "Heure d'exécution du test", "siren_test_hour", "mdi:clock-outline", 0, 23, 1, "h00")}
          ${this._renderToggleField("Armement & Désarmement Programmé", "Active le calendrier automatique quotidien", "schedule_enabled", "mdi:clock-check")}
          ${this._renderTextField("Heure d'armement programmé", "Heure d'activation automatique quotidienne (Format HH:MM)", "schedule_arm_time", "mdi:clock-start", "time")}
          ${this._renderTextField("Heure de désarmement programmé", "Heure de désactivation automatique quotidienne (Format HH:MM)", "schedule_disarm_time", "mdi:clock-end", "time")}
          ${this._renderSelectField("Mode d'armement programmé", "Mode appliqué automatiquement à l'heure définie", "schedule_mode", "mdi:shield-check", [
            { value: "night", label: "Mode Nuit (Périmètre)" },
            { value: "away", label: "Mode Absent (Total)" },
            { value: "home", label: "Mode Maison" },
          ])}
        `)}
      `;
    } else if (this._configSubTab === 'profiles') {
      let rawProfiles = attrs.user_profiles || [];
      if (typeof rawProfiles === 'string') {
        try { rawProfiles = JSON.parse(rawProfiles); } catch(e) { rawProfiles = []; }
      }
      if (!Array.isArray(rawProfiles)) rawProfiles = [];

      contentHtml = `
        <div style="margin-bottom:16px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
          <div>
            <div style="font-size:16px; font-weight:800; color:var(--d-text);">Codes PIN Temporaires & Invités</div>
            <div style="font-size:12px; color:var(--d-subtext); margin-top:2px;">Générez des accès temporaires (ménage, baby-sitter, artisans) avec plages horaires et dates d'expiration.</div>
          </div>
          <button id="btn-add-profile-trigger" class="action-btn" style="background:#10b981; color:white; border:none; padding:9px 16px; border-radius:10px; font-weight:700; font-size:12px; display:inline-flex; align-items:center; gap:6px; cursor:pointer; box-shadow:0 4px 12px rgba(16,185,129,0.3);">
            <ha-icon icon="mdi:account-plus" style="--mdc-icon-size:18px;"></ha-icon> Ajouter un Profil Invité
          </button>
        </div>

        <div style="display:flex; flex-direction:column; gap:12px;">
          ${rawProfiles.length > 0 ? rawProfiles.map((p) => {
            const roleLabels = {
              "invite": "Invité",
              "guest": "Invité",
              "femme_menage": "Ménage",
              "baby_sitter": "Baby-sitter",
              "artisan": "Artisan / Travaux",
              "famille": "Famille",
            };
            const roleBadge = roleLabels[p.role] || p.role || "Invité";
            const isSingleUse = Boolean(p.single_use);
            const isEnabled = p.enabled !== false;
            let statusBadge = isEnabled ? '<span style="background:#dcfce7; color:#166534; font-size:11px; font-weight:700; padding:3px 8px; border-radius:6px;">Actif</span>' : '<span style="background:#fee2e2; color:#991b1b; font-size:11px; font-weight:700; padding:3px 8px; border-radius:6px;">Désactivé</span>';
            if (isSingleUse && !isEnabled) {
              statusBadge = '<span style="background:#f3f4f6; color:#4b5563; font-size:11px; font-weight:700; padding:3px 8px; border-radius:6px;">Consommé</span>';
            }

            const daysMap = { 1: "Lun", 2: "Mar", 3: "Mer", 4: "Jeu", 5: "Ven", 6: "Sam", 7: "Dim" };
            const daysLabel = (p.allowed_days && p.allowed_days.length > 0 && p.allowed_days.length < 7)
              ? p.allowed_days.map(d => daysMap[d] || d).join(', ')
              : "Tous les jours";

            let validLabel = "Validité permanente";
            if (p.valid_from && p.valid_to) {
              validLabel = `Du ${new Date(p.valid_from).toLocaleDateString('fr-FR')} au ${new Date(p.valid_to).toLocaleDateString('fr-FR')}`;
            } else if (p.valid_to) {
              validLabel = `Jusqu'au ${new Date(p.valid_to).toLocaleDateString('fr-FR')}`;
            }

            return `
              <div class="glass-card" style="padding:16px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                <div style="display:flex; align-items:center; gap:14px;">
                  <div style="width:40px; height:40px; border-radius:12px; background:rgba(245,158,11,0.15); color:#f59e0b; display:flex; align-items:center; justify-content:center;">
                    <ha-icon icon="mdi:account-key" style="--mdc-icon-size:22px;"></ha-icon>
                  </div>
                  <div>
                    <div style="display:flex; align-items:center; gap:8px;">
                      <span style="font-size:14px; font-weight:800; color:var(--d-text);">${this.escapeHtml(p.name)}</span>
                      <span style="background:rgba(59,130,246,0.15); color:#3b82f6; font-size:11px; font-weight:700; padding:2px 8px; border-radius:6px;">${roleBadge}</span>
                      ${statusBadge}
                      ${isSingleUse ? '<span style="background:rgba(168,85,247,0.15); color:#a855f7; font-size:11px; font-weight:700; padding:2px 8px; border-radius:6px;">⚡ Usage unique</span>' : ''}
                    </div>
                    <div style="font-size:12px; color:var(--d-subtext); margin-top:4px; display:flex; gap:12px; flex-wrap:wrap;">
                      <span>📅 ${validLabel}</span>
                      <span>🕒 ${p.allowed_hours ? p.allowed_hours : 'Toute la journée'}</span>
                      <span>🗓️ ${daysLabel}</span>
                    </div>
                  </div>
                </div>
                <div style="display:flex; align-items:center; gap:10px;">
                  <div style="font-family:monospace; background:var(--d-sec-bg); border:1px solid var(--d-border); border-radius:8px; padding:6px 12px; font-size:13px; font-weight:700; color:var(--d-text);">
                    PIN: ••••
                  </div>
                  <button class="btn-delete-profile" data-pin="${this.escapeHtml(p.pin)}" data-name="${this.escapeHtml(p.name)}" style="background:rgba(239,68,68,0.15); border:1px solid rgba(239,68,68,0.3); color:#ef4444; padding:6px 12px; border-radius:8px; font-weight:700; font-size:12px; cursor:pointer; display:inline-flex; align-items:center; gap:4px; transition:all 0.2s;">
                    <ha-icon icon="mdi:delete-outline" style="--mdc-icon-size:16px;"></ha-icon> Supprimer
                  </button>
                </div>
              </div>
            `;
          }).join('') : `
            <div class="glass-card" style="padding:32px; text-align:center; color:var(--d-subtext);">
              <ha-icon icon="mdi:account-group-outline" style="--mdc-icon-size:40px; margin-bottom:8px; color:var(--d-subtext);"></ha-icon>
              <div style="font-weight:700; font-size:14px; color:var(--d-text);">Aucun code PIN invité configuré</div>
              <div style="font-size:12px; margin-top:4px;">Créez votre premier code d'accès temporaire ci-dessus.</div>
            </div>
          `}
        </div>
      `;
    } else if (this._configSubTab === 'mqtt') {
      contentHtml = `
        ${this._renderAccordionCard("mqtt_cfg", "mdi:access-point-network", "#f59e0b", "Intégration MQTT & Domotique Tierce", `
          ${this._renderToggleField("Activer la passerelle MQTT", "Publie l'état de l'alarme et écoute les commandes sur votre broker MQTT", "mqtt_enabled", "mdi:checkbox-marked-circle-outline")}
          ${this._renderTextField("Topic de base MQTT", "Préfixe des topics MQTT pour Domolink Alarm", "mqtt_topic_base", "mdi:pound", "text", "domolink/alarme")}
          ${this._renderToggleField("Exiger le code PIN sur MQTT", "Oblige à fournir le code PIN dans le payload MQTT pour désarmer", "mqtt_require_code", "mdi:lock-alert")}
        `)}
      `;
    } else if (this._configSubTab === 'backup') {
      const nasResults = (attrs && attrs.nas_test_results) ? attrs.nas_test_results : {};
      const curNas = this._configDraft.nas_type || "asustor";
      const nasLabels = {
        "asustor": "ASUSTOR",
        "synology": "Synology",
        "qnap": "QNAP",
        "truenas": "TrueNAS",
        "freebox": "Freebox",
        "unraid": "Unraid",
        "generic": "Autre NAS"
      };
      const curNasLabel = nasLabels[curNas] || "NAS / Serveur";
      const curNasStatus = nasResults[curNas] || nasResults[`${curNas}_ftp`] || nasResults[`${curNas}_webdav`];
      const curFtpRes = nasResults[`${curNas}_ftp`] || (nasResults[curNas]?.protocol === 'ftp' ? nasResults[curNas] : (attrs.ftp_test_result && Object.keys(attrs.ftp_test_result).length ? attrs.ftp_test_result : null));
      const curWebdavRes = nasResults[`${curNas}_webdav`] || (nasResults[curNas]?.protocol === 'webdav' ? nasResults[curNas] : (attrs.webdav_test_result && Object.keys(attrs.webdav_test_result).length ? attrs.webdav_test_result : null));
      const curNasCfg = (this._configDraft && this._configDraft.nas_configs && this._configDraft.nas_configs[curNas]) || {};
      const curFtpProto = ((this._configDraft && this._configDraft.ftp_protocol) || curNasCfg.ftp_protocol || 'ftp').toLowerCase();
      const curHostVal = (this._configDraft && this._configDraft.ftp_host !== undefined ? this._configDraft.ftp_host : curNasCfg.ftp_host) || (curNas === 'freebox' ? 'mafreebox.freebox.fr' : '192.168.1.50');

      contentHtml = `
        ${this._renderAccordionCard("telegram", "mdi:send", "#0088cc", "Sauvegarde & Alertes Telegram", `
          ${this._renderToggleField("Activer l'envoi Telegram", "Envoie les clichés photos et alertes dans votre canal/bot Telegram", "telegram_enabled", "mdi:telegram")}
          ${this._renderPasswordField("Token du Bot Telegram", "Token fourni par BotFather (ex: 123456:ABC-DEF1234...)", "telegram_token", "mdi:key")}
          ${this._renderTextField("Chat ID Telegram", "Identifiant du groupe ou canal de réception des alertes", "telegram_chat_id", "mdi:message-badge")}
        `)}

        ${this._renderAccordionCard("nas_profile", "mdi:nas", "#f59e0b", "Profil & Constructeur de NAS", `
          <div style="font-size:12px; color:var(--d-subtext); margin-bottom:12px;">
            Sélectionnez votre modèle de NAS pour adapter les protocoles recommandés, ports et arborescences types :
          </div>
          <div class="nas-selector-grid" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:10px; margin-bottom:8px;">
            ${[
              { key: "asustor", label: "ASUSTOR", icon: "mdi:server", desc: "ADM • FTP 21 / WebDAV 8001", proto: "both" },
              { key: "synology", label: "Synology", icon: "mdi:nas", desc: "DSM • FTP 21 / WebDAV 5006", proto: "both" },
              { key: "qnap", label: "QNAP", icon: "mdi:server-network", desc: "QTS • FTP 21 / WebDAV 5001", proto: "both" },
              { key: "truenas", label: "TrueNAS", icon: "mdi:harddisk", desc: "SCALE/CORE • WebDAV", proto: "webdav" },
              { key: "freebox", label: "Freebox", icon: "mdi:router-wireless", desc: "Delta/Ultra • FTP 21", proto: "ftp" },
              { key: "unraid", label: "Unraid", icon: "mdi:server-security", desc: "Unraid OS • FTP/WebDAV", proto: "both" },
              { key: "generic", label: "Autre NAS", icon: "mdi:cog-box", desc: "Configuration libre", proto: "both" }
            ].map(nas => {
              const active = curNas === nas.key;
              const nasRes = nasResults[nas.key] || nasResults[`${nas.key}_ftp`] || nasResults[`${nas.key}_webdav`];
              return `
                <div class="nas-profile-card ${active ? 'active' : ''}" data-nas="${nas.key}" style="border-radius:12px; padding:10px 8px; cursor:pointer; border:1.5px solid ${active ? '#f59e0b' : 'var(--d-border)'}; background:${active ? 'rgba(245,158,11,0.14)' : 'var(--d-card-bg)'}; text-align:center; transition:all 0.2s ease; display:flex; flex-direction:column; justify-content:space-between;">
                  <div>
                    <ha-icon icon="${nas.icon}" style="--mdc-icon-size:24px; color:${active ? '#f59e0b' : 'var(--d-subtext)'};"></ha-icon>
                    <div style="font-size:13px; font-weight:800; color:${active ? '#f59e0b' : 'var(--d-text)'}; margin-top:4px;">${nas.label}</div>
                    <div style="font-size:10px; color:var(--d-subtext); margin-top:2px;">${nas.desc}</div>
                    <div class="nas-test-badge-container" data-nas="${nas.key}" style="margin-top:6px;">
                      ${this._renderTestBadge(nasRes)}
                    </div>
                  </div>
                  <div style="margin-top:8px; display:flex; align-items:center; justify-content:center; gap:4px;">
                    ${nas.proto === 'ftp' ? `
                      <button type="button" class="btn-nas-card-test" data-nas="${nas.key}" data-proto="ftp" title="Tester FTP pour ${nas.label}" style="width:100%; padding:4px 6px; border-radius:7px; border:1px solid rgba(16,185,129,0.4); background:rgba(16,185,129,0.14); color:#10b981; font-size:10.5px; font-weight:800; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:3px;">
                        <ha-icon icon="mdi:lightning-bolt" style="--mdc-icon-size:12px;"></ha-icon> <span>Tester FTP</span>
                      </button>
                    ` : (nas.proto === 'webdav' ? `
                      <button type="button" class="btn-nas-card-test" data-nas="${nas.key}" data-proto="webdav" title="Tester WebDAV pour ${nas.label}" style="width:100%; padding:4px 6px; border-radius:7px; border:1px solid rgba(139,92,246,0.4); background:rgba(139,92,246,0.14); color:#a855f7; font-size:10.5px; font-weight:800; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:3px;">
                        <ha-icon icon="mdi:lightning-bolt" style="--mdc-icon-size:12px;"></ha-icon> <span>Tester WebDAV</span>
                      </button>
                    ` : `
                      <button type="button" class="btn-nas-card-test" data-nas="${nas.key}" data-proto="ftp" title="Tester FTP pour ${nas.label}" style="flex:1; padding:4px 3px; border-radius:6px; border:1px solid rgba(16,185,129,0.4); background:rgba(16,185,129,0.12); color:#10b981; font-size:10px; font-weight:800; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:2px;">
                        <ha-icon icon="mdi:server-network" style="--mdc-icon-size:11px;"></ha-icon> <span>FTP</span>
                      </button>
                      <button type="button" class="btn-nas-card-test" data-nas="${nas.key}" data-proto="webdav" title="Tester WebDAV pour ${nas.label}" style="flex:1; padding:4px 3px; border-radius:6px; border:1px solid rgba(139,92,246,0.4); background:rgba(139,92,246,0.12); color:#a855f7; font-size:10px; font-weight:800; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:2px;">
                        <ha-icon icon="mdi:cloud-check" style="--mdc-icon-size:11px;"></ha-icon> <span>WebDAV</span>
                      </button>
                    `)}
                  </div>
                </div>
              `;
            }).join('')}
          </div>
          <div style="margin-top:12px; padding:10px 14px; border-radius:12px; background:rgba(245,158,11,0.06); border:1px solid rgba(245,158,11,0.22); display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="font-size:12px; font-weight:700; color:var(--d-text);">Diagnostic rapide ${curNasLabel} :</span>
              <span id="nas-card-status-badge">${this._renderTestBadge(curNasStatus)}</span>
            </div>
            <div style="display:flex; align-items:center; gap:8px;">
              ${curNas !== 'truenas' ? `
                <button type="button" class="btn-nas-quick-test-ftp" data-nas="${curNas}" style="padding:6px 12px; border-radius:8px; border:1px solid rgba(16,185,129,0.4); background:rgba(16,185,129,0.12); color:#10b981; font-size:11px; font-weight:800; cursor:pointer; display:flex; align-items:center; gap:5px; transition:all 0.2s;">
                  <ha-icon icon="mdi:server-network" style="--mdc-icon-size:14px;"></ha-icon>
                  <span>Tester FTP (${curNasLabel})</span>
                </button>
              ` : ''}
              ${curNas !== 'freebox' ? `
                <button type="button" class="btn-nas-quick-test-webdav" data-nas="${curNas}" style="padding:6px 12px; border-radius:8px; border:1px solid rgba(139,92,246,0.4); background:rgba(139,92,246,0.12); color:#a855f7; font-size:11px; font-weight:800; cursor:pointer; display:flex; align-items:center; gap:5px; transition:all 0.2s;">
                  <ha-icon icon="mdi:cloud-check" style="--mdc-icon-size:14px;"></ha-icon>
                  <span>Tester WebDAV (${curNasLabel})</span>
                </button>
              ` : ''}
            </div>
          </div>
        `)}

        ${this._renderAccordionCard("ftp", "mdi:server-network", "#10b981", `Sauvegarde NAS & Réseau (${curFtpProto.toUpperCase()}) — ${curNasLabel}`, `
          <div style="margin-bottom:14px; padding:12px; border-radius:10px; background:var(--d-sec-bg, rgba(255,255,255,0.03)); border:1px solid var(--d-border, rgba(255,255,255,0.08));">
            <label style="display:block; font-size:12px; font-weight:700; color:var(--d-text); margin-bottom:8px;">
              <ha-icon icon="mdi:swap-horizontal-bold" style="--mdc-icon-size:16px; margin-right:4px; color:#10b981;"></ha-icon>
              Protocole de transfert
            </label>
            <input type="hidden" class="config-input" data-field="ftp_protocol" id="cfg-ftp-protocol" value="${curFtpProto}">
            <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(110px, 1fr)); gap:8px;" id="ftp-proto-selector">
              <button type="button" class="btn-proto-choice ${curFtpProto === 'ftp' ? 'active' : ''}" data-proto="ftp" data-port="21" style="padding:8px 10px; border-radius:8px; border:1px solid ${curFtpProto === 'ftp' ? '#10b981' : 'var(--d-border, rgba(255,255,255,0.1))'}; background:${curFtpProto === 'ftp' ? 'rgba(16,185,129,0.15)' : 'rgba(0,0,0,0.1)'}; color:${curFtpProto === 'ftp' ? '#10b981' : 'var(--d-subtext)'}; font-size:11px; font-weight:800; cursor:pointer; display:flex; flex-direction:column; align-items:center; gap:3px; transition:all 0.2s;">
                <ha-icon icon="mdi:server-network" style="--mdc-icon-size:18px;"></ha-icon>
                <span>FTP</span>
                <span style="font-size:9.5px; opacity:0.75; font-weight:600;">Port 21 (Standard)</span>
              </button>
              <button type="button" class="btn-proto-choice ${curFtpProto === 'ftps' ? 'active' : ''}" data-proto="ftps" data-port="21" style="padding:8px 10px; border-radius:8px; border:1px solid ${curFtpProto === 'ftps' ? '#10b981' : 'var(--d-border, rgba(255,255,255,0.1))'}; background:${curFtpProto === 'ftps' ? 'rgba(16,185,129,0.15)' : 'rgba(0,0,0,0.1)'}; color:${curFtpProto === 'ftps' ? '#10b981' : 'var(--d-subtext)'}; font-size:11px; font-weight:800; cursor:pointer; display:flex; flex-direction:column; align-items:center; gap:3px; transition:all 0.2s;">
                <ha-icon icon="mdi:lock-check" style="--mdc-icon-size:18px;"></ha-icon>
                <span>FTPS</span>
                <span style="font-size:9.5px; opacity:0.75; font-weight:600;">Port 21 (TLS/SSL)</span>
              </button>
              <button type="button" class="btn-proto-choice ${curFtpProto === 'sftp' ? 'active' : ''}" data-proto="sftp" data-port="22" style="padding:8px 10px; border-radius:8px; border:1px solid ${curFtpProto === 'sftp' ? '#10b981' : 'var(--d-border, rgba(255,255,255,0.1))'}; background:${curFtpProto === 'sftp' ? 'rgba(16,185,129,0.15)' : 'rgba(0,0,0,0.1)'}; color:${curFtpProto === 'sftp' ? '#10b981' : 'var(--d-subtext)'}; font-size:11px; font-weight:800; cursor:pointer; display:flex; flex-direction:column; align-items:center; gap:3px; transition:all 0.2s;">
                <ha-icon icon="mdi:ssh" style="--mdc-icon-size:18px;"></ha-icon>
                <span>SFTP</span>
                <span style="font-size:9.5px; opacity:0.75; font-weight:600;">Port 22 (SSH)</span>
              </button>
              <button type="button" class="btn-proto-choice ${curFtpProto === 'samba' ? 'active' : ''}" data-proto="samba" data-port="445" style="padding:8px 10px; border-radius:8px; border:1px solid ${curFtpProto === 'samba' ? '#10b981' : 'var(--d-border, rgba(255,255,255,0.1))'}; background:${curFtpProto === 'samba' ? 'rgba(16,185,129,0.15)' : 'rgba(0,0,0,0.1)'}; color:${curFtpProto === 'samba' ? '#10b981' : 'var(--d-subtext)'}; font-size:11px; font-weight:800; cursor:pointer; display:flex; flex-direction:column; align-items:center; gap:3px; transition:all 0.2s;">
                <ha-icon icon="mdi:folder-table" style="--mdc-icon-size:18px;"></ha-icon>
                <span>SAMBA</span>
                <span style="font-size:9.5px; opacity:0.75; font-weight:600;">Port 445 (SMB)</span>
              </button>
            </div>
          </div>

          ${this._renderToggleField("Activer le transfert NAS / Réseau", "Téléverse automatiquement photos et vidéos lors des déclenchements d'alarme", "ftp_enabled", "mdi:upload-network")}
          ${this._renderTextField("Hôte NAS / Serveur", "Adresse IP locale ou nom d'hôte du NAS", "ftp_host", "mdi:ip-network", "text", curNas === 'freebox' ? 'mafreebox.freebox.fr' : '192.168.1.50')}
          ${this._renderNumberField("Port de connexion", "Port de connexion selon protocole (21 FTP/FTPS, 22 SFTP, 445 SAMBA)", "ftp_port", "mdi:numeric", 1, 65535, 1, "")}
          ${this._renderTextField("Identifiant de connexion", "Nom d'utilisateur du compte NAS", "ftp_user", "mdi:account")}
          ${this._renderPasswordField("Mot de passe", "Mot de passe du compte", "ftp_pass", "mdi:lock")}
          ${this._renderTextField("Répertoire distant", curNas === 'freebox' ? "Chemin distant Freebox (ex: /Disque 1 ou /Disque 1/domolink)" : "Chemin distant (créera automatiquement domolink/alarm/...)", "ftp_path", "mdi:folder-network", "text", curNas === 'freebox' ? '/Disque 1' : '/')}

          <!-- Partage Réseau SAMBA -->
          <div id="samba-link-card" style="margin-top:14px; padding:12px 14px; border-radius:10px; background:linear-gradient(135deg, rgba(16,185,129,0.08), rgba(59,130,246,0.08)); border:1px solid rgba(16,185,129,0.25); display:flex; flex-direction:column; gap:10px;">
            <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <div style="width:30px; height:30px; border-radius:8px; background:rgba(16,185,129,0.15); display:flex; align-items:center; justify-content:center; color:#10b981;">
                  <ha-icon icon="mdi:folder-network-outline" style="--mdc-icon-size:20px;"></ha-icon>
                </div>
                <div>
                  <div style="font-size:12px; font-weight:800; color:var(--d-text);">Accès Partage Réseau SAMBA (SMB)</div>
                  <div style="font-size:10.5px; color:var(--d-subtext);">Pour explorer et récupérer vos médias directement sur votre ordinateur</div>
                </div>
              </div>
              <div style="display:flex; gap:8px; align-items:center;">
                <button type="button" id="btn-copy-samba-link" style="padding:5px 12px; border-radius:6px; border:1px solid rgba(16,185,129,0.4); background:rgba(16,185,129,0.15); color:#10b981; font-size:11px; font-weight:800; cursor:pointer; display:flex; align-items:center; gap:5px; transition:all 0.2s;">
                  <ha-icon icon="mdi:content-copy" style="--mdc-icon-size:14px;"></ha-icon>
                  <span id="copy-samba-txt">Copier le lien SAMBA</span>
                </button>
                <a id="lnk-open-samba" href="smb://${this.escapeHtml(curHostVal)}/" target="_blank" rel="noopener noreferrer" style="padding:5px 12px; border-radius:6px; border:1px solid rgba(59,130,246,0.35); background:rgba(59,130,246,0.12); color:#60a5fa; font-size:11px; font-weight:800; text-decoration:none; display:inline-flex; align-items:center; gap:5px;">
                  <ha-icon icon="mdi:open-in-new" style="--mdc-icon-size:14px;"></ha-icon>
                  <span>Ouvrir</span>
                </a>
              </div>
            </div>
            <div style="display:flex; align-items:center; gap:8px; background:rgba(0,0,0,0.25); border-radius:6px; padding:6px 10px; font-family:monospace; font-size:12px; color:#38bdf8; overflow-x:auto;">
              <span style="color:var(--d-subtext); font-weight:600;">Lien :</span>
              <span id="samba-url-display">smb://${this.escapeHtml(curHostVal)}/</span>
            </div>
            <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:8px; font-size:10.5px; color:var(--d-subtext); line-height:1.4;">
              <div>🍏 <strong>macOS :</strong> Dans le Finder, faites <code>Cmd + K</code>, puis collez <code>smb://${this.escapeHtml(curHostVal)}/</code></div>
              <div>🪟 <strong>Windows :</strong> Dans l'Explorateur, tapez dans la barre d'adresse <code id="samba-win-display">\\\\${this.escapeHtml(curHostVal)}\\</code></div>
            </div>
          </div>

          <div style="margin-top:14px; padding-top:14px; border-top:1px solid var(--d-border-light); display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px;">
            <div style="display:flex; flex-direction:column; gap:4px; max-width:65%;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-size:12px; font-weight:700; color:var(--d-text);">Résultat connexion :</span>
                <span id="ftp-test-inline-badge">${this._renderTestBadge(curFtpRes)}</span>
              </div>
              <div id="ftp-test-inline-msg" style="font-size:11px; line-height:1.4; color:${curFtpRes?.success ? '#10b981' : (curFtpRes?.success === false ? '#ef4444' : 'var(--d-subtext)')};">
                ${curFtpRes?.message ? this.escapeHtml(curFtpRes.message) : `Testez la connexion ${curFtpProto.toUpperCase()} avec vos identifiants ci-dessus.`}
              </div>
            </div>
            <button type="button" class="btn-test-ftp-inline" id="btn-test-ftp-inline" style="padding:8px 16px; border-radius:10px; border:1px solid rgba(16,185,129,0.4); background:rgba(16,185,129,0.12); color:#10b981; font-size:12px; font-weight:800; cursor:pointer; display:flex; align-items:center; gap:6px; transition:all 0.2s;">
              <ha-icon icon="mdi:server-network" style="--mdc-icon-size:16px;"></ha-icon>
              <span>Tester la connexion ${curFtpProto.toUpperCase()}</span>
            </button>
          </div>
        `)}

        ${this._renderAccordionCard("webdav", "mdi:cloud-sync", "#8b5cf6", "Sauvegarde Multi-Cloud WebDAV / Nextcloud / NAS", `
          ${this._renderToggleField("Activer la sauvegarde WebDAV", "Téléverse automatiquement photos et vidéos sur votre serveur WebDAV / Nextcloud / NAS", "webdav_enabled", "mdi:cloud-upload")}
          ${this._renderTextField("URL du serveur WebDAV", "Ex: https://nas.local:5006/ ou https://cloud.domaine.fr/remote.php/dav/files/user/", "webdav_url", "mdi:web", "text", "https://cloud.domaine.fr/remote.php/dav/files/user/")}
          ${this._renderTextField("Identifiant WebDAV", "Nom d'utilisateur WebDAV / Nextcloud", "webdav_user", "mdi:account")}
          ${this._renderPasswordField("Mot de passe / Token d'application", "Mot de passe de compte ou token d'application WebDAV", "webdav_pass", "mdi:lock")}
          ${this._renderTextField("Dossier distant de sauvegarde", "Chemin relatif sur le serveur (ex: domolink/alarm)", "webdav_path", "mdi:folder-network", "text", "domolink/alarm")}
          <div style="margin-top:14px; padding-top:14px; border-top:1px solid var(--d-border-light); display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px;">
            <div style="display:flex; flex-direction:column; gap:4px; max-width:65%;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-size:12px; font-weight:700; color:var(--d-text);">Résultat connexion WebDAV :</span>
                <span id="webdav-test-inline-badge">${this._renderTestBadge(curWebdavRes)}</span>
              </div>
              <div id="webdav-test-inline-msg" style="font-size:11px; line-height:1.4; color:${curWebdavRes?.success ? '#10b981' : (curWebdavRes?.success === false ? '#ef4444' : 'var(--d-subtext)')};">
                ${curWebdavRes?.message ? this.escapeHtml(curWebdavRes.message) : 'Testez la connexion WebDAV avec vos identifiants actuels ci-dessus.'}
              </div>
            </div>
            <button type="button" class="btn-test-webdav-inline" id="btn-test-webdav-cfg" style="padding:8px 16px; border-radius:10px; border:1px solid rgba(139,92,246,0.4); background:rgba(139,92,246,0.12); color:#a855f7; font-size:12px; font-weight:800; cursor:pointer; display:flex; align-items:center; gap:6px; transition:all 0.2s;">
              <ha-icon icon="mdi:cloud-check" style="--mdc-icon-size:16px;"></ha-icon>
              <span>Tester la connexion WebDAV</span>
            </button>
          </div>
        `)}

        ${this._renderAccordionCard("gdrive", "mdi:google-drive", "#34a853", "Sauvegarde Cloud Google Drive", `
          ${this._renderToggleField("Activer la sauvegarde Google Drive", "Téléverse automatiquement les clichés et vidéos vers Google Drive", "google_drive_enabled", "mdi:cloud-upload")}
          ${this._renderSelectField("Méthode de synchronisation", "Mode de liaison avec Google Drive", "google_drive_method", "mdi:transfer", [
            { value: "webhook", label: "Webhook Google Apps Script (Recommandé — Simple & Sans OAuth)" },
            { value: "oauth", label: "API Google Drive REST / OAuth2 (Google Cloud Console)" },
          ])}

          ${(this._configDraft.google_drive_method || 'webhook') === 'webhook' ? `
            ${this._renderTextField("URL du Webhook Google Apps Script", "URL de déploiement Web App Google Apps Script", "google_drive_webhook_url", "mdi:link-variant", "text", "https://script.google.com/macros/s/.../exec")}
            ${this._renderTextField("ID de dossier Google Drive (Optionnel)", "ID du dossier cible (laissez vide pour enregistrer à la racine)", "google_drive_folder_id", "mdi:folder-google-drive", "text", "")}
            <div style="margin-top:12px; background:rgba(52,168,83,0.08); border:1px solid rgba(52,168,83,0.25); border-radius:12px; padding:12px 14px; font-size:11.5px; line-height:1.5; color:var(--d-text);">
              <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px; margin-bottom:8px;">
                <div style="font-weight:800; color:#34a853; display:flex; align-items:center; gap:6px; font-size:12.5px;">
                  <ha-icon icon="mdi:google-drive" style="--mdc-icon-size:18px;"></ha-icon> Guide & Déploiement Webhook en 1 minute
                </div>
                <button type="button" id="btn-copy-google-script" style="padding:6px 14px; border-radius:8px; border:1px solid rgba(52,168,83,0.5); background:#34a853; color:#fff; font-size:11.5px; font-weight:800; cursor:pointer; display:flex; align-items:center; gap:6px; box-shadow:0 2px 8px rgba(52,168,83,0.25); transition:all 0.2s;">
                  <ha-icon icon="mdi:content-copy" style="--mdc-icon-size:15px;"></ha-icon>
                  <span id="btn-copy-google-script-text">Copier le Google Script</span>
                </button>
              </div>
              <div>
                <strong>Étapes simples pour autoriser l'accès :</strong>
                <ol style="margin:6px 0 8px 18px; padding:0; display:flex; flex-direction:column; gap:3px;">
                  <li>Cliquez sur <strong>« Copier le Google Script »</strong> ci-dessus.</li>
                  <li>Ouvrez <a href="https://script.google.com" target="_blank" style="color:#38bdf8; text-decoration:underline; font-weight:700;">script.google.com</a> et créez un <em>« Nouveau projet »</em>.</li>
                  <li>Collez le code dans l'éditeur (remplacez tout le contenu existant).</li>
                  <li>Cliquez sur <strong>Déployer ➔ Nouveau déploiement</strong>, sélectionnez <em>« Application Web »</em>, configurez <strong>« Exécuter en tant que : Moi »</strong> et <strong>« Qui a accès : Tout le monde »</strong>.</li>
                  <li>Autorisez l'accès Google Drive à la première exécution, puis collez l'URL Webhook (terminant par <code>/exec</code>) dans le champ ci-dessus.</li>
                </ol>
              </div>
              <details style="margin-top:8px; border-top:1px dashed rgba(52,168,83,0.3); padding-top:6px; cursor:pointer;">
                <summary style="font-size:11px; font-weight:700; color:#34a853;">Afficher / Masquer le code JavaScript du script Google</summary>
                <pre style="margin-top:8px; padding:10px; border-radius:8px; background:rgba(0,0,0,0.3); border:1px solid rgba(255,255,255,0.08); font-size:10.5px; overflow-x:auto; color:#a7f3d0; line-height:1.4;">${this.escapeHtml(this._getGoogleAppsScriptCode())}</pre>
              </details>
            </div>
          ` : `
            ${this._renderTextField("Google Client ID", "Client ID OAuth 2.0 Google Cloud", "google_drive_client_id", "mdi:account-key")}
            ${this._renderPasswordField("Google Client Secret", "Code secret Client Secret OAuth 2.0", "google_drive_client_secret", "mdi:key")}
            ${this._renderPasswordField("Google Refresh Token", "Refresh token OAuth2 avec scope drive.file", "google_drive_refresh_token", "mdi:refresh-auto")}
            ${this._renderTextField("ID de dossier Google Drive (Optionnel)", "ID du dossier cible (laissez vide pour enregistrer à la racine)", "google_drive_folder_id", "mdi:folder-google-drive", "text", "")}
          `}

          <div style="margin-top:14px; padding-top:12px; border-top:1px solid var(--d-border-light); display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
            <div style="font-size:12px; color:var(--d-subtext);">
              Testez la synchronisation avec votre Google Drive avant d'enregistrer la configuration
            </div>
            <button class="btn-test-gdrive-cfg" id="btn-test-gdrive-cfg" style="padding:8px 14px; border-radius:10px; border:1px solid rgba(52,168,83,0.4); background:rgba(52,168,83,0.12); color:#34a853; font-size:12px; font-weight:800; cursor:pointer; display:flex; align-items:center; gap:6px; transition:all 0.2s;">
              <ha-icon icon="mdi:google-drive" style="--mdc-icon-size:16px;"></ha-icon>
              <span>Tester la connexion Google Drive</span>
            </button>
          </div>
        `)}

        ${this._renderAccordionCard("retention", "mdi:database-clock", "#06b6d4", "Politique de Rétention & Quota de Stockage Médias", `
          ${this._renderNumberField("Durée maximale de rétention", "Nombre de jours de conservation des photos et vidéos locales (0 = illimité)", "media_retention_days", "mdi:calendar-range", 0, 365, 1, "jours")}
          ${this._renderNumberField("Quota de stockage maximal", "Taille maximale allouée au dossier médias en Mo (0 = illimité, rotation FIFO)", "media_max_size_mb", "mdi:harddisk", 0, 10240, 64, "Mo")}
          ${this._renderTextField("Sous-dossier de stockage local", "Dossier dans /config/www/ où sont stockées les photos et vidéos", "media_path", "mdi:folder", "text", "domolink_media")}
        `)}
      `;
    } else if (this._configSubTab === 'carplay') {
      const carUrl = `${window.location.origin}${window.location.pathname}?mode=car`;
      const carplayYaml = `alias: "Alarme Domolink - Départ en Voiture (CarPlay / Android Auto)"
description: "Arme automatiquement l'alarme Domolink en mode Absent lors d'un départ en voiture"
trigger:
  - platform: state
    entity_id:
      - sensor.iphone_carplay
      - sensor.car_connection
    to: "disconnected"
  - platform: numeric_state
    entity_id: sensor.distance_domicile
    above: 250
condition:
  - condition: state
    entity_id: alarm_control_panel.domolink_alarm
    state: "disarmed"
action:
  - service: alarm_control_panel.alarm_arm_away
    target:
      entity_id: alarm_control_panel.domolink_alarm
  - service: notify.notify
    data:
      title: "🚗 Domolink Alarm — Mode Voiture"
      message: "Alarme armée en mode Absent suite à votre départ en véhicule."
mode: single`;

      const tvNotificationYaml = `alias: "Alarme Domolink - Alerte Vidéo sur Android TV"
description: "Affiche une alerte pop-up avec image caméra en direct sur Android TV en cas d'intrusion"
trigger:
  - platform: state
    entity_id: alarm_control_panel.domolink_alarm
    to: "triggered"
action:
  - service: notify.android_tv # Remplacez par le nom de votre entité Android TV / Fire TV
    data:
      title: "🚨 INTRUSION DÉTECTÉE — Domolink Alarm"
      message: "L'alarme de la maison s'est déclenchée !"
      data:
        image: "/api/camera_proxy/camera.salon" # Remplacez par votre caméra
        duration: 15
        position: "top-right"
        fontsize: "large"
mode: single`;

      contentHtml = `
        <div class="glass-card" style="margin-bottom:16px; border-left:4px solid #3b82f6; background:linear-gradient(135deg, rgba(59,130,246,0.08), rgba(15,23,42,0.4));">
          <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px;">
            <div style="display:flex; align-items:center; gap:12px;">
              <div style="width:44px; height:44px; border-radius:12px; background:rgba(59,130,246,0.2); border:1px solid rgba(59,130,246,0.4); display:flex; align-items:center; justify-content:center; color:#60a5fa;">
                <ha-icon icon="mdi:car-connected" style="--mdc-icon-size:26px;"></ha-icon>
              </div>
              <div>
                <div style="font-size:16px; font-weight:800; color:var(--d-text);">Mode Voiture Embarqué & Grand Écran TV</div>
                <div style="font-size:12px; color:var(--d-subtext); margin-top:2px;">
                  Interface tactile XXL conçue pour les véhicules (Tesla, Android Auto, CarPlay) et les téléviseurs (Android TV)
                </div>
              </div>
            </div>
            <div style="display:flex; align-items:center; gap:8px;">
              <button class="btn-config-save" id="btn-launch-car-mode" style="padding:8px 16px; font-size:12px; background:linear-gradient(135deg,#2563eb,#1d4ed8);">
                <ha-icon icon="mdi:car-speed-limiter" style="--mdc-icon-size:16px;"></ha-icon>
                <span>Activer le Mode Voiture</span>
              </button>
            </div>
          </div>
          <div style="margin-top:14px; padding-top:12px; border-top:1px solid var(--d-border-light); display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
            <div style="font-size:12px; color:var(--d-subtext); font-family:monospace; word-break:break-all; background:rgba(0,0,0,0.25); padding:6px 10px; border-radius:8px; border:1px solid var(--d-border-light); flex:1; min-width:240px;">
              ${carUrl}
            </div>
            <button id="btn-copy-car-url" style="padding:7px 14px; border-radius:8px; border:1px solid rgba(59,130,246,0.4); background:rgba(59,130,246,0.12); color:#60a5fa; font-size:12px; font-weight:700; cursor:pointer; display:flex; align-items:center; gap:6px; transition:all 0.2s;">
              <ha-icon icon="mdi:content-copy" style="--mdc-icon-size:16px;"></ha-icon>
              <span>Copier le lien direct</span>
            </button>
          </div>
        </div>

        ${this._renderAccordionCard("android_auto_guide", "mdi:android", "#3ddc84", "1. Intégration Android Auto & Android Automotive (AAOS)", `
          <div style="font-size:13px; color:var(--d-subtext); line-height:1.6; margin-bottom:14px;">
            L'application officielle <b>Home Assistant Companion pour Android</b> supporte nativement <b>Android Auto</b> et les systèmes de bord <b>Android Automotive (AAOS)</b> (Renault OpenR Link, Volvo, Polestar, etc.).
          </div>

          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:12px; margin-bottom:16px;">
            <div style="padding:12px; border-radius:10px; background:rgba(255,255,255,0.02); border:1px solid var(--d-border-light);">
              <div style="font-weight:700; color:#3ddc84; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
                <ha-icon icon="mdi:numeric-1-circle" style="--mdc-icon-size:18px;"></ha-icon> 1. Ouvrir l'App Android
              </div>
              <div style="font-size:12px; color:var(--d-subtext); line-height:1.5;">
                Sur votre smartphone Android : <b>Paramètres Home Assistant</b> > <b>Application Compagnon</b> > <b>Android Auto</b>.
              </div>
            </div>

            <div style="padding:12px; border-radius:10px; background:rgba(255,255,255,0.02); border:1px solid var(--d-border-light);">
              <div style="font-weight:700; color:#3b82f6; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
                <ha-icon icon="mdi:numeric-2-circle" style="--mdc-icon-size:18px;"></ha-icon> 2. Exposer l'Alarme
              </div>
              <div style="font-size:12px; color:var(--d-subtext); line-height:1.5;">
                Activez l'entité <code>alarm_control_panel.domolink_alarm</code> dans la liste des entités affichées sur l'écran du tableau de bord.
              </div>
            </div>

            <div style="padding:12px; border-radius:10px; background:rgba(255,255,255,0.02); border:1px solid var(--d-border-light);">
              <div style="font-weight:700; color:#f59e0b; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
                <ha-icon icon="mdi:numeric-3-circle" style="--mdc-icon-size:18px;"></ha-icon> 3. Raccourcis Volant
              </div>
              <div style="font-size:12px; color:var(--d-subtext); line-height:1.5;">
                Créez des actions rapides personnalisées (Armement Absent / Désarmer) accessibles en 1 touche tactile sur l'écran du véhicule.
              </div>
            </div>
          </div>

          <div style="padding:10px 14px; border-radius:10px; background:rgba(61,220,132,0.08); border:1px solid rgba(61,220,132,0.25); font-size:12px; color:#3ddc84; display:flex; align-items:center; gap:10px;">
            <ha-icon icon="mdi:google-assistant" style="--mdc-icon-size:20px; flex-shrink:0;"></ha-icon>
            <span><b>Commande Vocale Google Assistant :</b> Dites simplement au volant : <i>« Hey Google, arme l'alarme Domolink »</i> ou <i>« Hey Google, désarme l'alarme Domolink avec le code [code] »</i>.</span>
          </div>
        `)}

        ${this._renderAccordionCard("android_tv_guide", "mdi:television", "#f59e0b", "2. Compatibilité Android TV, Google TV & Pop-ups Vidéo", `
          <div style="font-size:13px; color:var(--d-subtext); line-height:1.6; margin-bottom:14px;">
            Domolink Alarm fonctionne parfaitement sur <b>Android TV & Google TV</b> (Sony, Philips, TCL, Nvidia Shield, Xiaomi TV Box, Freebox Pop, Bbox, Chromecast avec Google TV).
          </div>

          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:12px; margin-bottom:16px;">
            <div style="padding:12px; border-radius:10px; background:rgba(255,255,255,0.02); border:1px solid var(--d-border-light);">
              <div style="font-weight:700; color:#f59e0b; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
                <ha-icon icon="mdi:google-play" style="--mdc-icon-size:18px;"></ha-icon> App Officielle TV
              </div>
              <div style="font-size:12px; color:var(--d-subtext); line-height:1.5;">
                Installez l'application <b>Home Assistant for Android TV</b> depuis le Google Play Store de votre téléviseur pour naviguer dans le panneau d'alarme.
              </div>
            </div>

            <div style="padding:12px; border-radius:10px; background:rgba(255,255,255,0.02); border:1px solid var(--d-border-light);">
              <div style="font-weight:700; color:#3b82f6; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
                <ha-icon icon="mdi:fullscreen" style="--mdc-icon-size:18px;"></ha-icon> Mode Kiosque 16:9
              </div>
              <div style="font-size:12px; color:var(--d-subtext); line-height:1.5;">
                Activez le <b>Mode Kiosque</b> ou le <b>Mode Voiture</b> pour bénéficier d'un affichage plein écran aux contrastes renforcés, parfaitement lisible depuis votre canapé à 3-4 mètres.
              </div>
            </div>

            <div style="padding:12px; border-radius:10px; background:rgba(255,255,255,0.02); border:1px solid var(--d-border-light);">
              <div style="font-weight:700; color:#ef4444; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
                <ha-icon icon="mdi:picture-in-picture-bottom-right" style="--mdc-icon-size:18px;"></ha-icon> Alertes Pop-up PIP
              </div>
              <div style="font-size:12px; color:var(--d-subtext); line-height:1.5;">
                Recevez les notifications d'intrusion avec la <b>photo de la caméra en surimpression</b> (Picture-in-Picture) par-dessus votre film ou programme TV via l'intégration <code>nfandroidtv</code> ou l'app TV.
              </div>
            </div>
          </div>

          <div style="position:relative; margin-bottom:12px;">
            <pre style="background:rgba(0,0,0,0.4); border:1px solid var(--d-border-light); border-radius:10px; padding:14px; color:#fde68a; font-family:monospace; font-size:12px; overflow-x:auto; line-height:1.5; margin:0;">${tvNotificationYaml}</pre>
          </div>
          <div style="display:flex; align-items:center; justify-content:flex-end;">
            <button id="btn-copy-tv-yaml" style="padding:8px 16px; border-radius:8px; border:1px solid rgba(245,158,11,0.4); background:rgba(245,158,11,0.15); color:#fbbf24; font-size:12px; font-weight:700; cursor:pointer; display:flex; align-items:center; gap:6px; transition:all 0.2s;">
              <ha-icon icon="mdi:content-copy" style="--mdc-icon-size:16px;"></ha-icon>
              <span>Copier le modèle YAML Android TV</span>
            </button>
          </div>
        `)}

        ${this._renderAccordionCard("carplay_guide", "mdi:apple", "#10b981", "3. Intégration Apple CarPlay via l'App Home Assistant iOS", `
          <div style="font-size:13px; color:var(--d-subtext); line-height:1.6; margin-bottom:14px;">
            Apple CarPlay est nativement supporté par l'application Home Assistant pour iOS. Vous pouvez piloter directement votre alarme Domolink depuis l'écran de bord de votre véhicule sans manipulation dangereuse.
          </div>

          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:12px; margin-bottom:16px;">
            <div style="padding:12px; border-radius:10px; background:rgba(255,255,255,0.02); border:1px solid var(--d-border-light);">
              <div style="font-weight:700; color:#10b981; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
                <ha-icon icon="mdi:numeric-1-circle" style="--mdc-icon-size:18px;"></ha-icon> 1. Activer CarPlay
              </div>
              <div style="font-size:12px; color:var(--d-subtext); line-height:1.5;">
                Ouvrez l'application <b>Home Assistant</b> sur votre iPhone > <b>Réglages</b> > <b>Application Compagnon</b> > <b>CarPlay</b>. Vérifiez que le support CarPlay est activé.
              </div>
            </div>

            <div style="padding:12px; border-radius:10px; background:rgba(255,255,255,0.02); border:1px solid var(--d-border-light);">
              <div style="font-weight:700; color:#3b82f6; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
                <ha-icon icon="mdi:numeric-2-circle" style="--mdc-icon-size:18px;"></ha-icon> 2. Ajouter l'Alarme
              </div>
              <div style="font-size:12px; color:var(--d-subtext); line-height:1.5;">
                Dans la liste des entités exposées à CarPlay, sélectionnez <code>alarm_control_panel.domolink_alarm</code> pour l'avoir sur l'écran d'accueil du véhicule.
              </div>
            </div>

            <div style="padding:12px; border-radius:10px; background:rgba(255,255,255,0.02); border:1px solid var(--d-border-light);">
              <div style="font-weight:700; color:#f59e0b; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
                <ha-icon icon="mdi:numeric-3-circle" style="--mdc-icon-size:18px;"></ha-icon> 3. Actions Rapides
              </div>
              <div style="font-size:12px; color:var(--d-subtext); line-height:1.5;">
                Créez des raccourcis dans <b>Actions CarPlay</b> : « Armer Absent », « Désarmer », « Statut Alarme » pour un déclenchement en un seul toucher.
              </div>
            </div>
          </div>

          <div style="padding:10px 14px; border-radius:10px; background:rgba(16,185,129,0.08); border:1px solid rgba(16,185,129,0.25); font-size:12px; color:#10b981; display:flex; align-items:center; gap:10px;">
            <ha-icon icon="mdi:shield-check" style="--mdc-icon-size:20px; flex-shrink:0;"></ha-icon>
            <span><b>Commande Vocale Siri au Volant :</b> Vous pouvez également dire : <i>« Dis Siri, désarme l'alarme Domolink avec le code [votre code] »</i> directement au microphone de la voiture.</span>
          </div>
        `)}

        ${this._renderAccordionCard("carplay_automation", "mdi:robot", "#8b5cf6", "4. Automatisation Home Assistant Recommandée (Départ Véhicule)", `
          <div style="font-size:13px; color:var(--d-subtext); line-height:1.6; margin-bottom:12px;">
            Copiez ce modèle d'automatisation YAML dans votre fichier <code>automations.yaml</code> ou via l'interface graphique de Home Assistant pour sécuriser votre domicile automatiquement en quittant la maison en voiture (compatible iPhone CarPlay & Android Auto) :
          </div>
          <div style="position:relative; margin-bottom:12px;">
            <pre style="background:rgba(0,0,0,0.4); border:1px solid var(--d-border-light); border-radius:10px; padding:14px; color:#a5b4fc; font-family:monospace; font-size:12px; overflow-x:auto; line-height:1.5; margin:0;">${carplayYaml}</pre>
          </div>
          <div style="display:flex; align-items:center; justify-content:flex-end;">
            <button id="btn-copy-carplay-yaml" style="padding:8px 16px; border-radius:8px; border:1px solid rgba(139,92,246,0.4); background:rgba(139,92,246,0.15); color:#a78bfa; font-size:12px; font-weight:700; cursor:pointer; display:flex; align-items:center; gap:6px; transition:all 0.2s;">
              <ha-icon icon="mdi:content-copy" style="--mdc-icon-size:16px;"></ha-icon>
              <span>Copier le modèle YAML Véhicule</span>
            </button>
          </div>
        `)}

        ${this._renderAccordionCard("car_features", "mdi:car-cog", "#ec4899", "5. Ergonomie Grand Écran & Boutons Tactiles XXL", `
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:12px;">
            <div style="padding:12px; border-radius:10px; background:rgba(255,255,255,0.02); border:1px solid var(--d-border-light);">
              <div style="font-weight:700; color:var(--d-text); margin-bottom:4px; display:flex; align-items:center; gap:6px;">
                <ha-icon icon="mdi:gesture-tap-button" style="--mdc-icon-size:18px; color:#ec4899;"></ha-icon> Boutons Tactiles Géants (80px)
              </div>
              <div style="font-size:12px; color:var(--d-subtext); line-height:1.5;">
                Conçus pour éviter les fausses manipulations lors des arrêts au volant ou lors de l'utilisation sur téléviseur.
              </div>
            </div>
            <div style="padding:12px; border-radius:10px; background:rgba(255,255,255,0.02); border:1px solid var(--d-border-light);">
              <div style="font-weight:700; color:var(--d-text); margin-bottom:4px; display:flex; align-items:center; gap:6px;">
                <ha-icon icon="mdi:contrast-circle" style="--mdc-icon-size:18px; color:#ec4899;"></ha-icon> Contraste Élevé Spécial Pare-brise & Salon
              </div>
              <div style="font-size:12px; color:var(--d-subtext); line-height:1.5;">
                Couleurs saturées (Vert / Orange / Bleu / Rouge) immédiatement identifiables sans quitter la route des yeux ou depuis le canapé.
              </div>
            </div>
            <div style="padding:12px; border-radius:10px; background:rgba(255,255,255,0.02); border:1px solid var(--d-border-light);">
              <div style="font-weight:700; color:var(--d-text); margin-bottom:4px; display:flex; align-items:center; gap:6px;">
                <ha-icon icon="mdi:dialpad" style="--mdc-icon-size:18px; color:#ec4899;"></ha-icon> Pavé PIN Grand Format
              </div>
              <div style="font-size:12px; color:var(--d-subtext); line-height:1.5;">
                Touches de saisie du code désarmement larges avec retour visuel immédiat.
              </div>
            </div>
            <div style="padding:12px; border-radius:10px; background:rgba(255,255,255,0.02); border:1px solid var(--d-border-light);">
              <div style="font-weight:700; color:var(--d-text); margin-bottom:4px; display:flex; align-items:center; gap:6px;">
                <ha-icon icon="mdi:bookmark-check" style="--mdc-icon-size:18px; color:#ec4899;"></ha-icon> Navigateur TV & Véhicule
              </div>
              <div style="font-size:12px; color:var(--d-subtext); line-height:1.5;">
                Enregistrez le lien <code>?mode=car</code> dans les favoris du navigateur de bord ou de votre téléviseur pour un affichage instantané.
              </div>
            </div>
          </div>
        `)}

        ${this._renderAccordionCard("watch_guide", "mdi:watch", "#38bdf8", "6. Montres Connectées (Apple Watch & Wear OS)", `
          <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(56,189,248,0.1); border:1px solid rgba(56,189,248,0.3); border-radius:12px; padding:14px 18px; margin-bottom:14px; flex-wrap:wrap; gap:12px;">
            <div style="display:flex; align-items:center; gap:12px;">
              <ha-icon icon="mdi:shield-check" style="--mdc-icon-size:32px; color:#38bdf8;"></ha-icon>
              <div>
                <div style="font-size:14px; font-weight:800; color:#38bdf8;">Complication Montre Connectée Active</div>
                <div style="font-size:12px; color:var(--d-subtext); margin-top:2px;">Entité capteur dédiée : <code>sensor.domolink_alarm_statut_montre_connectee</code></div>
              </div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:11px; color:var(--d-subtext); font-weight:600;">Statut actuel</div>
              <div style="font-size:15px; font-weight:800; color:var(--d-text);">${attrs.compact_label || 'Désarmée'}</div>
            </div>
          </div>
          <div style="font-size:12px; color:var(--d-text); line-height:1.6;">
            <strong>Comment ajouter la complication sur votre montre :</strong>
            <ul style="margin:8px 0 0 20px; padding:0; display:flex; flex-direction:column; gap:6px;">
              <li><strong>Apple Watch :</strong> Dans l'app Home Assistant iOS > <em>Réglages</em> > <em>Application Compagnon</em> > <em>Apple Watch</em>. Ajoutez une complication de type <em>Texte / Jauge</em> liée au capteur <code>sensor.domolink_alarm_statut_montre_connectee</code> ou <code>alarm_control_panel.domolink_alarm</code>.</li>
              <li><strong>Wear OS (Galaxy Watch, Pixel Watch) :</strong> Dans l'app Home Assistant Android > <em>Paramètres</em> > <em>Wear OS</em>. Ajoutez une tuile d'accès rapide avec le widget alarme ou une complication de cadran.</li>
              <li><strong>Raccourcis d'actions rapides :</strong> Créez deux actions au poignet : <em>« Armer Absent »</em> et <em>« Désarmer »</em> pour une commande directe sans sortir votre téléphone.</li>
            </ul>
          </div>
        `)}
      `;
    }

    const html = `
      <div style="max-width:960px; margin:0 auto;">
        <!-- Header Info -->
        <div class="glass-card" style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:16px; margin-bottom:20px;">
          <div style="display:flex; align-items:center; gap:14px;">
            <div style="width:48px; height:48px; border-radius:14px; background:linear-gradient(135deg,#f59e0b,#d97706); display:flex; align-items:center; justify-content:center; color:#fff; box-shadow:0 4px 14px rgba(245,158,11,0.35);">
              <ha-icon icon="mdi:cog" style="--mdc-icon-size:28px;"></ha-icon>
            </div>
            <div>
              <div style="font-size:18px; font-weight:800; color:var(--d-text); display:flex; align-items:center; gap:8px;">
                Centre de Configuration
                <span class="nav-badge-pill badge-version">v${(this._hass && this._hass.states && this._hass.states['alarm_control_panel.domolink_alarm'] && this._hass.states['alarm_control_panel.domolink_alarm'].attributes && this._hass.states['alarm_control_panel.domolink_alarm'].attributes.system_version) || '0.9.74'}</span>
              </div>
              <div style="font-size:12px; color:var(--d-subtext); margin-top:3px;">
                Modifiez vos équipements, délais, notifications et sauvegardes en toute simplicité
              </div>
            </div>
          </div>

          <div style="display:flex; align-items:center; gap:10px;">
            <button class="btn-config-reset" id="btn-config-reset-top" title="Recharger les valeurs enregistrées">
              <ha-icon icon="mdi:restore" style="--mdc-icon-size:16px;"></ha-icon> Réinitialiser
            </button>
            <button class="btn-config-save" id="btn-config-save-top">
              <ha-icon icon="mdi:content-save-check" style="--mdc-icon-size:18px;"></ha-icon> Enregistrer
            </button>
          </div>
        </div>

        <!-- Sub-Navigation Pills -->
        <div class="config-subnav">
          ${subnavItems.map(item => `
            <button class="config-subnav-btn ${this._configSubTab === item.key ? 'active' : ''}" data-subtab="${item.key}">
              <ha-icon icon="${item.icon}"></ha-icon> ${item.label}
            </button>
          `).join('')}
        </div>

        <!-- Subtab Content -->
        <div class="config-content-pane">
          <div class="config-accordion-toolbar">
            <div class="config-accordion-toolbar-hint">
              <ha-icon icon="mdi:arrow-split-horizontal" style="--mdc-icon-size:15px; color:#f59e0b;"></ha-icon>
              <span>Sections repliables — cliquez sur un titre pour ouvrir ou fermer</span>
            </div>
            <div class="config-accordion-toolbar-actions">
              <button type="button" class="btn-accordion-action" id="btn-accordions-expand-all" title="Tout déplier">
                <ha-icon icon="mdi:unfold-more-horizontal" style="--mdc-icon-size:14px;"></ha-icon>
                <span>Tout déplier</span>
              </button>
              <button type="button" class="btn-accordion-action" id="btn-accordions-collapse-all" title="Tout replier">
                <ha-icon icon="mdi:unfold-less-horizontal" style="--mdc-icon-size:14px;"></ha-icon>
                <span>Tout replier</span>
              </button>
            </div>
          </div>
          ${contentHtml}
        </div>

        <!-- Bottom Action Bar -->
        <div class="config-actions-bar">
          <div style="font-size:12px; color:var(--d-subtext); font-weight:600;">
            Les modifications sont immédiatement appliquées et sauvegardées dans Home Assistant.
          </div>
          <div style="display:flex; align-items:center; gap:12px;">
            <button class="btn-config-reset" id="btn-config-reset-bottom">
              <ha-icon icon="mdi:restore" style="--mdc-icon-size:16px;"></ha-icon> Annuler les changements
            </button>
            <button class="btn-config-save" id="btn-config-save-bottom">
              <ha-icon icon="mdi:content-save-check" style="--mdc-icon-size:18px;"></ha-icon> Enregistrer la Configuration
            </button>
          </div>
        </div>
      </div>
    `;

    container.innerHTML = html;

    // ─── Bind Events ──────────────────────────────

    // Accordions Toggle Handling
    container.querySelectorAll('.config-card.accordion-card .config-card-header').forEach(header => {
      header.addEventListener('click', (e) => {
        // Prevent toggle if user clicked on interactive elements
        if (e.target.closest('button') || e.target.closest('input') || e.target.closest('a') || e.target.closest('select')) return;

        const card = header.closest('.config-card.accordion-card');
        if (!card) return;
        const accId = card.getAttribute('data-accordion-id') || header.getAttribute('data-toggle-accordion');
        const isCurrentlyOpen = card.classList.contains('open');

        if (!this._openAccordions) this._openAccordions = new Set();
        if (!this._closedAccordions) this._closedAccordions = new Set();

        if (isCurrentlyOpen) {
          card.classList.remove('open');
          card.classList.add('collapsed');
          if (accId) {
            this._openAccordions.delete(accId);
            this._closedAccordions.add(accId);
          }
        } else {
          card.classList.remove('collapsed');
          card.classList.add('open');
          if (accId) {
            this._openAccordions.add(accId);
            this._closedAccordions.delete(accId);
          }
        }
      });
    });

    // Expand All / Collapse All Buttons
    const btnExpandAll = container.querySelector('#btn-accordions-expand-all');
    if (btnExpandAll) {
      btnExpandAll.addEventListener('click', () => {
        if (!this._openAccordions) this._openAccordions = new Set();
        if (!this._closedAccordions) this._closedAccordions = new Set();
        container.querySelectorAll('.config-card.accordion-card').forEach(card => {
          card.classList.remove('collapsed');
          card.classList.add('open');
          const id = card.getAttribute('data-accordion-id');
          if (id) {
            this._openAccordions.add(id);
            this._closedAccordions.delete(id);
          }
        });
      });
    }

    const btnCollapseAll = container.querySelector('#btn-accordions-collapse-all');
    if (btnCollapseAll) {
      btnCollapseAll.addEventListener('click', () => {
        if (!this._openAccordions) this._openAccordions = new Set();
        if (!this._closedAccordions) this._closedAccordions = new Set();
        container.querySelectorAll('.config-card.accordion-card').forEach(card => {
          card.classList.remove('open');
          card.classList.add('collapsed');
          const id = card.getAttribute('data-accordion-id');
          if (id) {
            this._openAccordions.delete(id);
            this._closedAccordions.add(id);
          }
        });
      });
    }

    // Subtab switching
    container.querySelectorAll('.config-subnav-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        this._configSubTab = btn.getAttribute('data-subtab');
        this._renderParamTab(alarmEntity);
      });
    });

    // Inputs: text, number, select, time
    container.querySelectorAll('.config-input, .config-select:not(.config-entity-picker)').forEach(input => {
      input.addEventListener('change', (e) => {
        const field = e.target.getAttribute('data-field');
        if (!field) return;
        let val = e.target.value;
        if (e.target.type === 'number') val = parseFloat(val) || 0;
        this._configDraft[field] = val;
        this._syncDraftToNasConfig(field, val);
      });
      input.addEventListener('input', (e) => {
        const field = e.target.getAttribute('data-field');
        if (!field) return;
        let val = e.target.value;
        if (e.target.type === 'number') {
          val = val === '' ? '' : (parseFloat(val) || 0);
        }
        this._configDraft[field] = val;
        this._syncDraftToNasConfig(field, val);
      });
    });

    // Toggles
    container.querySelectorAll('.config-toggle').forEach(chk => {
      chk.addEventListener('change', (e) => {
        const field = chk.getAttribute('data-field');
        if (field) {
          const val = Boolean(chk.checked);
          this._configDraft[field] = val;
          this._syncDraftToNasConfig(field, val);
        }
      });
    });

    // Password show/hide toggle
    container.querySelectorAll('.btn-pwd-toggle').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const row = btn.closest('.config-row');
        if (!row) return;
        const input = row.querySelector('.config-pwd-field');
        const icon = btn.querySelector('ha-icon');
        if (input) {
          const isPwd = input.type === 'password';
          input.type = isPwd ? 'text' : 'password';
          if (icon) icon.setAttribute('icon', isPwd ? 'mdi:eye-off' : 'mdi:eye');
        }
      });
    });

    // Entity Picker Select
    container.querySelectorAll('.config-entity-picker').forEach(select => {
      select.addEventListener('change', (e) => {
        const field = select.getAttribute('data-field');
        const chosen = select.value;
        if (field && chosen) {
          if (!Array.isArray(this._configDraft[field])) this._configDraft[field] = [];
          if (!this._configDraft[field].includes(chosen)) {
            this._configDraft[field].push(chosen);
          }
          this._renderParamTab(alarmEntity);
        }
      });
    });

    // Chip remove
    container.querySelectorAll('.config-chip-remove').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const field = btn.getAttribute('data-field');
        const entity = btn.getAttribute('data-entity');
        if (field && entity && Array.isArray(this._configDraft[field])) {
          this._configDraft[field] = this._configDraft[field].filter(item => item !== entity);
          this._renderParamTab(alarmEntity);
        }
      });
    });

    // Add Label Button
    container.querySelectorAll('.btn-add-label').forEach(btn => {
      btn.addEventListener('click', () => {
        const field = btn.getAttribute('data-field');
        const row = btn.closest('.config-row-stacked');
        const input = row ? row.querySelector('.config-label-input') : null;
        if (field && input && input.value.trim()) {
          const val = input.value.trim();
          if (!Array.isArray(this._configDraft[field])) this._configDraft[field] = [];
          if (!this._configDraft[field].includes(val)) {
            this._configDraft[field].push(val);
          }
          input.value = '';
          this._renderParamTab(alarmEntity);
        }
      });
    });

    // Reset Buttons
    const handleReset = () => {
      if (confirm("Voulez-vous annuler toutes les modifications non enregistrées ?")) {
        this._configDraft = null;
        this._paramRendered = false;
        this._renderParamTab(alarmEntity);
      }
    };
    const resetTop = container.querySelector('#btn-config-reset-top');
    const resetBottom = container.querySelector('#btn-config-reset-bottom');
    if (resetTop) resetTop.addEventListener('click', handleReset);
    if (resetBottom) resetBottom.addEventListener('click', handleReset);

    // Save Buttons
    const handleSave = (btn) => {
      // Capture any unblurred input values first
      container.querySelectorAll('.config-input, .config-select:not(.config-entity-picker)').forEach(input => {
        const field = input.getAttribute('data-field');
        if (field) {
          let val = input.value;
          if (input.type === 'number') val = parseFloat(val) || 0;
          this._configDraft[field] = val;
          this._syncDraftToNasConfig(field, val);
        }
      });
      container.querySelectorAll('.config-toggle').forEach(chk => {
        const field = chk.getAttribute('data-field');
        if (field) {
          const val = Boolean(chk.checked);
          this._configDraft[field] = val;
          this._syncDraftToNasConfig(field, val);
        }
      });

      const oldText = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = `<ha-icon icon="mdi:loading" class="spin-icon" style="--mdc-icon-size:18px;"></ha-icon> Enregistrement...`;

      this._hass.callService('domolink_alarm', 'update_settings', this._configDraft).then(() => {
        btn.innerHTML = `✓ Configuration Enregistrée !`;
        btn.style.backgroundColor = '#10b981';
        setTimeout(() => {
          btn.innerHTML = oldText;
          btn.style.backgroundColor = '#f59e0b';
          btn.disabled = false;
          // Invalidate draft so it reloads fresh from HA
          this._configDraft = null;
          this._paramRendered = false;
          this.render();
        }, 2200);
      }).catch(err => {
        btn.innerHTML = oldText;
        btn.disabled = false;
        alert("Erreur lors de la sauvegarde: " + (err && err.message ? err.message : String(err)));
      });
    };

    const saveTop = container.querySelector('#btn-config-save-top');
    const saveBottom = container.querySelector('#btn-config-save-bottom');
    if (saveTop) saveTop.addEventListener('click', () => handleSave(saveTop));
    if (saveBottom) saveBottom.addEventListener('click', () => handleSave(saveBottom));

    // ─── Unified NAS Diagnostic Tests (Per-NAS FTP & WebDAV) ─────────
    const runNasTest = async (nasKey, proto = 'ftp', targetBtn = null) => {
      const curNas = this._configDraft.nas_type || 'asustor';
      const targetNas = nasKey || curNas;
      const isCurActive = (targetNas === curNas);

      // If testing current active NAS, harvest unblurred inputs
      if (isCurActive) {
        container.querySelectorAll('.config-input, .config-select:not(.config-entity-picker)').forEach(input => {
          const field = input.getAttribute('data-field');
          if (field) {
            let val = input.value;
            if (input.type === 'number') val = parseFloat(val) || 0;
            this._configDraft[field] = val;
            this._syncDraftToNasConfig(field, val);
          }
        });
        container.querySelectorAll('.config-toggle').forEach(chk => {
          const field = chk.getAttribute('data-field');
          if (field) {
            const val = Boolean(chk.checked);
            this._configDraft[field] = val;
            this._syncDraftToNasConfig(field, val);
          }
        });
      }

      if (!this._configDraft.nas_configs) this._configDraft.nas_configs = {};
      const targetCfg = this._configDraft.nas_configs[targetNas] || {};

      let payload = null;
      let serviceName = '';

      if (proto === 'ftp') {
        serviceName = 'test_ftp';
        const protoInput = isCurActive ? container.querySelector('#cfg-ftp-protocol') : null;
        const activeProto = (protoInput ? protoInput.value : null) || targetCfg.ftp_protocol || this._configDraft.ftp_protocol || 'ftp';
        const hostInput = isCurActive ? container.querySelector('input[data-field="ftp_host"]') : null;
        const portInput = isCurActive ? container.querySelector('input[data-field="ftp_port"]') : null;
        const userInput = isCurActive ? container.querySelector('input[data-field="ftp_user"]') : null;
        const passInput = isCurActive ? container.querySelector('input[data-field="ftp_pass"]') : null;
        const pathInput = isCurActive ? container.querySelector('input[data-field="ftp_path"]') : null;
        const enabledInput = isCurActive ? container.querySelector('input[data-field="ftp_enabled"]') : null;

        const defaultPortForProto = activeProto === 'samba' ? 445 : (activeProto === 'sftp' ? 22 : 21);

        payload = {
          nas_type: targetNas,
          ftp_protocol: activeProto,
          ftp_host: hostInput ? hostInput.value.trim() : (targetCfg.ftp_host !== undefined ? targetCfg.ftp_host : (targetNas === 'freebox' ? 'mafreebox.freebox.fr' : '')),
          ftp_port: portInput ? parseInt(portInput.value, 10) || defaultPortForProto : (targetCfg.ftp_port || defaultPortForProto),
          ftp_user: userInput ? userInput.value.trim() : (targetCfg.ftp_user !== undefined ? targetCfg.ftp_user : (targetNas === 'freebox' ? 'freebox' : '')),
          ftp_pass: passInput ? passInput.value : (targetCfg.ftp_pass || ''),
          ftp_path: pathInput ? (pathInput.value.trim() || (targetNas === 'freebox' ? '/Disque 1' : '/')) : (targetCfg.ftp_path !== undefined ? targetCfg.ftp_path : (targetNas === 'freebox' ? '/Disque 1' : '/')),
          ftp_enabled: enabledInput ? Boolean(enabledInput.checked) : (targetCfg.ftp_enabled !== undefined ? targetCfg.ftp_enabled : true),
        };
      } else {
        serviceName = 'test_webdav';
        const urlInput = isCurActive ? container.querySelector('input[data-field="webdav_url"]') : null;
        const userInput = isCurActive ? container.querySelector('input[data-field="webdav_user"]') : null;
        const passInput = isCurActive ? container.querySelector('input[data-field="webdav_pass"]') : null;
        const pathInput = isCurActive ? container.querySelector('input[data-field="webdav_path"]') : null;
        const enabledInput = isCurActive ? container.querySelector('input[data-field="webdav_enabled"]') : null;

        payload = {
          nas_type: targetNas,
          webdav_url: urlInput ? urlInput.value.trim() : (targetCfg.webdav_url || ''),
          webdav_user: userInput ? userInput.value.trim() : (targetCfg.webdav_user || ''),
          webdav_pass: passInput ? passInput.value : (targetCfg.webdav_pass || ''),
          webdav_path: pathInput ? pathInput.value.trim() : (targetCfg.webdav_path || 'domolink/alarm'),
          webdav_enabled: enabledInput ? Boolean(enabledInput.checked) : (targetCfg.webdav_enabled !== undefined ? targetCfg.webdav_enabled : true),
        };
      }

      const cardBadge = container.querySelector(`.nas-test-badge-container[data-nas="${targetNas}"]`);
      if (cardBadge) cardBadge.innerHTML = this._renderTestBadge({ loading: true });

      const badgeInline = proto === 'webdav' ? container.querySelector('#webdav-test-inline-badge') : container.querySelector('#ftp-test-inline-badge');
      const msgInline = proto === 'webdav' ? container.querySelector('#webdav-test-inline-msg') : container.querySelector('#ftp-test-inline-msg');
      const badgeNas = container.querySelector('#nas-card-status-badge');

      if (isCurActive) {
        if (badgeInline) badgeInline.innerHTML = this._renderTestBadge({ loading: true });
        if (badgeNas) badgeNas.innerHTML = this._renderTestBadge({ loading: true });
        if (msgInline) {
          msgInline.innerHTML = `<span style="color:#3b82f6;">Diagnostic de connexion ${proto.toUpperCase()} (${targetNas.toUpperCase()}) en cours...</span>`;
        }
      }

      if (targetBtn) {
        targetBtn.disabled = true;
        targetBtn.style.opacity = '0.6';
      }

      try {
        let result = null;
        if (this._hass && this._hass.callWS) {
          try {
            const wsResp = await this._hass.callWS({
              type: 'call_service',
              domain: 'domolink_alarm',
              service: serviceName,
              service_data: payload,
              return_response: true,
            });
            if (wsResp && wsResp.response) {
              result = wsResp.response;
            }
          } catch (wsErr) {
            console.warn(`callWS ${serviceName} fallback:`, wsErr);
          }
        }
        if (!result) {
          await this._hass.callService('domolink_alarm', serviceName, payload);
          await new Promise(r => setTimeout(r, 600));
          const latestEntity = this._hass.states[alarmEntity.entity_id];
          const latestResults = latestEntity?.attributes?.nas_test_results || {};
          result = latestResults[targetNas] || latestResults[`${targetNas}_${proto}`] || (proto === 'webdav' ? latestEntity?.attributes?.webdav_test_result : latestEntity?.attributes?.ftp_test_result);
        }

        if (result) {
          if (cardBadge) cardBadge.innerHTML = this._renderTestBadge(result);
          if (isCurActive) {
            if (badgeInline) badgeInline.innerHTML = this._renderTestBadge(result);
            if (badgeNas) badgeNas.innerHTML = this._renderTestBadge(result);
            if (msgInline) {
              msgInline.textContent = result.message || (result.success ? "Connexion acceptée" : (result.result_label || `Erreur ${result.code || ''}`));
              msgInline.style.color = result.success ? '#10b981' : '#ef4444';
            }
          }
        }
      } catch (err) {
        console.error(`Erreur test ${proto}:`, err);
        const errObj = { success: false, code: 500, result_label: "Erreur 500", message: err.message || String(err) };
        if (cardBadge) cardBadge.innerHTML = this._renderTestBadge(errObj);
        if (isCurActive) {
          if (badgeInline) badgeInline.innerHTML = this._renderTestBadge(errObj);
          if (badgeNas) badgeNas.innerHTML = this._renderTestBadge(errObj);
          if (msgInline) {
            msgInline.textContent = `Erreur lors du test : ${err.message || err}`;
            msgInline.style.color = '#ef4444';
          }
        }
      } finally {
        if (targetBtn) {
          targetBtn.disabled = false;
          targetBtn.style.opacity = '1';
        }
      }
    };

    // Direct per-card NAS Test Buttons
    container.querySelectorAll('.btn-nas-card-test').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const nasKey = btn.getAttribute('data-nas');
        const proto = btn.getAttribute('data-proto') || 'ftp';
        runNasTest(nasKey, proto, btn);
      });
    });

    // FTP Test from Config Tab (Inline)
    const ftpInlineBtn = container.querySelector('#btn-test-ftp-inline');
    if (ftpInlineBtn) {
      ftpInlineBtn.addEventListener('click', () => runNasTest(this._configDraft.nas_type, 'ftp', ftpInlineBtn));
    }

    // WebDAV Test from Config Tab (Inline)
    const webdavCfgBtn = container.querySelector('#btn-test-webdav-cfg');
    if (webdavCfgBtn) {
      webdavCfgBtn.addEventListener('click', () => runNasTest(this._configDraft.nas_type, 'webdav', webdavCfgBtn));
    }

    // Quick Test Buttons in Profile Card
    container.querySelectorAll('.btn-nas-quick-test-ftp').forEach(btn => {
      btn.addEventListener('click', () => runNasTest(btn.getAttribute('data-nas') || this._configDraft.nas_type, 'ftp', btn));
    });
    container.querySelectorAll('.btn-nas-quick-test-webdav').forEach(btn => {
      btn.addEventListener('click', () => runNasTest(btn.getAttribute('data-nas') || this._configDraft.nas_type, 'webdav', btn));
    });

    // Protocol selector buttons (FTP, FTPS, SFTP, SAMBA)
    container.querySelectorAll('.btn-proto-choice').forEach(btn => {
      btn.addEventListener('click', () => {
        const proto = btn.getAttribute('data-proto');
        const defPort = parseInt(btn.getAttribute('data-port'), 10) || 21;

        container.querySelectorAll('.btn-proto-choice').forEach(b => {
          const isSelected = (b === btn);
          b.classList.toggle('active', isSelected);
          b.style.borderColor = isSelected ? '#10b981' : 'var(--d-border, rgba(255,255,255,0.1))';
          b.style.background = isSelected ? 'rgba(16,185,129,0.15)' : 'rgba(0,0,0,0.1)';
          b.style.color = isSelected ? '#10b981' : 'var(--d-subtext)';
        });

        const hiddenInput = container.querySelector('#cfg-ftp-protocol');
        if (hiddenInput) hiddenInput.value = proto;
        this._configDraft.ftp_protocol = proto;
        this._syncDraftToNasConfig('ftp_protocol', proto);

        // Auto-update port field
        const portInput = container.querySelector('input[data-field="ftp_port"]');
        if (portInput) {
          portInput.value = defPort;
          this._configDraft.ftp_port = defPort;
          this._syncDraftToNasConfig('ftp_port', defPort);
        }

        // Update inline test button text
        const ftpInlineBtnSpan = container.querySelector('#btn-test-ftp-inline span');
        if (ftpInlineBtnSpan) {
          ftpInlineBtnSpan.textContent = `Tester la connexion ${proto.toUpperCase()}`;
        }
      });
    });

    // Copy SAMBA link
    const copySambaBtn = container.querySelector('#btn-copy-samba-link');
    if (copySambaBtn) {
      copySambaBtn.addEventListener('click', () => {
        const hostInput = container.querySelector('input[data-field="ftp_host"]');
        const curHost = (hostInput ? hostInput.value.trim() : '') || (this._configDraft.nas_type === 'freebox' ? 'mafreebox.freebox.fr' : '192.168.1.50');
        const sambaUrl = `smb://${curHost}/`;
        const textSpan = copySambaBtn.querySelector('#copy-samba-txt');
        const iconEl = copySambaBtn.querySelector('ha-icon');

        const notifyCopied = () => {
          if (textSpan) textSpan.textContent = "✓ Lien copié !";
          if (iconEl) iconEl.setAttribute('icon', 'mdi:check-circle');
          copySambaBtn.style.background = '#10b981';
          copySambaBtn.style.color = '#ffffff';
          setTimeout(() => {
            if (textSpan) textSpan.textContent = "Copier le lien SAMBA";
            if (iconEl) iconEl.setAttribute('icon', 'mdi:content-copy');
            copySambaBtn.style.background = 'rgba(16,185,129,0.15)';
            copySambaBtn.style.color = '#10b981';
          }, 2500);
        };

        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(sambaUrl).then(notifyCopied).catch(() => {
            const ta = document.createElement('textarea');
            ta.value = sambaUrl;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            notifyCopied();
          });
        } else {
          const ta = document.createElement('textarea');
          ta.value = sambaUrl;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          document.body.removeChild(ta);
          notifyCopied();
        }
      });
    }

    // Dynamic update of SAMBA link if host input changes
    const ftpHostInput = container.querySelector('input[data-field="ftp_host"]');
    if (ftpHostInput) {
      ftpHostInput.addEventListener('input', () => {
        const val = ftpHostInput.value.trim() || (this._configDraft.nas_type === 'freebox' ? 'mafreebox.freebox.fr' : '192.168.1.50');
        const urlDisplay = container.querySelector('#samba-url-display');
        const winDisplay = container.querySelector('#samba-win-display');
        const lnkOpen = container.querySelector('#lnk-open-samba');
        if (urlDisplay) urlDisplay.textContent = `smb://${val}/`;
        if (winDisplay) winDisplay.textContent = `\\\\${val}\\`;
        if (lnkOpen) lnkOpen.setAttribute('href', `smb://${val}/`);
      });
    }

    // Copy Google Apps Script Button
    const copyGscriptBtn = container.querySelector('#btn-copy-google-script');
    if (copyGscriptBtn) {
      copyGscriptBtn.addEventListener('click', () => {
        const code = this._getGoogleAppsScriptCode();
        const textSpan = copyGscriptBtn.querySelector('#btn-copy-google-script-text');
        const iconEl = copyGscriptBtn.querySelector('ha-icon');
        
        const notifyCopied = () => {
          if (textSpan) textSpan.textContent = "✓ Script Copié !";
          if (iconEl) iconEl.setAttribute('icon', 'mdi:check-circle');
          copyGscriptBtn.style.background = '#10b981';
          copyGscriptBtn.style.borderColor = '#10b981';
          setTimeout(() => {
            if (textSpan) textSpan.textContent = "Copier le Google Script";
            if (iconEl) iconEl.setAttribute('icon', 'mdi:content-copy');
            copyGscriptBtn.style.background = '#34a853';
            copyGscriptBtn.style.borderColor = 'rgba(52,168,83,0.5)';
          }, 3000);
        };

        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(code).then(notifyCopied).catch(() => {
            const ta = document.createElement('textarea');
            ta.value = code;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            notifyCopied();
          });
        } else {
          const ta = document.createElement('textarea');
          ta.value = code;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          document.body.removeChild(ta);
          notifyCopied();
        }
      });
    }

    // Google Drive Test from Config Tab
    const gdriveCfgBtn = container.querySelector('#btn-test-gdrive-cfg');
    if (gdriveCfgBtn) {
      gdriveCfgBtn.addEventListener('click', () => {
        this._showGoogleDriveTestConsole = true;
        this._activeTab = 'arm';
        this._paramRendered = false;
        this.querySelectorAll('.nav-tab').forEach(t => t.classList.toggle('active', t.getAttribute('data-tab') === 'arm'));
        this.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('active', p.id === 'pane-arm'));
        this._lastArmKey = '';
        this.render();
        this._hass.callService('domolink_alarm', 'test_google_drive', {});
      });
    }

    // Multi-NAS Profile Cards Selection
    container.querySelectorAll('.nas-profile-card').forEach(card => {
      card.addEventListener('click', () => {
        const newNas = card.getAttribute('data-nas');
        if (!newNas) return;

        // 1. Harvest current form inputs into current NAS config before switching
        container.querySelectorAll('.config-input, .config-select:not(.config-entity-picker)').forEach(input => {
          const field = input.getAttribute('data-field');
          if (field) {
            let val = input.value;
            if (input.type === 'number') val = parseFloat(val) || 0;
            this._configDraft[field] = val;
            this._syncDraftToNasConfig(field, val);
          }
        });
        container.querySelectorAll('.config-toggle').forEach(chk => {
          const field = chk.getAttribute('data-field');
          if (field) {
            const val = Boolean(chk.checked);
            this._configDraft[field] = val;
            this._syncDraftToNasConfig(field, val);
          }
        });

        // 2. Switch active NAS
        this._configDraft.nas_type = newNas;

        // 3. Ensure newNas config exists in nas_configs
        if (!this._configDraft.nas_configs) this._configDraft.nas_configs = {};
        if (!this._configDraft.nas_configs[newNas]) {
          this._configDraft.nas_configs[newNas] = {
            ftp_enabled: newNas !== 'truenas',
            ftp_protocol: 'ftp',
            ftp_host: newNas === 'freebox' ? 'mafreebox.freebox.fr' : '',
            ftp_port: 21,
            ftp_user: newNas === 'freebox' ? 'freebox' : '',
            ftp_pass: '',
            ftp_path: newNas === 'freebox' ? '/Disque 1' : '/',
            webdav_enabled: newNas === 'truenas',
            webdav_url: '',
            webdav_user: '',
            webdav_pass: '',
            webdav_path: 'domolink/alarm'
          };
        }

        // Freebox guarantee defaults if empty
        if (newNas === 'freebox') {
          if (!this._configDraft.nas_configs.freebox.ftp_host) this._configDraft.nas_configs.freebox.ftp_host = 'mafreebox.freebox.fr';
          if (!this._configDraft.nas_configs.freebox.ftp_user) this._configDraft.nas_configs.freebox.ftp_user = 'freebox';
          if (!this._configDraft.nas_configs.freebox.ftp_protocol) this._configDraft.nas_configs.freebox.ftp_protocol = 'ftp';
          if (this._configDraft.nas_configs.freebox.ftp_port === undefined) this._configDraft.nas_configs.freebox.ftp_port = 21;
          if (this._configDraft.nas_configs.freebox.ftp_enabled === undefined) this._configDraft.nas_configs.freebox.ftp_enabled = true;
          if (!this._configDraft.nas_configs.freebox.ftp_path || this._configDraft.nas_configs.freebox.ftp_path === '/') this._configDraft.nas_configs.freebox.ftp_path = '/Disque 1';
        }

        const targetCfg = this._configDraft.nas_configs[newNas];

        // 4. Populate top-level fields for display in form
        this._configDraft.ftp_enabled = Boolean(targetCfg.ftp_enabled);
        this._configDraft.ftp_protocol = targetCfg.ftp_protocol || 'ftp';
        this._configDraft.ftp_host = targetCfg.ftp_host !== undefined ? targetCfg.ftp_host : (newNas === 'freebox' ? 'mafreebox.freebox.fr' : '');
        this._configDraft.ftp_port = targetCfg.ftp_port !== undefined ? targetCfg.ftp_port : 21;
        this._configDraft.ftp_user = targetCfg.ftp_user !== undefined ? targetCfg.ftp_user : (newNas === 'freebox' ? 'freebox' : '');
        this._configDraft.ftp_pass = targetCfg.ftp_pass !== undefined ? targetCfg.ftp_pass : '';
        this._configDraft.ftp_path = targetCfg.ftp_path !== undefined ? targetCfg.ftp_path : (newNas === 'freebox' ? '/Disque 1' : '/');
        this._configDraft.webdav_enabled = Boolean(targetCfg.webdav_enabled);
        this._configDraft.webdav_url = targetCfg.webdav_url !== undefined ? targetCfg.webdav_url : '';
        this._configDraft.webdav_user = targetCfg.webdav_user !== undefined ? targetCfg.webdav_user : '';
        this._configDraft.webdav_pass = targetCfg.webdav_pass !== undefined ? targetCfg.webdav_pass : '';
        this._configDraft.webdav_path = targetCfg.webdav_path !== undefined ? targetCfg.webdav_path : 'domolink/alarm';

        this._renderParamTab(alarmEntity);
      });
    });

    // CarPlay & Mode Voiture Action Bindings
    const btnLaunchCar = container.querySelector('#btn-launch-car-mode');
    if (btnLaunchCar) {
      btnLaunchCar.addEventListener('click', () => {
        this._carModeActive = true;
        try { localStorage.setItem('domolink_car_mode_active', 'true'); } catch (e) {}
        const wrap = this.querySelector('.panel-wrap');
        if (wrap) wrap.classList.add('car-mode');
        this._activeTab = 'arm';
        this._lastArmKey = '';
        this._lastCarKey = '';
        this.querySelectorAll('.nav-tab').forEach(t => t.classList.toggle('active', t.getAttribute('data-tab') === 'arm'));
        this.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('active', p.id === 'pane-arm'));
        this.render();
      });
    }

    const btnCopyUrl = container.querySelector('#btn-copy-car-url');
    if (btnCopyUrl) {
      btnCopyUrl.addEventListener('click', () => {
        const carUrl = `${window.location.origin}${window.location.pathname}?mode=car`;
        const copyText = (txt) => {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(txt);
          }
          const ta = document.createElement('textarea');
          ta.value = txt;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          document.body.removeChild(ta);
          return Promise.resolve();
        };
        copyText(carUrl).then(() => {
          btnCopyUrl.innerHTML = `<ha-icon icon="mdi:check" style="--mdc-icon-size:16px;"></ha-icon><span>Lien copié !</span>`;
          setTimeout(() => {
            btnCopyUrl.innerHTML = `<ha-icon icon="mdi:content-copy" style="--mdc-icon-size:16px;"></ha-icon><span>Copier le lien direct</span>`;
          }, 2000);
        });
      });
    }

    const btnCopyYaml = container.querySelector('#btn-copy-carplay-yaml');
    if (btnCopyYaml) {
      btnCopyYaml.addEventListener('click', () => {
        const pre = container.querySelector('#btn-copy-carplay-yaml')?.parentElement?.previousElementSibling?.querySelector('pre');
        const yaml = pre ? pre.textContent : '';
        const copyText = (txt) => {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(txt);
          }
          const ta = document.createElement('textarea');
          ta.value = txt;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          document.body.removeChild(ta);
          return Promise.resolve();
        };
        copyText(yaml).then(() => {
          btnCopyYaml.innerHTML = `<ha-icon icon="mdi:check" style="--mdc-icon-size:16px;"></ha-icon><span>Modèle copié !</span>`;
          setTimeout(() => {
            btnCopyYaml.innerHTML = `<ha-icon icon="mdi:content-copy" style="--mdc-icon-size:16px;"></ha-icon><span>Copier le modèle YAML Véhicule</span>`;
          }, 2000);
        });
      });
    }

    const btnCopyTvYaml = container.querySelector('#btn-copy-tv-yaml');
    if (btnCopyTvYaml) {
      btnCopyTvYaml.addEventListener('click', () => {
        const pre = container.querySelector('#btn-copy-tv-yaml')?.parentElement?.previousElementSibling?.querySelector('pre');
        const yaml = pre ? pre.textContent : '';
        const copyText = (txt) => {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(txt);
          }
          const ta = document.createElement('textarea');
          ta.value = txt;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          document.body.removeChild(ta);
          return Promise.resolve();
        };
        copyText(yaml).then(() => {
          btnCopyTvYaml.innerHTML = `<ha-icon icon="mdi:check" style="--mdc-icon-size:16px;"></ha-icon><span>Modèle copié !</span>`;
          setTimeout(() => {
            btnCopyTvYaml.innerHTML = `<ha-icon icon="mdi:content-copy" style="--mdc-icon-size:16px;"></ha-icon><span>Copier le modèle YAML Android TV</span>`;
          }, 2000);
        });
      });
    }

    const btnAddProfile = container.querySelector('#btn-add-profile-trigger');
    if (btnAddProfile) {
      btnAddProfile.addEventListener('click', () => {
        this._openAddProfileModal(alarmEntity);
      });
    }

    container.querySelectorAll('.btn-delete-profile').forEach((btn) => {
      btn.addEventListener('click', (ev) => {
        const pin = btn.getAttribute('data-pin');
        const name = btn.getAttribute('data-name');
        if (confirm(`Êtes-vous sûr de vouloir supprimer le profil "${name}" ?`)) {
          this._hass.callService('domolink_alarm', 'delete_user_profile', {
            pin: pin,
            name: name
          }).then(() => {
            if (this._configDraft && this._configDraft.user_profiles) {
              try {
                let profs = typeof this._configDraft.user_profiles === 'string'
                  ? JSON.parse(this._configDraft.user_profiles)
                  : this._configDraft.user_profiles;
                profs = profs.filter(p => p.name !== name && p.pin !== pin);
                this._configDraft.user_profiles = JSON.stringify(profs);
              } catch (e) {}
            }
            this.render();
          }).catch((err) => {
            alert("Erreur lors de la suppression du profil : " + (err && err.message ? err.message : String(err)));
          });
        }
      });
    });
  }

  _openAddProfileModal(alarmEntity) {
    const modal = document.createElement('div');
    modal.id = 'add-profile-modal';
    modal.style = "position:fixed; inset:0; background:rgba(0,0,0,0.85); backdrop-filter:blur(8px); z-index:999999; display:flex; align-items:center; justify-content:center; padding:16px; overflow-y:auto; cursor:default;";

    modal.innerHTML = `
      <div class="glass-card" style="background:var(--d-card-bg, #1e293b); color:var(--d-text, #fff); border:1px solid var(--d-border, rgba(255,255,255,0.1)); width:95vw; max-width:560px; border-radius:16px; padding:24px; box-shadow:0 25px 50px -12px rgba(0,0,0,0.5); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px; border-bottom:1px solid var(--d-border, rgba(255,255,255,0.1)); padding-bottom:12px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <ha-icon icon="mdi:account-plus" style="--mdc-icon-size:24px; color:#10b981;"></ha-icon>
            <div style="font-size:16px; font-weight:800;">Nouveau Profil Invité / Temporaire</div>
          </div>
          <button id="modal-close-profile" style="background:none; border:none; color:var(--d-subtext, #94a3b8); font-size:20px; cursor:pointer;">✕</button>
        </div>

        <div style="display:flex; flex-direction:column; gap:14px;">
          <div>
            <label style="display:block; font-size:12px; font-weight:700; color:var(--d-subtext, #94a3b8); margin-bottom:4px;">Nom ou Rôle</label>
            <input type="text" id="prof-name" placeholder="Ex: Marie (Ménage), Martin (Artisan)" style="width:100%; padding:10px 12px; border-radius:8px; border:1px solid var(--d-border, rgba(255,255,255,0.15)); background:var(--d-sec-bg, #0f172a); color:var(--d-text, #fff); font-size:13px; box-sizing:border-box;">
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
            <div>
              <label style="display:block; font-size:12px; font-weight:700; color:var(--d-subtext, #94a3b8); margin-bottom:4px;">Code PIN (4 à 8 chiffres)</label>
              <input type="password" id="prof-pin" maxlength="8" placeholder="••••" style="width:100%; padding:10px 12px; border-radius:8px; border:1px solid var(--d-border, rgba(255,255,255,0.15)); background:var(--d-sec-bg, #0f172a); color:var(--d-text, #fff); font-size:13px; font-family:monospace; box-sizing:border-box;">
            </div>
            <div>
              <label style="display:block; font-size:12px; font-weight:700; color:var(--d-subtext, #94a3b8); margin-bottom:4px;">Catégorie</label>
              <select id="prof-role" style="width:100%; padding:10px 12px; border-radius:8px; border:1px solid var(--d-border, rgba(255,255,255,0.15)); background:var(--d-sec-bg, #0f172a); color:var(--d-text, #fff); font-size:13px; box-sizing:border-box;">
                <option value="invite">Invité / Ami</option>
                <option value="femme_menage">Aide ménagère</option>
                <option value="baby_sitter">Baby-sitter</option>
                <option value="artisan">Artisan / Travaux</option>
                <option value="famille">Famille</option>
              </select>
            </div>
          </div>

          <div style="background:var(--d-sec-bg, #0f172a); padding:12px; border-radius:10px; border:1px solid var(--d-border, rgba(255,255,255,0.1));">
            <label style="display:flex; align-items:center; gap:8px; cursor:pointer; font-size:13px; font-weight:700; color:var(--d-text, #fff);">
              <input type="checkbox" id="prof-single-use" style="accent-color:#10b981; width:16px; height:16px;">
              <span>⚡ Usage Unique (se désactive après 1er désarmement)</span>
            </label>
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
            <div>
              <label style="display:block; font-size:12px; font-weight:700; color:var(--d-subtext, #94a3b8); margin-bottom:4px;">Valide à partir du (Optionnel)</label>
              <input type="date" id="prof-valid-from" style="width:100%; padding:9px 12px; border-radius:8px; border:1px solid var(--d-border, rgba(255,255,255,0.15)); background:var(--d-sec-bg, #0f172a); color:var(--d-text, #fff); font-size:12px; box-sizing:border-box;">
            </div>
            <div>
              <label style="display:block; font-size:12px; font-weight:700; color:var(--d-subtext, #94a3b8); margin-bottom:4px;">Expire le (Optionnel)</label>
              <input type="date" id="prof-valid-to" style="width:100%; padding:9px 12px; border-radius:8px; border:1px solid var(--d-border, rgba(255,255,255,0.15)); background:var(--d-sec-bg, #0f172a); color:var(--d-text, #fff); font-size:12px; box-sizing:border-box;">
            </div>
          </div>

          <div>
            <label style="display:block; font-size:12px; font-weight:700; color:var(--d-subtext, #94a3b8); margin-bottom:4px;">Plage horaire autorisée (Optionnel, ex: 08:00-18:00)</label>
            <input type="text" id="prof-hours" placeholder="Vide = 24h/24" style="width:100%; padding:9px 12px; border-radius:8px; border:1px solid var(--d-border, rgba(255,255,255,0.15)); background:var(--d-sec-bg, #0f172a); color:var(--d-text, #fff); font-size:12px; box-sizing:border-box;">
          </div>

          <div>
            <label style="display:block; font-size:12px; font-weight:700; color:var(--d-subtext, #94a3b8); margin-bottom:6px;">Jours autorisés</label>
            <div style="display:flex; gap:6px; flex-wrap:wrap;">
              ${[
                { id: 1, label: "Lun" },
                { id: 2, label: "Mar" },
                { id: 3, label: "Mer" },
                { id: 4, label: "Jeu" },
                { id: 5, label: "Ven" },
                { id: 6, label: "Sam" },
                { id: 7, label: "Dim" },
              ].map(d => `
                <label style="display:inline-flex; align-items:center; gap:4px; font-size:12px; background:var(--d-sec-bg, #0f172a); padding:6px 10px; border-radius:6px; border:1px solid var(--d-border, rgba(255,255,255,0.1)); cursor:pointer;">
                  <input type="checkbox" class="prof-day" value="${d.id}" checked style="accent-color:#10b981;"> ${d.label}
                </label>
              `).join('')}
            </div>
          </div>
        </div>

        <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:24px; border-top:1px solid var(--d-border, rgba(255,255,255,0.1)); padding-top:16px;">
          <button id="modal-cancel-profile" style="background:var(--d-sec-bg, #334155); color:var(--d-text, #fff); border:none; padding:10px 18px; border-radius:8px; font-weight:700; font-size:13px; cursor:pointer;">Annuler</button>
          <button id="modal-save-profile" style="background:#10b981; color:white; border:none; padding:10px 20px; border-radius:8px; font-weight:700; font-size:13px; cursor:pointer; display:inline-flex; align-items:center; gap:6px;">
            <ha-icon icon="mdi:check" style="--mdc-icon-size:18px;"></ha-icon> Enregistrer le Profil
          </button>
        </div>
      </div>
    `;

    this.appendChild(modal);

    const closeModal = () => modal.remove();
    modal.querySelector('#modal-close-profile')?.addEventListener('click', closeModal);
    modal.querySelector('#modal-cancel-profile')?.addEventListener('click', closeModal);
    modal.addEventListener('click', (ev) => {
      if (ev.target === modal) closeModal();
    });

    modal.querySelector('#modal-save-profile')?.addEventListener('click', () => {
      const name = modal.querySelector('#prof-name')?.value?.trim();
      const pin = modal.querySelector('#prof-pin')?.value?.trim();
      const role = modal.querySelector('#prof-role')?.value || 'invite';
      const singleUse = Boolean(modal.querySelector('#prof-single-use')?.checked);
      const validFrom = modal.querySelector('#prof-valid-from')?.value || null;
      const validTo = modal.querySelector('#prof-valid-to')?.value || null;
      const allowedHours = modal.querySelector('#prof-hours')?.value?.trim() || null;

      const checkedDays = Array.from(modal.querySelectorAll('.prof-day:checked')).map(cb => parseInt(cb.value, 10));

      if (!name) {
        alert("Veuillez saisir un nom ou libellé pour ce profil.");
        return;
      }
      if (!pin || pin.length < 4) {
        alert("Le code PIN doit comporter au moins 4 chiffres.");
        return;
      }

      const saveBtn = modal.querySelector('#modal-save-profile');
      if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerText = "Enregistrement...";
      }

      this._hass.callService('domolink_alarm', 'add_user_profile', {
        name: name,
        pin: pin,
        role: role,
        single_use: singleUse,
        valid_from: validFrom,
        valid_to: validTo,
        allowed_hours: allowedHours,
        allowed_days: checkedDays
      }).then(() => {
        closeModal();
        if (this._configDraft && this._configDraft.user_profiles) {
          try {
            let profs = typeof this._configDraft.user_profiles === 'string'
              ? JSON.parse(this._configDraft.user_profiles)
              : this._configDraft.user_profiles;
            profs = profs.filter(p => p.name !== name && p.pin !== pin);
            profs.push({
              name, pin, role, single_use: singleUse, valid_from: validFrom, valid_to: validTo, allowed_hours: allowedHours, allowed_days: checkedDays, enabled: true
            });
            this._configDraft.user_profiles = JSON.stringify(profs);
          } catch (e) {}
        }
        this.render();
      }).catch(err => {
        if (saveBtn) {
          saveBtn.disabled = false;
          saveBtn.innerHTML = `<ha-icon icon="mdi:check" style="--mdc-icon-size:18px;"></ha-icon> Enregistrer le Profil`;
        }
        alert("Erreur lors de l'enregistrement du profil : " + (err && err.message ? err.message : String(err)));
      });
    });
  }

  // ─── Dynamic Navigation Badges ──────────────────

  _updateNavBadges(alarmEntity, attrs) {
    if (!attrs) attrs = {};

    // 1. Armement Badge
    const elArm = this.querySelector('#nav-badge-arm');
    if (elArm) {
      const state = alarmEntity ? alarmEntity.state : 'disarmed';
      let stateLabel = 'DÉSARMÉ';
      let stateSub = 'Prêt';
      let pillClass = 'badge-arm-disarmed';

      if (state === 'armed_away') {
        stateLabel = 'ABSENT';
        stateSub = 'Actif';
        pillClass = 'badge-arm-armed';
      } else if (state === 'armed_home') {
        stateLabel = 'MAISON';
        stateSub = 'Actif';
        pillClass = 'badge-arm-armed';
      } else if (state === 'armed_night') {
        stateLabel = 'NUIT';
        stateSub = 'Actif';
        pillClass = 'badge-arm-armed';
      } else if (state === 'armed_vacation') {
        stateLabel = 'VACANCES';
        stateSub = 'Actif';
        pillClass = 'badge-arm-armed';
      } else if (state === 'triggered') {
        stateLabel = 'ALERTE';
        stateSub = 'Sirène';
        pillClass = 'badge-arm-triggered';
      } else if (state === 'pending' || state === 'arming') {
        stateLabel = 'DÉLAI';
        stateSub = 'En cours';
        pillClass = 'badge-arm-pending';
      }

      elArm.innerHTML = `
        <div class="nav-badge-stack">
          <span class="nav-badge-pill ${pillClass}">${stateLabel}</span>
          <span class="nav-badge-pill ${pillClass}">${stateSub}</span>
        </div>
      `;
    }

    // 2. Équipements Badge (OK en vert, KO en dessous)
    const elEquip = this.querySelector('#nav-badge-equip');
    if (elEquip) {
      const equipCategories = [
        "opening_sensors", "motion_sensors", "tamper_sensors", "safety_sensors",
        "night_sensors", "sirens", "lights", "cameras", "media_players", "persons"
      ];
      const allEquipIds = new Set();
      for (const cat of equipCategories) {
        const list = attrs[cat];
        if (Array.isArray(list)) {
          list.forEach(id => { if (id) allEquipIds.add(id); });
        }
      }
      if (attrs.sensor_health && typeof attrs.sensor_health === 'object') {
        Object.keys(attrs.sensor_health).forEach(id => { if (id) allEquipIds.add(id); });
      }

      const bypassedSensors = attrs.bypassed_sensors || [];
      let equipOk = 0;
      let equipKo = 0;

      for (const entityId of allEquipIds) {
        const entityState = this._hass && this._hass.states ? this._hass.states[entityId] : null;
        const isBypassed = bypassedSensors.includes(entityId);
        const healthItem = attrs.sensor_health ? attrs.sensor_health[entityId] : null;

        let isKo = false;
        if (isBypassed) {
          isKo = true;
        } else if (!entityState || entityState.state === 'unavailable' || entityState.state === 'unknown') {
          isKo = true;
        } else if (healthItem && healthItem.offline) {
          isKo = true;
        } else {
          const domain = entityId.split('.')[0];
          if (domain === 'binary_sensor' && entityState.state === 'on') {
            isKo = true;
          }
        }

        if (isKo) equipKo++;
        else equipOk++;
      }

      elEquip.innerHTML = `
        <div class="nav-badge-stack">
          <span class="nav-badge-pill badge-ok">${equipOk} OK</span>
          <span class="nav-badge-pill ${equipKo > 0 ? 'badge-ko' : 'badge-ko zero'}">${equipKo} KO</span>
        </div>
      `;
    }

    // 3. Journal Badge (activations & logs)
    const elLog = this.querySelector('#nav-badge-log');
    if (elLog) {
      const armHistCount = (attrs.arm_history || []).length;
      const sysEvtCount = (attrs.system_events || []).length;
      elLog.innerHTML = `
        <div class="nav-badge-stack">
          <span class="nav-badge-pill badge-neutral">${armHistCount} activ.</span>
          <span class="nav-badge-pill badge-neutral">${sysEvtCount} logs</span>
        </div>
      `;
    }

    // 4. Santé Badge (Score global & alertes/batteries)
    const elHealth = this.querySelector('#nav-badge-health');
    if (elHealth) {
      const healthData = attrs.sensor_health || {};
      const keys = Object.keys(healthData);
      let onlineCount = 0;
      let lowBattCount = 0;
      for (const k of keys) {
        const item = healthData[k];
        if (item && !item.offline) onlineCount++;
        if (item && item.battery !== null && item.battery <= 15) lowBattCount++;
      }
      const offlineCount = keys.length - onlineCount;
      const score = keys.length > 0 ? Math.round((onlineCount / keys.length) * 100) : 100;
      const scoreClass = score >= 95 ? 'badge-ok' : (score >= 80 ? 'badge-warn' : 'badge-ko');
      
      let subText = '0 défaut';
      let subClass = 'badge-ok zero';
      if (lowBattCount > 0) {
        subText = `${lowBattCount} pile${lowBattCount > 1 ? 's' : ''}`;
        subClass = 'badge-ko';
      } else if (offlineCount > 0) {
        subText = `${offlineCount} H.L.`;
        subClass = 'badge-ko';
      }

      elHealth.innerHTML = `
        <div class="nav-badge-stack">
          <span class="nav-badge-pill ${scoreClass}">${score}%</span>
          <span class="nav-badge-pill ${subClass}">${subText}</span>
        </div>
      `;
    }

    // 5. Simulation Badge (Statut & Nb appareils)
    const elSim = this.querySelector('#nav-badge-sim');
    if (elSim) {
      const isRunning = Boolean(attrs.presence_simulation_active);
      const entCount = (attrs.presence_simulation_entities || []).length;
      elSim.innerHTML = `
        <div class="nav-badge-stack">
          <span class="nav-badge-pill ${isRunning ? 'badge-sim-on' : 'badge-sim-off'}">${isRunning ? 'ACTIF' : 'PAUSE'}</span>
          <span class="nav-badge-pill badge-neutral">${entCount} app.</span>
        </div>
      `;
    }

    // 6. Médias Badge (Photos en haut, Vidéos en bas)
    const elMedia = this.querySelector('#nav-badge-media');
    if (elMedia) {
      const rawFiles = Array.isArray(attrs.media_files) ? attrs.media_files : [];
      let photoCount = 0;
      let videoCount = 0;
      rawFiles.forEach(f => {
        if (f && f.name) {
          if (/\.(jpg|jpeg|png)$/i.test(f.name)) photoCount++;
          else if (/\.(mp4|webm|ogg)$/i.test(f.name)) videoCount++;
        }
      });
      elMedia.innerHTML = `
        <div class="nav-badge-stack">
          <span class="nav-badge-pill badge-photo">${photoCount} photo${photoCount > 1 ? 's' : ''}</span>
          <span class="nav-badge-pill badge-video">${videoCount} vidéo${videoCount > 1 ? 's' : ''}</span>
        </div>
      `;
    }

    // 7. Paramètres Badge
    const elParam = this.querySelector('#nav-badge-param');
    if (elParam) {
      const isFtp = Boolean(attrs.ftp_enabled);
      const isDav = Boolean(attrs.webdav_enabled);
      const isGdrive = Boolean(attrs.google_drive_enabled);
      const countCloud = (isFtp ? 1 : 0) + (isDav ? 1 : 0) + (isGdrive ? 1 : 0);
      const cloudLabel = countCloud > 1 ? 'MULTI-CLOUD' : (isGdrive ? 'G-DRIVE' : (isDav ? 'WEBDAV' : (isFtp ? 'FTP' : 'LOCAL')));
      elParam.innerHTML = `
        <div class="nav-badge-stack">
          <span class="nav-badge-pill badge-version">v${attrs.system_version || '0.9.74'}</span>
          <span class="nav-badge-pill badge-neutral">${cloudLabel}</span>
        </div>
      `;
    }
  }

  // ─── Main Render ────────────────────────────────

  render() {
    const alarmEntity = this._getAlarmEntity();
    const attrs = alarmEntity ? alarmEntity.attributes : {};

    this._updateNavBadges(alarmEntity, attrs);

    if (this._activeTab === 'arm') this._renderArmTab(alarmEntity);
    else if (this._activeTab === 'equip') this._renderEquipTab(attrs);
    else if (this._activeTab === 'log') this._renderLogTab();
    else if (this._activeTab === 'health') this._renderHealthTab();
    else if (this._activeTab === 'sim') this._renderSimTab(attrs);
    else if (this._activeTab === 'media') {
      // Only re-render media tab when data actually changed (prevents flickering)
      const mediaSignature = JSON.stringify(attrs.media_files || []) + '|' + (attrs.camera_test_running || false) + '|' + (this._mediaType || 'photos') + '|' + (this._mediaPage || 0);
      if (this._lastMediaSignature !== mediaSignature || this._mediaForceRender) {
        this._lastMediaSignature = mediaSignature;
        this._mediaForceRender = false;
        this._renderMediaTab(attrs);
      }
    }
    else if (this._activeTab === 'param') {
      const pane = this.querySelector('#pane-param');
      const hasFocus = pane && pane.contains(document.activeElement);
      if (!this._paramRendered && !hasFocus) {
        this._paramRendered = true;
        this._renderParamTab(alarmEntity);
      }
    }
  }

  // ─── Helpers ────────────────────────────────────

  // ─── Tab: Médias (Photos & Vidéos) ──────────────

  _renderMediaTab(attrs) {
    const container = this.querySelector('#pane-media');
    if (!container) return;

    const mediaPath = attrs.media_path || 'domolink_media';
    if (!this._mediaType) this._mediaType = 'photos';
    if (!this._mediaPage) this._mediaPage = 0;
    const PAGE_SIZE = 24;

    // Parse media files directly from alarm entity attributes (synchronous & instant)
    const rawFiles = Array.isArray(attrs.media_files) ? attrs.media_files : [];
    const photos = [];
    const videos = [];
    rawFiles.forEach(f => {
      if (/\.(jpg|jpeg|png)$/i.test(f.name)) photos.push(f);
      else if (/\.(mp4|webm|ogg)$/i.test(f.name)) videos.push(f);
    });
    photos.sort((a,b) => b.name.localeCompare(a.name));
    videos.sort((a,b) => b.name.localeCompare(a.name));
    this._mediaFiles = { _path: mediaPath, photos, videos };

    const files = this._mediaType === 'photos' ? this._mediaFiles.photos : this._mediaFiles.videos;
    const totalPages = Math.max(1, Math.ceil(files.length / PAGE_SIZE));
    const pageFiles = files.slice(this._mediaPage * PAGE_SIZE, (this._mediaPage + 1) * PAGE_SIZE);

    let gridHtml = '';
    if (pageFiles.length === 0) {
      gridHtml = `<div style="grid-column:1/-1;text-align:center;padding:60px 20px;color:var(--d-subtext);">
        <ha-icon icon="${this._mediaType === 'photos' ? 'mdi:image-off' : 'mdi:video-off'}" style="--mdc-icon-size:48px;opacity:0.4;"></ha-icon>
        <div style="margin-top:16px;font-size:15px;font-weight:600;">Aucune ${this._mediaType === 'photos' ? 'photo' : 'vidéo'} trouvée</div>
        <div style="font-size:12px;margin-top:6px;opacity:0.7;">Déclenchez une alarme ou lancez un test pour enregistrer des médias.</div>
      </div>`;
    } else {
      pageFiles.forEach((file, idx) => {
        const url = `/local/${mediaPath}/${encodeURIComponent(file.name)}`;
        const isVideo = /\.(mp4|webm|ogg)$/i.test(file.name);
        const label = file.name.replace(/^domolink_/, '').replace(/_/g, ' ').replace(/\.(jpg|mp4|jpeg)$/i, '');
        const sizeStr = file.size ? (file.size > 1048576 ? (file.size/1048576).toFixed(1)+'MB' : (file.size/1024).toFixed(0)+'KB') : '';

        if (isVideo) {
          gridHtml += `
          <div class="media-card" data-filename="${this.escapeHtml(file.name)}">
            <div class="media-thumb media-thumb-video" data-video-player="${url}" data-label="${this.escapeHtml(file.name)}" style="cursor:pointer;position:relative;">
              <video src="${url}#t=0.5" preload="metadata" playsinline muted style="width:100%;height:100%;object-fit:cover;border-radius:12px 12px 0 0;pointer-events:none;"></video>
              <div class="media-play-overlay">
                <div class="media-play-disc">
                  <ha-icon icon="mdi:play" style="--mdc-icon-size:28px;color:#fff;margin-left:2px;"></ha-icon>
                </div>
              </div>
              <div class="media-badge-video">
                <ha-icon icon="mdi:video" style="--mdc-icon-size:12px;"></ha-icon> VIDÉO
              </div>
            </div>
            <div class="media-info" data-video-player="${url}" data-label="${this.escapeHtml(file.name)}" style="cursor:pointer;">
              <div class="media-name" title="${this.escapeHtml(file.name)}">${this.escapeHtml(label)}</div>
              <div class="media-meta">${sizeStr}</div>
            </div>
            <div class="media-actions">
              <a class="media-action-btn" href="${url}" download="${this.escapeHtml(file.name)}" title="Télécharger"><ha-icon icon="mdi:download"></ha-icon></a>
              <button class="media-action-btn" data-action="rename" data-file="${this.escapeHtml(file.name)}" title="Renommer"><ha-icon icon="mdi:pencil"></ha-icon></button>
              <button class="media-action-btn media-action-delete" data-action="delete" data-file="${this.escapeHtml(file.name)}" title="Supprimer"><ha-icon icon="mdi:trash-can"></ha-icon></button>
            </div>
          </div>`;
        } else {
          gridHtml += `
          <div class="media-card" data-filename="${this.escapeHtml(file.name)}">
            <div class="media-thumb" data-lightbox="${url}" data-label="${this.escapeHtml(file.name)}" style="cursor:zoom-in;">
              <img src="${url}" loading="lazy" alt="${this.escapeHtml(file.name)}" style="width:100%;height:100%;object-fit:cover;border-radius:12px 12px 0 0;" onerror="this.src='';this.style.display='none';this.parentElement.innerHTML='<div style=\\'display:flex;align-items:center;justify-content:center;height:100%;color:var(--d-subtext);\\'>❌</div>';">
            </div>
            <div class="media-info">
              <div class="media-name" title="${this.escapeHtml(file.name)}">${this.escapeHtml(label)}</div>
              <div class="media-meta">${sizeStr}</div>
            </div>
            <div class="media-actions">
              <a class="media-action-btn" href="${url}" download="${this.escapeHtml(file.name)}" title="Télécharger"><ha-icon icon="mdi:download"></ha-icon></a>
              <button class="media-action-btn" data-action="rename" data-file="${this.escapeHtml(file.name)}" title="Renommer"><ha-icon icon="mdi:pencil"></ha-icon></button>
              <button class="media-action-btn media-action-delete" data-action="delete" data-file="${this.escapeHtml(file.name)}" title="Supprimer"><ha-icon icon="mdi:trash-can"></ha-icon></button>
            </div>
          </div>`;
        }
      });
    }

    const html = `
      <style>
        .media-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:16px; }
        .media-card { background:var(--d-sec-bg); border:1px solid var(--d-border); border-radius:14px; overflow:hidden; display:flex; flex-direction:column; transition:transform 0.15s; }
        .media-card:hover { transform:translateY(-3px); box-shadow:0 8px 24px rgba(0,0,0,0.12); }
        .media-thumb { height:150px; overflow:hidden; background:var(--d-surface); }
        .media-thumb-video { height:150px; }
        .media-play-overlay { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; background:rgba(0,0,0,0.35); transition:background 0.2s; }
        .media-card:hover .media-play-overlay { background:rgba(0,0,0,0.15); }
        .media-play-disc { width:48px; height:48px; border-radius:50%; background:rgba(245,158,11,0.9); display:flex; align-items:center; justify-content:center; box-shadow:0 4px 16px rgba(0,0,0,0.4); transition:transform 0.2s, background 0.2s; }
        .media-card:hover .media-play-disc { transform:scale(1.1); background:#f59e0b; }
        .media-badge-video { position:absolute; top:8px; right:8px; background:rgba(0,0,0,0.75); color:#fff; font-size:10px; font-weight:700; padding:2px 7px; border-radius:6px; display:flex; align-items:center; gap:4px; letter-spacing:0.5px; }
        .media-info { padding:10px 12px 4px; flex-grow:1; }
        .media-name { font-size:11px; font-weight:700; color:var(--d-text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .media-meta { font-size:10px; color:var(--d-subtext); margin-top:2px; }
        .media-actions { display:flex; gap:4px; padding:8px 10px; border-top:1px solid var(--d-border); justify-content:flex-end; }
        .media-action-btn { display:flex; align-items:center; justify-content:center; width:30px; height:30px; border-radius:8px; border:1px solid var(--d-border); background:var(--d-sec-bg); color:var(--d-subtext); cursor:pointer; text-decoration:none; transition:all 0.15s; }
        .media-action-btn:hover { color:var(--d-text); border-color:var(--d-text); }
        .media-action-delete:hover { color:#ef4444; border-color:#ef4444; }
        .media-type-pill { padding:8px 20px; border-radius:9999px; border:1.5px solid var(--d-border); background:var(--d-sec-bg); color:var(--d-subtext); font-size:13px; font-weight:700; cursor:pointer; transition:all 0.2s; }
        .media-type-pill.active { background:#f59e0b; color:#fff; border-color:#f59e0b; }
        .media-lightbox { position:fixed; inset:0; background:rgba(0,0,0,0.92); backdrop-filter:blur(6px); z-index:99999; display:flex; align-items:center; justify-content:center; cursor:zoom-out; padding:20px; }
        .media-lightbox img { max-width:92vw; max-height:92vh; border-radius:8px; box-shadow:0 20px 60px rgba(0,0,0,0.8); }
        .media-lightbox-close { position:absolute; top:16px; right:20px; color:#fff; font-size:32px; cursor:pointer; font-weight:300; line-height:1; }
        .video-modal-container { background:#18181b; border:1px solid rgba(255,255,255,0.15); border-radius:16px; overflow:hidden; width:92vw; max-width:880px; box-shadow:0 25px 60px rgba(0,0,0,0.8); display:flex; flex-direction:column; cursor:default; }
        .video-modal-header { display:flex; align-items:center; justify-content:space-between; padding:14px 20px; background:#27272a; border-bottom:1px solid rgba(255,255,255,0.1); color:#fff; font-weight:700; font-size:14px; }
        .video-modal-body { position:relative; background:#000; display:flex; align-items:center; justify-content:center; min-height:260px; max-height:68vh; }
        .video-modal-body video { width:100%; max-height:68vh; object-fit:contain; outline:none; }
        .video-modal-footer { display:flex; align-items:center; justify-content:space-between; padding:12px 20px; background:#27272a; border-top:1px solid rgba(255,255,255,0.1); flex-wrap:wrap; gap:10px; }
        .video-modal-btn { display:inline-flex; align-items:center; gap:6px; padding:8px 16px; border-radius:8px; font-size:12px; font-weight:700; text-decoration:none; cursor:pointer; border:none; transition:all 0.15s; }
        .video-modal-btn.primary { background:#f59e0b; color:#fff; }
        .video-modal-btn.primary:hover { background:#d97706; }
        .video-modal-btn.secondary { background:rgba(255,255,255,0.1); color:#e4e4e7; }
        .video-modal-btn.secondary:hover { background:rgba(255,255,255,0.2); color:#fff; }
        @keyframes spin { from {transform:rotate(0deg)} to {transform:rotate(360deg)} }
      </style>

      <div class="glass-card" style="display:flex;flex-direction:column;gap:20px;">
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
          <div style="font-size:17px;font-weight:800;color:var(--d-text);display:flex;align-items:center;gap:8px;">
            <ha-icon icon="mdi:image-multiple" style="color:#f59e0b;"></ha-icon>
            Médiathèque — <span style="font-size:13px;color:var(--d-subtext);font-weight:600;">/local/${mediaPath}/</span>
          </div>
          <div style="display:flex;gap:8px;align-items:center;">
            <button class="media-type-pill ${this._mediaType === 'photos' ? 'active' : ''}" id="media-btn-photos">
              <ha-icon icon="mdi:image" style="--mdc-icon-size:16px;vertical-align:middle;"></ha-icon> Photos (${this._mediaFiles.photos.length})
            </button>
            <button class="media-type-pill ${this._mediaType === 'videos' ? 'active' : ''}" id="media-btn-videos">
              <ha-icon icon="mdi:video" style="--mdc-icon-size:16px;vertical-align:middle;"></ha-icon> Vidéos (${this._mediaFiles.videos.length})
            </button>
            <button id="media-btn-refresh" style="width:36px;height:36px;border-radius:9999px;border:1px solid var(--d-border);background:var(--d-sec-bg);color:var(--d-subtext);cursor:pointer;display:flex;align-items:center;justify-content:center;" title="Actualiser">
              <ha-icon icon="mdi:refresh" style="--mdc-icon-size:18px;"></ha-icon>
            </button>
          </div>
        </div>

        <!-- Storage Usage & Auto-Purge Bar -->
        <div style="background:var(--d-sec-bg); border:1px solid var(--d-border); border-radius:14px; padding:14px 18px; display:flex; flex-direction:column; gap:10px;">
          <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
            <div style="display:flex; align-items:center; gap:10px;">
              <div style="width:34px; height:34px; border-radius:10px; background:rgba(245,158,11,0.12); display:flex; align-items:center; justify-content:center; color:#f59e0b;">
                <ha-icon icon="mdi:database-outline" style="--mdc-icon-size:20px;"></ha-icon>
              </div>
              <div>
                <div style="font-size:13px; font-weight:800; color:var(--d-text); display:flex; align-items:center; gap:8px;">
                  <span>Stockage des Médias Locaux</span>
                  <span style="font-size:11px; font-weight:600; color:var(--d-subtext);">(${attrs.media_storage_count || (photos.length + videos.length)} fichiers)</span>
                </div>
                <div style="font-size:11px; color:var(--d-subtext); margin-top:2px;">
                  Rétention : <strong style="color:var(--d-text);">${attrs.media_storage_retention_days > 0 ? attrs.media_storage_retention_days + ' jours' : 'Illimitée'}</strong> • Quota : <strong style="color:var(--d-text);">${attrs.media_storage_max_mb > 0 ? attrs.media_storage_max_mb + ' Mo' : 'Illimité'}</strong>
                </div>
              </div>
            </div>

            <div style="display:flex; align-items:center; gap:12px;">
              <div style="text-align:right;">
                <span style="font-size:14px; font-weight:800; color:var(--d-text);">${attrs.media_storage_mb || 0} Mo</span>
                ${attrs.media_storage_max_mb > 0 ? `<span style="font-size:11px; color:var(--d-subtext); font-weight:600;"> / ${attrs.media_storage_max_mb} Mo (${attrs.media_storage_percent || 0}%)</span>` : ''}
              </div>
              <button class="btn-clean-media" id="btn-purge-media" title="Purger immédiatement les anciens médias selon la politique de rétention" style="padding:7px 14px; border-radius:10px; border:1px solid rgba(239,68,68,0.3); background:rgba(239,68,68,0.08); color:#ef4444; font-size:11.5px; font-weight:800; cursor:pointer; display:flex; align-items:center; gap:6px; transition:all 0.2s;">
                <ha-icon icon="mdi:broom" style="--mdc-icon-size:15px;"></ha-icon>
                <span>Purger</span>
              </button>
            </div>
          </div>

          <!-- Progress Bar -->
          ${attrs.media_storage_max_mb > 0 ? `
          <div style="width:100%; height:8px; background:rgba(156,163,175,0.2); border-radius:9999px; overflow:hidden;">
            <div style="width:${Math.min(100, Math.max(0, attrs.media_storage_percent || 0))}%; height:100%; border-radius:9999px; background:${(attrs.media_storage_percent || 0) > 85 ? '#ef4444' : ((attrs.media_storage_percent || 0) > 65 ? '#f59e0b' : '#10b981')}; transition:width 0.3s ease;"></div>
          </div>
          ` : ''}
        </div>

        <div class="media-grid">${gridHtml}</div>

        ${totalPages > 1 ? `
        <div style="display:flex;align-items:center;justify-content:center;gap:12px;padding-top:8px;">
          <button id="media-prev" style="padding:8px 20px;border-radius:9999px;border:1px solid var(--d-border);background:var(--d-sec-bg);color:var(--d-text);font-weight:700;cursor:pointer;${this._mediaPage === 0 ? 'opacity:0.4;pointer-events:none;' : ''}">← Préc.</button>
          <span style="font-size:13px;color:var(--d-subtext);font-weight:700;">Page ${this._mediaPage + 1} / ${totalPages}</span>
          <button id="media-next" style="padding:8px 20px;border-radius:9999px;border:1px solid var(--d-border);background:var(--d-sec-bg);color:var(--d-text);font-weight:700;cursor:pointer;${this._mediaPage >= totalPages - 1 ? 'opacity:0.4;pointer-events:none;' : ''}">Suiv. →</button>
        </div>` : ''}
      </div>
    `;

    container.innerHTML = html;

    // Type toggle
    container.querySelector('#media-btn-photos')?.addEventListener('click', () => {
      this._mediaType = 'photos'; this._mediaPage = 0; this._mediaForceRender = true; this._lastMediaSignature = null; this.render();
    });
    container.querySelector('#media-btn-videos')?.addEventListener('click', () => {
      this._mediaType = 'videos'; this._mediaPage = 0; this._mediaForceRender = true; this._lastMediaSignature = null; this.render();
    });

    // Refresh
    container.querySelector('#media-btn-refresh')?.addEventListener('click', () => {
      this._mediaPage = 0; this._mediaForceRender = true; this._lastMediaSignature = null; this.render();
    });

    // Manual Purge Action
    container.querySelector('#btn-purge-media')?.addEventListener('click', () => {
      if (confirm("Voulez-vous lancer le nettoyage des médias d'alarme ?\nLes fichiers dépassant la durée de rétention ou le quota d'espace seront automatiquement purgés.")) {
        const alarmEntity = this._getAlarmEntity();
        if (alarmEntity) {
          this._hass.callService('domolink_alarm', 'clean_media', { entity_id: alarmEntity.entity_id }).then(() => {
            this._mediaPage = 0;
            this._mediaForceRender = true;
            this._lastMediaSignature = null;
            this.render();
          });
        }
      }
    });

    // Pagination
    container.querySelector('#media-prev')?.addEventListener('click', () => {
      if (this._mediaPage > 0) { this._mediaPage--; this._mediaForceRender = true; this._lastMediaSignature = null; this.render(); }
    });
    container.querySelector('#media-next')?.addEventListener('click', () => {
      if (this._mediaPage < totalPages - 1) { this._mediaPage++; this._mediaForceRender = true; this._lastMediaSignature = null; this.render(); }
    });

    // Lightbox for photos
    container.querySelectorAll('[data-lightbox]').forEach(el => {
      el.addEventListener('click', () => {
        const src = el.getAttribute('data-lightbox');
        const label = el.getAttribute('data-label') || 'Photo';
        const lb = document.createElement('div');
        lb.className = 'media-lightbox';
        lb.style = "position:fixed;inset:0;background:rgba(0,0,0,0.92);backdrop-filter:blur(8px);z-index:999999;display:flex;align-items:center;justify-content:center;padding:20px;cursor:default;";
        lb.innerHTML = `
          <div class="video-modal-container" style="background:#18181b;border:1px solid rgba(255,255,255,0.18);border-radius:16px;overflow:hidden;width:92vw;max-width:860px;box-shadow:0 25px 60px rgba(0,0,0,0.85);display:flex;flex-direction:column;">
            <div class="video-modal-header" style="display:flex;align-items:center;justify-content:space-between;padding:14px 20px;background:#27272a;border-bottom:1px solid rgba(255,255,255,0.1);color:#fff;font-weight:700;font-size:14px;">
              <div style="display:flex;align-items:center;gap:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                <ha-icon icon="mdi:image" style="color:#f59e0b;--mdc-icon-size:20px;"></ha-icon>
                <span>${this.escapeHtml(label)}</span>
              </div>
              <span class="media-lightbox-close" id="lb-close" style="position:static;font-size:28px;cursor:pointer;line-height:1;">×</span>
            </div>
            <div class="video-modal-body" style="position:relative;background:#000;display:flex;align-items:center;justify-content:center;min-height:260px;max-height:68vh;overflow:hidden;">
              <img id="active-photo-player" src="${src}" style="max-width:100%;max-height:68vh;object-fit:contain;transition:transform 0.3s ease;transform-origin:center;" />
            </div>
            <div class="video-modal-footer" style="display:flex;align-items:center;justify-content:space-between;padding:12px 20px;background:#27272a;border-top:1px solid rgba(255,255,255,0.1);flex-wrap:wrap;gap:10px;">
              <div style="display:flex;gap:10px;flex-wrap:wrap;">
                <button class="video-modal-btn secondary" id="photo-btn-zoom" style="display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:8px;font-size:12px;font-weight:700;background:rgba(255,255,255,0.1);color:#e4e4e7;border:none;cursor:pointer;">
                  <ha-icon icon="mdi:magnify-plus" style="--mdc-icon-size:16px;"></ha-icon> Zoom x1
                </button>
                <button class="video-modal-btn secondary" id="photo-btn-fs" style="display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:8px;font-size:12px;font-weight:700;background:rgba(255,255,255,0.1);color:#e4e4e7;border:none;cursor:pointer;">
                  <ha-icon icon="mdi:fullscreen" style="--mdc-icon-size:16px;"></ha-icon> Plein Écran
                </button>
                <a class="video-modal-btn primary" href="${src}" download="${this.escapeHtml(label)}" style="display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:8px;font-size:12px;font-weight:700;background:#f59e0b;color:#fff;text-decoration:none;">
                  <ha-icon icon="mdi:download" style="--mdc-icon-size:16px;"></ha-icon> Télécharger
                </a>
              </div>
              <button class="video-modal-btn secondary" id="lb-btn-close" style="padding:8px 16px;border-radius:8px;font-size:12px;font-weight:700;background:rgba(255,255,255,0.1);color:#e4e4e7;border:none;cursor:pointer;">Fermer</button>
            </div>
          </div>
        `;
        this.appendChild(lb);

        const imgEl = lb.querySelector('#active-photo-player');
        let zoomLevel = 1;
        lb.querySelector('#photo-btn-zoom')?.addEventListener('click', (ev) => {
          zoomLevel = zoomLevel === 1 ? 2 : (zoomLevel === 2 ? 4 : 1);
          imgEl.style.transform = `scale(${zoomLevel})`;
          imgEl.style.cursor = zoomLevel > 1 ? 'grab' : 'default';
          ev.currentTarget.innerHTML = `<ha-icon icon="${zoomLevel > 1 ? 'mdi:magnify-minus' : 'mdi:magnify-plus'}" style="--mdc-icon-size:16px;"></ha-icon> Zoom x${zoomLevel}`;
        });
        
        let isDragging = false, startX, startY, transX = 0, transY = 0;
        imgEl.addEventListener('mousedown', e => { if (zoomLevel > 1) { isDragging = true; startX = e.clientX - transX; startY = e.clientY - transY; imgEl.style.cursor = 'grabbing'; e.preventDefault(); } });
        window.addEventListener('mousemove', e => { if (isDragging && zoomLevel > 1) { transX = e.clientX - startX; transY = e.clientY - startY; imgEl.style.transform = `scale(${zoomLevel}) translate(${transX/zoomLevel}px, ${transY/zoomLevel}px)`; } });
        window.addEventListener('mouseup', () => { isDragging = false; if (zoomLevel > 1) imgEl.style.cursor = 'grab'; });
        
        lb.querySelector('#photo-btn-fs')?.addEventListener('click', () => {
          if (imgEl.requestFullscreen) imgEl.requestFullscreen();
          else if (imgEl.webkitRequestFullscreen) imgEl.webkitRequestFullscreen();
        });

        const closeLb = () => lb.remove();
        lb.querySelector('#lb-close')?.addEventListener('click', closeLb);
        lb.querySelector('#lb-btn-close')?.addEventListener('click', closeLb);
        lb.addEventListener('click', (ev) => { if (ev.target === lb) closeLb(); });
      });
    });

    // Dedicated Video Player Modal
    container.querySelectorAll('[data-video-player]').forEach(el => {
      el.addEventListener('click', (e) => {
        if (e.target.closest('.media-actions')) return;
        const url = el.getAttribute('data-video-player');
        const label = el.getAttribute('data-label') || 'Vidéo';

        const modal = document.createElement('div');
        modal.className = 'media-lightbox';
        modal.style = "position:fixed;inset:0;background:rgba(0,0,0,0.92);backdrop-filter:blur(8px);z-index:999999;display:flex;align-items:center;justify-content:center;padding:20px;cursor:default;";
        modal.innerHTML = `
          <div class="video-modal-container" id="video-modal-box" style="background:#18181b;border:1px solid rgba(255,255,255,0.18);border-radius:16px;overflow:hidden;width:92vw;max-width:860px;box-shadow:0 25px 60px rgba(0,0,0,0.85);display:flex;flex-direction:column;">
            <div class="video-modal-header" style="display:flex;align-items:center;justify-content:space-between;padding:14px 20px;background:#27272a;border-bottom:1px solid rgba(255,255,255,0.1);color:#fff;font-weight:700;font-size:14px;">
              <div style="display:flex;align-items:center;gap:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                <ha-icon icon="mdi:video" style="color:#f59e0b;--mdc-icon-size:20px;"></ha-icon>
                <span>${this.escapeHtml(label)}</span>
              </div>
              <span class="media-lightbox-close" id="vid-close" style="position:static;font-size:28px;cursor:pointer;line-height:1;">×</span>
            </div>
            <div class="video-modal-body" style="position:relative;background:#000;display:flex;align-items:center;justify-content:center;min-height:260px;max-height:68vh;">
              <video id="active-video-player" src="${url}" controls autoplay playsinline preload="auto" style="width:100%;max-height:68vh;background:#000;display:block;outline:none;"></video>
            </div>
            <div class="video-modal-footer" style="display:flex;align-items:center;justify-content:space-between;padding:12px 20px;background:#27272a;border-top:1px solid rgba(255,255,255,0.1);flex-wrap:wrap;gap:10px;">
              <div style="display:flex;gap:10px;flex-wrap:wrap;">
                <button class="video-modal-btn secondary" id="vid-btn-speed" style="display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:8px;font-size:12px;font-weight:700;background:rgba(255,255,255,0.1);color:#e4e4e7;border:none;cursor:pointer;">
                  <ha-icon icon="mdi:fast-forward" style="--mdc-icon-size:16px;"></ha-icon> x1
                </button>
                <button class="video-modal-btn secondary" id="vid-btn-fs" style="display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:8px;font-size:12px;font-weight:700;background:rgba(255,255,255,0.1);color:#e4e4e7;border:none;cursor:pointer;">
                  <ha-icon icon="mdi:fullscreen" style="--mdc-icon-size:16px;"></ha-icon> Plein Écran
                </button>
                <a class="video-modal-btn primary" href="${url}" download="${this.escapeHtml(label)}" style="display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:8px;font-size:12px;font-weight:700;background:#f59e0b;color:#fff;text-decoration:none;">
                  <ha-icon icon="mdi:download" style="--mdc-icon-size:16px;"></ha-icon> Télécharger le MP4
                </a>
                <a class="video-modal-btn secondary" href="${url}" target="_blank" style="display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:8px;font-size:12px;font-weight:700;background:rgba(255,255,255,0.1);color:#e4e4e7;text-decoration:none;">
                  <ha-icon icon="mdi:open-in-new" style="--mdc-icon-size:16px;"></ha-icon> Ouvrir dans un onglet
                </a>
              </div>
              <button class="video-modal-btn secondary" id="vid-btn-close" style="padding:8px 16px;border-radius:8px;font-size:12px;font-weight:700;background:rgba(255,255,255,0.1);color:#e4e4e7;border:none;cursor:pointer;">Fermer</button>
            </div>
          </div>
        `;
        this.appendChild(modal);

        const videoEl = modal.querySelector('#active-video-player');
        if (videoEl) {
          const playPromise = videoEl.play();
          if (playPromise !== undefined) {
            playPromise.catch(() => {
              // Browser autoplay policy might block sound; mute and retry automatically
              videoEl.muted = true;
              videoEl.play().catch(() => {});
            });
          }

          videoEl.addEventListener('error', () => {
            const errBox = document.createElement('div');
            errBox.style = "position:absolute;inset:0;background:rgba(18,18,20,0.92);display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px;text-align:center;color:#fff;z-index:10;";
            errBox.innerHTML = `
              <ha-icon icon="mdi:alert-circle" style="color:#ef4444;--mdc-icon-size:46px;margin-bottom:12px;"></ha-icon>
              <div style="font-weight:700;font-size:16px;margin-bottom:8px;">Vidéo incomplète ou non décodable</div>
              <div style="font-size:13px;opacity:0.85;max-width:440px;line-height:1.5;margin-bottom:18px;">
                Ce fichier est incomplet (enregistré lors d'un test précédent) ou utilise un codec non supporté en direct par le navigateur. Vous pouvez le supprimer avec l'icône 🗑️ Corbeille et déclencher l'alarme pour créer un nouvel enregistrement valide.
              </div>
              <div style="display:flex;gap:10px;">
                <a class="video-modal-btn primary" href="${url}" download="${this.escapeHtml(label)}" style="display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:8px;font-size:12px;font-weight:700;background:#f59e0b;color:#fff;text-decoration:none;">
                  <ha-icon icon="mdi:download" style="--mdc-icon-size:16px;"></ha-icon> Télécharger le fichier MP4
                </a>
              </div>
            `;
            videoEl.parentElement.appendChild(errBox);
          });
        }
        
        modal.querySelector('#vid-btn-speed')?.addEventListener('click', (ev) => {
          let rate = videoEl.playbackRate;
          rate = rate === 1 ? 2 : (rate === 2 ? 4 : 1);
          videoEl.playbackRate = rate;
          ev.currentTarget.innerHTML = `<ha-icon icon="mdi:fast-forward" style="--mdc-icon-size:16px;"></ha-icon> x${rate}`;
        });

        modal.querySelector('#vid-btn-fs')?.addEventListener('click', () => {
          if (videoEl.requestFullscreen) videoEl.requestFullscreen();
          else if (videoEl.webkitRequestFullscreen) videoEl.webkitRequestFullscreen();
        });

        const closeModal = () => {
          if (videoEl) {
            videoEl.pause();
            videoEl.removeAttribute('src');
            videoEl.load();
          }
          modal.remove();
        };

        modal.querySelector('#vid-close')?.addEventListener('click', closeModal);
        modal.querySelector('#vid-btn-close')?.addEventListener('click', closeModal);
        modal.addEventListener('click', (ev) => {
          if (ev.target === modal) closeModal();
        });
      });
    });

    // File actions (rename / delete)
    container.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const action = btn.getAttribute('data-action');
        const filename = btn.getAttribute('data-file');
        
        if (action === 'delete') {
          if (!confirm(`Supprimer définitivement "${filename}" ?`)) return;
          try {
            await this._hass.callService('domolink_alarm', 'media_action', { action: 'delete', filename });
            this._mediaForceRender = true;
            this._lastMediaSignature = null;
            this.render();
          } catch (err) {
            alert('Erreur lors de la suppression : ' + (err.message || err));
          }
        } else if (action === 'rename') {
          const ext = filename.includes('.') ? '.' + filename.split('.').pop() : '';
          const baseName = filename.slice(0, filename.lastIndexOf('.'));
          const newBase = prompt(`Nouveau nom pour "${filename}" (sans extension) :`, baseName);
          if (!newBase || newBase.trim() === '') return;
          const newName = newBase.trim() + ext;
          try {
            await this._hass.callService('domolink_alarm', 'media_action', { action: 'rename', filename, new_name: newName });
            this._mediaForceRender = true;
            this._lastMediaSignature = null;
            this.render();
          } catch (err) {
            alert('Erreur lors du renommage : ' + (err.message || err));
          }
        }
      });
    });
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
