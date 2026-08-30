# 🚨 Domolink Alarm

**Domolink Alarm** est une intégration de sécurité "Premium" pour Home Assistant.  
Conçue pour dépasser les standards du marché, elle offre une configuration 100% UI fluide et embarque nativement des fonctionnalités dignes des meilleures alarmes professionnelles : gestion des utilisateurs, codes de détresse, alertes mobiles interactives (CarPlay/Apple Watch) et géolocalisation.

---

## 🌟 Fonctionnalités Principales


### 🚀 Nouveautés de la version 0.9.15
- **Photos et Vidéos Multi-Caméras** : Lors d'une intrusion, une capture photo et un enregistrement vidéo de 30 secondes sont sauvegardés **pour toutes vos caméras**. Intègre une optimisation spécifique pour les caméras **Arlo** (`aarlo`).
- **Envoi de SMS Natif (Free Mobile)** : Envoyez des alertes de secours hors réseau Wi-Fi via l'API Free Mobile SMS de façon 100% autonome.
- **Bouton Panique (SOS)** : Déclenchez l'alerte générale (sirènes, notifications d'urgence) d'un simple appui, incluant vos contacts d'urgence.
- **Réarmement Automatique** : À la fin du temps de sonnerie, l'alarme se réarme toute seule et vous informe ("Maison de nouveau sous alarme").
- **Horodatage Français** : Les notifications sont désormais lisibles et horodatées précisément (ex: *30 Août 2026 à 18h00*).
- **Test Sirène Automatique** : Vérifiez le bon fonctionnement de vos sirènes de façon planifiée.
- **Planification (Schedule)** : Armement et désarmement automatiques selon vos propres horaires.

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

Pour accompagner cette alarme, voici deux propositions de cartes Lovelace au design ultra-moderne (*Liquid Glass*).  
*(Nécessite [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom) et [Card-Mod](https://github.com/thomasloven/lovelace-card-mod) d'installés).*

### 🎛️ Option 1 : Dashboard Complet Pro (Pavé Numérique & Monitoring)

Cette carte complète intègre le pavé numérique pour la saisie des codes utilisateurs/détresse ainsi que la surveillance en temps réel de tous les indicateurs clés (dernier utilisateur, dernier capteur déclencheur, statut géolocalisation, health check, compteur brute-force).

```yaml
type: vertical-stack
cards:
  # ─── En-tête : État de l'alarme avec pavé numérique ───
  - type: alarm-panel
    entity: alarm_control_panel.domolink_alarm
    states:
      - arm_home
      - arm_away
      - arm_night
    card_mod:
      style: |
        ha-card {
          background: rgba(255, 255, 255, 0.08) !important;
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 24px;
          box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
          overflow: hidden;
        }

        {% if is_state(config.entity, 'arming') or is_state(config.entity, 'pending') %}
        ha-card {
          animation: pulse-warn 2s infinite;
        }
        {% endif %}

        {% if is_state(config.entity, 'triggered') %}
        ha-card {
          animation: pulse-danger 1s infinite;
        }
        {% endif %}

        @keyframes pulse-warn {
          0%, 100% { border-color: rgba(255, 165, 0, 0.3); box-shadow: 0 0 10px rgba(255, 165, 0, 0.1); }
          50% { border-color: rgba(255, 165, 0, 1); box-shadow: 0 0 25px rgba(255, 165, 0, 0.6); }
        }

        @keyframes pulse-danger {
          0%, 100% { border-color: rgba(255, 0, 0, 0.3); box-shadow: 0 0 10px rgba(255, 0, 0, 0.1); }
          50% { border-color: rgba(255, 0, 0, 1); box-shadow: 0 0 30px rgba(255, 0, 0, 0.7); }
        }

  # ─── Infos : Dernier événement / Dernier utilisateur ───
  - type: horizontal-stack
    cards:
      - type: custom:mushroom-template-card
        primary: "{{ state_attr('alarm_control_panel.domolink_alarm', 'last_user') or '—' }}"
        secondary: Dernier utilisateur
        icon: mdi:account-check
        icon_color: teal
        card_mod:
          style: |
            ha-card {
              background: rgba(255, 255, 255, 0.05) !important;
              border: 1px solid rgba(255, 255, 255, 0.1);
              border-radius: 16px;
            }

      - type: custom:mushroom-template-card
        primary: >-
          {{ state_attr('alarm_control_panel.domolink_alarm', 'last_triggered_by') 
             | default('Aucun', true) 
             | regex_replace('.*\\.', '') 
             | replace('_', ' ') 
             | title }}
        secondary: Dernier déclencheur
        icon: mdi:alarm-light
        icon_color: >-
          {% if is_state('alarm_control_panel.domolink_alarm', 'triggered') %}red
          {% else %}grey{% endif %}
        card_mod:
          style: |
            ha-card {
              background: rgba(255, 255, 255, 0.05) !important;
              border: 1px solid rgba(255, 255, 255, 0.1);
              border-radius: 16px;
            }


  # ─── SOS & Journal d'Événements ───
  - type: horizontal-stack
    cards:
      - type: custom:mushroom-template-card
        entity: button.domolink_sos_votre_id
        primary: "Panique SOS"
        secondary: "Déclencher l'alarme"
        icon: mdi:alert-decagram
        icon_color: red
        layout: horizontal
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.domolink_sos_votre_id
          confirmation:
            text: "Voulez-vous vraiment déclencher l'alarme ?"
        card_mod:
          style: |
            ha-card {
              background: rgba(255, 0, 0, 0.1) !important;
              border: 1px solid rgba(255, 0, 0, 0.3);
              border-radius: 16px;
            }

      - type: custom:mushroom-template-card
        entity: sensor.domolink_event_log_votre_id
        primary: "Dernier Événement"
        secondary: "{{ states('sensor.domolink_event_log_votre_id') }}"
        icon: mdi:history
        icon_color: blue
        layout: horizontal
        tap_action:
          action: more-info
        card_mod:
          style: |
            ha-card {
              background: rgba(255, 255, 255, 0.05) !important;
              border: 1px solid rgba(255, 255, 255, 0.1);
              border-radius: 16px;
            }

  # ─── Monitoring : Géolocalisation / Health Check / Tentatives ───
  - type: horizontal-stack
    cards:
      - type: custom:mushroom-template-card
        primary: >-
          {% if state_attr('alarm_control_panel.domolink_alarm', 'geofence_active') %}Actif
          {% else %}Inactif{% endif %}
        secondary: Géolocalisation
        icon: mdi:map-marker-radius
        icon_color: >-
          {% if state_attr('alarm_control_panel.domolink_alarm', 'geofence_active') %}green
          {% else %}grey{% endif %}
        card_mod:
          style: |
            ha-card {
              background: rgba(255, 255, 255, 0.05) !important;
              border: 1px solid rgba(255, 255, 255, 0.1);
              border-radius: 16px;
            }

      - type: custom:mushroom-template-card
        primary: >-
          {% if state_attr('alarm_control_panel.domolink_alarm', 'health_check_active') %}Actif
          {% else %}Inactif{% endif %}
        secondary: Health Check
        icon: mdi:heart-pulse
        icon_color: >-
          {% if state_attr('alarm_control_panel.domolink_alarm', 'health_check_active') %}green
          {% else %}grey{% endif %}
        card_mod:
          style: |
            ha-card {
              background: rgba(255, 255, 255, 0.05) !important;
              border: 1px solid rgba(255, 255, 255, 0.1);
              border-radius: 16px;
            }

      - type: custom:mushroom-template-card
        primary: "{{ state_attr('alarm_control_panel.domolink_alarm', 'failed_attempts') or 0 }}/3"
        secondary: Tentatives
        icon: mdi:lock-alert
        icon_color: >-
          {% set n = state_attr('alarm_control_panel.domolink_alarm', 'failed_attempts') | int(0) %}
          {% if n >= 2 %}red{% elif n >= 1 %}orange{% else %}grey{% endif %}
        card_mod:
          style: |
            ha-card {
              background: rgba(255, 255, 255, 0.05) !important;
              border: 1px solid rgba(255, 255, 255, 0.1);
              border-radius: 16px;
            }
```

---

### 🔲 Option 2 : Carte Épurée Mushroom (Compacte)

Une version compacte idéale pour une vue d'ensemble ou une barre latérale.

```yaml
type: custom:mushroom-alarm-control-panel-card
entity: alarm_control_panel.domolink_alarm
states:
  - armed_home
  - armed_away
  - armed_night
show_keypad: true
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

    /* Animation de pulsation rouge si déclenchée */
    {% if is_state(config.entity, 'triggered') %}
    ha-card {
      animation: pulse-danger 1s infinite;
      border-color: rgba(255, 0, 0, 0.8) !important;
    }
    {% endif %}

    @keyframes pulse-border {
      0% { border-color: rgba(255, 165, 0, 0.3); box-shadow: 0 0 10px rgba(255, 165, 0, 0.1); }
      50% { border-color: rgba(255, 165, 0, 1); box-shadow: 0 0 20px rgba(255, 165, 0, 0.6); }
      100% { border-color: rgba(255, 165, 0, 0.3); box-shadow: 0 0 10px rgba(255, 165, 0, 0.1); }
    }

    @keyframes pulse-danger {
      0% { border-color: rgba(255, 0, 0, 0.3); box-shadow: 0 0 10px rgba(255, 0, 0, 0.1); }
      50% { border-color: rgba(255, 0, 0, 1); box-shadow: 0 0 25px rgba(255, 0, 0, 0.7); }
      100% { border-color: rgba(255, 0, 0, 0.3); box-shadow: 0 0 10px rgba(255, 0, 0, 0.1); }
    }
```

---

## 📜 Changelog

### 🚀 v0.8.0-beta (Current)
- 🛡️ **Double Détection / Cross-Zoning Anti-Fausses Alertes** : Option permettant d'exiger une confirmation (deux détections de mouvement dans un intervalle configurable de 60s) avant d'activer le cycle d'intrusion complet.
- 🚨 **Capteurs Techniques 24/7 (Fumée, Eau, Gaz, CO)** : Nouvelle catégorie de capteurs surveillés en permanence (même alarme désarmée), avec annonces vocales TTS dédiées et alertes critiques spécifiques.
- 📍 **Rappel d'Oubli d'Armement (Geofencing Pro)** : Si le domicile est déserté depuis 15 minutes sans être armé, une notification push actionnable est envoyée pour armer d'un simple geste à distance (`⚡ Armer en Absence`).
- 💡 **Simulation de Présence Basée sur l'Historique (Mode Vacances)** : Rejoue fidèlement l'historique réel des allumages/extinctions (lumières, prises, volets) enregistré 7 jours plus tôt dès que l'alarme est en mode `ARMED_AWAY`.

### 🚀 v0.7.8-beta
- 📸 **Levée de doute Caméra & Snapshot Automatique** : En cas de détection d'intrusion ou déclenchement de l'alarme, le système capture automatiquement un instantané photo sur la caméra principale et l'attache directement dans la notification push critique (compatible iOS et Android), vous permettant de voir instantanément ce qui se passe avant de désarmer.

### 🚀 v0.7.7-beta
- 📋 **Journal d'Événements dans le Panneau Latéral** : Ajout d'une section "Journal des événements récents" directement intégrée en bas du panneau latéral. Vous pouvez suivre en direct l'historique chronologique des 20 derniers événements (qui a armé/désarmé, quel badge a été scanné, capteurs ignorés, déclenchements, carillons, etc.).

### 🚀 v0.7.6-beta
- 🔔 **Mode Carillon (Chime)** : Option configurable dans les paramètres. Lorsque l'alarme est désarmée, l'ouverture de n'importe quelle porte ou fenêtre annonce vocalement en direct sur vos enceintes (ex: *« Porte d'entrée ouverte »*), idéal pour savoir en temps réel qui entre ou sort de la maison.

### 🚀 v0.7.5-beta
- 🔋 **Diagnostic Piles & Santé Pro (Health Check Pro)** : Détection intelligente des niveaux de batterie sur tous les capteurs (lecture directe ou via le `device_registry`). L'alarme vous avertit proactivement si un capteur passe sous les 15% lors de l'armement ou lors du diagnostic périodique, vous évitant toute panne inattendue.

### 🚀 v0.7.4-beta
- 👁️ **Bouton « Ignorer » (Bypass dynamique)** : Apparition d'un bouton "Ignorer" sur la tuile des capteurs lorsqu'ils sont **non joignables** (`unavailable`, déconnectés) ou **ouverts**. En un clic, le capteur est exclu temporairement de la surveillance, permettant d'armer l'alarme sans blocage. Un bouton "Rétablir" permet de le réintégrer à tout moment, et les exclusions sont automatiquement réinitialisées lors du désarmement.

### 🚀 v0.7.3-beta
- 🎛️ **Contrôles dans le Panneau Latéral** : Ajout des boutons pour armer (Absence, Présence, Nuit) et désarmer l'alarme directement depuis le panneau latéral de Domolink (avec champ de code PIN si requis).
- 🕒 **Dernier contact** : Ajout de la date et l'heure du dernier changement d'état sur la tuile de chaque capteur.

### 🚀 v0.7.2-beta
- 🖥️ **Nouveau Panneau de Contrôle Latéral** : Ajout d'un panneau "Domolink Alarm" dans la barre de gauche de Home Assistant. Vous pouvez désormais voir en un coup d'œil l'état de l'alarme et l'état en temps réel de tous les capteurs classés par catégories (portes ouvertes, mouvements, etc.).

### 🚀 v0.6.17-beta
- 🐛 **Correctif Critique** : Correction d'un bug d'import (NameError) lié aux étiquettes des Personnes et Notifications qui empêchait l'intégration de démarrer correctement. L'entité principale charge maintenant sans erreur.

### 🚀 v0.6.16-beta
- 🏷️ **Support COMPLET des Étiquettes (Labels)** : Ajout des étiquettes manquantes pour les catégories "Claviers", "Appareils pour Notifications" et "Personnes". Toutes les catégories de l'alarme possèdent désormais leur champ d'étiquette dédié.

### 🚀 v0.6.15-beta
- 🏷️ **Support des Étiquettes (Labels)** : Il est désormais possible de sélectionner des étiquettes entières au lieu de sélectionner les capteurs un par un. Le système filtre automatiquement les entités correspondantes (par exemple, si vous étiquetez un capteur multiple, seule l'entité "ouverture" sera gardée pour la section capteurs d'ouverture).

### 🚀 v0.6.14-beta
- 💳 **Support Natif des Badges RFID/NFC** : L'alarme écoute désormais nativement les événements `tag_scanned` de Home Assistant. Vous pouvez configurer des tags depuis l'interface (ex: `04-7A-5B:Jean`). Le scan agit comme un bouton bascule : si l'alarme est désarmée, elle s'arme en mode "Absent" (avec bypass autorisé) ; si elle est armée ou déclenchée, elle se désarme immédiatement avec message TTS de bienvenue.

### 🚀 v0.6.13-beta
- 🔓 **Bypass direct depuis le tableau de bord** : Si un capteur est ouvert, au lieu d'être bloqué avec une erreur, vous pouvez désormais taper votre code PIN valide directement sur le pavé numérique du tableau de bord HA puis cliquer sur "Activer". L'alarme considérera ce code comme une autorisation de bypass forcé.

### 🚀 v0.6.12-beta
- 🐛 **Retour visuel sur le tableau de bord (Erreur d'armement)** : Lorsqu'un armement échoue à cause de capteurs ouverts, l'intégration génère désormais une `HomeAssistantError`. Cela affiche instantanément une pop-up d'erreur rouge directement sur le tableau de bord Home Assistant ("Échec armement : X capteur(s) ouvert(s)"), au lieu d'échouer silencieusement tout en envoyant la notification mobile.

### 🚀 v0.6.11-beta
- 🔄 **Rechargement automatique à chaud** : Dès validation du menu de configuration (Options Flow), l'intégration se recharge automatiquement pour appliquer immédiatement tous les ajouts/retraits de capteurs sans action manuelle.
- 📱 **Notification interactive de Bypass (Mise en marche forcée)** : Si un ou plusieurs capteurs sont ouverts lors de l'armement, l'application mobile envoie une notification avec la liste des capteurs ouverts, un bouton "Forcer la mise en marche" (avec saisie du code PIN) et un bouton "Annuler".
- 🔁 **Réarmement automatique & Réactivation des alertes** : Après la fin de la durée de sirène (ex: 3 min), le système se ré-arme automatiquement. Tout nouveau mouvement ou ouverture ultérieure (même 10+ min après, sur le même capteur ou un autre) déclenche un nouveau cycle d'alerte complet (Sirène, Flash, TTS, Caméras, Push).

### 🚀 v0.6.10-beta
- 🐛 **Fix Critique Erreur 500** : Résolution définitive du crash 500 sur le menu d'options. Cause racine : dans les versions récentes de Home Assistant (2025+), `config_entry` est une propriété en lecture seule sur `OptionsFlow`. Le constructeur tentait de l'écraser (`self.config_entry = ...`), ce qui provoquait une `AttributeError` systématique.

### 🚀 v0.6.9-beta
- 🐛 **Fix Erreur 500 (Options Flow)** : La clé de traduction `cameras` était absente des fichiers de langue (fr, en, es, it, de, uk), ce qui provoquait un crash du serveur interne de Home Assistant lors de l'ouverture du menu de configuration. Corrigé dans toutes les langues.

### 🚀 v0.6.8-beta
- 🐛 **Fix Critique 500** : Le système de cases à cocher forcées sur la version 0.6.7 provoquait un plantage du serveur interne Home Assistant (Erreur 500) à cause d'une incompatibilité de validation des schémas. Rétro-pédalage vers le sélecteur natif HA.

### 🚀 v0.6.7-beta
- 🎛️ **Amélioration UX (UI)** : Remplacement des menus déroulants de sélection d'entités par des vraies **listes de cases à cocher** déroulables, générées dynamiquement. Il est désormais beaucoup plus intuitif et visuel de sélectionner plusieurs capteurs ou caméras d'un seul coup directement sur la page !

### 🚀 v0.6.6-beta
- 🐛 **Fix OptionsFlow** : Correction de l'erreur `500 Internal Server Error` qui empêchait la modification de la configuration de l'alarme, causée par le renommage récent des étapes de configuration dans les fichiers de langue (sensors, actuators, logic).

### 🚀 v0.6.5-beta
- 🌍 **Internationalisation (i18n)** : Ajout des traductions complètes pour l'intégration et les entités en Français, Anglais, Espagnol, Italien, Allemand et Ukrainien (notamment pour l'état "unknown" des capteurs et les boutons d'entité).

### 🚀 v0.6.4-beta
- 📝 **Journal détaillé (Audit Trail)** : Le capteur d'événements (`sensor.domolink_event_log`) enregistre maintenant finement chaque action technique du système lors d'une alerte : allumage des amplis, réglage du volume, diffusion du message TTS, envoi des notifications, activation des caméras, déclenchement et arrêt des sirènes/lumières.

### 🚀 v0.6.3-beta
- 🎨 **Fix Icônes** : Les icônes sont désormais servies depuis le dossier `brand/` conformément au standard Home Assistant 2026.3+. Elles apparaissent maintenant dans la page Intégrations et Appareils.

### 🚀 v0.6.2-beta
- 🚨 **Notifications Continues** : Si l'alarme est déjà déclenchée et qu'un nouveau capteur détecte une intrusion, une nouvelle alerte est envoyée ("Détection supplémentaire").
- 🐛 **Fix Journal d'Événements** : Correction d'un bug qui effaçait le capteur de log en cas de déclenchement.
- 🐛 **Fix Mode Nuit & Geofencing** : Correction d'une régression dans l'évaluation des états des capteurs.

### 🚀 v0.6.1-beta
- 🔊 **Ampli & Media Players** : Avant de lire un message TTS vocal, Domolink s'assure maintenant d'allumer le lecteur (ex: Ampli Home-Cinéma) et règle automatiquement le volume à 50% pour garantir que le message soit entendu !

### 🚀 v0.6.0-beta
- 🌙 **Mode Nuit (`Arm Night`)** : Sélection d'un groupe spécifique de capteurs (ex: portes/fenêtres uniquement) qui s'activeront la nuit.
- 🧑‍🤝‍🧑 **Geofencing intelligent (Personnes)** : L'alarme s'arme automatiquement (Absent) si toutes les personnes sélectionnées quittent la maison, et se désarme si une personne rentre.
- 🆘 **Entité Bouton de Panique (SOS)** : Nouvelle entité `button.domolink_sos` permettant de déclencher les sirènes immédiatement.
- 📜 **Journal d'Événements** : Nouvelle entité `sensor.domolink_event_log` stockant le dernier événement et un historique de 20 événements en attribut.
- 🔍 **Détail des Défauts** : L'entité alarme liste désormais les capteurs ouverts (`faults`) et le capteur exact de déclenchement (`triggered_by`) en attributs.
- 📱 **Notifications Apple Watch / CarPlay Enrichies** : Ajout du flux/snapshot de la caméra directement dans les alertes push iOS.
- ⚙️ **Configuration Dynamique** : Tous les capteurs et actionneurs peuvent désormais être ajoutés/supprimés depuis le bouton "Configurer" sans réinstaller l'alarme.

### 🏢 v0.5.2-beta
- Ajout d'une action "Ouvrir l'application" au clic sur une notification.
- Restructuration totale du menu "Configurer" (OptionsFlow) pour permettre la modification des capteurs/actionneurs.

### 🏢 v0.5.0-beta
- 🏢 **Multi-Systèmes d'Alarme** : Support complet de multiples alarmes indépendantes (ex: "Alarme Maison", "Alarme Garage", "Alarme Bureau").
- 🏷️ **Nom personnalisable** dans l'assistant de configuration avec création d'un appareil (`Device`) dédié pour chaque alarme.
- 🛡️ **Icônes et Logos HACS / HA** : Ajout des icônes à tous les niveaux (`/`, `images/`, `.github/`, `custom_components/domolink_alarm/`) pour une visibilité immédiate dans HACS et la liste des intégrations.
- ⚡ **Amélioration Détection Capteurs** : Détection insensible à la casse et support étendu des formats d'états (`on`, `open`, `true`, `detected`, `unlocked`, `1`).

### 🔒 v0.4.0-beta
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
