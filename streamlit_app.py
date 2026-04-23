from __future__ import annotations

import io
import json
import os
import re
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional dependency at runtime
    PdfReader = None

try:
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover - optional dependency at runtime
    genai = None
    types = None


APP_TITLE = "IA CSV Converter"
DEFAULT_OUTPUT_NAME = "converted_data.csv"
DEFAULT_GOOGLE_MODEL = "gemini-2.5-flash"


def clean_column_name(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    return text or "column"


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [clean_column_name(col) for col in normalized.columns]
    normalized = normalized.dropna(axis=0, how="all").dropna(axis=1, how="all")
    normalized = normalized.reset_index(drop=True)

    for column in normalized.columns:
        if normalized[column].dtype == object:
            normalized[column] = normalized[column].map(
                lambda value: value.strip() if isinstance(value, str) else value
            )

    return normalized


def build_dataframe_from_records(records: list[dict[str, object]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()

    df = pd.json_normalize(records)
    return normalize_dataframe(df)


def parse_json_text(raw_text: str) -> pd.DataFrame:
    parsed = json.loads(raw_text)

    if isinstance(parsed, list):
        if parsed and all(isinstance(item, dict) for item in parsed):
            return build_dataframe_from_records(parsed)
        return pd.DataFrame({"value": parsed})

    if isinstance(parsed, dict):
        list_candidates = [
            value
            for value in parsed.values()
            if isinstance(value, list) and value and all(isinstance(item, dict) for item in value)
        ]
        if len(list_candidates) == 1:
            return build_dataframe_from_records(list_candidates[0])
        return build_dataframe_from_records([parsed])

    return pd.DataFrame({"value": [parsed]})


def detect_delimiter(raw_text: str) -> str | None:
    delimiters = [",", ";", "\t", "|"]
    lines = [line for line in raw_text.splitlines() if line.strip()]
    sample = lines[:5]

    best_delimiter = None
    best_score = 0
    for delimiter in delimiters:
        counts = [line.count(delimiter) for line in sample]
        if counts and min(counts) > 0 and len(set(counts)) == 1:
            if counts[0] > best_score:
                best_score = counts[0]
                best_delimiter = delimiter

    return best_delimiter


def parse_key_value_lines(lines: Iterable[str]) -> pd.DataFrame:
    records: list[dict[str, str]] = []
    current_record: dict[str, str] = {}

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if current_record:
                records.append(current_record)
                current_record = {}
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            current_record[clean_column_name(key)] = value.strip()
        else:
            current_record.setdefault("raw_text", "")
            current_record["raw_text"] = f"{current_record['raw_text']} {line}".strip()

    if current_record:
        records.append(current_record)

    return build_dataframe_from_records(records)


def parse_plain_text(raw_text: str, delimiter: str | None, has_header: bool) -> pd.DataFrame:
    text = raw_text.strip()
    if not text:
        return pd.DataFrame()

    if text.startswith("{") or text.startswith("["):
        return parse_json_text(text)

    selected_delimiter = delimiter if delimiter and delimiter != "auto" else detect_delimiter(text)
    if selected_delimiter:
        header = 0 if has_header else None
        df = pd.read_csv(io.StringIO(text), sep=selected_delimiter, header=header)
        if not has_header:
            df.columns = [f"column_{index + 1}" for index in range(df.shape[1])]
        return normalize_dataframe(df)

    lines = [line for line in text.splitlines()]
    key_value_df = parse_key_value_lines(lines)
    if not key_value_df.empty and len(key_value_df.columns) > 1:
        return key_value_df

    return normalize_dataframe(pd.DataFrame({"raw_text": [line for line in lines if line.strip()]}))


def read_pdf(uploaded_file) -> str:
    if PdfReader is None:
        raise RuntimeError("Le support PDF n'est pas disponible. Installe `pypdf`.")

    reader = PdfReader(io.BytesIO(uploaded_file.getvalue()))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def parse_uploaded_file(uploaded_file, delimiter: str | None, has_header: bool) -> tuple[pd.DataFrame, str]:
    suffix = Path(uploaded_file.name).suffix.lower()

    if suffix in {".csv", ".txt", ".tsv"}:
        raw_text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
        return parse_plain_text(raw_text, delimiter, has_header), "text"

    if suffix == ".json":
        raw_text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
        return parse_json_text(raw_text), "json"

    if suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(io.BytesIO(uploaded_file.getvalue()))
        return normalize_dataframe(df), "excel"

    if suffix == ".pdf":
        raw_text = read_pdf(uploaded_file)
        return parse_plain_text(raw_text, delimiter, has_header), "pdf"

    raise ValueError(f"Format non supporte : {suffix or 'inconnu'}")


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def build_ai_prompt(raw_text: str) -> str:
    return f"""
Tu es un moteur de structuration de donnees.

Transforme le contenu ci-dessous en tableau exploitable.
Regles:
- identifie des colonnes utiles et stables,
- normalise les en-tetes en snake_case ASCII,
- preserve autant que possible l'information source,
- retourne uniquement un JSON valide,
- ne renvoie aucune explication.

Le format attendu est:
{{
  "columns": ["colonne_1", "colonne_2"],
  "rows": [
    ["valeur_1", "valeur_2"],
    ["valeur_1", null]
  ]
}}

Contenu source:
{raw_text}
""".strip()


def dataframe_from_ai_payload(payload: dict[str, object]) -> pd.DataFrame:
    columns = payload.get("columns", [])
    rows = payload.get("rows", [])

    if not isinstance(columns, list) or not isinstance(rows, list):
        raise ValueError("Reponse JSON invalide")

    cleaned_columns = [clean_column_name(column) for column in columns]
    df = pd.DataFrame(rows, columns=cleaned_columns if cleaned_columns else None)
    if not cleaned_columns and not df.empty:
        df.columns = [f"column_{index + 1}" for index in range(df.shape[1])]
    return normalize_dataframe(df)


def convert_with_google_ai(raw_text: str, api_key: str, model_name: str) -> pd.DataFrame:
    if genai is None or types is None:
        raise RuntimeError("Le SDK Google GenAI n'est pas installe. Ajoute `google-genai`.")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=build_ai_prompt(raw_text),
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )

    if not getattr(response, "text", None):
        raise RuntimeError("Le modele Google n'a retourne aucun texte exploitable.")

    payload = json.loads(response.text)
    return dataframe_from_ai_payload(payload)


def render_sidebar() -> tuple[str, str, bool, bool, str, str]:
    st.sidebar.header("Parametres")
    source_mode = st.sidebar.radio(
        "Source",
        options=["Fichier", "Texte colle"],
        help="Choisis si tu veux importer un fichier ou coller du contenu brut.",
    )
    delimiter = st.sidebar.selectbox(
        "Separateur",
        options=["auto", ",", ";", "\\t", "|"],
        format_func=lambda value: "auto" if value == "auto" else ("tabulation" if value == "\\t" else value),
    )
    has_header = st.sidebar.checkbox("La premiere ligne contient les en-tetes", value=True)
    use_ai = st.sidebar.checkbox("Utiliser Google AI pour structurer", value=False)
    google_model = st.sidebar.text_input("Modele Google", value=DEFAULT_GOOGLE_MODEL)
    google_api_key = st.sidebar.text_input(
        "Google API key",
        value=os.getenv("GOOGLE_API_KEY", ""),
        type="password",
        help="Cle lue depuis GOOGLE_API_KEY ou saisie ici pour cette session uniquement.",
    )
    return (
        source_mode,
        ("\t" if delimiter == "\\t" else delimiter),
        has_header,
        use_ai,
        google_model.strip() or DEFAULT_GOOGLE_MODEL,
        google_api_key.strip(),
    )


def render_intro() -> None:
    st.title(APP_TITLE)
    st.caption("Transforme un texte, un JSON, un Excel ou un PDF simple en tableau CSV exploitable.")

    with st.expander("Ce que fait cette version"):
        st.markdown(
            """
            - importe un fichier ou du texte colle,
            - detecte quelques structures courantes,
            - nettoie les colonnes et les lignes vides,
            - laisse corriger les donnees avant export.

            Cette version peut fonctionner en mode local ou avec Google AI pour une structuration plus intelligente.
            """
        )


def df_to_text(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    return df.to_csv(index=False)


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")
    render_intro()

    source_mode, delimiter, has_header, use_ai, google_model, google_api_key = render_sidebar()

    df = pd.DataFrame()
    source_label = ""
    raw_text_for_ai = ""

    if source_mode == "Fichier":
        uploaded_file = st.file_uploader(
            "Importer un fichier",
            type=["csv", "txt", "tsv", "json", "xlsx", "xls", "pdf"],
        )
        if uploaded_file is not None:
            try:
                df, source_label = parse_uploaded_file(uploaded_file, delimiter, has_header)
                raw_text_for_ai = df_to_text(df)
            except Exception as exc:
                st.error(f"Impossible de lire le fichier : {exc}")
    else:
        raw_text = st.text_area(
            "Coller le contenu a convertir",
            height=260,
            placeholder=(
                "nom: Alice\nmontant: 42\n\nnom: Bob\nmontant: 15\n"
                "\nOu colle ici un CSV, TSV, JSON ou texte brut."
            ),
        )
        if raw_text.strip():
            raw_text_for_ai = raw_text
            try:
                df = parse_plain_text(raw_text, delimiter, has_header)
                source_label = "texte"
            except Exception as exc:
                st.error(f"Impossible d'analyser le contenu : {exc}")

    if use_ai:
        if not google_api_key:
            st.warning("Active GOOGLE_API_KEY ou saisis une cle dans la barre laterale pour utiliser Google AI.")
        elif not raw_text_for_ai.strip():
            st.info("Ajoute d'abord un contenu a convertir avant d'utiliser l'IA.")
        else:
            try:
                with st.spinner(f"Structuration via Google AI ({google_model})..."):
                    df = convert_with_google_ai(raw_text_for_ai, google_api_key, google_model)
                    source_label = f"google_ai:{google_model}"
            except Exception as exc:
                st.error(f"Conversion IA impossible : {exc}")

    if df.empty:
        st.info("Ajoute un fichier ou colle du texte pour generer un tableau.")
        return

    st.success(f"Tableau genere depuis la source : {source_label or 'analyse locale'}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Lignes", len(df))
    col2.metric("Colonnes", len(df.columns))
    col3.metric("Cellules vides", int(df.isna().sum().sum()))

    st.subheader("Apercu editable")
    edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")

    st.subheader("Colonnes detectees")
    st.write(", ".join(f"`{column}`" for column in edited_df.columns))

    st.download_button(
        label="Telecharger le CSV",
        data=dataframe_to_csv_bytes(edited_df),
        file_name=DEFAULT_OUTPUT_NAME,
        mime="text/csv",
        use_container_width=True,
    )

    with st.expander("Voir le CSV genere"):
        st.code(edited_df.to_csv(index=False), language="csv")


if __name__ == "__main__":
    main()
