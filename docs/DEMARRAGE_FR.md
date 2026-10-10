# Démarrage de CaseTrace

## Installation et lancement

1. Effectuer l'installation Python décrite dans le [README](../README.md).
2. Configurer le fournisseur et le modèle dans le fichier local `.env`.
3. Double-cliquer sur **start.cmd** et laisser la fenêtre ouverte.
4. Ouvrir **http://127.0.0.1:8768** dans le navigateur.
5. Cliquer sur **Load synthetic cases**, choisir un dossier et sélectionner un mode.
6. Pour une investigation avec modèle, autoriser la transmission des extraits puis cliquer sur **Investigate**.

La clé API reste dans `.env`, exclu de Git. Une modification de la configuration nécessite le redémarrage du serveur. L'environnement Python doit être installé sur chaque machine.

## Modes disponibles

- **Two-agent investigation** : appels au modèle configuré, sélection d'outils par l'investigateur, puis vérification par un second rôle.
- **Single-pass RAG baseline** : réponse du modèle à partir de passages retrouvés, sans boucle d'outils ni second rôle.
- **Offline template demo** : règles déterministes appliquées aux champs des dossiers fictifs, sans appel au modèle.

Le fichier **CaseTrace_Demo.html** permet également de consulter des exécutions enregistrées sans installer le serveur. Cette démonstration ne lance pas de nouvelles investigations.

## Consultation des résultats

**Findings** présente les observations et les citations. Un clic sur une citation ouvre son texte source. **Agent activity** présente les opérations enregistrées. **Human review** permet d'enregistrer une appréciation du rapport. Les exports sont disponibles en PDF, JSON et Markdown.

## Résolution des problèmes

- **HTTP 429** : quota ou limite de débit du fournisseur atteint. Consulter les limites du compte et le délai de renouvellement. L'application n'active pas de facturation et ne change pas automatiquement de fournisseur.
- **HTTP 404** : vérifier que le modèle et l'URL du fournisseur sont accessibles avec le projet API configuré, puis redémarrer le serveur.
- **Adresse déjà utilisée** : vérifier si une instance est déjà lancée avant d'en ouvrir une autre.
- **Page inaccessible** : vérifier que la fenêtre du serveur reste ouverte et affiche l'adresse locale. Consulter les dernières lignes de cette fenêtre en cas d'erreur de démarrage.
- **PDF sans texte** : utiliser un PDF contenant du texte extractible ; l'OCR n'est pas inclus.
- **Erreur de clé** : vérifier la configuration locale puis redémarrer. Les clés ne doivent pas apparaître dans les journaux partagés ou les captures d'écran.

## Périmètre

CaseTrace est un prototype local d'analyse de cohérence documentaire. Les exemples sont fictifs et l'évaluation porte sur trois dossiers utilisés pendant le développement. Les résultats ne démontrent pas une amélioration générale par rapport au RAG simple. La décision et l'interprétation finale restent humaines.
