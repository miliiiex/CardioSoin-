# CardioSoin — Application Médicale Sécurisée

Application web full-stack d'aide au suivi médical et à l'évaluation des risques cardiovasculaires, conçue pour centraliser le suivi des dossiers patients tout en garantissant un contrôle d'accès strict aux données de santé.

## 🚀 Fonctionnalités

* 🔐 Authentification forte et contrôle des accès (RBAC)
* 👨‍⚕️ Espace de travail dédié aux médecins
* 💼 Espace de travail dédié aux secrétaires
* 👤 Espace patient sécurisé
* 🧮 Calculateur automatisé du score de risque de Framingham
* 📋 Gestion des dossiers cliniques et d'identité des patients
* 📑 Suivi complet des antécédents médicaux
* 📅 Planification et gestion des rendez-vous médicaux
* 💊 Édition, suivi et archivage des prescriptions (ordonnances)
* ✉️ Système de notifications et d'alertes par mail

## 🛠️ Technologies utilisées

* Python
* Django
* MySQL
* HTML / CSS
* JavaScript
* Git / GitHub

## 📂 Architecture du projet

```text
CardioSoin/
├── backend/
│   ├── accounts/          # Authentification et profils utilisateurs
│   ├── appointments/      # Planification des rendez-vous
│   ├── backend/           # Configuration globale Django (settings, urls)
│   ├── cabinet/           # Administration de la structure médicale
│   ├── history/           # Historiques et antécédents médicaux
│   ├── patients/          # Fiches patients et dossiers cliniques
│   ├── prescriptions/     # Gestion et édition des ordonnances
│   ├── static/            # Fichiers statiques (CSS, JS, images)
│   └── manage.py          # Point d'entrée de l'application Django
├── .env.example           # Configuration des variables d'environnement
├── email_secret.txt       # Configuration sécurisée du serveur de messagerie
└── requirements.txt       # Dépendances du projet Python
