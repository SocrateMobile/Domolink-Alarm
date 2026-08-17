# Domolink Alarm

Domolink Alarm est une intégration de sécurité de niveau professionnel pour Home Assistant.
Conçue pour dépasser les standards du marché, elle offre une configuration 100% UI fluide et multi-étapes, gère les sirènes, les caméras, la détection de sabotage (tamper) 24h/24, et embarque des alertes TTS scénarisées.

## Fonctionnalités Principales

- **Configuration Multi-Étapes (Wizard UI)** : Fini les fichiers YAML, tout se configure proprement via un assistant UI (Config Flow) supportant la multi-sélection d'entités avec auto-complétion.
- **Gestion des Modes Intelligente** :
  - *Armé Absent* : Toute détection (portes, fenêtres, radars, caméras) déclenche l'alerte complète (Notifications, Sirène, Caméras, TTS).
  - *Armé Présent* : Seules les ouvertures périphériques déclenchent (pas de radars intérieurs), déclenchant notifications et caméras sans sirène.
  - *Armé Nuit* : Surveillance complète mais alertes discrètes (TTS et notifications, pas de sirène hurlante).
- **Sécurité 24/7 (Tamper)** : Les capteurs de sabotage (ex: boîtier d'alarme ouvert) déclenchent l'alarme instantanément, même si le système est désarmé.
- **Actions Asynchrones Puissantes** :
  - TTS : Message dissuasif complet ("Alerte intrusion détectée... La police est prévenue...").
  - Caméras : Enregistrement local via `camera.record`.
  - Notifications dynamiques listant précisément le ou les capteurs ayant détecté l'intrusion.
- **Persistance d'État (RestoreEntity)** : L'alarme retrouve son état exact (Armé, Désarmé, Déclenché) après un redémarrage de Home Assistant.

## Installation via HACS

1. Ajoutez ce dépôt `https://github.com/SocrateMobile/domolink_alarm` comme dépôt personnalisé dans HACS (Catégorie: Intégration).
2. Installez `Domolink Alarm` depuis HACS.
3. Redémarrez Home Assistant.
4. Allez dans *Paramètres > Appareils et services*, cliquez sur *Ajouter une intégration* et cherchez *Domolink Alarm*.
5. Suivez le guide de configuration en 3 étapes.

---

## Dashboard Premium - iOS 26 Liquid Glass

Pour accompagner cette alarme, voici le code YAML d'une carte Lovelace au design ultra-moderne (Nécessite [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom) et [Card-Mod](https://github.com/thomasloven/lovelace-card-mod) installés).

Ce design inclut :
- Un effet **Glassmorphism** (fond flouté translucide, bordures blanches lumineuses).
- Des animations CSS de pulsation pendant les délais d'armement (`STATE_ALARM_ARMING` et `STATE_ALARM_PENDING`).
- Un pavé numérique épuré.

```yaml
type: custom:mushroom-alarm-control-panel
entity: alarm_control_panel.domolink_alarm
states:
  - armed_home
  - armed_away
  - armed_night
show_keypad: true
primary_info: state
secondary_info: last-changed
card_mod:
  style: |
    ha-card {
      background: rgba(255, 255, 255, 0.1) !important;
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid rgba(255, 255, 255, 0.3);
      border-radius: 24px;
      box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
      padding: 16px;
      transition: all 0.3s ease;
    }
    
    /* Animation de pulsation si en délai d'armement ou de déclenchement */
    {% if is_state(config.entity, 'arming') or is_state(config.entity, 'pending') %}
    ha-card {
      animation: pulse-border 2s infinite;
    }
    {% endif %}

    @keyframes pulse-border {
      0% { border-color: rgba(255, 165, 0, 0.3); box-shadow: 0 0 10px rgba(255, 165, 0, 0.1); }
      50% { border-color: rgba(255, 165, 0, 1); box-shadow: 0 0 20px rgba(255, 165, 0, 0.6); }
      100% { border-color: rgba(255, 165, 0, 0.3); box-shadow: 0 0 10px rgba(255, 165, 0, 0.1); }
    }

    /* Style du pavé numérique (Boutons Glass) */
    mwc-button {
      --mdc-theme-primary: white !important;
      background: rgba(255, 255, 255, 0.05);
      border-radius: 12px;
      border: 1px solid rgba(255,255,255,0.1);
      backdrop-filter: blur(5px);
    }
```

## Changelog

### v0.1.0-beta
- Initial release.
- Création du Config Flow multi-étapes.
- Gestion complète des 4 modes d'armement et tamper.
- Actions automatisées sur déclenchement (TTS, Sirène, Record, Notifications).
