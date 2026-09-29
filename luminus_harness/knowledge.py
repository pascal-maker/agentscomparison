"""Local retrieval over the curated Belgian energy FAQ PDF."""

from __future__ import annotations  # om dit mogelijk te maken dat we een object kunnen doorverwijzen naar zichzelf in de dataclass

import re
from io import BytesIO# is een manier om een soort van txt file te maken in je geheugen
from collections import Counter# dit is een manier om een soort van dictionary te maken die woorden telt
from dataclasses import dataclass# maakt het mogelijk om een class te maken met alleen data
from pathlib import Path# dit is een manier om te werken met paden naar bestanden

from pypdf import PdfReader# dit is een manier om pdf's te lezen


TOKEN_RE = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)#Regular expression die woorden opspoort
URL_RE = re.compile(r"https?://[^\s<>\]\[()]+", re.IGNORECASE)#Regular expression die urls opspoort
STOP_WORDS = {
    "de", "het", "een", "en", "van", "in", "op", "ik", "je", "jij",
    "mijn", "me", "wat", "hoe", "is", "zijn", "kan", "voor", "met",
    "naar", "bij", "of", "dat", "dit", "die", "er", "aan", "als",
    "the", "a", "an", "and", "of", "to", "is", "for", "my", "me",
}


@dataclass(frozen=True)# dataclass is handiger dan een gewone class want deze is speciaal gemaakt om data in op te slaan.
class KnowledgeChunk:
    page: int# pagina nummer in de pdf
    text: str# tekst uit een pagina
    urls: tuple[str, ...]# links naar websites
    source: str = "EnergyAgent kennisbasis"# bron van de pagina's

    def format(self) -> str:# dit is een manier om een string te maken van de pagina
        sources = ", ".join(self.urls) if self.urls else "geen bronlink op deze pagina"# als er geen links zijn, geef "geen bronlink op deze pagina" terug
        return f"[PDF: {self.source}, pagina {self.page}; bronnen: {sources}]\n{self.text}"# dit is een manier om de pagina te formatteren


def load_pdf_chunks(#
    path: Path,
    *,
    chunk_size: int = 1000,# dit is de groote van de tekst in de chunks
    overlap: int = 160,# dit is de overlap tussen de chunks
    source: str = "EnergyAgent kennisbasis",# dit is de bron van de pagina's
) -> list[KnowledgeChunk]:
    reader = PdfReader(str(path), strict=False)# dit is een manier om pdf's te lezen
    return _chunks_from_reader(reader, chunk_size=chunk_size, overlap=overlap, source=source)# dit is een manier om chunks te maken van de pdf's


def load_pdf_chunks_from_bytes(
    pdf_data: bytes,# pdf_data is een variabele die de pdf bevat
    *,
    chunk_size: int = 1000,# dit is de groote van de tekst in de chunks
    overlap: int = 160,# dit is de overlap tussen de chunks
    source: str = "uploaded.pdf",# dit is de bron van de pagina's
) -> list[KnowledgeChunk]:
    """Extract selectable PDF text directly from memory without writing the upload to disk."""
    reader = PdfReader(BytesIO(pdf_data), strict=False)# dit is een manier om pdf's te lezen uit het geheugen
    return _chunks_from_reader(reader, chunk_size=chunk_size, overlap=overlap, source=source)# dit is een manier om chunks te maken van de pdf's


def pdf_page_count(pdf_data: bytes) -> int:# dit is een manier om het aantal pagina's in een pdf te tellen
    return len(PdfReader(BytesIO(pdf_data), strict=False).pages)# dit is een manier om het aantal pagina's in een pdf te tellen


def _chunks_from_reader(# dit is een manier om chunks te maken van de pdf's
    reader: PdfReader,
    *,
    chunk_size: int,# dit is de groote van de tekst in de chunks
    overlap: int,# dit is de overlap tussen de chunks
    source: str,# dit is de bron van de pagina's
) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []# dit is een manier om een lijst van chunks te maken
    for page_number, page in enumerate(reader.pages, start=1):
        text = " ".join((page.extract_text() or "").split())# dit is een manier om tekst uit een pagina te halen
        if not text:
            continue
        urls = tuple(dict.fromkeys(url.rstrip(".,;:") for url in URL_RE.findall(text)))# dit is een manier om urls uit tekst te halen
        start = 0
        while start < len(text):# dit is een manier om chunks te maken van de pdf's
            end = min(len(text), start + chunk_size)# dit is een manier om chunks te maken van de pdf's
            # Prefer a word boundary without making short chunks.
            if end < len(text):
                boundary = text.rfind(" ", start + chunk_size // 2, end)# dit is een manier om chunks te maken van de pdf's
                if boundary > start:
                    end = boundary
            chunks.append(KnowledgeChunk(page_number, text[start:end].strip(), urls, source))# dit is een manier om chunks te maken van de pdf's
            if end == len(text):# dit is een manier om chunks te maken van de pdf's
                break
            start = max(start + 1, end - overlap)# dit is een manier om chunks te maken van de pdf's
    return chunks


def retrieve(chunks: list[KnowledgeChunk], question: str, *, limit: int = 5) -> list[KnowledgeChunk]:# dit is een manier om chunks te maken van de pdf's
    terms = [token.lower() for token in TOKEN_RE.findall(question) if token.lower() not in STOP_WORDS]
    if not terms:# dit is een manier om chunks te maken van de pdf's
        return []
    query = Counter(terms)
    scored: list[tuple[float, int, KnowledgeChunk]] = []# dit is een manier om chunks te maken van de pdf's
    for order, chunk in enumerate(chunks):
        body = Counter(token.lower() for token in TOKEN_RE.findall(chunk.text))# dit is een manier om chunks te maken van de pdf's
        overlap_score = sum(min(count, body[term]) for term, count in query.items())# dit is een manier om chunks te maken van de pdf's
        phrase_bonus = 2.0 if question.strip().lower() in chunk.text.lower() else 0.0# dit is een manier om chunks te maken van de pdf's
        # Repetition is damped so a long page does not win just by being long.
        score = overlap_score / (len(body) ** 0.35 if body else 1) + phrase_bonus
        if score > 0:
            scored.append((score, -order, chunk))
    scored.sort(reverse=True, key=lambda item: (item[0], item[1]))
    return [chunk for _, _, chunk in scored[:limit]]
