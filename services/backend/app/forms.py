from pydantic import Field
from .schemas import Strict
from typing import Literal
from fastapi import HTTPException
from .db import Instrument
from sqlalchemy import select

DEMO_FORM = {
    "instrument_id": "CHECKIN_DEMO_V1",
    "version": "1",
    "language": "es-PE",
    "provenance": "Inventado exclusivamente para probar software",
    "usage_permission": "Definición propia de laboratorio",
    "recall": "hoy",
    "real": False,
    "questions": [
        {"id": "energy", "text": "¿Cómo sentiste tu energía hoy?"},
        {"id": "focus", "text": "¿Qué tan fácil te resultó concentrarte hoy?"},
        {"id": "rest", "text": "¿Cómo sentiste tu descanso hoy?"},
    ],
    "options": [
        {"value": 0, "label": "Muy bien"},
        {"value": 1, "label": "Bien"},
        {"value": 2, "label": "Regular"},
        {"value": 3, "label": "Mal"},
    ],
    "scoring": "sum",
    "review_threshold": 6,
    "item_rules": [],
    "notice": "Formulario inventado. Suma 0–9 y regla ≥6 arbitrarias, sin significado clínico.",
}


class Question(Strict):
    id: str = Field(pattern=r"^[a-zA-Z0-9_]{1,50}$")
    text: str = Field(min_length=1, max_length=2000)


class Option(Strict):
    value: int = Field(ge=0, le=100)
    label: str = Field(min_length=1, max_length=300)


class ItemRule(Strict):
    question_id: str
    operator: Literal["gte", "eq"]
    value: int
    reason: str = Field(min_length=1, max_length=200)


class FormDefinition(Strict):
    instrument_id: str = Field(pattern=r"^[A-Z0-9_]{1,80}$")
    version: str = Field(min_length=1, max_length=30)
    language: str
    provenance: str = Field(min_length=1)
    usage_permission: str = Field(min_length=1)
    recall: str = Field(min_length=1)
    real: bool = True
    questions: list[Question] = Field(min_length=1, max_length=100)
    options: list[Option] = Field(min_length=2, max_length=30)
    scoring: Literal["sum"]
    review_threshold: int = Field(ge=0)
    item_rules: list[ItemRule]
    notice: str
    protocol: dict[str, str] = Field(default_factory=dict)


def validate_definition(data):
    f = FormDefinition.model_validate(data)
    ids = [q.id for q in f.questions]
    values = [o.value for o in f.options]
    if len(ids) != len(set(ids)) or len(values) != len(set(values)):
        raise ValueError("IDs y valores deben ser únicos")
    if any(r.question_id not in ids for r in f.item_rules):
        raise ValueError("Regla de ítem desconocido")
    if f.review_threshold > len(ids) * max(values):
        raise ValueError("Umbral fuera del rango")
    return f.model_dump()


def score(definition, answers):
    expected = {q["id"] for q in definition["questions"]}
    options = {o["value"] for o in definition["options"]}
    if set(answers) != expected or any(
        type(v) is not int or v not in options for v in answers.values()
    ):
        raise HTTPException(
            422,
            "Responda todas las preguntas con opciones válidas; no se calcula puntaje parcial",
        )
    total = sum(answers.values())
    rules = [
        r["reason"]
        for r in definition["item_rules"]
        if (
            answers[r["question_id"]] >= r["value"]
            if r["operator"] == "gte"
            else answers[r["question_id"]] == r["value"]
        )
    ]
    return total, total >= definition["review_threshold"] or bool(rules), rules


def ensure_demo_form(db):
    item = db.scalar(select(Instrument).where(Instrument.code == "CHECKIN_DEMO_V1"))
    if not item:
        item = Instrument(code="CHECKIN_DEMO_V1", definition=DEMO_FORM, enabled=True)
        db.add(item)
        db.flush()
    return item
