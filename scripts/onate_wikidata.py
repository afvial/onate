#!/usr/bin/env python3
"""
onate_wikidata.py — Identificadores de Wikidata y VIAF para el listPerson.

Dos pasos, con tu revisión en medio:

1) candidatos — busca cada <person> del header en Wikidata y puntúa los
   resultados comparando sus fechas de nacimiento/muerte con las del header.
   Escribe una tabla para revisar:

       python3 scripts/onate_wikidata.py candidatos tei_header.xml \
               --out autoridades/wikidata.tsv

   Columna `elegido`: viene rellena solo cuando un candidato coincide en
   AMBAS fechas y no hay empate. Revísala siempre; corrígela, déjala vacía
   (no asignar) o escribe a mano un Q que hayas encontrado tú.

2) aplicar — inserta <idno type="wikidata"> y <idno type="VIAF"> (este se
   toma de la propiedad P214 del elemento elegido) en cada <person>:

       python3 scripts/onate_wikidata.py aplicar tei_header.xml \
               autoridades/wikidata.tsv

   Edita el header como texto, sin reformatearlo. Si una persona ya tiene
   esos <idno>, los reemplaza. Repetirlo es seguro.

Necesita conexión a internet (API pública de Wikidata). Solo usa la
biblioteca estándar y lxml.
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from lxml import etree

TEI = "http://www.tei-c.org/ns/1.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
API = "https://www.wikidata.org/w/api.php"
UA = "OnateDigitalEdition/1.0 (edición digital De contractibus; uso académico)"
TOL = 2          # años de tolerancia al comparar fechas


# ── API ───────────────────────────────────────────────────────────────────────
# Wikidata limita la frecuencia de peticiones (HTTP 429). Por eso: una pausa
# entre llamadas, espera progresiva respetando Retry-After, y una caché en
# disco para que, si se corta, la siguiente ejecución continúe donde quedó.
PAUSE = 1.0
CACHE_PATH = Path("autoridades/.wikidata_cache.json")
_cache = None


def _load_cache():
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            _cache = {}
    return _cache


def _save_cache():
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")


def api(**params):
    params["format"] = "json"
    url = API + "?" + urllib.parse.urlencode(sorted(params.items()))
    cache = _load_cache()
    if url in cache:
        return cache[url]
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    wait = 5
    for attempt in range(8):
        try:
            time.sleep(PAUSE)
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
            cache[url] = data
            _save_cache()
            return data
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 7:
                raise
            retry = e.headers.get("Retry-After")
            delay = int(retry) if retry and retry.isdigit() else wait
            print(f"  Wikidata pide esperar (HTTP {e.code}): {delay} s…", file=sys.stderr)
            time.sleep(delay)
            wait = min(wait * 2, 120)
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 7:
                raise
            print(f"  error de red ({e}); reintento en {wait} s", file=sys.stderr)
            time.sleep(wait)
            wait = min(wait * 2, 120)


def search_ids(term, limit=8):
    """Búsqueda de texto completo (encuentra también alias latinos), solo humanos."""
    data = api(action="query", list="search", srsearch=f"{term} haswbstatement:P31=Q5",
               srlimit=limit, srnamespace=0)
    return [h["title"] for h in data.get("query", {}).get("search", [])]


def get_entities(ids):
    out = {}
    for i in range(0, len(ids), 40):
        data = api(action="wbgetentities", ids="|".join(ids[i:i + 40]),
                   props="labels|descriptions|claims", languages="es|en|la")
        out.update(data.get("entities", {}))
    return out


def claim_year(ent, prop):
    for c in ent.get("claims", {}).get(prop, []):
        try:
            t = c["mainsnak"]["datavalue"]["value"]["time"]   # "+1535-00-00T…" / "-0384-…"
            return int(t[0] + t[1:].split("-")[0])
        except (KeyError, ValueError):
            continue
    return None


def claim_str(ent, prop):
    for c in ent.get("claims", {}).get(prop, []):
        try:
            return c["mainsnak"]["datavalue"]["value"]
        except KeyError:
            continue
    return ""


def label(ent, field="labels"):
    for lang in ("es", "en", "la"):
        if lang in ent.get(field, {}):
            return ent[field][lang]["value"]
    return ""


# ── Header ────────────────────────────────────────────────────────────────────
def year_of(el, *attrs):
    for a in attrs:
        v = el.get(a) if el is not None else None
        if v:
            m = re.match(r"(-?\d+)", v)
            if m:
                return int(m.group(1))
    return None


def read_persons(header):
    root = etree.parse(str(header)).getroot()
    persons = []
    for p in root.iter(f"{{{TEI}}}person"):
        names = [" ".join("".join(n.itertext()).split()) for n in p.findall(f"{{{TEI}}}persName")]
        b, d = p.find(f"{{{TEI}}}birth"), p.find(f"{{{TEI}}}death")
        persons.append({
            "id": p.get(XML_ID),
            "names": [n for n in names if n],
            "birth": year_of(b, "when", "notBefore", "notAfter"),
            "birth_max": year_of(b, "when", "notAfter", "notBefore"),
            "death": year_of(d, "when", "notBefore", "notAfter"),
            "death_max": year_of(d, "when", "notAfter", "notBefore"),
            "unknown": p.get("cert") == "unknown",
        })
    return persons


def search_terms(person):
    terms = []
    for n in person["names"]:
        terms.append(n)
        words = [w for w in re.split(r"\W+", n) if len(w) >= 4]
        if words:
            terms.append(words[-1])              # 'Azorius', 'Bonacina', 'Navarrus'…
    seen, out = set(), []
    for t in terms:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def score(person, ent):
    s = 0
    by, dy = claim_year(ent, "P569"), claim_year(ent, "P570")
    if person["birth"] is not None and by is not None:
        if person["birth"] - TOL <= by <= person["birth_max"] + TOL:
            s += 2
    if person["death"] is not None and dy is not None:
        if person["death"] - TOL <= dy <= person["death_max"] + TOL:
            s += 2
    return s, by, dy


# ── Paso 1: candidatos ────────────────────────────────────────────────────────
def cmd_candidatos(args):
    persons = read_persons(args.header)
    rows = []
    for p in persons:
        print(f"{p['id']}: {', '.join(p['names'])}")
        if p["unknown"]:
            rows.append([p["id"], " / ".join(p["names"]), "", "", "", "identidad no establecida"])
            continue
        ids = []
        for t in search_terms(p):
            for q in search_ids(t):
                if q not in ids:
                    ids.append(q)
        ents = get_entities(ids) if ids else {}
        scored = []
        for q, ent in ents.items():
            s, by, dy = score(p, ent)
            scored.append((s, q, by, dy, label(ent), label(ent, "descriptions")))
        scored.sort(key=lambda x: -x[0])
        best = [c for c in scored if c[0] == 4]
        elegido = best[0][1] if len(best) == 1 else ""
        cands = " | ".join(
            f"{q} {lab} ({by if by is not None else '?'}–{dy if dy is not None else '?'}) "
            f"{s}pt — {desc[:60]}"
            for s, q, by, dy, lab, desc in scored[:4])
        fechas = f"{p['birth'] if p['birth'] is not None else '?'}–{p['death'] if p['death'] is not None else '?'}"
        nota = "" if elegido else ("empate: decidir" if len(best) > 1 else "sin coincidencia de fechas: revisar")
        rows.append([p["id"], " / ".join(p["names"]), fechas, elegido, cands, nota])
        print(f"   → {elegido or '(sin decidir)'}  {nota}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["pers_id", "nombres", "fechas_header", "elegido", "candidatos", "nota"])
        w.writerows(rows)
    n_ok = sum(1 for r in rows if r[3])
    print(f"\n{n_ok}/{len(rows)} con candidato propuesto → {args.out}  (revísalo antes de aplicar)")


# ── Paso 2: aplicar ───────────────────────────────────────────────────────────
def cmd_aplicar(args):
    chosen = {}
    with args.tsv.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            q = (row.get("elegido") or "").strip()
            if re.fullmatch(r"Q\d+", q):
                chosen[row["pers_id"]] = q
    if not chosen:
        sys.exit("No hay ningún Q en la columna 'elegido'.")

    ents = get_entities(sorted(set(chosen.values())))
    text = args.header.read_text(encoding="utf-8")
    done = 0
    for pid, q in chosen.items():
        viaf = claim_str(ents.get(q, {}), "P214")
        pat = re.compile(r'(<person\b[^>]*xml:id="' + re.escape(pid) + r'"[^>]*>)(.*?)(\n([ \t]*)</person>)', re.S)
        m = pat.search(text)
        if not m:
            print(f"aviso: {pid} no está en el header", file=sys.stderr)
            continue
        body = re.sub(r'\n[ \t]*<idno type="(?:wikidata|VIAF)">[^<]*</idno>', "", m.group(2))
        indent = m.group(4) + "  "
        new = f'\n{indent}<idno type="wikidata">{q}</idno>'
        if viaf:
            new += f'\n{indent}<idno type="VIAF">{viaf}</idno>'
        text = text[:m.start()] + m.group(1) + body + new + m.group(3) + text[m.end():]
        done += 1
        print(f"{pid}: {q}" + (f"  VIAF {viaf}" if viaf else "  (sin VIAF en Wikidata)"))

    etree.fromstring(text.encode("utf-8"))      # comprobar que sigue bien formado
    args.header.write_text(text, encoding="utf-8")
    print(f"\n{done} personas actualizadas en {args.header}")


def main():
    ap = argparse.ArgumentParser(description="Wikidata/VIAF para el listPerson del header.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("candidatos")
    c.add_argument("header", type=Path)
    c.add_argument("--out", type=Path, default=Path("autoridades/wikidata.tsv"))
    a = sub.add_parser("aplicar")
    a.add_argument("header", type=Path)
    a.add_argument("tsv", type=Path)
    args = ap.parse_args()
    {"candidatos": cmd_candidatos, "aplicar": cmd_aplicar}[args.cmd](args)


if __name__ == "__main__":
    main()
