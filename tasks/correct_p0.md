# Template : Correction P0

> Utilisation : créer une copie de ce fichier nommée `docs/corrections/{date}_{ID}.md`
> Exemple : `docs/corrections/2026-03-15_B5-01.md`

---

## Identification

| Champ | Valeur |
|-------|--------|
| **ID** | B5-01 *(ex. B5-01, B2-02, issue GitHub #42)* |
| **Sévérité** | P0 — Critique bloquant prod |
| **Module** | `Dockerfile`, `docker-compose.yml` |
| **Fichier:Ligne** | `Dockerfile:34`, `docker-compose.yml:11` |
| **Découvert le** | AAAA-MM-JJ |
| **Découvert par** | [nom / audit automatique / test] |

---

## Description

*Description concise du bug en 2-3 phrases.*

> Exemple : `EDGECORE_ENV=production` dans Dockerfile et docker-compose.yml. La valeur `production` n'est pas un environnement valide — la config tombe silencieusement sur `dev.yaml` en production. Cela désactive les contrôles de risque production et expose le système avec des seuils de développement.

---

## Impact

- **Système affecté** : `[module(s) impacté(s)]`
- **Comportement observé** : `[ce qui se passe réellement]`
- **Comportement attendu** : `[ce qui devrait se passer]`
- **Risque si non corrigé** : `[conséquence opérationnelle / financière / sécurité]`

---

## Reproduction

```powershell
# Étapes pour reproduire le bug
# Exemple :
docker-compose up -d
docker exec edgecore python -c "from config.settings import get_settings; print(get_settings()._env)"
# Sortie actuelle  : dev
# Sortie attendue  : prod
```

---

## Analyse de cause racine

*Expliquer pourquoi le bug existe, pas juste ce qu'il fait.*

> Exemple : La classe `Settings.__init__()` appelle `os.environ.get("EDGECORE_ENV", "dev")`. Lorsque la valeur n'est pas dans `{"dev", "test", "prod"}`, elle utilise le fallback `"dev"`. Le mot `"production"` vient d'une convention différente non documentée.

---

## Fix appliqué

### Fichier(s) modifié(s)

```diff
# Dockerfile:34
- ENV EDGECORE_ENV=production
+ ENV EDGECORE_ENV=prod

# docker-compose.yml:11
- ENVIRONMENT: production
+ EDGECORE_ENV: prod
```

### Commandes appliquées (si applicable)

```powershell
# Exemple
(Get-Content Dockerfile) -replace 'EDGECORE_ENV=production', 'EDGECORE_ENV=prod' | Set-Content Dockerfile
```

---

## Tests modifiés / ajoutés

| Test | Fichier | Type | Statut |
|------|---------|------|--------|
| `test_docker_env_prod` | `tests/test_config/test_settings.py` | Nouveau | ✅ |
| `test_settings_invalid_env` | `tests/test_config/test_settings.py` | Modifié | ✅ |

### Vérification après fix

```powershell
# Tests complets
venv\Scripts\python.exe -m pytest tests/ -q
# Attendu : >= 2654 passed, 0 failed

# Vérification spécifique
venv\Scripts\python.exe -m pytest tests/test_config/ -v

# Risk tiers
venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"
```

---

## Validation

- [ ] Fix déployé en dev (`EDGECORE_ENV=dev`)
- [ ] Fix validé en test (`EDGECORE_ENV=test`)
- [ ] Tests passants (>= baseline)
- [ ] Aucune régression détectée
- [ ] Revue par un second développeur
- [ ] Checklist `tasks/audit_structural.md` mise à jour (issue marquée ✅)

---

## Suivi

| Champ | Valeur |
|-------|--------|
| **Fix committé le** | AAAA-MM-JJ |
| **Hash commit** | `abc1234` |
| **PR / MR** | #XX |
| **Déployé en prod le** | AAAA-MM-JJ |
| **Vérifié en prod le** | AAAA-MM-JJ |
| **Fermé par** | [nom] |

---

## Notes additionnelles

*Toute information supplémentaire : workarounds temporaires, issues liées, dette créée.*
