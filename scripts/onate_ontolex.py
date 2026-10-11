#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
onate_ontolex.py
────────────────
Análisis por oración en OntoLex-Lemon + LexInfo + LiLa, a partir del TEI
ensamblado y de las decisiones editoriales ya tomadas.

Uso:
    python3 scripts/onate_ontolex.py output/disp63_bibl_completo.xml

Lee:
    output/disp63_bibl_completo.xml     oraciones, palabras, lemas, @lemmaRef, @msd
    senses/disp63/*.json                sentidos anotados por aparición (Latin WordNet)
    lexico/expresiones_candidatas.yaml  expresiones multipalabra (estado: aceptada / pendiente)
    translations/disp63/*.json          traducción por oración (si existe)

Escribe:
    rdf/disp63_texto.ttl     oraciones (nif:Sentence) y palabras (nif:Word) con morfología
                             LexInfo, lema LiLa y enlace al facsímil
    rdf/disp63_lexico.ttl    léxico: una ontolex:Word por (lema, categoría), formas
                             atestiguadas, sentidos con frac:Attestation, y las
                             expresiones multipalabra ACEPTADAS (decomp:subterm)
    html/disp63/oraciones.js datos de la vista por oración (oracion.html)

Identificador de cada oración: s_p<página><columna>_<n>, con n = orden de la
<s> dentro de su columna (la misma numeración que usan senses/ y translations/).

La morfología de LatinCy (rasgos UD) se traduce a LexInfo 3.0; los rasgos sin
equivalente en LexInfo (Ger, Sup, Prosp, Pqp…) se conservan en onate:ud.
"""
import re
import sys
import json
import glob
import argparse
import datetime
from pathlib import Path
from lxml import etree

TEI = "http://www.tei-c.org/ns/1.0"
T = lambda local: f"{{{TEI}}}{local}"
NORM = {T("reg"), T("expan"), T("corr")}
DIPL = {T("orig"), T("abbr"), T("sic")}

BASE = "https://example.org/onate/"          # URI base provisional: cambiar aquí
COL_PREFIX = "pg_63_"

# ── UD → LexInfo 3.0 (términos comprobados contra lexinfo.owl) ───────────────
POS = {"NOUN": "noun", "PROPN": "properNoun", "VERB": "verb", "AUX": "auxiliary",
       "ADJ": "adjective", "ADV": "adverb", "ADP": "preposition", "PRON": "pronoun",
       "DET": "determiner", "NUM": "numeral", "CCONJ": "coordinatingConjunction",
       "SCONJ": "subordinatingConjunction", "PART": "particle", "INTJ": "interjection",
       "PUNCT": "punctuation", "SYM": "symbol"}
FEAT = {
    "Case":   ("case", {"Nom": "nominativeCase", "Gen": "genitiveCase", "Dat": "dativeCase",
                        "Acc": "accusativeCase", "Abl": "ablativeCase", "Voc": "vocativeCase",
                        "Loc": "locativeCase"}),
    "Gender": ("gender", {"Masc": "masculine", "Fem": "feminine", "Neut": "neuter"}),
    "Number": ("number", {"Sing": "singular", "Plur": "plural"}),
    "Person": ("person", {"1": "firstPerson", "2": "secondPerson", "3": "thirdPerson"}),
    "Tense":  ("tense", {"Pres": "present", "Past": "past", "Fut": "future"}),
    "Mood":   ("mood", {"Ind": "indicative", "Sub": "subjunctive", "Imp": "imperative"}),
    "Voice":  ("voice", {"Act": "activeVoice", "Pass": "passiveVoice"}),
    "Degree": ("degree", {"Pos": "positive", "Cmp": "comparative", "Sup": "superlative"}),
    "Aspect": ("aspect", {"Imp": "imperfective", "Perf": "perfective"}),
    "VerbForm": ("verbFormMood", {"Inf": "infinitive", "Part": "participle", "Gdv": "gerundive"}),
}

PREFIXES = f"""@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:    <http://www.w3.org/2004/02/skos/core#> .
@prefix dct:     <http://purl.org/dc/terms/> .
@prefix ontolex: <http://www.w3.org/ns/lemon/ontolex#> .
@prefix decomp:  <http://www.w3.org/ns/lemon/decomp#> .
@prefix frac:    <http://www.w3.org/ns/lemon/frac#> .
@prefix lexinfo: <http://www.lexinfo.net/ontology/3.0/lexinfo#> .
@prefix lila:    <http://lila-erc.eu/ontologies/lila/> .
@prefix lilalem: <http://lila-erc.eu/data/id/lemma/> .
@prefix lilahyp: <http://lila-erc.eu/data/id/hypolemma/> .
@prefix lwn:     <http://lila-erc.eu/data/lexicalResources/LatinWordNet/id/LexicalConcept/> .
@prefix nif:     <http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#> .
@prefix conll:   <http://ufal.mff.cuni.cz/conll2009-st/task-description.html#> .
@prefix onate:   <{BASE}vocab#> .
@prefix tok:     <{BASE}text/disp63/> .
@prefix lex:     <{BASE}lexicon/> .
"""


# ── lectura del TEI (misma lógica que onate_search_index.py) ─────────────────
def side_text(el, keep):
    if el.tag == T("choice"):
        kids = [b for b in el if isinstance(b.tag, str)]
        br = next((b for b in kids if b.tag in keep), kids[0] if kids else None)
        return side_text(br, keep) if br is not None else ""
    out = [el.text or ""]
    for ch in el:
        if isinstance(ch.tag, str):
            out.append(side_text(ch, keep))
        out.append(ch.tail or "")
    return "".join(out)


def in_branch(el, tags):
    p = el.getparent()
    while p is not None:
        if p.tag in tags:
            return True
        p = p.getparent()
    return False


def token_root(w):
    root, p = w, w.getparent()
    while p is not None and p.tag in (T("choice"), T("reg"), T("expan"), T("corr"),
                                      T("orig"), T("abbr"), T("sic")):
        if p.tag == T("choice"):
            root = p
        p = p.getparent()
    return root


def norm_adv(t):
    t = (t or "").lower().replace("ſ", "s").replace("æ", "ae").replace("ę", "ae")
    t = t.replace("œ", "oe").replace("&", "et")
    return re.sub(r"[.,;:!?()\[\]{}\-\s]", "", t)


def feats(msd):
    return dict(x.split("=", 1) for x in (msd or "").split("|") if "=" in x)


def read_sentences(xml):
    tree = etree.parse(str(xml))
    divs = tree.getroot().findall(f".//{T('div')}[@type='page']")
    seen_n, cols = {}, []
    for d in divs:                                   # columna: @col o posición
        n = d.get("n", "?"); k = seen_n.get(n, 0); seen_n[n] = k + 1
        cols.append(d.get("col") or ("izq", "der", "c3")[k])
    out = []
    for div, col in zip(divs, cols):
        page = div.get("n", "")
        sents = div.findall(f".//{T('s')}")
        s_index = {id(s): i for i, s in enumerate(sents, 1)}
        buckets = {i: [] for i in range(1, len(sents) + 1)}
        line, done, occ_line = "", set(), {}
        for el in div.iter(T("lb"), T("w"), T("pc")):
            if el.tag == T("lb"):
                if not in_branch(el, {T("w")}) and el.get("n"):
                    line = el.get("n")
                continue
            if in_branch(el, DIPL):
                continue
            root = token_root(el)
            if root in done:
                continue
            done.add(root)
            s = next((a for a in el.iterancestors(T("s"))), None)
            if s is None:
                continue
            si = s_index[id(s)]
            if el.tag == T("pc"):
                txt = (el.text or "").strip()
                if txt:
                    buckets[si].append(dict(f=txt, d=txt, l="", ref="", p="PUNCT", m="", ln=line, o=0))
                continue
            f = "".join(side_text(root, NORM).split()).replace("ſ", "s")
            dd = "".join(side_text(root, DIPL).split())
            if not f:
                continue
            key = (line, norm_adv(dd)); o = occ_line.get(key, 0); occ_line[key] = o + 1
            buckets[si].append(dict(f=f, d=dd, l=el.get("lemma", ""), ref=el.get("lemmaRef", ""),
                                    p=el.get("pos", ""), m=el.get("msd", ""), ln=line, o=o,
                                    wp=root.get("wpair") if root.tag == T("choice") else None,
                                    n=el.get("n"), head=el.get("head"), rel=el.get("deprel", "")))
        for i, s in enumerate(sents, 1):
            toks = buckets[i]
            by_n = {t["n"]: k for k, t in enumerate(toks) if t.get("n")}
            for t in toks:
                t.update(pg=page, col=col, sn=i)
                h = t.get("head")
                t["hl"] = None if h is None else (-1 if h == "0" else by_n.get(h))
            out.append(dict(page=page, col=col, n=i, id=f"s_p{page}{col}_{i}",
                            part=s.get("part") or "", toks=toks, el=s,
                            xid=s.get("{http://www.w3.org/XML/1998/namespace}id")))
    return merge_split(out)


def merge_split(sents):
    """
    Une las partes de cada oración partida entre columnas o páginas
    (<s part="I" next="#…"> → <s part="F">) en UNA oración, con el id de la
    primera parte. La parte F queda como remisión ({"cont": id}) sin
    palabras. Cada palabra conserva su página/columna (pg, col, sn) para
    el enlace al facsímil y los sentidos. Las dos mitades de una palabra
    partida (@wpair) se cuentan una sola vez.
    t["hidx"]: índice del núcleo dentro de la oración unida (-1 = raíz).
    """
    by_xid = {s["xid"]: s for s in sents if s["xid"]}
    taken = set()
    for s in sents:
        if s["part"] != "I" or s["xid"] in taken:
            for t in s["toks"]:
                t.setdefault("hidx", t["hl"])
            continue
        chain, cur = [], s
        while cur is not None and cur["xid"] not in taken:
            chain.append(cur); taken.add(cur["xid"])
            nxt = (cur["el"].get("next") or "").lstrip("#")
            cur = by_xid.get(nxt) if nxt else None
        if len(chain) == 1:
            for t in s["toks"]:
                t.setdefault("hidx", t["hl"])
            continue
        merged, seen_wp, ns = [], {}, []
        maps = []                                   # índice local → índice unido
        for part in chain:
            m = {}
            for k, t in enumerate(part["toks"]):
                if t.get("wp") and t["wp"] in seen_wp:   # 2.ª mitad de palabra partida
                    m[k] = seen_wp[t["wp"]]; continue
                m[k] = len(merged)
                if t.get("wp"):
                    seen_wp[t["wp"]] = len(merged)
                merged.append(t)
                if t.get("n"):
                    ns.append(t["n"])
            maps.append(m)
        # ¿numeración continua (onate_sentences.py analizó la oración entera)?
        continuous = len(ns) == len(set(ns))
        if continuous:
            by_n = {t["n"]: k for k, t in enumerate(merged) if t.get("n")}
            for t in merged:
                h = t.get("head")
                t["hidx"] = None if h is None else (-1 if h == "0" else by_n.get(h))
        else:                                       # análisis antiguo, por columna
            for part, m in zip(chain, maps):
                for k, t in enumerate(part["toks"]):
                    if m[k] < len(merged) and merged[m[k]] is t:
                        t["hidx"] = t["hl"] if t["hl"] in (None, -1) else m.get(t["hl"])
        s["toks"] = merged
        s["parts"] = [dict(page=c["page"], col=c["col"], n=c["n"], id=c["id"]) for c in chain]
        for c in chain[1:]:
            c["toks"] = []
            c["cont"] = s["id"]
    for s in sents:
        s.pop("el", None)
    return sents


# ── decisiones editoriales ───────────────────────────────────────────────────
def load_senses(pattern):
    """{(page_col, sentence): [entradas]} desde senses/disp63/*.json"""
    res = {}
    for f in sorted(glob.glob(pattern)):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        pc = d.get("page") or Path(f).stem.replace(COL_PREFIX, "")
        for e in d.get("senses", []):
            res.setdefault((pc, int(e["sentence"])), []).append(e)
    return res


def load_translations(pattern):
    res = {}
    for f in sorted(glob.glob(pattern)):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        pc = Path(f).stem.replace(COL_PREFIX, "")
        for e in d.get("sentences", []):
            if e.get("es"):
                res[(pc, int(e["n"]))] = e["es"]
    return res


def load_mwes(path):
    """Lee lexico/expresiones_candidatas.yaml (formato que escribe onate_candidatos.py)."""
    p = Path(path)
    if not p.exists():
        return []
    items, cur = [], None
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.rstrip().endswith(":"):
            cur = {"name": line.rstrip()[:-1]}; items.append(cur); continue
        m = re.match(r"\s+(\w+):\s*(.*)$", line)
        if m and cur is not None:
            k, v = m.group(1), m.group(2).strip()
            if v.startswith("[") and v.endswith("]"):
                v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
            cur[k] = v
    return [i for i in items if isinstance(i.get("lemas"), list) and len(i["lemas"]) == 2]


CASE_GROUP = {"Nom": "N", "Voc": "N", "Dat": "D", "Abl": "D"}


def agree(a, b):
    fa, fb = feats(a["m"]), feats(b["m"])
    if "Case" not in fa or "Case" not in fb:
        return False
    neut = "Neut" in (fa.get("Gender"), fb.get("Gender"))
    grp = lambda c: "N" if neut and c in ("Nom", "Acc", "Voc") else CASE_GROUP.get(c, c)
    if fa["Case"] != fb["Case"] and grp(fa["Case"]) != grp(fb["Case"]):
        return False
    return not ("Number" in fa and "Number" in fb and fa["Number"] != fb["Number"])


def dep_head(toks, j):
    """Núcleo sintáctico de toks[j] subiendo por las coordinaciones
    (naturale → legale → pretium). Devuelve (índice | None, relación)."""
    t = toks[j]
    rel, h = t.get("rel", ""), t.get("hidx")
    while rel == "conj" and h not in (None, -1) and toks[h]["p"] == t["p"]:
        rel, h = toks[h].get("rel", ""), toks[h].get("hidx")
    if h in (None, -1):
        return None, rel
    return h, rel


def match_mwe(toks, mwe, window=3):
    """Índices (en toks) de las apariciones de la expresión en la oración:
    por dependencias si la oración las tiene; si no, por proximidad."""
    head, dep = mwe["lemas"]
    kind = mwe.get("tipo", "sust+adj")
    if any(t.get("hidx") is not None for t in toks):
        found = []
        for j, t in enumerate(toks):
            if t["l"] != dep:
                continue
            h, rel = dep_head(toks, j)
            if h is None or toks[h]["l"] != head:
                continue
            if kind == "sust+gen":
                ok = rel == "nmod" and feats(t["m"]).get("Case") == "Gen"
            else:
                ok = rel == "amod" or (rel == "conj" and agree(toks[h], t))
            if ok:
                found.append(sorted((h, j)))
        return found
    words = [i for i, t in enumerate(toks) if t["p"] != "PUNCT"]
    found = []
    for a_pos, i in enumerate(words):
        if toks[i]["l"] != head:
            continue
        lo, hi = max(0, a_pos - window), min(len(words), a_pos + window + 1)
        for j in words[lo:hi]:
            if j == i or toks[j]["l"] != dep:
                continue
            if kind == "sust+gen":
                ok = feats(toks[j]["m"]).get("Case") == "Gen"
            else:
                ok = agree(toks[i], toks[j])
            if ok:
                found.append(sorted((i, j)))
        # adjetivo coordinado más allá de la ventana: pretium legale, naturale & conuentionale
        if kind != "sust+gen" and not any(i in f for f in found):
            k = a_pos + 1
            while k < len(words) and k - a_pos <= 6 and toks[words[k]]["p"] in ("ADJ", "CCONJ"):
                if toks[words[k]]["l"] == dep:
                    found.append(sorted((i, words[k]))); break
                k += 1
    return found


# ── RDF ──────────────────────────────────────────────────────────────────────
def lit(s, lang=None):
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{s}"' + (f"@{lang}" if lang else "")


def safe(s):
    s = re.sub(r"[^A-Za-z0-9_-]", "_", s.replace("ſ", "s"))
    return s or "x"


def lemma_uri(ref):
    if ref.startswith("lila:"):
        return "lilalem:" + ref[5:]
    if ref.startswith("lilah:"):
        return "lilahyp:" + ref[6:]
    return None


def main():
    ap = argparse.ArgumentParser(description="Análisis por oración: OntoLex + LexInfo + LiLa")
    ap.add_argument("xml")
    ap.add_argument("--senses", default="senses/disp63/*.json")
    ap.add_argument("--translations", default="translations/disp63/*.json")
    ap.add_argument("--mwe", default="lexico/expresiones_candidatas.yaml")
    ap.add_argument("--rdf-dir", default="rdf")
    ap.add_argument("--js", default="html/disp63/oraciones.js")
    ap.add_argument("--no-validate", action="store_true", help="no validar el Turtle con rdflib")
    a = ap.parse_args()

    sents = read_sentences(a.xml)
    senses = load_senses(a.senses)
    trans = load_translations(a.translations)
    mwes = load_mwes(a.mwe)

    texto, lexico = [PREFIXES], [PREFIXES]
    entries = {}            # (lemma, pos) → {"ref", "forms", "senses": {sid: {...}}}
    mwe_att = {}            # mwe name → [token uris]
    view = []
    n_tok = n_sense = n_mwe_occ = 0
    n_deps_total = [0]
    unmatched = []

    for s in sents:
        if s.get("cont"):          # parte final de una oración partida: remite a la inicial
            view.append(dict(id=s["id"], p=s["page"], c=s["col"], n=s["n"], part="F",
                             cont=s["cont"], tr="", t=[], mwe=[]))
            continue
        parts = s.get("parts") or [dict(page=s["page"], col=s["col"], n=s["n"], id=s["id"])]
        part_ix = {(x["page"], x["col"], x["n"]): k for k, x in enumerate(parts)}
        sid, toks = s["id"], s["toks"]
        words = [t for t in toks if t["p"] != "PUNCT"]
        if not words:
            continue
        # aparición de cada forma diplomática dentro de cada parte (para senses/,
        # que numera las oraciones por columna)
        occ_sent, cnt = [], {}
        for t in toks:
            k = (t["pg"], t["col"], t["sn"], norm_adv(t["d"])); cnt[k] = cnt.get(k, 0) + 1; occ_sent.append(cnt[k])
        text = " ".join(t["f"] for t in toks)
        text = re.sub(r" ([.,;:?!)])", r"\1", text)
        su = f"tok:{sid}"
        trs = [trans.get((f'{x["page"]}_{x["col"]}', x["n"])) for x in parts]
        tr = " ".join(dict.fromkeys(x for x in trs if x))
        texto.append(f"{su}\n    a nif:Sentence ;\n    nif:anchorOf {lit(text, 'la')} ;\n"
                     + "".join(f"    dct:isPartOf tok:p{x['page']}{x['col']} ;\n" for x in parts)
                     + f"    onate:n {s['n']} ;"
                     + "".join(f"\n    onate:continuedIn tok:{x['id']} ;" for x in parts[1:])
                     + (f"\n    onate:translation {lit(tr, 'es')} ;" if tr else "")
                     + f"\n    nif:firstWord {su}_t1 .\n")

        # sentidos anotados en esta oración
        sense_of = {}
        for x in parts:
            inpart = lambda t: (t["pg"], t["col"], t["sn"]) == (x["page"], x["col"], x["n"])
            for e in senses.get((f'{x["page"]}_{x["col"]}', x["n"]), []):
                want, occ = norm_adv(e.get("text", "")), int(e.get("occurrence", 1))
                hit = next((i for i, t in enumerate(toks) if inpart(t) and norm_adv(t["d"]) == want and occ_sent[i] == occ), None)
                if hit is None:
                    hit = next((i for i, t in enumerate(toks) if inpart(t) and norm_adv(t["f"]) == want and occ_sent[i] == occ), None)
                if hit is None:
                    unmatched.append(f'{x["id"]}: «{e.get("text")}» ({occ})'); continue
                sense_of[hit] = e

        # expresiones multipalabra
        s_mwes = []
        for m in mwes:
            for pair in match_mwe(toks, m):
                s_mwes.append(dict(name=m["name"], forma=m.get("forma", ""), estado=m.get("estado", "pendiente"),
                                   idx=pair, tipo=m.get("tipo", "")))

        # dependencias (onate_nlp.py / onate_sentences.py: @n, @head, @deprel)
        head_of = {}
        for i, t in enumerate(toks):
            if t.get("head") is None:
                continue
            head_of[i] = (t.get("hidx"), t.get("rel", ""))
        n_dep = 0

        vt = []
        for i, t in enumerate(toks):
            k = i + 1
            tu = f"{su}_t{k}"
            facs = f'{COL_PREFIX}{t["pg"]}_{t["col"]}:{t["ln"]}:{t["d"]}:{t["o"]}'
            pk = part_ix.get((t["pg"], t["col"], t["sn"]), 0)
            if t["p"] == "PUNCT":
                vt.append([t["f"], t["d"], "", "", "PUNCT", "", t["ln"], t["o"], None, None, "", pk])
                continue
            n_tok += 1
            fe = feats(t["m"])
            lines = [f"{tu}", "    a nif:Word ;", f"    nif:anchorOf {lit(t['f'], 'la')} ;"]
            if t["d"] != t["f"]:
                lines.append(f"    onate:diplomatic {lit(t['d'], 'la')} ;")
            lines.append(f"    nif:sentence {su} ;")
            nxt = next((j + 1 for j in range(i + 1, len(toks)) if toks[j]["p"] != "PUNCT"), None)
            if nxt:
                lines.append(f"    nif:nextWord {su}_t{nxt} ;")
            if t["p"] in POS:
                lines.append(f"    lexinfo:partOfSpeech lexinfo:{POS[t['p']]} ;")
            rest = []
            for kf, v in fe.items():
                if kf in FEAT and v in FEAT[kf][1]:
                    lines.append(f"    lexinfo:{FEAT[kf][0]} lexinfo:{FEAT[kf][1][v]} ;")
                else:
                    rest.append(f"{kf}={v}")
            if t["m"]:
                lines.append(f"    onate:ud {lit(t['m'])} ;")
            lu = lemma_uri(t["ref"])
            if lu:
                lines.append(f"    lila:hasLemma {lu} ;")
            if t["l"]:
                eid = f"{safe(t['l'])}_{t['p'] or 'X'}"
                lines.append(f"    onate:lexicalEntry lex:{eid} ;")
                e = entries.setdefault((t["l"], t["p"]), {"ref": t["ref"], "forms": set(), "senses": {}, "id": eid, "n": 0})
                e["forms"].add(t["f"].lower()); e["n"] += 1
                if not e["ref"] and t["ref"]:
                    e["ref"] = t["ref"]
            if i in head_of:
                hi, rel = head_of[i]
                if hi is not None and hi >= 0:
                    lines.append(f"    conll:HEAD {su}_t{hi + 1} ;")
                if rel:
                    lines.append(f"    conll:EDGE {lit(rel)} ;")
                n_dep += 1
            lines.append(f"    onate:line {t['ln'] or 0} ;")
            lines.append(f"    rdfs:seeAlso <{BASE}html/disp63/disp63_facs.html#{facs.replace(':', '%3A')}> .")
            texto.append("\n".join(lines) + "\n")

            sense = None
            if i in sense_of and t["l"]:
                e = sense_of[i]
                syn = e.get("synset") or (e.get("lila_uri", "").rsplit("/", 1)[-1] if e.get("lila_uri") else "")
                if syn:
                    se = entries[(t["l"], t["p"])]["senses"].setdefault(syn, {"def": e.get("lila_def", ""), "gloss": e.get("gloss_en", ""), "att": [], "notes": []})
                    se["att"].append(tu)
                    if e.get("note"):
                        se["notes"].append(e["note"])
                    n_sense += 1
                    sense = dict(syn=syn, gloss=e.get("gloss_en", ""), def_=e.get("lila_def", ""), note=e.get("note", ""), es=e.get("match_text", ""))
            hd = head_of.get(i)
            vt.append([t["f"], t["d"], t["l"], t["ref"], t["p"], t["m"], t["ln"], t["o"], sense,
                       (hd[0] if hd and hd[0] is not None else None), (hd[1] if hd else ""), pk])

        for m in s_mwes:
            if m["estado"] == "aceptada":
                mwe_att.setdefault(m["name"], {"forma": m["forma"], "att": []})["att"].append([f"{su}_t{x + 1}" for x in m["idx"]])
                n_mwe_occ += 1
        n_deps_total[0] += n_dep
        view.append(dict(id=sid, p=s["page"], c=s["col"], n=s["n"], part="I" if len(parts) > 1 else "",
                         parts=[[x["page"], x["col"], x["n"], x["id"]] for x in parts], tr=tr or "",
                         t=vt, mwe=[[m["name"], m["forma"], m["estado"], m["idx"]] for m in s_mwes]))

    # léxico
    for (l, p), e in sorted(entries.items()):
        lines = [f"lex:{e['id']}", "    a ontolex:Word ;", f"    rdfs:label {lit(l, 'la')} ;"]
        if p in POS:
            lines.append(f"    lexinfo:partOfSpeech lexinfo:{POS[p]} ;")
        lu = lemma_uri(e["ref"])
        if lu:
            lines.append(f"    ontolex:canonicalForm {lu} ;")
        forms = sorted(e["forms"])
        lines.append("    ontolex:otherForm " + " ,\n        ".join(
            f"[ a ontolex:Form ; ontolex:writtenRep {lit(f, 'la')} ]" for f in forms) + " ;")
        for syn in sorted(e["senses"]):
            lines.append(f"    ontolex:sense lex:{e['id']}_{safe(syn)} ;")
        lines[-1] = lines[-1][:-2] + " ."
        lexico.append("\n".join(lines) + "\n")
        for syn, se in sorted(e["senses"].items()):
            sl = [f"lex:{e['id']}_{safe(syn)}", "    a ontolex:LexicalSense ;",
                  f"    ontolex:isLexicalizedSenseOf lwn:{syn} ;"]
            if se["gloss"]:
                sl.append(f"    rdfs:label {lit(se['gloss'], 'en')} ;")
            if se["def"]:
                sl.append(f"    skos:definition {lit(se['def'], 'en')} ;")
            for nt in dict.fromkeys(se["notes"]):
                sl.append(f"    skos:editorialNote {lit(nt, 'es')} ;")
            sl.append("    frac:attestation " + " ,\n        ".join(
                f"[ a frac:Attestation ; frac:locus {x} ]" for x in se["att"]) + " .")
            lexico.append("\n".join(sl) + "\n")
    # para decomp:subterm: la entrada más frecuente de cada lema (LatinCy a veces
    # etiqueta el mismo lema con dos categorías)
    lemma_ids = {}
    for (l, p), e in sorted(entries.items(), key=lambda kv: kv[1]["n"]):
        lemma_ids[l] = e["id"]
    for name, m in sorted(mwe_att.items()):
        l1, l2 = name.split("_", 1)
        subs = [f"lex:{lemma_ids[x]}" for x in (l1, l2) if x in lemma_ids]
        ml = [f"lex:mwe_{safe(name)}", "    a ontolex:MultiwordExpression ;",
              f"    ontolex:canonicalForm [ a ontolex:Form ; ontolex:writtenRep {lit(m['forma'], 'la')} ] ;"]
        if subs:
            ml.append(f"    decomp:subterm {' , '.join(subs)} ;")
        ml.append("    frac:attestation " + " ,\n        ".join(
            f"[ a frac:Attestation ; frac:locus {' , '.join(x)} ]" for x in m["att"]) + " .")
        lexico.append("\n".join(ml) + "\n")

    rd = Path(a.rdf_dir); rd.mkdir(parents=True, exist_ok=True)
    (rd / "disp63_texto.ttl").write_text("\n".join(texto), encoding="utf-8")
    (rd / "disp63_lexico.ttl").write_text("\n".join(lexico), encoding="utf-8")
    js = Path(a.js); js.parent.mkdir(parents=True, exist_ok=True)
    data = dict(generated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), colPrefix=COL_PREFIX,
                sentences=view)
    js.write_text("window.ONATE_SENT = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n",
                  encoding="utf-8")

    msg = (f"✓ {sum(1 for v in view if not v.get('cont'))} oraciones ({sum(1 for v in view if len(v.get('parts') or []) > 1)} partidas entre columnas, unidas), {n_tok} palabras, {len(entries)} entradas léxicas, "
           f"{n_sense} sentidos anotados, {n_mwe_occ} apariciones de expresiones aceptadas, "
           f"{n_deps_total[0]} palabras con dependencias")
    if not n_deps_total[0]:
        msg += ("\n  (sin dependencias: el TEI no tiene @head/@deprel; vuelve a pasar el paso nlp "
                "con la nueva versión de onate_nlp.py)")
    if not a.no_validate:
        try:
            import rdflib
            for f in ("disp63_texto.ttl", "disp63_lexico.ttl"):
                g = rdflib.Graph(); g.parse(rd / f, format="turtle")
                msg += f"\n  {rd / f}: {len(g)} tripletas (Turtle válido)"
        except ImportError:
            msg += "\n  (rdflib no instalado: sin validar)"
    print(msg, file=sys.stderr)
    print(f"  → {js}", file=sys.stderr)
    if unmatched:
        print(f"  ⚠ {len(unmatched)} sentido(s) sin palabra correspondiente:", file=sys.stderr)
        for u in unmatched[:10]:
            print(f"    {u}", file=sys.stderr)


if __name__ == "__main__":
    main()
