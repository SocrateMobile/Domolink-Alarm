# 🚨 Domolink Alarm

**Domolink Alarm** est une intégration de sécurité "Premium" pour Home Assistant.  
Conçue pour dépasser les standards du marché, elle offre une configuration 100% UI fluide et embarque nativement des fonctionnalités dignes des meilleures alarmes professionnelles : gestion des utilisateurs, codes de détresse, alertes mobiles interactives (CarPlay/Apple Watch) et géolocalisation.

---

## 🌟 Fonctionnalités Principales

### 🛡️ Sécurité & Dissuasion
- **Gestion des Modes Intelligente** :
  - 🏡 *Armé Présent (Home)* : Seules les ouvertures périphériques déclenchent (pas de radars intérieurs), déclenchant notifications et caméras sans sirène.
  - 🏃‍♂️ *Armé Absent (Away)* : Toute détection (portes, fenêtres, radars, caméras) déclenche l'alerte complète avec Sirènes, Lumières, Caméras et TTS.
  - 🌙 *Armé Nuit (Night)* : Surveillance complète mais alertes discrètes (TTS et notifications, sans sirène hurlante).
- **Lumières de Panique (Panic Lights)** : Flash rouge clignotant des lumières connectées pendant le délai d'entrée (dissuasion) et en cas d'intrusion.
- **Sécurité 24/7 (Tamper)** : Les capteurs de sabotage (ex: boîtier d'alarme ouvert) déclenchent l'alarme instantanément, même si le système est désarmé.

### 👤 Contrôle d'Accès Avancé
- **Gestion des Utilisateurs** : Associez des codes PIN à des personnes spécifiques. Le système vous accueille vocalement ("Bienvenue Jean") et trace l'historique.
- **Protection Brute-Force** : Le clavier se verrouille automatiquement pendant 5 minutes et vous alerte après 3 tentatives de codes erronés.
- **Code de Détresse (SOS)** : Un code secret qui désarme l'alarme de manière silencieuse tout en envoyant une notification d'urgence cachée à la famille.

### 📱 Expérience Mobile & Auto
- **Actionable Notifications Critiques** : Les alertes d'intrusion sont envoyées en mode Critique (sonnent à plein volume même en silencieux). Elles incluent un bouton "Désarmer" accessible d'un tap.
- **Support CarPlay & Apple Watch** : Interceptez l'alerte et désarmez l'alarme d'un clic depuis votre poignet ou le tableau de bord de votre véhicule.
- **Géolocalisation (Geofencing)** : L'alarme s'arme automatiquement quand la maison est vide, et se désarme silencieusement dès que vous approchez du domicile.

### 🔋 Résilience
- **Health Check** : Routine silencieuse qui vérifie en permanence l'état du système. Recevez une notification si la batterie d'un capteur passe sous les 10% ou s'il perd la connexion.

---

## ⚙️ Installation (via HACS)

1. Ajoutez ce dépôt `https://github.com/SocrateMobile/Domolink-Alarm` comme dépôt personnalisé dans HACS (Catégorie: Intégration).
2. Installez `Domolink Alarm` depuis HACS.
3. Redémarrez Home Assistant.
4. Allez dans **Paramètres > Appareils et services**, cliquez sur **Ajouter une intégration** et cherchez `Domolink Alarm`.
5. Suivez le guide de configuration interactif.

---

## 🎨 Dashboard Premium - iOS 26 Liquid Glass

Pour accompagner cette alarme, voici le code YAML d'une carte Lovelace au design ultra-moderne.  
*(Nécessite [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom) et [Card-Mod](https://github.com/thomasloven/lovelace-card-mod) d'installés).*

Ce design inclut un effet **Glassmorphism** (fond flouté translucide), des animations de pulsation pendant l'armement, et un pavé numérique élégant.

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

---

## 📜 Changelog

### 🔒 v0.4.0-beta (Current)
- **Audit complet et refactoring** : 18 points corrigés.
- 🔴 Fix critique : La sirène et les lumières s'éteignent correctement après le délai (callback `@callback` / `async` corrigé).
- 🔴 Fix critique : L'armement "Absent" avec délai de sortie fonctionne (ne reste plus bloqué en "Armement en cours").
- 🔴 Fix critique : Restauration d'état fiable après redémarrage HA (mapping string → Enum).
- 🔴 Fix critique : Plus de fuite mémoire sur les listeners de notifications mobiles.
- 🔴 Fix critique : Les options (délais, codes…) prennent effet immédiatement sans redémarrer HA.
- 🟠 Fix : Les capteurs ne déclenchent plus l'alarme pendant le délai de sortie.
- 🟠 Fix : `manifest.json` version et URLs GitHub corrigés.
- 🟠 Fix : Tous les `except:` nus remplacés par `except Exception` avec logging.
- ✨ Nouveau : Attributs d'entité enrichis (`last_triggered_by`, `last_user`, `failed_attempts`…).
- ✨ Nouveau : Notification de bypass avec la liste des capteurs ignorés.
- ✨ Nouveau : Health Check étendu aux sirènes, caméras et lumières.
- ✨ Nouveau : Fichier `strings.json` et traductions `options` pour l'OptionsFlow.

### 🚀 v0.3.0-beta
- Intégration CarPlay et Apple Watch via Actionable Notifications.
- Notification Critique iOS/Android.
- Geofencing Automatique (Armement/Désarmement via `zone.home`).

### 💎 v0.2.0-beta
- **Mise à jour majeure** : Architecture Premium.
- Ajout de la gestion dynamique des Utilisateurs/Codes (ex: `Jean:1234`).
- Ajout du code de détresse (Duress Code / Panic SOS).
- Ajout du blocage Brute-Force du pavé numérique.
- Ajout des Lumières de Panique (Flash dissuasif + allumage rouge).
- Ajout du mode de diagnostic (Health Check) des capteurs (batteries < 10%).

### 🛠 v0.1.4-beta & v0.1.3-beta
- Filtrage propre du Config Flow via les `device_class` des capteurs.
- Sécurisation du lancement de l'alarme sans certains actionneurs configurés.

### 🐛 v0.1.2-beta
- Fix majeur : Migration des anciennes constantes `STATE_ALARM_*` vers la nouvelle Enum Home Assistant `AlarmControlPanelState`.

### 🎉 v0.1.0-beta
- Initial release.
- Création du Config Flow multi-étapes.
- Gestion complète des 4 modes d'armement et tamper.
- Actions automatisées sur déclenchement (TTS, Sirène, Record, Notifications).
