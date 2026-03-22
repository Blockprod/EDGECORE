---
type: plan_action
source: tasks/audits/audit_email_alerts_edgecore.md
date: 2026-03-20
statut: en_attente
---

# PLAN D'ACTION — EDGECORE — Alertes Email — 2026-03-20

**Sources** : `tasks/audits/audit_email_alerts_edgecore.md`  
**Total** : 🔴 3 · 🟠 4 · 🟡 5 · **Effort estimé : 2 jours**

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Ajouter retry avec backoff exponentiel sur échec SMTP

**Fichier** : `monitoring/email_alerter.py:133–158` (`_send_smtp()`)  
**Problème** : L'envoi SMTP est tenté une seule fois. Un échec transitoire (réseau, SMTP momentanément indisponible) entraîne la perte définitive de l'alerte, sans nouvelle tentative. Une alerte kill-switch ou stop-loss peut être silencieusement perdue.  
**Correction** :
- Dans `_send_smtp()`, encapsuler l'appel dans une boucle `for attempt in range(3):`
- En cas d'exception `SMTPException` non-authentification : `time.sleep(2 ** attempt)` puis retry
- Ne jamais retry sur `SMTPAuthenticationError` (credentials incorrects → permanent)
- Logger chaque tentative avec `logger.warning("EMAIL_SMTP_RETRY", attempt=attempt, error=...)`
- Lever l'exception finale si les 3 tentatives échouent

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/monitoring/040_test_email_alerter.py -x -q
# Attendu : tous les tests existants passent
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659+ passed, 0 failed
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-02] Implémenter cooldown/déduplication sur EmailAlerter

**Fichier** : `monitoring/email_alerter.py` (classe `EmailAlerter`) + `config/schemas.py:409,415`  
**Problème** : L'`EmailAlerter` n'a aucun mécanisme de throttle contrairement à `SlackAlerter` (throttle 30s). La config `AlerterConfigSchema.alert_deduplication_seconds=60` et `max_alerts_per_minute=60` sont définies mais jamais lues. En cas de boucle d'erreur courte (10s/itération), des centaines d'emails identiques peuvent être envoyés, saturant le quota SMTP (Gmail : 500/jour) et risquant le blacklistage.  
**Correction** :
- Ajouter `self._last_sent: Dict[str, float] = {}` dans `__init__`
- Ajouter `self.cooldown_seconds: int = 60` (lire depuis env ou laisser configurable)
- Dans `send_alert()`, avant l'envoi : construire `alert_key = f"{level}:{title}"`, vérifier `time.time() - self._last_sent.get(alert_key, 0) < self.cooldown_seconds`
- Si cooldown actif : `logger.debug("EMAIL_ALERT_THROTTLED", ...)` + return `(False, "throttled")`
- Après envoi réussi : `self._last_sent[alert_key] = time.time()`
- Exposer `cooldown_seconds` dans `get_status()`

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/monitoring/040_test_email_alerter.py -x -q
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659+ passed, 0 failed
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-03] Envoyer email lors du déclenchement d'un stop-loss

**Fichier** : `main.py:499–516` (bloc `if stopped_positions:`)  
**Problème** : Quand `risk_engine.check_position_stops()` retourne des positions stoppées, le code loggue uniquement (`warning("position_stopped_out")`, `info("stop_loss_order_submitted")`). Aucun email n'est envoyé. Un stop-loss représente une perte réalisée — c'est l'événement le plus critique pour un opérateur.  
**Correction** :
- Après `logger.warning("position_stopped_out", ...)`, ajouter le bloc email :
```python
for _alerter in (email_alerter, slack_alerter):
    if _alerter:
        try:
            _alerter.send_alert(
                level="CRITICAL",
                title=f"Stop-loss déclenché : {stopped_pos['symbol']}",
                message=(
                    f"Position {stopped_pos['symbol']} liquidée par stop-loss. "
                    f"Raison : {stopped_pos['reason']}. "
                    f"PnL : {stopped_pos['pnl_pct']:.2%}"
                ),
                data={
                    "symbol": stopped_pos['symbol'],
                    "reason": stopped_pos['reason'],
                    "pnl_pct": f"{stopped_pos['pnl_pct']:.2%}",
                    "current_price": stopped_pos.get('current_price'),
                    "iteration": attempt,
                },
            )
        except Exception:
            pass
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659+ passed, 0 failed
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

## PHASE 2 — MAJEURES 🟠

### [C-04] Corriger `MIMEMultipart('text', 'plain')` invalide

**Fichier** : `monitoring/email_alerter.py:78`  
**Problème** : `MIMEMultipart('text', 'plain')` est un appel invalide. `MIMEMultipart` accepte un sous-type MIME (`'mixed'`, `'alternative'`, `'related'`), pas un type/charset. Le Content-Type résultant `multipart/text; charset='plain'` est malformé et peut causer des rejets silencieux par certains serveurs SMTP ou clients mail.  
**Correction** :
```python
# Avant :
msg = MIMEMultipart('text', 'plain')
# Après :
msg = MIMEMultipart()  # subtype par défaut: 'mixed'
```

**Validation** :
```powershell
venv\Scripts\python.exe -c "
from email.mime.multipart import MIMEMultipart
msg = MIMEMultipart()
print(msg.get_content_type())  # Attendu: multipart/mixed
"
venv\Scripts\python.exe -m pytest tests/monitoring/040_test_email_alerter.py -x -q
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-05] Câbler `KillSwitch(on_activate=...)` pour notification immédiate

**Fichier** : `live_trading/runner.py:209` (dans `_initialize()`)  
**Problème** : `self._kill_switch = KillSwitch()` — le callback `on_activate` est `None`. La détection repose sur un poll `is_active` au début du tick suivant. Si le processus crashe entre l'activation et le tick suivant, l'alerte n'est jamais envoyée. Délai d'1 tick minimum (configurable, peut être plusieurs minutes en prod).  
**Correction** :
```python
# Avant :
self._kill_switch = KillSwitch()

# Après :
self._kill_switch = KillSwitch(
    on_activate=lambda reason, message: self._send_alert(
        "CRITICAL",
        f"KillSwitch activé : {reason.value}",
        message,
        {"reason": reason.value, "iteration": self._iteration},
    )
)
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/risk_engine/ -x -q
venv\Scripts\python.exe -m pytest tests/live_trading/ -x -q
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659+ passed, 0 failed
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-06] Envoyer email si sauvegarde état finale échoue

**Fichier** : `main.py:746–750` (bloc `finally` → `save_equity_snapshot`)  
**Problème** : En cas d'échec de `risk_engine.save_equity_snapshot()`, seul un `logger.warning("final_snapshot_save_skipped")` est émis. Si la sauvegarde échoue, le crash recovery de la prochaine session sera compromis — sans que l'opérateur en soit informé.  
**Correction** :
```python
# Dans le bloc except du finally :
except Exception as e:
    logger.warning("final_snapshot_save_skipped", error=str(e))
    # Ajouter :
    for _alerter in (email_alerter, slack_alerter):
        if _alerter:
            try:
                _alerter.send_alert(
                    level="ERROR",
                    title="Sauvegarde état finale échouée",
                    message=f"Crash recovery compromis : {e}",
                    data={"error": str(e)[:200]},
                )
            except Exception:
                pass
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659+ passed, 0 failed
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-07] Enrichir les `data` dicts des call-sites critiques

**Fichier** : `main.py` (call-sites lignes 412, 443, 604, 676, 716) · `live_trading/runner.py` (call-sites lignes 389, 491, 544, 623, 663)  
**Problème** : Les emails envoyés à ces call-sites contiennent des `data` dicts minimalistes (`{"iteration": attempt, "reason": ...}`). Un opérateur ne peut pas diagnostiquer l'état du portefeuille sans consulter les logs : pas de prix, pas de PnL, pas de paire, pas de quantité.  
**Correction** : Pour chaque call-site critique, enrichir `data` avec les champs disponibles dans le contexte :
- `symbol` / `pair` — identifiant de la paire
- `current_equity` — équité courante si disponible
- `pnl_pct` — PnL en % si disponible
- `open_positions` — nombre de positions ouvertes
- `error` — `str(e)[:500]` pour les erreurs

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659+ passed, 0 failed
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

## PHASE 3 — MINEURES 🟡

### [C-08] Corriger `datetime.now()` sans timezone dans le body email

**Fichier** : `monitoring/email_alerter.py:95`  
**Problème** : `{datetime.now().isoformat()}` — heure locale sans timezone. Règle codebase : toujours `datetime.now(timezone.utc)`.  
**Correction** :
```python
# Avant :
Timestamp:   {datetime.now().isoformat()}
# Après :
Timestamp:   {datetime.now(timezone.utc).isoformat()}
```
Ajouter `from datetime import timezone` si absent (déjà importé via `from datetime import datetime`).

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -W error::DeprecationWarning -x -q
# Attendu : 2659+ passed, 0 DeprecationWarning
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-09] Inclure traceback dans les emails d'erreur

**Fichier** : `main.py:716`, `live_trading/runner.py:133–138` (call-sites erreurs génériques)  
**Problème** : Les call-sites ne passent que `str(e)[:200]` — sans traceback. In production sans log access, il est impossible de diagnostiquer la cause racine depuis l'email seul.  
**Correction** : Dans les call-sites où l'exception `e` est disponible, enrichir `data` :
```python
import traceback as _tb
data={"error": str(e)[:500], "traceback": _tb.format_exc()[:2000], ...}
```
À appliquer dans : `main.py:716`, `runner.py:491`, `runner.py:623`.

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659+ passed, 0 failed
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-10] Masquer `recipient_list` dans `get_status()`

**Fichier** : `monitoring/email_alerter.py:177`  
**Problème** : `'recipient_list': self.recipients` expose les adresses email complètes. Si l'API de monitoring est exposée sans authentification, c'est une fuite PII (RGPD).  
**Correction** :
```python
# Avant :
'recipient_list': self.recipients
# Après :
'recipient_count': len(self.recipients)
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/monitoring/ -x -q
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659+ passed, 0 failed
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-11] Envoyer email sur ordre rejeté par risk engine (raisons critiques)

**Fichier** : `main.py:548` (bloc `if not can_enter:`)  
**Problème** : `logger.warning("trade_rejected_by_risk", pair=..., reason=...)` uniquement. Si le risk engine rejette systématiquement tous les ordres (config incorrecte, drawdown), l'opérateur n'en sera notifié que via les logs — le trading est silencieusement paralysé.  
**Correction** :
```python
logger.warning("trade_rejected_by_risk", pair=signal.symbol_pair, reason=reason)
# Ajouter — uniquement pour raisons critiques (drawdown, kill-switch) :
if any(kw in reason.lower() for kw in ("drawdown", "kill", "halt", "emergency")):
    for _alerter in (email_alerter, slack_alerter):
        if _alerter:
            try:
                _alerter.send_alert(
                    level="ERROR",
                    title=f"Ordre bloqué (risk critique) : {signal.symbol_pair}",
                    message=f"Raison : {reason}",
                    data={"pair": signal.symbol_pair, "reason": reason, "iteration": attempt},
                )
            except Exception:
                pass
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659+ passed, 0 failed
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

### [C-12] Câbler un callback email sur ouverture du circuit breaker

**Fichier** : `common/circuit_breaker.py`  
**Problème** : Le circuit breaker n'est pas connecté au système d'alerte email. Quand il passe en état OPEN, aucune notification n'est envoyée — le pipeline de données est dégradé silencieusement.  
**Correction** : Vérifier si `CircuitBreaker` supporte un `on_open` callback. Si oui, câbler `send_alert(level="ERROR", ...)` lors de l'instanciation dans les call-sites de production. Si non, ajouter un paramètre `on_open: Optional[Callable] = None` à la classe et l'invoquer lors du changement d'état → OPEN.  
**Note** : Applicable uniquement si le circuit breaker est utilisé en dehors de `research/` ou `scripts/`.

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2659+ passed, 0 failed
```
**Dépend de** : Aucune  
**Statut** : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
C-04  → C-08  → C-10    # Trivial (< 1h chacun) — aucun risque
  ↓
C-01  → C-02             # Base SMTP robuste avant d'ajouter les nouveaux call-sites
  ↓
C-03  → C-06             # Nouveaux call-sites email (stop-loss, snapshot)
  ↓
C-05                     # KillSwitch on_activate (dépend de _send_alert stable)
  ↓
C-07  → C-09  → C-11    # Enrichissement data dicts et call-sites mineurs
  ↓
C-12                     # Circuit breaker — nécessite lecture préalable du code
```

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] `pytest tests/ : 100% pass (2659+)`
- [ ] `mypy risk/ risk_engine/ execution/ : exit 0`
- [ ] `ruff check . : 0 erreurs`
- [ ] Zéro credential IBKR dans les logs
- [ ] Kill-switch persisté au redémarrage
- [ ] Risk tiers cohérents (`_assert_risk_tier_coherence OK`)
- [ ] `EDGECORE_ENV=prod` dans Dockerfile (pas `"production"`)
- [ ] Paper trading validé avant live
- [ ] Email throttle testé manuellement : 2e envoi identique dans les 60s → `(False, "throttled")`
- [ ] Email retry testé : SMTP down → 3 tentatives loggées, exception finale propre

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Retry SMTP avec backoff | 🔴 P0 | `email_alerter.py:133` | 2h | ⏳ | — |
| C-02 | Cooldown/déduplication EmailAlerter | 🔴 P0 | `email_alerter.py` | 3h | ⏳ | — |
| C-03 | Email stop-loss déclenché | 🔴 P0 | `main.py:499` | 1h | ⏳ | — |
| C-04 | Corriger MIMEMultipart invalide | 🟠 P1 | `email_alerter.py:78` | 15min | ⏳ | — |
| C-05 | KillSwitch on_activate câblé | 🟠 P1 | `runner.py:209` | 1h | ⏳ | — |
| C-06 | Email si snapshot finale échoue | 🟠 P1 | `main.py:749` | 30min | ⏳ | — |
| C-07 | Enrichir data dicts call-sites | 🟠 P1 | `main.py, runner.py` | 3h | ⏳ | — |
| C-08 | datetime.now() → timezone.utc | 🟡 P2 | `email_alerter.py:95` | 15min | ⏳ | — |
| C-09 | Traceback dans emails erreur | 🟡 P2 | `main.py:716, runner.py:491` | 1h | ⏳ | — |
| C-10 | Masquer recipient_list PII | 🟡 P2 | `email_alerter.py:177` | 15min | ⏳ | — |
| C-11 | Email ordre rejeté risk critique | 🟡 P2 | `main.py:548` | 1h | ⏳ | — |
| C-12 | Circuit breaker on_open callback | 🟡 P2 | `common/circuit_breaker.py` | 2h | ⏳ | — |
