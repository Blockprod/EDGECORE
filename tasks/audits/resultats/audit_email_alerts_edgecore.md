---
produit: tasks/audits/audit_email_alerts_edgecore.md
date: 2026-03-20
creation: 2026-03-20 à 17:32
perimetre: système d'alertes email — monitoring/email_alerter.py + live_trading/runner.py + main.py
---

# Audit — Système d'alertes email EDGECORE

---

## BLOC 1 — SYSTÈME D'ENVOI

### B1-01 · Aucun retry avec backoff sur échec SMTP
**Fichier** : `monitoring/email_alerter.py:133–158`  
**Constat** : `_send_smtp()` tente l'envoi une seule fois. En cas d'échec transitoire (réseau instable, serveur SMTP temporairement indisponible), l'email est perdu sans aucune nouvelle tentative. Le `try/except` catchant `SMTPException` ne réessaie pas.  
**Risque** : Une alerte critique (kill-switch, drawdown) peut être silencieusement swallowée si le serveur SMTP est momentanément indisponible.  
**Sévérité** : 🔴 P0  
**Impact** : Perte d'alertes critiques en production  
**Effort** : Faible — ajouter une boucle `for attempt in range(3)` avec `time.sleep(2**attempt)`

---

### B1-02 · Aucun cooldown/déduplication sur l'EmailAlerter
**Fichier** : `monitoring/email_alerter.py` (entier — aucune variable `last_sent`, `last_alert_time`)  
**Constat** : La `SlackAlerter` possède un mécanisme de throttle (`throttle_seconds=30`, `last_alert_time` dict — voir `slack_alerter.py:36,78`). L'`EmailAlerter` n'en a aucun. La config `AlerterConfigSchema.alert_deduplication_seconds=60` et `max_alerts_per_minute=60` (`config/schemas.py:409,415`) sont définies mais **jamais lues** par `EmailAlerter`.  
**Risque** : En cas de boucle d'erreur (ex: data fetch qui échoue toutes les 10s dans `main.py:604`), le système peut générer des dizaines d'emails identiques par minute, saturant la boîte email et potentiellement le quota SMTP (Gmail : 500/jour).  
**Sévérité** : 🔴 P0  
**Impact** : Tempête d'emails, quota SMTP épuisé, filtre spam côté destinataire  
**Effort** : Moyen — implémenter un dict `_last_sent: Dict[str, float]` + vérification elapsed comme dans `SlackAlerter`

---

### B1-03 · `MIMEMultipart('text', 'plain')` — appel invalide
**Fichier** : `monitoring/email_alerter.py:78`  
**Constat** : `MIMEMultipart` accepte comme premier argument le sous-type MIME (`'mixed'`, `'alternative'`, `'related'`). L'appel `MIMEMultipart('text', 'plain')` interprète `'text'` comme subtype et `'plain'` comme `_charset` — ce n'est pas un sous-type valide de `multipart/`. Le constructeur de `MIMEMultipart` ne plante pas immédiatement mais génère un Content-Type `multipart/text; charset='plain'` invalide, ce qui peut causer des rejets silencieux par certains serveurs SMTP.  
**Usage correct** : `MIMEMultipart()` (subtype par défaut: `'mixed'`) ou `MIMEMultipart('alternative')`.  
**Sévérité** : 🟠 P1  
**Impact** : Emails malformés pouvant être rejetés ou marqués spam  
**Effort** : Trivial — corriger en `MIMEMultipart()` ou `MIMEMultipart('mixed')`

---

### B1-04 · TLS correctement utilisé (`starttls()` sur port 587)
**Fichier** : `monitoring/email_alerter.py:144`  
**Constat** : `server.starttls()` appelé avant `server.login()` — conforme STARTTLS (port 587). Pas de `smtplib.SMTP_SSL` (port 465) — pas de SSL direct. ✅ **Conforme**.

---

### B1-05 · Échec d'envoi email logué sans crasher le système
**Fichier** : `monitoring/email_alerter.py:125–131`, `live_trading/runner.py:138`  
**Constat** : Les exceptions `SMTPException` et génériques sont catchées, loggées via `structlog`, et la méthode retourne `(False, reason)`. Dans `runner.py._send_alert()`, le try/catch (`except Exception as exc`) empêche toute propagation. La méthode est explicitement documentée comme "Never raises — fire-and-forget". ✅ **Conforme**.

---

### B1-06 · `datetime.now()` sans timezone dans le corps de l'email
**Fichier** : `monitoring/email_alerter.py:95`  
**Constat** : `{datetime.now().isoformat()}` — utilise l'heure locale sans timezone.  
Selon la règle codebase : toujours `datetime.now(timezone.utc)`.  
**Sévérité** : 🟡 P2  
**Impact** : Timestamp ambigu dans les emails — difficile à corréler avec les logs UTC  
**Effort** : Trivial — remplacer par `datetime.now(timezone.utc).isoformat()`

---

## BLOC 2 — COUVERTURE DES ÉVÉNEMENTS

### Événements d'erreurs système

| Événement | Statut | Fichier:Ligne |
|-----------|--------|---------------|
| Exception critique non gérée | ✅ COUVERT | `main.py:716` — `CRITICAL "Max consecutive errors"` |
| Échec de sauvegarde d'état (3 tentatives) | ❌ NON COUVERT | `main.py:749` — `logger.warning("final_snapshot_save_skipped")` uniquement, aucun email |
| Échec connexion broker/exchange au démarrage | ✅ COUVERT | `live_trading/runner.py:389` — `CRITICAL "Startup reconciliation CRITICAL"` |
| Données de marché manquantes ou corrompues | ✅ COUVERT | `main.py:604` — `CRITICAL "Fatal data error"` ; `live_trading/runner.py:491` — `ERROR "Market data fetch failed"` |
| Erreur réseau prolongée (retryable→fatal) | ✅ COUVERT | `main.py:604` — déclenche alert sur `ErrorCategory.NON_RETRYABLE` |
| Circuit breaker déclenché | ❌ NON COUVERT | `common/circuit_breaker.py` — aucun appel `send_alert` en sortie |

### Événements de trading

| Événement | Statut | Fichier:Ligne |
|-----------|--------|---------------|
| Ordre d'achat exécuté (prix, quantité, PnL) | ❌ NON COUVERT | `main.py:582` — `logger.info("paper_order_submitted")` uniquement. Aucun email sur exécution confirmée |
| Ordre de vente exécuté (raison, PnL) | ❌ NON COUVERT | Idem — aucun email sur close |
| Ordre bloqué (raison: risk, capital, OOS, kill-switch) | ⚠️ PARTIEL | `main.py:548` — `logger.warning("trade_rejected_by_risk")` uniquement. Aucun email sur rejet |
| Ordre tenté mais échoué (timeout, rejet exchange) | ✅ COUVERT | `main.py:612` — `ERROR "Order failed: {pair}"` |
| Stop-loss déclenché | ❌ NON COUVERT | `main.py:499–516` — `logger.warning("position_stopped_out")` + `logger.info("stop_loss_order_submitted")`, aucun email |
| Position ouverte sans stop-loss détectée | À VÉRIFIER | Logique absente dans le pipeline review |
| Timeout ordre détecté et annulé | ⚠️ PARTIEL | `main.py:635` — `logger.warning("order_timeouts_detected_and_cancelled")` uniquement |

### Événements de protection du capital

| Événement | Statut | Fichier:Ligne |
|-----------|--------|---------------|
| Daily loss limit atteint | ❌ NON COUVERT | `KillSwitch.check()` déclenche `KillReason.DAILY_LOSS` (`kill_switch.py:189`) mais `on_activate` n'est pas connecté au `_send_alert` dans `runner.py._initialize()` |
| Drawdown kill-switch déclenché | ⚠️ PARTIEL | `live_trading/runner.py:475` — `CRITICAL "Kill-switch activated"` détecté via `is_active` poll, mais **seulement au tick suivant**. Le callback `on_activate` du `KillSwitch` n'est pas câblé dans `_initialize()` — délai d'1 tick entre l'activation et l'email |
| OOS gate bloqué | ❌ NON COUVERT | `risk/engine.py` — aucun appel email sur blocage OOS |
| Emergency halt activé | ✅ COUVERT | `live_trading/runner.py:405–414` — `CRITICAL "Trading shutdown triggered"` via `ShutdownManager` |

---

## BLOC 3 — QUALITÉ DU CONTENU

### B3-01 · Informations de diagnostic insuffisantes dans les emails de trading
**Fichier** : `monitoring/email_alerter.py:88–115` (template du body)  
**Constat** : Le template contient `Project`, `Severity`, `Title`, `Timestamp`, `Message`, et le dict `data`. Mais les call-sites dans `main.py` et `runner.py` passent des `data` dicts minimalistes : `{"iteration": attempt, "reason": shutdown_reason}` sans prix, PnL, paire de trading, quantité. Un opérateur ne peut pas diagnostiquer l'état du portefeuille sans consulter les logs. Par contraste, `SlackAlerter.send_trade_alert()` (`slack_alerter.py:140`) inclut symbol, side, quantity, price.  
**Sévérité** : 🟠 P1  
**Impact** : Emails informationnellement insuffisants pour le diagnostic sans log access  
**Effort** : Moyen — enrichir les `data` dicts aux call-sites critiques

---

### B3-02 · Emails d'erreur sans traceback
**Fichier** : `main.py:712`, `live_trading/runner.py:136`  
**Constat** : Les call-sites transmettent `str(e)[:200]` comme message. Aucun `traceback.format_exc()` n'est inclus. Pour diagnostiquer un crash en production sans accès aux logs, le traceback est essentiel.  
**Sévérité** : 🟡 P2  
**Impact** : Temps de diagnostic allongé en cas d'incident  
**Effort** : Faible — ajouter `"traceback": traceback.format_exc()[:2000]` dans `data`

---

### B3-03 · Aucun credential dans les emails
**Constat** : Les bodies d'emails (`monitoring/email_alerter.py:88–115`) ne contiennent que les champs passés en argument. Aucun secret (clé API, mot de passe SMTP, token IBKR) n'est inclus. ✅ **Conforme**.

---

### B3-04 · Sujets d'emails permettent de distinguer critique vs informatif
**Fichier** : `monitoring/email_alerter.py:84`  
**Constat** : Subject format : `[EDGECORE — Live Trading] [CRITICAL] Kill-switch activated`. Le niveau est visible en clair dans le sujet. ✅ **Conforme**.

---

### B3-05 · `get_status()` expose la liste des destinataires en clair
**Fichier** : `monitoring/email_alerter.py:177`  
**Constat** : `get_status()` retourne `'recipient_list': self.recipients`. Si cette méthode est exposée via l'API de monitoring (`monitoring/api.py`), des adresses email personnelles/professionnelles pourraient être divulguées.  
**Sévérité** : 🟡 P2 (sécurité)  
**Impact** : Fuite PII (RGPD) si l'API est exposée sans auth  
**Effort** : Trivial — remplacer `'recipient_list': self.recipients` par `'recipient_count': len(self.recipients)` dans `get_status()`

---

## BLOC 4 — CAS MANQUANTS ET RISQUES

### B4-01 · KillSwitch `on_activate` non câblé sur l'email alerter
**Fichier** : `live_trading/runner.py:209` (instanciation de `KillSwitch()`)  
**Constat** : `self._kill_switch = KillSwitch()` — le paramètre `on_activate` est `None`. La détection du kill-switch repose sur un **poll** `self._kill_switch.is_active` au début de chaque tick (`runner.py:475`). Conséquences :
1. Le callback immédiat n'existe pas — l'email est envoyé au **début du tick suivant** après activation, pas au moment de l'activation.
2. Si le processus crashe entre l'activation du kill-switch et le prochain tick, l'email n'est jamais envoyé.  
**Sévérité** : 🟠 P1  
**Impact** : Délai d'alerte kill-switch ; email potentiellement perdu si crash immédiat  
**Effort** : Faible — passer `on_activate=lambda r, m: self._send_alert("CRITICAL", f"KillSwitch: {r.value}", m)` lors de l'instanciation

---

### B4-02 · Boucle d'erreur pouvant générer des emails en cascade (absence de cooldown)
**Fichier** : `main.py:596–614` (boucle `DataError` transient/retryable) + `email_alerter.py` (aucun throttle)  
**Constat** : Si `ErrorCategory.NON_RETRYABLE` est levée à chaque itération (ex: configuration invalide), le code envoie un email via `_alerter.send_alert()` ET sort de la boucle avec `break`. Ce cas est donc géré. Mais pour les erreurs génériques (`Exception`) au-dessus du break (`main.py:693–728`), si `consecutive_errors >= max_consecutive_errors`, un email CRITICAL est envoyé, puis la boucle s'arrête. Ce n'est pas un problème de cascade dans ce cas précis. **Cependant**, il n'y a aucun protection si un code appelant invoque `send_alert()` en boucle tight extérieure (ex: wrapper futur), car `EmailAlerter` n'a aucun throttle.  
**Sévérité** : 🟠 P1 (risque latent — voir B1-02)  
**Ref** : Voir B1-02 pour correction

---

### B4-03 · Stop-loss déclenché sans email
**Fichier** : `main.py:471–516`  
**Constat** : Lorsqu'une position atteint son stop-loss (`risk_engine.check_position_stops()`), le code loggue `warning("position_stopped_out")` et `info("stop_loss_order_submitted")` mais n'envoie **aucun email**. Un stop-loss représente une perte réalisée — c'est exactement le type d'événement qui doit déclencher une notification immédiate.  
**Sévérité** : 🔴 P0  
**Impact** : L'opérateur peut ne jamais savoir qu'un stop-loss a été déclenché sauf en consultant les logs  
**Effort** : Faible — ajouter `_alerter.send_alert(level="CRITICAL", ...)` après `logger.warning("position_stopped_out")`

---

### B4-04 · Ordre rejected/blocked par risk sans email
**Fichier** : `main.py:548`  
**Constat** : `logger.warning("trade_rejected_by_risk", pair=..., reason=...)` uniquement. Si le risk engine rejette systématiquement tous les ordres (ex: `can_enter_trade` retourne toujours `False` à cause d'une config incorrecte), l'opérateur n'en sera notifié que via les logs.  
**Sévérité** : 🟡 P2  
**Impact** : Cycle de trading silencieusement paralysé  
**Effort** : Faible — ajouter alert WARNING pour raisons critiques (drawdown, kill-switch)

---

### B4-05 · Sauvegarde état finale sans email en cas d'échec
**Fichier** : `main.py:749`  
**Constat** : `logger.warning("final_snapshot_save_skipped", error=str(e))` — si la sauvegarde de l'état final d'une session de trading échoue, aucun email n'est envoyé. Le crash recovery peut alors être compromis à la prochaine session.  
**Sévérité** : 🟠 P1  
**Impact** : Crash recovery compromis sans que l'opérateur en soit informé  
**Effort** : Faible — ajouter `email_alerter.send_alert(level="ERROR", ...)` dans le bloc `except`

---

### B4-06 · Circuit breaker `common/circuit_breaker.py` sans notification email
**Fichier** : `common/circuit_breaker.py`  
**Constat** : Le circuit breaker monitore les appels défaillants mais n'est pas connecté au système d'alerte email. Lorsqu'il passe en état OPEN, aucun email n'est envoyé. Le circuit breaker est utilisé dans le pipeline de données mais pas dans le pipeline d'exécution — l'impact est modéré.  
**Sévérité** : 🟡 P2  
**Impact** : Circuit ouvert silencieux — trading dégradé sans notification  
**Effort** : Moyen — passer un `on_open` callback lors de l'instanciation

---

## SYNTHÈSE

### Tableau complet

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|
| B1-01 | Envoi | Aucun retry SMTP avec backoff | `email_alerter.py:133–158` | 🔴 P0 | Perte alertes critiques | Faible |
| B1-02 | Envoi | Aucun cooldown/déduplication email | `email_alerter.py` (entier) | 🔴 P0 | Tempête d'emails, quota SMTP | Moyen |
| B4-03 | Manquants | Stop-loss sans email | `main.py:471–516` | 🔴 P0 | Perte financière silencieuse | Faible |
| B1-03 | Envoi | `MIMEMultipart('text','plain')` invalide | `email_alerter.py:78` | 🟠 P1 | Emails malformés / rejetés | Trivial |
| B3-01 | Contenu | Data dict insuffisant dans les emails | `main.py, runner.py` (call-sites) | 🟠 P1 | Diagnostic difficile | Moyen |
| B4-01 | Manquants | KillSwitch `on_activate` non câblé | `runner.py:209` | 🟠 P1 | Délai/perte alerte kill-switch | Faible |
| B4-02 | Manquants | Risque cascade emails (pas de throttle) | `email_alerter.py` + `main.py` | 🟠 P1 | Quota SMTP (risque latent) | Moyen (= B1-02) |
| B4-05 | Manquants | Sauvegarde état finale sans email | `main.py:749` | 🟠 P1 | Crash recovery compromis | Faible |
| B1-06 | Envoi | `datetime.now()` sans timezone | `email_alerter.py:95` | 🟡 P2 | Timestamp ambigu | Trivial |
| B3-02 | Contenu | Emails sans traceback | `main.py:712`, `runner.py:136` | 🟡 P2 | Diagnostic allongé | Faible |
| B3-05 | Contenu | `get_status()` expose recipient_list | `email_alerter.py:177` | 🟡 P2 | Fuite PII si API exposée | Trivial |
| B4-04 | Manquants | Ordre rejeté par risk sans email | `main.py:548` | 🟡 P2 | Trading silencieusement bloqué | Faible |
| B4-06 | Manquants | Circuit breaker sans notification | `common/circuit_breaker.py` | 🟡 P2 | Circuit ouvert silencieux | Moyen |

---

### Événements NON COUVERTS par ordre de criticité financière

1. **Stop-loss déclenché** (B4-03) — perte financière réalisée sans notification
2. **KillSwitch drawdown/daily-loss** (B4-01) — notification différée d'1 tick minimum
3. **Sauvegarde état finale échouée** (B4-05) — crash recovery compromis
4. **OOS gate bloqué** — trading silencieusement interrompu
5. **Circuit breaker OPEN** (B4-06) — pipeline dégradé silencieux
6. **Ordre rejeté par risk** (B4-04) — trading paralysé détectable uniquement via logs

---

### Top 3 risques immédiats liés aux alertes manquantes

1. **🔴 Tempête d'emails** (B1-02) : Une boucle d'erreur courte (10s par itération) peut générer >300 emails/heure identiques. L'`EmailAlerter` n'a aucun throttle contrairement à `SlackAlerter`. Risque immédiat de blacklistage SMTP ou saturation quota.

2. **🔴 Stop-loss silencieux** (B4-03) : Une position liquidée par stop-loss n'envoie pas d'email. L'opérateur en position de surveillance légère (mobile, hors bureau) ne sera pas notifié d'une perte réalisée.

3. **🔴 Perte d'alerte sur échec SMTP transitoire** (B1-01) : En cas de courte indisponibilité SMTP (30s–2min), une alerte critique (kill-switch, drawdown) est définitivement perdue. Aucune file d'attente, aucun retry.

---

### Points forts du système de notification à conserver

- ✅ **Architecture dual-channel** : Email + Slack en parallèle (`runner._send_alert()`) avec fallback indépendant
- ✅ **Fire-and-forget** : `_send_alert()` ne propage jamais d'exception — le trading continue même si les alertes échouent
- ✅ **TLS STARTTLS** : Implémenté correctement sur port 587
- ✅ **`from_env()` factory** : Configuration 100% par variables d'environnement, aucun credential hardcodé
- ✅ **SlackAlerter throttle** : Mécanisme de déduplication 30s côté Slack — modèle à répliquer sur EmailAlerter
- ✅ **Filtrage INFO/WARNING** : L'email ne reçoit que `ERROR` et `CRITICAL` — évite le spam sur les événements nominaux
- ✅ **Alertes réconciliation** : startup (ligne 389) et périodique (ligne 544) sont couverts dans `runner.py`
- ✅ **Alertes shutdown/kill-switch** : Couvertes via poll `is_active` dans `_tick()` et via `ShutdownManager`
