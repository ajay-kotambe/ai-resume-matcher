"""AI extraction service: resume text -> structured candidate information.

Primary path: NVIDIA NIM (DeepSeek) with strict JSON output.
Fallback path: deterministic regex heuristics, so the demo still works when no
API key is configured or the provider fails. The method used is always recorded.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.core.errors import AIProviderError, AIResponseError, AITimeoutError
from app.services.nvidia_client import AIResult, get_nvidia_client
from app.utils.text_utils import (
    clean_text,
    find_skills,
    pretty_name,
    education_level,
    extract_emails,
    extract_phones,
    extract_years_of_experience,
    normalize_skills,
    truncate,
)

logger = logging.getLogger(__name__)

RESUME_SYSTEM_PROMPT = """You are an expert technical recruiter's assistant.
Extract structured information from the resume text provided by the user.

ABSOLUTE RULES:
1. NEVER invent, guess, or infer information that is not written in the resume.
2. If a field is not present in the resume, return an empty string "" or an empty list [].
3. Preserve evidence: keep the candidate's own wording, do not paraphrase away detail.
4. In the "evidence" object, quote the exact resume line(s) that support each field.
   If a field has no support, use an empty string.
5. Keep "stated" and "inferred" separate. "stated_skills" are skills the candidate
   explicitly claims. "inferred_skills" are only skills strongly implied by the text
   (for example a project description). If you are unsure, put it in stated_skills
   only if it literally appears, otherwise leave inferred empty.
6. Normalize obvious skill variants to a single canonical spelling, for example:
   "JS"/"JavaScript" -> "JavaScript", "ReactJS"/"React.js" -> "React",
   "Postgres"/"PostgreSQL" -> "PostgreSQL", "Node"/"NodeJS" -> "Node.js",
   "K8s" -> "Kubernetes", "ML" -> "Machine Learning", "REST"/"RESTful APIs" -> "REST API".
   Do NOT merge genuinely different skills.
7. For years_of_experience, use only numbers explicitly written in the resume.
   If none are written, return 0.

Return ONLY a JSON object with exactly these keys:
{
  "name": "",
  "email": "",
  "phone": "",
  "location": "",
  "summary": "",
  "skills": [],
  "stated_skills": [],
  "inferred_skills": [],
  "education": [{"degree": "", "institution": "", "year": "", "detail": ""}],
  "experience": [{"title": "", "company": "", "duration": "", "years": 0, "description": "", "responsibilities": []}],
  "projects": [{"name": "", "technologies": [], "description": ""}],
  "certifications": [{"name": "", "issuer": "", "year": ""}],
  "years_of_experience": 0,
  "evidence": {"name": "", "email": "", "phone": "", "skills": "", "experience": "", "education": ""}
}"""

SKILL_SECTION_RE = re.compile(
    r"(?im)^\s*(?:technical\s+skills|core\s+skills|key\s+skills|skills\s*(?:&|and)\s*tools|"
    r"technologies|tech\s*stack|technical proficiencies|areas of expertise)\s*[:\-]?\s*$"
)
SECTION_RE = re.compile(
    r"(?im)^\s*([A-Z][A-Za-z /&\-]{2,40})\s*[:\-]?\s*$"
)


@dataclass
class ExtractionResult:
    """Structured candidate information + provenance."""

    data: dict
    method: str = "ai"  # ai | heuristic
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    warning: str | None = None
    raw_text: str = ""
    evidence: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def extract_candidate(resume_text: str, *, use_ai: bool = True) -> ExtractionResult:
    """Extract structured candidate information from resume text.

    Tries DeepSeek first; falls back to heuristics when allowed. AI failures
    are surfaced as warnings rather than crashing the whole batch, so one bad
    resume cannot abort a recruiter's upload of 20 files.
    """

    settings = get_settings()
    text = clean_text(resume_text)

    if use_ai and settings.nvidia_configured:
        try:
            data, ai_result = _extract_with_ai(text)
            normalised = _normalise_candidate(data, text)
            return ExtractionResult(
                data=normalised,
                method="ai",
                latency_ms=ai_result.latency_ms,
                prompt_tokens=ai_result.prompt_tokens,
                completion_tokens=ai_result.completion_tokens,
                raw_text=text,
                evidence=normalised.get("evidence", {}),
            )
        except (AITimeoutError, AIProviderError, AIResponseError) as exc:
            logger.warning("AI extraction failed, using heuristic fallback: %s", exc.message)
            if not settings.ALLOW_HEURISTIC_FALLBACK:
                raise
            fallback = extract_candidate(text, use_ai=False)
            fallback.warning = exc.message
            return fallback

    data = _extract_with_heuristics(text)
    return ExtractionResult(
        data=data,
        method="heuristic",
        raw_text=text,
        evidence=data.get("evidence", {}),
    )


# ---------------------------------------------------------------------------
# AI path
# ---------------------------------------------------------------------------
def _extract_with_ai(text: str) -> tuple[dict, AIResult]:
    """Call DeepSeek and validate the structured response."""

    client = get_nvidia_client()
    client.ensure_ready()

    # Long resumes are truncated with a marker so the prompt stays bounded.
    prompt = (
        "Extract the structured candidate information from the resume below.\n"
        "<resume>\n"
        f"{truncate(text, 12000)}\n"
        "</resume>"
    )

    data, result = client.chat_json(
        RESUME_SYSTEM_PROMPT,
        prompt,
        temperature=0.0,
        max_tokens=1000,
    )
    return _validate_ai_payload(data), result


def _validate_ai_payload(data: dict) -> dict:
    """Reject malformed AI output rather than crashing later."""

    if not isinstance(data, dict):
        raise AIResponseError("AI response was not a JSON object.")

    if not any(
        data.get(key) for key in ("name", "email", "skills", "experience", "education")
    ):
        raise AIResponseError(
            "AI response did not contain any recognisable candidate fields.",
            details={"keys": sorted(data.keys())},
        )
    return data


# ---------------------------------------------------------------------------
# Heuristic path (deterministic, offline)
# ---------------------------------------------------------------------------
def _extract_with_heuristics(text: str) -> dict:
    """Regex-based extraction. Used when the AI provider is unavailable."""

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    name = pretty_name(_guess_name(lines))
    emails = extract_emails(text)
    phones = extract_phones(text)

    skills = _guess_skills(text)
    education = _guess_education(lines)
    experience = _guess_experience(lines)
    certifications = _guess_certifications(lines)
    projects = _guess_projects(lines)

    years = extract_years_of_experience(text)
    if not years:
        years = _years_from_date_ranges(text)

    location = _guess_location(lines)

    return {
        "name": name,
        "email": emails[0] if emails else "",
        "phone": phones[0] if phones else "",
        "location": location,
        "summary": truncate(" ".join(lines[:3]), 400),
        "skills": skills,
        "stated_skills": skills,
        "inferred_skills": [],
        "education": education,
        "experience": experience,
        "projects": projects,
        "certifications": certifications,
        "years_of_experience": years,
        "evidence": {
            "name": name,
            "email": emails[0] if emails else "",
            "phone": phones[0] if phones else "",
            "skills": ", ".join(skills[:12]),
            "experience": "; ".join(f"{e.get('title', '')}" for e in experience[:3]),
            "education": "; ".join(e.get("degree", "") for e in education[:3]),
        },
    }


def _guess_name(lines: list[str]) -> str:
    """Pick the most likely candidate name from the first lines."""

    for line in lines[:6]:
        if "@" in line or "linkedin" in line.lower() or line.isdigit():
            continue
        if re.search(r"resume|curriculum|vitae|cv\b", line, re.IGNORECASE):
            continue
        candidate = line.strip(" |-Ã¢â‚¬â€œÃ¢â‚¬â€Ã¢â‚¬Â¢\t")
        # 2-4 capitalised words, no digits.
        if re.fullmatch(r"[A-Z][A-Za-z'.\-]*(?: [A-Z][A-Za-z'.\-]*){1,3}", candidate):
            return candidate
        if re.fullmatch(r"[A-Za-z][A-Za-z'\-]+ [A-Za-z][A-Za-z'\-]+", candidate):
                        w o r d s   =   c a n d i d a t e . s p l i t ( )  
                         i f   a l l ( w [ : 1 ] . i s u p p e r ( )   o r   w . l o w e r ( )   i n   { " v a n " ,   " d e " ,   " b i n " }   f o r   w   i n   w o r d s ) :  
                                 r e t u r n   c a n d i d a t e  
         r e t u r n   " "  
  
  
 d e f   _ g u e s s _ s k i l l s ( t e x t :   s t r )   - >   l i s t [ s t r ] :  
         " " " D e t e c t   s k i l l s   u s i n g   w o r d - b o u n d a r y   m a t c h i n g   ( n o   s u b s t r i n g   f a l s e   p o s i t i v e s ) . " " "  
  
         r e t u r n   n o r m a l i z e _ s k i l l s ( f i n d _ s k i l l s ( t e x t ) )  
  
  
 d e f   _ s e c t i o n _ b o d y ( t e x t :   s t r ,   k e y w o r d s :   l i s t [ s t r ] )   - >   s t r :  
         " " " R e t u r n   t h e   l i n e s   b e l o n g i n g   t o   t h e   f i r s t   s e c t i o n   w h o s e   t i t l e   m a t c h e s . " " "  
  
         l i n e s   =   t e x t . s p l i t ( " \ n " )  
         f o r   i n d e x ,   l i n e   i n   e n u m e r a t e ( l i n e s ) :  
                 t i t l e   =   l i n e . s t r i p ( ) . l o w e r ( ) . r s t r i p ( " : " ) . s t r i p ( )  
                 i f   n o t   t i t l e   o r   l e n ( t i t l e )   >   4 5 :  
                         c o n t i n u e  
                 i f   a n y ( k e y w o r d   i n   t i t l e   f o r   k e y w o r d   i n   k e y w o r d s ) :  
                         b o d y :   l i s t [ s t r ]   =   [ ]  
                         f o r   f o l l o w i n g   i n   l i n e s [ i n d e x   +   1   : ] :  
                                 c a n d i d a t e   =   f o l l o w i n g . s t r i p ( )  
                                 i f   n o t   c a n d i d a t e :  
                                         i f   b o d y :  
                                                 b r e a k  
                                         c o n t i n u e  
                                 #   A   n e w   s e c t i o n   h e a d e r   e n d s   t h e   b l o c k .  
                                 i f   S E C T I O N _ R E . m a t c h ( c a n d i d a t e )   a n d   l e n ( c a n d i d a t e )   <   4 5 :  
                                         b r e a k  
                                 b o d y . a p p e n d ( c a n d i d a t e )  
                                 i f   l e n ( b o d y )   >   2 5 :  
                                         b r e a k  
                         i f   b o d y :  
                                 r e t u r n   " \ n " . j o i n ( b o d y )  
         r e t u r n   " "  
  
  
 d e f   _ s p l i t _ e n t r i e s ( b l o c k :   s t r )   - >   l i s t [ s t r ] :  
         " " " S p l i t   a   s e c t i o n   b o d y   i n t o   i n d i v i d u a l   e n t r i e s . " " "  
  
         e n t r i e s :   l i s t [ s t r ]   =   [ ]  
         f o r   l i n e   i n   b l o c k . s p l i t ( " \ n " ) :  
                 c l e a n   =   l i n e . s t r i p ( "   \ t - * â ¬ ¢ " )  
                 i f   n o t   c l e a n :  
                         c o n t i n u e  
                 #   E n t r i e s   o f t e n   s t a r t   w i t h   a   c a p i t a l   o r   a   b u l l e t - l i k e   t o k e n .  
                 i f   l i n e . s t r i p ( ) . s t a r t s w i t h ( ( " - " ,   " * " ,   " â ¬ ¢ " ) )   o r   l i n e   ! =   l i n e . l s t r i p ( ) :  
                         e n t r i e s . a p p e n d ( c l e a n )  
                 e l i f   n o t   e n t r i e s :  
                         e n t r i e s . a p p e n d ( c l e a n )  
                 e l s e :  
                         e n t r i e s [ - 1 ]   =   f " { e n t r i e s [ - 1 ] }   { c l e a n } "  
         r e t u r n   e n t r i e s  
  
  
 D E G R E E _ R E   =   r e . c o m p i l e (  
         r " \ b ( "  
         r " b \ . ? t e c h | b \ . ? t e c h | b \ . ? s c | b \ . ? s \ . ? c | b \ . ? c o m | b \ . ? b a | b \ . ? a \ b | b \ . ? e \ b | b \ . ? s \ b | b \ . ? m \ b | "  
         r " b a c h e l o r | b \ . ? c a | b \ . ? p h a r m | b \ . ? a r c h | "  
         r " m \ . ? t e c h | m \ . ? s c | m \ . ? s \ b | m s c | m b a | m \ . ? p h a r m | m a s t e r | "  
         r " p h \ . ? d | d o c t o r a t e | d i p l o m a | p o l y t e c h n i c | a s s o c i a t e | "  
         r " h i g h   s c h o o l | s e c o n d a r y | i n t e r m e d i a t e | c l a s s \ s * ( ? : x | x i | x i i ) "  
         r " ) \ b " ,  
         r e . I G N O R E C A S E ,  
 )  
  
  
 d e f   _ g u e s s _ e d u c a t i o n ( l i n e s :   l i s t [ s t r ] )   - >   l i s t [ d i c t ] :  
         b l o c k   =   _ s e c t i o n _ b o d y ( " \ n " . j o i n ( l i n e s ) ,   [ " e d u c a t i o n " ,   " a c a d e m i c " ,   " q u a l i f i c a t i o n " ] )  
         s o u r c e   =   b l o c k   o r   " \ n " . j o i n ( l i n e s )  
         r e s u l t s :   l i s t [ d i c t ]   =   [ ]  
         f o r   l i n e   i n   s o u r c e . s p l i t ( " \ n " ) :  
                 i f   D E G R E E _ R E . s e a r c h ( l i n e ) :  
                         y e a r _ m a t c h   =   r e . s e a r c h ( r " ( 1 9 | 2 0 ) \ d { 2 } " ,   l i n e )  
                         r e s u l t s . a p p e n d (  
                                 {  
                                         " d e g r e e " :   t r u n c a t e ( l i n e . s t r i p ( ) [ : 1 2 0 ] ,   1 2 0 ) ,  
                                         " i n s t i t u t i o n " :   " " ,  
                                         " y e a r " :   y e a r _ m a t c h . g r o u p ( 0 )   i f   y e a r _ m a t c h   e l s e   " " ,  
                                         " d e t a i l " :   l i n e . s t r i p ( ) ,  
                                 }  
                         )  
                 i f   l e n ( r e s u l t s )   > =   5 :  
                         b r e a k  
         r e t u r n   r e s u l t s  
  
  
 d e f   _ y e a r s _ f r o m _ d a t e _ r a n g e s ( t e x t :   s t r )   - >   f l o a t :  
         " " " A p p r o x i m a t e   e x p e r i e n c e   f r o m   e x p l i c i t   m o n t h - y e a r   r a n g e s   ( e . g .   2 0 2 1   -   2 0 2 3 ) . " " "  
  
         i m p o r t   d a t e t i m e   a s   _ d t  
  
         m o n t h s   =   {  
                 " j a n " :   1 ,   " f e b " :   2 ,   " m a r " :   3 ,   " a p r " :   4 ,   " m a y " :   5 ,   " j u n " :   6 ,  
                 " j u l " :   7 ,   " a u g " :   8 ,   " s e p " :   9 ,   " o c t " :   1 0 ,   " n o v " :   1 1 ,   " d e c " :   1 2 ,  
         }  
         n o w   =   _ d t . d a t e t i m e . n o w ( _ d t . t i m e z o n e . u t c )  
         t o t a l   =   0 . 0  
         f o r   m a t c h   i n   r e . f i n d i t e r (  
                 r " ( ? i ) ( j a n | f e b | m a r | a p r | m a y | j u n | j u l | a u g | s e p | o c t | n o v | d e c ) [ a - z ] * \ . ? \ s * ' ? \ s * ( 2 0 \ d { 2 } ) \ s * "  
                 r " ( ? : - | â ¬  | â ¬  | t o ) \ s * ( p r e s e n t | c u r r e n t | n o w | ( j a n | f e b | m a r | a p r | m a y | j u n | j u l | a u g | s e p | o c t | n o v | d e c ) [ a - z ] * \ . ? \ s * ' ? \ s * ( 2 0 \ d { 2 } ) ) " ,  
                 t e x t ,  
         ) :  
                 s t a r t _ m o n t h   =   m o n t h s [ m a t c h . g r o u p ( 1 ) [ : 3 ] . l o w e r ( ) ]  
                 s t a r t _ y e a r   =   i n t ( m a t c h . g r o u p ( 2 ) )  
                 e n d _ t o k e n   =   m a t c h . g r o u p ( 3 ) . s t r i p ( ) . l o w e r ( )  
                 i f   e n d _ t o k e n   i n   { " p r e s e n t " ,   " c u r r e n t " ,   " n o w " } :  
                         e n d _ m o n t h ,   e n d _ y e a r   =   n o w . m o n t h ,   n o w . y e a r  
                 e l s e :  
                         e m   =   r e . m a t c h ( r " ( j a n | f e b | m a r | a p r | m a y | j u n | j u l | a u g | s e p | o c t | n o v | d e c ) " ,   e n d _ t o k e n )  
                         e y   =   r e . s e a r c h ( r " ( 2 0 \ d { 2 } ) " ,   e n d _ t o k e n )  
                         e n d _ m o n t h   =   m o n t h s [ e m . g r o u p ( 1 ) [ : 3 ] . l o w e r ( ) ]   i f   e m   e l s e   s t a r t _ m o n t h  
                         e n d _ y e a r   =   i n t ( e y . g r o u p ( 1 ) )   i f   e y   e l s e   s t a r t _ y e a r  
                 d e l t a   =   ( e n d _ y e a r   -   s t a r t _ y e a r )   *   1 2   +   ( e n d _ m o n t h   -   s t a r t _ m o n t h )  
                 i f   0   <   d e l t a   < =   4 8 0 :  
                         t o t a l   + =   d e l t a   /   1 2  
  
         r e t u r n   r o u n d ( t o t a l ,   2 )  
 