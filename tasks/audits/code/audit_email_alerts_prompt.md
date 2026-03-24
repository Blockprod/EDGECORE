---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/audit_email_alerts_edgecore.md
derniere_revision: 2026-03-20
creation: 2026-03-17 à 22:27
---

#codebase

Tu es un Senior Software Engineer spécialisé en systèmes
de notification et de monitoring pour applications critiques.
Tu réalises un audit EXCLUSIVEMENT centré sur le système
d'alertes email du projet ouvert dans ce workspace.

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Réfléchis profondément étape par étape avant
de produire ta sortie. Explore d'abord, planifie
ensuite, puis exécute.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà dans :
  tasks/audits/audit_email_alerts_edgecore.md

Si trouvé, affiche :
"⚠️ Audit email existant détecté :
 Fichier : tasks/audits/audit_email_alerts_edgecore.md
 Date    : [date modification]
 Lignes  : [nombre approximatif]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit email existant. Démarrage..."

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
Tu analyses UNIQUEMENT :
- Le système d'envoi d'emails et sa robustesse
- La couverture des événements notifiés
- La sécurité du contenu des alertes
- La protection contre les tempêtes d'emails

Tu n'analyses PAS :
- La stratégie de trading
- L'architecture des modules
- La sécurité des credentials exchange
- La concurrence et le thread-safety

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Ne lis aucun fichier .md, .txt, .rst
- Cite fichier:ligne pour chaque problème
- Écris "À VÉRIFIER" sans preuve dans le code
- Ignore tout commentaire de style PEP8

─────────────────────────────────────────────
BLOC 1 — SYSTÈME D'ENVOI
─────────────────────────────────────────────
- Les fonctions d'envoi email ont-elles un retry
  avec backoff en cas d'échec SMTP ?
- Y a-t-il un cooldown entre alertes similaires
  pour éviter les tempêtes d'emails
  (ex : boucle de retry = 50 emails identiques) ?
- Le transport SMTP utilise-t-il TLS (port 587)
  et non SSL direct ?
- Les échecs d'envoi email sont-ils loggés
  sans crasher le système principal ?

─────────────────────────────────────────────
BLOC 2 — COUVERTURE DES ÉVÉNEMENTS
─────────────────────────────────────────────
Vérifie si chaque événement critique déclenche
une notification email. Pour chaque item :
conclus par COUVERT / NON COUVERT / À VÉRIFIER

Événements d'erreurs système :
- [ ] Exception critique non gérée
- [ ] Échec de sauvegarde d'état (3 tentatives)
- [ ] Échec de connexion à l'exchange / broker
- [ ] Données de marché manquantes ou corrompues
- [ ] Erreur réseau prolongée
- [ ] Circuit breaker déclenché

Événements de trading :
- [ ] Ordre d'achat exécuté (avec prix, quantité, PnL)
- [ ] Ordre de vente exécuté (avec raison, PnL)
- [ ] Ordre bloqué (raison explicite : capital,
      corrélation, garde, OOS, kill-switch)
- [ ] Ordre tenté mais échoué (timeout, rejet exchange)
- [ ] Stop-loss déclenché
- [ ] Vente partielle exécutée
- [ ] Position ouverte sans stop-loss détectée

Événements de protection du capital :
- [ ] Daily loss limit atteint
- [ ] Drawdown kill-switch déclenché
- [ ] OOS gate bloqué
- [ ] Emergency halt activé

─────────────────────────────────────────────
BLOC 3 — QUALITÉ DU CONTENU
─────────────────────────────────────────────
- Les emails contiennent-ils suffisamment
  d'informations pour diagnostiquer sans logs
  (paire, prix, quantité, raison, horodatage) ?
- Les emails d'erreur incluent-ils le traceback
  ou uniquement un message générique ?
- Y a-t-il un credential (clé API, mot de passe)
  dans le corps des emails ?
- Les sujets des emails permettent-ils de
  distinguer immédiatement critique vs informatif ?

─────────────────────────────────────────────
BLOC 4 — CAS MANQUANTS ET RISQUES
─────────────────────────────────────────────
- Y a-t-il des erreurs critiques swallowées
  silencieusement sans aucune notification ?
- Des événements de trading sont-ils loggés
  uniquement en console sans email associé ?
- Le système peut-il générer une cascade d'emails
  identiques en cas de retry loop ?
- En cas d'échec SMTP, le bot continue-t-il
  à fonctionner normalement ?

─────────────────────────────────────────────
SYNTHÈSE
─────────────────────────────────────────────
Tableau complet :
| ID | Bloc | Description | Fichier:Ligne |
| Sévérité | Impact | Effort |

Sévérité P0/P1/P2/P3.

Liste des événements NON COUVERTS par ordre
de criticité financière.
Top 3 risques immédiats liés aux alertes manquantes.
Points forts du système de notification à conserver.

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/audit_email_alerts_edgecore.md
Crée le dossier tasks/audits/ s'il n'existe pas.

Structure du fichier :
## BLOC 1 — SYSTÈME D'ENVOI
## BLOC 2 — COUVERTURE DES ÉVÉNEMENTS
## BLOC 3 — QUALITÉ DU CONTENU
## BLOC 4 — CAS MANQUANTS
## SYNTHÈSE

Tableau synthèse :
| ID | Bloc | Description | Fichier:Ligne |
| Sévérité | Impact | Effort |

Sévérité P0/P1/P2/P3.
Liste événements NON COUVERTS par criticité.
Top 3 risques liés aux alertes manquantes.
Points forts à conserver.

Confirme dans le chat :
"✅ tasks/audits/audit_email_alerts_edgecore.md créé
 🔴 X · 🟠 X · 🟡 X"
