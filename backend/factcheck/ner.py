import logging
import re

logger = logging.getLogger(__name__)

_NLP = None
_LOAD_FAILED = False

CLAIM_ENTITY_TYPES = {"PERSON", "ORG", "GPE", "LOC", "DATE", "EVENT", "MONEY", "PERCENT", "QUANTITY", "CARDINAL"}


def _get_nlp():
    global _NLP, _LOAD_FAILED
    if _NLP is not None or _LOAD_FAILED:
        return _NLP
    try:
        import spacy
        try:
            _NLP = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
        except OSError:
            from spacy.cli import download
            download("en_core_web_sm")
            _NLP = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
        if "sentencizer" not in _NLP.pipe_names and "parser" not in _NLP.pipe_names:
            _NLP.add_pipe("sentencizer")
    except Exception as exc:
        logger.warning("spaCy unavailable, falling back to regex: %s", exc)
        _LOAD_FAILED = True
        _NLP = None
    return _NLP


def extract_claim_sentences(text: str, max_claims: int = 8) -> list[str]:
    if not text or not text.strip():
        return []

    nlp = _get_nlp()
    if nlp is None:
        return _regex_split(text, max_claims)

    doc = nlp(text[:5000])
    candidates = []
    for sent in doc.sents:
        sent_text = sent.text.strip()
        if len(sent_text) < 20 or len(sent_text) > 500:
            continue
        ents = [e for e in sent.ents if e.label_ in CLAIM_ENTITY_TYPES]
        has_number = any(t.like_num for t in sent)
        if ents or has_number:
            candidates.append((sent_text, len(ents) + (1 if has_number else 0)))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return [c[0] for c in candidates[:max_claims]]


def _regex_split(text: str, max_claims: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if 20 < len(s.strip()) < 500][:max_claims]


def extract_entities(text: str) -> list[dict]:
    nlp = _get_nlp()
    if nlp is None:
        return []
    doc = nlp(text[:5000])
    return [
        {"text": ent.text, "type": ent.label_, "start": ent.start_char, "end": ent.end_char}
        for ent in doc.ents
        if ent.label_ in CLAIM_ENTITY_TYPES
    ]
