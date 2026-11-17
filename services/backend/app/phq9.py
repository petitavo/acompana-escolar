"""PHQ-9 estándar español. AETC PDF, consultado y cotejado visualmente 2026-09-06."""
import hashlib
import json
from sqlalchemy import select
from .db import Instrument

SOURCE_SHA256 = "1041559d940ba6dd5c03132e8922dcc537b750051594322b68c8fe265a79e90c"
PHQ9 = {
    "instrument_id": "PHQ9_ES_AETC_2016",
    "title": "Cuestionario sobre la salud del paciente-9 (PHQ-9)",
    "version": "AETC-2016-es-2",
    "language": "es",
    "real": True,
    "recall": "Durante las últimas 2 semanas, ¿qué tan seguido ha tenido molestias debido a los siguientes problemas?",
    "recall_days": 14,
    "cadence_days": 14,
    "questions": [
        {"id": "q1", "text": "Poco interés o placer en hacer cosas"},
        {"id": "q2", "text": "Se ha sentido decaído(a), deprimido(a) o sin esperanzas"},
        {"id": "q3", "text": "Ha tenido dificultad para quedarse o permanecer dormido(a), o ha dormido demasiado"},
        {"id": "q4", "text": "Se ha sentido cansado(a) o con poca energía"},
        {"id": "q5", "text": "Sin apetito o ha comido en exceso"},
        {"id": "q6", "text": "Se ha sentido mal con usted mismo(a) – o que es un fracaso o que ha quedado mal con usted mismo(a) o con su familia"},
        {"id": "q7", "text": "Ha tenido dificultad para concentrarse en ciertas actividades, tales como leer el periódico o ver la televisión"},
        {"id": "q8", "text": "¿Se ha movido o hablado tan lento que otras personas podrían haberlo notado? o lo contrario – muy inquieto(a) o agitado(a) que ha estado moviéndose mucho más de lo normal"},
        {"id": "q9", "text": "Pensamientos de que estaría mejor muerto(a) o de lastimarse de alguna manera"},
    ],
    "options": [{"value": 0, "label": "Ningún día"}, {"value": 1, "label": "Varios días"}, {"value": 2, "label": "Más de la mitad de los días"}, {"value": 3, "label": "Casi todos los días"}],
    "functioning": {
        "text": "Si marcó cualquiera de los problemas, ¿qué tanta dificultad le han dado estos problemas para hacer su trabajo, encargarse de las tareas del hogar, o llevarse bien con otras personas?",
        "options": ["No ha sido difícil", "Un poco difícil", "Muy difícil", "Extremadamente difícil"],
        "contributes_to_total": False,
    },
    "scoring": "sum",
    # Corte para adolescentes de 13 a 17 años: Richardson et al. (2010), Pediatrics 126(6),
    # sensibilidad 89.5 % y especificidad 77.5 % frente a entrevista clínica. El corte 10
    # corresponde a adultos (Kroenke et al., 2001).
    "review_threshold": 11,
    "threshold_reference": "Richardson LP et al. (2010). Evaluation of the PHQ-9 item for detecting major depression among adolescents. Pediatrics 126(6):1117-1123.",
    # PHQ-2 = ítems 1 y 2 del mismo cuestionario (Kroenke, Spitzer y Williams, 2003). Se guarda
    # con cada respuesta; corte orientativo ≥ 3.
    "phq2_items": ["q1", "q2"],
    "phq2_threshold": 3,
    "item_rules": [{"question_id": "q9", "operator": "gte", "value": 1, "reason": "safety_review"}],
    "provenance": "https://aidsetc.org/sites/default/files/resources_files/PHQ-9_Spanish.pdf",
    "source_sha256": SOURCE_SHA256,
    "attribution": "Adapted from the patient health questionnaire (PHQ) screeners (www.phqscreeners.com). Accessed October 6, 2016. See website for additional information and translations.",
    "usage_permission": "AIMS Center: no permission is required to reproduce, translate, display, or distribute PHQ-9. https://aims.uw.edu/resource/phq-9-depression-scale/",
    "notice": "PHQ-9 estándar en español con corte ≥ 11 validado en adolescentes de 13 a 17 años. El puntaje propone revisión profesional, no establece un diagnóstico.",
}
PHQ9["definition_sha256"] = hashlib.sha256(json.dumps(PHQ9, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def phq2(answers):
    """Suma de los ítems 1 y 2 (0–6). None si faltan."""
    try:
        return sum(int(answers[q]) for q in PHQ9["phq2_items"])
    except (KeyError, TypeError, ValueError):
        return None


def ensure_phq9(db):
    form = db.scalar(select(Instrument).where(Instrument.code == PHQ9["instrument_id"]))
    if form is None:
        form = Instrument(code=PHQ9["instrument_id"], definition=PHQ9, enabled=False)
        db.add(form)
        db.flush()
    elif form.definition != PHQ9:
        # La definición vigente (p. ej. el corte ≥ 11) reemplaza a la guardada; las respuestas
        # anteriores conservan su propio definition_sha256.
        form.definition = PHQ9
    return form
