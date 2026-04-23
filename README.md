# IA CSV Converter

Application de conversion assistee par IA pour transformer des fichiers ou contenus non structures en tableaux CSV exploitables.

L'objectif du projet est simple : prendre une source brute comme du texte, un PDF ou un tableau imparfait, en extraire les informations utiles, puis produire un CSV propre, coherent et directement reutilisable.

## Objectif

Ce projet vise a automatiser une tache souvent fastidieuse :

- lire un contenu peu structure,
- identifier les donnees importantes,
- organiser ces donnees en colonnes logiques,
- normaliser les formats,
- exporter le resultat en `.csv`.

L'application est pensee pour un usage personnel ou pour des petits workflows de nettoyage de donnees.

## Fonctionnalites de la version actuelle

- Import de fichiers `.csv`, `.txt`, `.tsv`, `.json`, `.xlsx`, `.xls` et `.pdf`
- Collage direct de texte brut dans l'interface
- Detection automatique d'un separateur simple
- Conversion de JSON en tableau
- Parsing basique de texte de type `cle: valeur`
- Nettoyage des colonnes et suppression des lignes vides
- Apercu editable dans l'interface
- Export du resultat en `.csv`
- Interface web simple avec Streamlit

## Formats pris en charge

La premiere version locale traite notamment :

- `.txt`
- `.pdf`
- `.xlsx`
- texte colle manuellement
- JSON simple ou semi-structure

Le support PDF reste simple et depend de la qualite du texte extractible depuis le document.

## Stack

- Python 3.8+
- Streamlit pour l'interface
- `pandas` pour la manipulation tabulaire
- `openpyxl` pour Excel
- `pypdf` pour l'extraction texte depuis des PDF simples

## Arborescence locale actuelle

Dans ce dossier local, les fichiers principaux sont actuellement :

- `readme.md`
- `memory.md`
- `streamlit_app.py`
- `requirements.txt`

Chemin local de travail memorise pour l'application :

`/Users/alexandrepaviel/Desktop/OF/application CSV`

## Installation

Installation locale :

```bash
git clone https://github.com/Blackpearl97410/appcsv.git
cd appcsv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

La version actuelle fonctionne sans cle API.

Une integration OpenAI ou Gemini pourra etre ajoutee ensuite pour enrichir l'extraction et la structuration automatique.

## Lancement

Lancement local :

```bash
streamlit run streamlit_app.py
```

## Cas d'usage

- Convertir un document texte en tableau CSV
- Extraire des donnees de factures ou listes simples
- Reorganiser un contenu brut en colonnes coherentes
- Gagner du temps sur du nettoyage manuel repetitif

## Etat actuel

Le projet dispose maintenant d'une premiere base fonctionnelle en local.

Cette version repose sur des heuristiques locales et sur des parsers simples. Elle permet deja de charger, nettoyer, visualiser et exporter des donnees sous forme de CSV.

## Prochaines etapes recommandees

- ajouter une couche IA pour mieux inferer les colonnes,
- preciser le fournisseur IA retenu,
- ajouter un exemple d'entree et de CSV de sortie,
- documenter la gestion des erreurs et limites du parsing,
- gerer les PDF complexes ou scannes,
- proposer un mapping manuel des colonnes avant export.

## Licence

A definir.
