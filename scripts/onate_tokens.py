#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
onate_tokens.py
───────────────
Tablas léxicas, tokenizador y extracción PAGE XML para el proyecto Oñate.
Importado por onate_bibl, onate_tei y onate_page2tei.
"""

import re
from pathlib import Path
from lxml import etree

PAGE_NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15"
TEI_NS  = "http://www.tei-c.org/ns/1.0"
XI_NS   = "http://www.w3.org/2001/XInclude"

ABBREV_WITH_DOT = {
    # Referencias bibliográficas estructurales
    "cap.", "lib.", "q.", "n.", "nu.", "art.", "ar.", "disp.", "disput.",
    "tract.", "tit.", "dub.", "punct.", "sect.", "par.", "prop.",
    "concl.", "coroll.", "obs.", "def.", "theor.", "prol.",
    # Partes de obra
    "p.", "pp.", "tom.", "vol.", "pars.", "part.",
    "var.", "verb.", "sum.", "inst.", "instit.", "§.",
    # Abreviaturas de autores clásicos y patrísticos
    "Arist.", "Aristot.", "Aug.", "August.", "Th.", "Thom.",
    "Cic.", "Plat.", "Plut.", "Ambr.", "Hier.", "Greg.",
    "Ign.", "Tert.", "Orig.", "Bas.", "Chrys.",
    # Abreviaturas de autores frecuentes en Oñate
    "D.", "S.", "B.", "P.", "R.", "M.", "V.", "Fr.",
    "Nau.", "Mol.", "Molin.", "Less.", "Lessius.",
    "Sal.", "Salas.", "Salon.", "Couar.", "Couarr.",
    "Bonac.", "Bonacin.", "Regin.", "Reginald.",
    "Azor.", "Tolet.", "Sot.", "Sotus.", "Med.", "Medin.",
    "Filliuc.", "Filliucc.", "Gabr.", "Manuel.", "Leff.",
    "Anton.", "Sylu.", "Conrad.",
    "Faustus.", "Faust.", "Valent.", "Aragon.", "Caiet.",
    "Bannes.", "Bann.", "Mai.", "Maior.",
    "Ledes.", "Ledesm.", "Ioan.", "Io.",
    # Obras y colecciones
    "ethic.", "instit.", "mor.", "restit.", "restitut.",
    "iust.", "contract.", "contractib.", "empt.", "emptione.",
    "peccat.", "pecca.", "septem.", "trinitate.",
    "c.",   # caput (forma breve)
    "princ.", "conc.", "controu.", "controuers.",
    "diffieul.", "difficul.", "diffic.", "ca.", "2n.",
    # Divisiones internas de obra (van dentro de bibl)
    "princ.", "conc.", "controu.", "controuers.",
    "diffieul.", "difficul.", "diffic.", "ca.", "2n.",
    "opusc.", "fect.",   # opusculum, sectio (grafía alt.)
    "Rebel.", "Nauar.",  # Rebellus, Navarrus
    # Términos jurídico-escolásticos abreviados
    "reip.", "repub.", "rep.", "ff.", "seqq.", "iun.", "contr.",
    # Fuentes del derecho romano y canónico
    "l.",        # lex
    "C.",        # Codex Iustinianus
    "reg.",      # regula (iuris)
    # Títulos jurídicos abreviados (Corpus Iuris Civilis)
    "mand.",     # de mandato / mandati
    "mandata.",  # in re mandata (incipit C. 4.35.1)
    "Trebel.",   # ad SC Trebellianum
    "Falcid.",   # ad legem Falcidiam
    "Aquil.",    # ad legem Aquiliam
    "Falc.",     # ad legem Falcidiam (forma breve)
    "restit.",   # de restitutione (ya en BIBL_INTRA, aquí como abbrev)
    "glos.",     # glosa
    "fin.",      # in fine
    "ma.",       # mandati (forma ultracorta)
}

# Expansiones canónicas de abreviaturas conocidas (nominativo)
# Las que no están aquí quedan vacías para completar en Emacs
ABBREV_EXPAN = {
    # Referencias estructurales
    "cap.":       "capitulo",
    "lib.":       "libro",
    "n.":         "numero",
    "nu.":        "numero",
    "art.":       "articulo",
    "ar.":        "articulo",
    "artic.":     "articulo",
    "d.":         "distinctio",
    "disp.":      "disputatio",
    "disput.":    "disputatio",
    "tract.":     "tractatus",
    "tit.":       "titulo",
    "dub.":       "dubium",
    "punct.":     "punctum",
    "sect.":      "sectio",
    "par.":       "paragraphus",
    "q.":         "quaestio",
    "prop.":      "propositio",
    "concl.":     "conclusio",
    "coroll.":    "corollarium",
    "obs.":       "observatio",
    "def.":       "definitio",
    "theor.":     "theorema",
    "prol.":      "prologus",
    "§.":         "",
    # Partes de obra
    "p.":         "pars",
    "pp.":        "partes",
    "tom.":       "tomus",
    "vol.":       "volumen",
    "pars.":      "pars",
    "part.":      "pars",
    "inst.":      "institutio",
    "instit.":    "institutio",
    "sum.":       "summa",
    "var.":       "variarum",
    "verb.":      "verbo",
    # Términos jurídico-escolásticos
    "reip.":      "reipublicae",
    "repub.":     "republica",
    "rep.":       "republica", 
    "ff.":        "Digesta",
    "l.":         "lex",
    "C.":         "Codex Iustinianus",
    "reg.":       "regula",
    # Títulos jurídicos
    "mand.":      "de mandato",
    "mandata.":   "in re mandata",
    "Trebel.":    "ad senatus consultum Trebellianum",
    "Falcid.":    "ad legem Falcidiam",
    "Aquil.":     "ad legem Aquiliam",
    "Falc.":      "ad legem Falcidiam",
    "glos.":      "glosa",
    "fin.":       "in fine",
    "ma.":        "mandati",
    "seqq.":      "sequentibus",
    "iun.":       "iuncto",
    "contr.":     "controversia",
    "controu.":   "controversia",
    "controuers.": "controversia",
    "princ.":     "principio",
    "conc.":      "conclusio",
    "diffieul.":  "difficultas",
    "difficul.":  "difficultas",
    "diffic.":    "difficultas",
    "ca.":        "caput",
    "c.":         "caput",
    "pecca.":     "peccatis",
    "Ioan.":      "Ioannes",
    "2n.":        "secundo",
    "opusc.":     "opusculum",
    "fect.":      "sectio",
    "Rebel.":     "Rebellus",
    "Nauar.":     "Navarrus",
    "Ledes.":     "Ledesma",
    # Autores clásicos y patrísticos
    "D.":         "",
    "Arist.":     "Aristoteles",
    "Aristot.":   "Aristoteles",
    "Aug.":       "Augustinus",
    "August.":    "Augustinus",
    "Th.":        "Thomas",
    "Thom.":      "Thomas",
    "Tho.":       "Thomas",
    "Cic.":       "Cicero",
    "Plat.":      "Plato",
    "Ambr.":      "Ambrosius",
    "Hier.":      "Hieronymus",
    "Greg.":      "Gregorius",
    "Orig.":      "Origenes",
    "Bas.":       "Basilius",
    # Autores escolásticos frecuentes en Oñate
    "Nau.":       "Navarrus",
    "Mol.":       "Molina",
    "Molin.":     "Molina",
    "Less.":      "Lessius",
    "Sal.":       "Salas",
    "Salon.":     "Salon",
    "Couar.":     "Covarrubias",
    "Couarr.":    "Covarrubias",
    "Bonac.":     "Bonacina",
    "Bonacin.":   "Bonacina",
    "Regin.":     "Reginaldus",
    "Reginald.":  "Reginaldus",
    "Azor.":      "Azorius",
    "Tolet.":     "Toletanus",
    "Sot.":       "Sotus",
    "Sotus.":     "Sotus",
    "Med.":       "Medina",
    "Mai.":       "Maior",
    "Maior.":     "Maior",
    "Medin.":     "Medina",
    "Filliuc.":   "Filliucius",
    "Filliucc.":  "Filliucius",
    "Gabr.":      "Gabriel",
    "Anton.":     "Antoninus",
    "Sylu.":      "Sylvester",
    "Conrad.":    "Conradus",
    "Faust.":     "Faustus",
    "Faustus.":   "Faustus",
    "Valent.":    "Valentinus",
    "Aragon.":    "Aragonius",
    "Caiet.":     "Caietanus",
    "Bannes.":    "Bannez",
    "Bann.":      "Bannez",
    "Lessius.":   "Lessius",
    "Leff.":      "Lessius",
    "Manuel.":    "Manuel",
    "Gabr.":      "Gabriel",
    # Obras
    "ethic.":     "Ethica",
    "mor.":       "moralis",
    "restit.":    "restitutione",
    "restitut.":  "restitutione",
    "iust.":      "iustitia",
    "contract.":  "contractibus",
    "contractib.": "contractibus",
    "empt.":      "emptione",
    "emptione.":  "emptione",
    "peccat.":    "peccatis",
    "septem.":    "septem",
}


# Abreviaturas de autor que inician un nuevo <bibl>
AUTHOR_ABBREVS = {
    # Clásicos y patrísticos
    "Arist.", "Aristot.", "Aug.", "August.", "Th.", "Thom.",
    "Cic.", "Plat.", "Plut.", "Ambr.", "Hier.", "Greg.",
    "Ign.", "Tert.", "Orig.", "Bas.", "Chrys.", "D.",
    # Escolásticos
    "Nau.", "Mol.", "Molin.", "Less.", "Lessius.", "Leff.",
    "Sal.", "Salas.", "Salon.", "Couar.", "Couarr.",
    "Bonac.", "Bonacin.", "Regin.", "Reginald.",
    "Azor.", "Tolet.", "Sot.", "Sotus.", "Med.", "Medin.",
    "Filliuc.", "Filliucc.", "Gabr.", "Manuel.",
    "Anton.", "Sylu.", "Conrad.",
    "Faust.", "Faustus.", "Valent.", "Aragon.", "Caiet.",
    "Bannes.", "Bann.", "S.", "Mai.", "Maior.",
    "Ledes.", "Ledesm.", "Ioan.", "Io.",
    "Rebel.", "Nauar.",
}

# Tokens que van DENTRO de un <bibl> (referencias estructurales)
BIBL_INTRA = {
    "cap.", "lib.", "q.", "n.", "nu.", "art.", "ar.", "disp.", "disput.",
    "tract.", "tit.", "dub.", "punct.", "sect.", "par.", "prop.",
    "concl.", "coroll.", "obs.", "def.", "theor.", "prol.",
    "p.", "pp.", "tom.", "vol.", "pars.", "part.",
    "var.", "verb.", "sum.", "inst.", "instit.",
    "ethic.", "mor.", "restit.", "restitut.",
    "iust.", "contract.", "contractib.", "empt.", "emptione.",
    "peccat.", "pecca.", "septem.", "trinitate.",
    "c.",
    "reip.", "repub.", "ff.", "seqq.", "iun.", "contr.",
    # Preposiciones intra-bibl (forman parte del título de la obra)
    "de", "ad", "in", "ibi",
    # Nota: "ex" se omite — en el corpus aparece como separador (ex parte)
    # Divisiones internas de obra
    "princ.", "conc.", "controu.", "controuers.",
    "diffieul.", "difficul.", "diffic.", "ca.", "2n.",
}

# Tokens que van ENTRE <bibl> dentro del <hi> (conectores)
BIBL_INTER = {
    "ibi",
}

# Secuencias de dos tokens que actúan como conectores entre <bibl>.
# Cada entrada es una tupla (text1, text2).
BIBL_INTER_2 = {
    ("ex", "parte"),
}

# Prefijos honoríficos que preceden al nombre del autor.
# "D. Th." = Divus Thomas, "S. Aug." = Sanctus Augustinus, etc.
# Cuando el último token del bibl en construcción es un honorífico,
# el siguiente token de autor NO debe cerrar ese bibl ni abrir uno nuevo.
HONORIFIC_PREFIXES = {"D.", "S.", "B.", "V.", "P.", "Fr.", "R.", "M.", "Ioan.", "Io."}

# Nombres completos (sin punto) que actúan como inicio de <bibl>.
# Incluye word_lb (palabras partidas por guión de línea).
AUTHOR_FULL_NAMES = {
    "Reginaldus", "Bannes", "Aragon", "Salon", "Lessius", "Salas",
    "Molina", "Navarrus", "Covarrubias", "Bonacina", "Filliucius",
    "Medina", "Azorius", "Antoninus", "Sylvester", "Conradus",
    "Sotus", "Soto", "Valentinus", "Caietanus", "Scotus", "Maior",
    "Toletus", "Gabriel", "Faustus", "Bannez", "Aragonius",
    "Rebellus", "Leffius",
}

PC_TYPES = {
    ",": "comma", ";": "semicolon", ":": "colon",
    "?": "question", "!": "exclamation",
    "[": "bracket", "]": "bracket",
    "(": "bracket", ")": "bracket",
}

ORIG_REG = {
    "vt": "ut", "vsu": "usu", "vſu": "usu",
    "eft": "est", "eſt": "est",
    "ſunt": "sunt", "ſed": "sed", "ſi": "si", "ſub": "sub",
    "iuſtitiam": "iustitiam", "iuſtitiae": "iustitiae",
    "indiuiſibili": "indiuisibili",
}

# Macrones que representan letras abreviadas
MACRON_MAP = {
    "ā": "am", "ē": "em", "ī": "im", "ō": "om", "ū": "um",
    "Ā": "Am", "Ē": "Em", "Ī": "Im", "Ō": "Om", "Ū": "Um",
}

# Grafías con s larga frecuentes en impresos latinos del s. XVII
# La clave es la forma normalizada (como la devuelve Noscemus),
# el valor es la forma diplomática con ſ.
# Regla general: ſ aparece en posición inicial y medial, nunca final.
LONG_S = {
    # formas de sum/esse
    "est":              "eſt",
    "esse":             "eſſe",
    "sunt":             "ſunt",
    "sit":              "ſit",
    "sint":             "ſint",
    "sim":              "ſim",
    "sis":              "ſis",
    "esset":            "eſſet",
    "essent":           "eſſent",
    "esse":             "eſſe",
    # inesse / insunt
    "insunt":           "inſunt",
    "inest":            "ineſt",
    "inesse":           "ineſſe",
    # conjunciones/adverbios frecuentes
    "sed":              "ſed",
    "si":               "ſi",
    "sic":              "ſic",
    "sub":              "ſub",
    "sine":             "ſine",
    "sive":             "ſiue",
    "sibi":             "ſibi",
    "seu":              "ſeu",
    "satis":            "ſatis",
    "semper":           "ſemper",
    "solum":            "ſolum",
    "solus":            "ſolus",
    "sola":             "ſola",
    "solo":             "ſolo",
    "super":            "ſuper",
    # términos jurídico-escolásticos de Oñate
    "secundum":         "ſecundum",
    "sequendum":        "ſequendum",
    "secundam":         "ſecundam",
    "secundo":          "ſecundo",
    "secundò":          "ſecundò",
    "sequi":            "ſequi", 
    "status":           "ſtatus",
    "statuerc":         "ſtatuere",
    "statuere":         "ſtatuere",
    "stricta":          "ſtricta",
    "stricte":          "ſtricte",
    "significatione":   "ſignificatione",
    "sariae":           "ſariæ",
    "subintrat":        "ſubintrat",
    "scientes":         "ſcientes",
    "sumitur":          "ſumitur",
    "summus":           "ſummus",
    "summi":            "ſummi",
    "summo":            "ſummo",
    "summos":           "ſummos",
    "summum":           "ſummum",
    "summe":            "ſumme",
    "summa":            "ſumma",
    "superiorum":       "ſuperiorum",
    "supponuntur":      "ſupponuntur",
    "iustitiam":        "iuſtitiam",
    "iustitiae":        "iuſtitiae",
    "iustitia":         "iuſtitia",
    "indiuisibili":     "indiuiſibili",
    "indiuisibilis":    "indiuiſibilis",
    "estimatio":        "æſtimatio",
    "aestimatio":       "æſtimatio",
    "mensura":          "menſura",
    "permutationem":    "permutationem",
    "possumus":         "poſſumus",
    "posset":           "poſſet",
    "possent":          "poſſent",
    "possim":           "poſſim",
    "possint":          "poſſint",
    "possem":           "poſſem",
    "obserua":          "obſerua",
    "consistere":       "conſiſtere",
    "consueuerunt":     "conſueuerunt",
    "consuetudine":     "conſuetudine",
    "consequaris":      "conſequaris",
    "constituitur":     "conſtituitur",
    "consensus":        "conſenſus",
    "conclusa":         "concluſa",
    "casu":             "caſu",  
    "censetur":         "cenſetur",
    "cuiusque":         "cuiuſque",
    "dispensatio":      "diſpenſatio",
    "dispositio":       "diſpoſitio",
    "distinctio":       "diſtinctio",
    "discedere":        "diſcedere", 
    "quaestioni":       "quæſtioni",
    "quaestionem":      "quæſtionem",
    "quaestio":         "quæſtio",
    "praestatio":       "præſtatio",
    "praesumptio":      "præſumptio",
    "substantia":       "ſubſtantia",
    "subiectum":        "ſubiectum",
    "subrepere":        "ſubreperc",
    "sufficit":         "ſufficit",
    "supponit":         "ſupponit",
    "supponitur":       "ſupponitur",
    "suppono":          "ſuppono",
    "supponimus":       "ſupponimus",
    "supponunt":        "ſupponunt",
    "suppositum":       "ſuppoſitum",
    "suppositio":       "ſuppoſitio",
    "suppositionem":    "ſuppoſitionem",
    "suppositionis":    "ſuppoſitionis",
    "species":          "ſpecies",
    "speciem":          "ſpeciem",
    "specifice":        "ſpecifice",
    "stracta":         "ſtracta",
    "restitutio":       "reſtitutio",
    "restitutionis":    "reſtitutionis",
    "restituit":        "reſtituit",
    "respondeam":       "reſpondeam",
    "expositores":      "expoſitores",
    "institutio":       "inſtitutio",
    "institutum":       "inſtitutum",
    "immensam":         "immenſam",
    "iustum":           "iuſtum",
    "iustam":           "iuſtam",
    "iustus":           "iuſtus",
    "iusta":            "iuſta",
    "iusti":            "iuſti",
    "iustis":           "iuſtis",
    "iusto":            "iuſto",
    "iustos":           "iuſtos",
    "iustorum":         "iuſtorum",
    "iuste":            "iuſte",
    "iustè":            "iuſtè",
    "iniustum":         "iniuſtum",
    "satisfactio":      "ſatisfactio",
    "satisfacit":       "ſatisfacit",
    "stipulatio":       "ſtipulatio",
    "probatissimam":    "probatiſſimam",
    "probatissima":     "probatiſſima",
    "vnusquisque":      "vnuſquiſque",
    "versatur":         "verſsatur",
    # sanctus y derivados
    "sanctitatem":      "ſanctitatem",
    "sanctitas":        "ſanctitas",
    "sanctitate":       "ſanctitate",
    "sanctitatis":      "ſanctitatis",
    "sanctum":          "ſanctum",
    "sancta":           "ſancta",
    "sanctus":          "ſanctus",
    "sancti":           "ſancti",
    "sancte":           "ſancte",
    # sequor/consequor y derivados
    "consequaris":      "conſequaris",
    "consequitur":      "conſequitur",
    "consequens":       "conſequens",
    "consequenter":     "conſequenter",
    "sequitur":         "ſequitur",
    "sequatur":         "ſequatur",
    # scientia y derivados
    "scientia":         "ſcientia",
    "scientiam":        "ſcientiam",
    "scientiae":        "ſcientiae",
    "scilicet":         "ſcilicet",
    # solutio y derivados
    "solutio":          "ſolutio",
    "solutionem":       "ſolutionem",
    "soluti":           "ſoluti",
    "solvit":           "ſoluit",
    "solvitur":         "ſoluitur",
    # stare/statuo
    "stare":            "ſtare",
    "stat":             "ſtat",
    "statim":           "ſtatim",
    "statuit":          "ſtatuit",
    "statuunt":         "ſtatuunt",
    "statuimus":        "ſtatuimus",
    "statuerunt":       "ſtatuerunt",
    "statutum":         "ſtatutum",
    "statuta":          "ſtatuta",
    # sensus y derivados
    "sensum":           "ſenſum",
    "sensus":           "ſenſus",
    "sensu":            "ſenſu",
    "sensum":           "ſenſum",
    # similis y derivados
    "similiter":        "ſimiliter",
    "similis":          "ſimilis",
    "simile":           "ſimile",
    # supra/super
    "supra":            "ſupra",
    "supradicto":       "ſupradicto",
    "supradicta":       "ſupradicta",
    # suum/suus
    "suum":             "ſuum",
    "suus":             "ſuus",
    "sua":              "ſua",
    "suam":             "ſuam",
    "sui":              "ſui",
    "suo":              "ſuo",
    "suae":             "ſuæ",
    "suis":             "ſuis", 
    # pronombres y formas breves frecuentes
    "se":               "ſe",
    "ipsis":            "ipſis",
    "usu":              "uſu",
    "quasi":            "quaſi",
    # formas verbales frecuentes
    "potest":           "poteſt",
    "consurgit":        "conſurgit",
    "consurgere":       "conſurgere",
    # autores: Faustus / Faustinus
    "faustus":          "fauſtus",
    "Faustinus":        "Fauſtinus",
    "Faustini":         "Fauſtini",
    "Faustinum":        "Fauſtinum",
    "Faustino":         "Fauſtino",
    # consuetudo y flexiones no cubiertas por la entrada exacta
    "consuetudinis":    "conſuetudinis",
    "consuetudini":     "conſuetudini",
    "consuetudinum":    "conſuetudinum",
    "consuetudines":    "conſuetudines",
    # diuersus y flexiones
    "diuersus":         "diuerſus",
    "diuersa":          "diuerſa",
    "diuersum":         "diuerſum",
    "diuersi":          "diuerſi",
    "diuerso":          "diuerſo",
    "diuersam":         "diuerſam",
    "diuersos":         "diuerſos",
    "diuersas":         "diuerſas",
    "diuersorum":       "diuerſorum",
    "diuersarum":       "diuerſarum",
    "diuersis":         "diuerſis",
    "diuerse":          "diuerſe",
    "diuersitas":       "diuerſitas",
    "diuersitatem":     "diuerſitatem",
    "diuersitate":      "diuerſitate",
    # persona y flexiones
    "persona":          "perſona",
    "personam":         "perſonam",
    "personae":         "perſonae",
    "personarum":       "perſonarum",
    "personis":         "perſonis",
    "personas":         "perſonas",
    "persone":          "perſone",
    # usura / vsura y flexiones
    "usura":            "uſura",
    "usurae":           "uſurae",
    "usuram":           "uſuram",
    "usurarum":         "uſurarum",
    "usuris":           "uſuris",
    "usuras":           "uſuras",
    "vsura":            "vſura",
    "vsurae":           "vſurae",
    "vsuram":           "vſuram",
    "vsurarum":         "vſurarum",
    "vsuris":           "vſuris",
    "vsuras":           "vſuras",
    "vsu":              "vſu",
    # praesens / præsens y flexiones
    "praesenti":        "præſenti",
    "praesens":         "præſens",
    "praesentem":       "præſentem",
    "praesentis":       "præſentis",
    "praesentia":       "præſentia",
    "praesentiam":      "præſentiam",
    "praesentibus":     "præſentibus",
    # inspicere y compuestos
    "inspiciendum":     "inſpiciendum",
    "inspicere":        "inſpicere",
    "inspicit":         "inſpicit",
    "inspicitur":       "inſpicitur",
    # existere y flexiones
    "existente":        "exiſtente",
    "existens":         "exiſtens",
    "existentem":       "exiſtentem",
    "existentis":       "exiſtentis",
    "existentia":       "exiſtentia",
    "existentiam":      "exiſtentiam",
    "existentibus":     "exiſtentibus",
    "existit":          "exiſtit",
    "existunt":         "exiſtunt",
    # generosus y flexiones
    "generosus":        "generoſus",
    "generosa":         "generoſa",
    "generosi":         "generoſi",
    "generoso":         "generoſo",
    "generosam":        "generoſam",
    "generosos":        "generoſos",
    "generosis":        "generoſis",
    "generose":         "generoſe",
    # splendidus y flexiones
    "splendidus":       "ſplendidus",
    "splendida":        "ſplendida",
    "splendidae":       "ſplendidæ",
    "splendidi":        "ſplendidi",
    "splendidum":       "ſplendidum",
    "splendide":        "ſplendide",
    # idest
    "idest":            "ideſt",
    # circumstantia y flexiones (incluye grafía con j del s. XVII)
    "circumstantia":    "circumſtantia",
    "circumstantiam":   "circumſtantiam",
    "circumstantiae":   "circumſtantiae",
    "circumstantiarum": "circumſtantiarum",
    "circumstantiis":   "circumſtantiis",
    "circumstantias":   "circumſtantias",
    "circumstantijs":   "circumſtantijs",
    # repraesentation- / repræsentatio
    "repraesentatio":   "repræſentatio",
    "repraesentationem":"repræſentationem",
    "repraesentationis":"repræſentationis",
    "repraesentat":     "repræſentat",
    "repraesentare":    "repræſentare",
    # magisterium (también cubierto parcialmente por la raíz magistr-)
    "magisterium":      "magiſterium",
    "magisterii":       "magiſterii",
    "magisterio":       "magiſterio",
    # nisi
    "nisi":             "niſi",
    # diuisio y flexiones
    "diuisio":          "diuiſio",
    "diuisionem":       "diuiſionem",
    "diuisionis":       "diuiſionis",
    "diuisione":        "diuiſione",
    "diuisi":           "diuiſi",
    "diuisus":          "diuiſus",
    "diuisum":          "diuiſum",
    "diuisa":           "diuiſa",
    # sufficiens y flexiones (sufficit ya cubierto)
    "sufficiens":       "ſufficiens",
    "sufficientem":     "ſufficientem",
    "sufficientis":     "ſufficientis",
    "sufficienter":     "ſufficienter",
    "sufficientia":     "ſufficientia",
    "sufficientiam":    "ſufficientiam",
    # quaestio: flexiones adicionales (quaestio/i/em ya cubiertas)
    "quaestionis":      "quæſtionis",
    "quaestione":       "quæſtione",
    "quaestionum":      "quæſtionum",
    "quaestiones":      "quæſtiones",
    "quaestionibus":    "quæſtionibus",
    # huiusmodi
    "huiusmodi":        "huiuſmodi",
    # decrescere y flexiones
    "decrescere":       "decreſcere",
    "decrescit":        "decreſcit",
    "decrescunt":       "decreſcunt",
    "decrescens":       "decreſcens",
    # excrescere y flexiones
    "excrescere":       "excreſcere",
    "excrescit":        "excreſcit",
    "excrescunt":       "excreſcunt",
    "excrescens":       "excreſcens",
    "excrescebat":      "excreſcebat",
    "excresceret":      "excreſceret",
    "excrescat":        "excreſcat",
    "excrescent":       "excreſcent",

    # Abreviaturas con s larga (forma diplomática de la abreviatura)
    "disp.":            "diſp.",
    "disput.":          "diſput.",
    "sect.":            "ſect.",
    "subsect.":         "ſubſect.",
    "assert.":          "aſſert.",
    "assert":           "aſſert",
    "disp":             "diſp",
    "disput":           "diſput",
    "sect":             "ſect",
}

# Raíces diplomáticas: si la forma normalizada *contiene* la subcadena clave,
# se sustituye por el valor diplomático. Cubre todos los casos morfológicos
# sin tener que enumerar cada forma.
# Orden importante: raíces más largas primero para evitar solapamientos.
LONG_S_ROOTS = [
    # administr- antes que ministr- y magistr-
    ("administr",  "adminiſtr"),  # administratio, administratorem…
    ("ministr",    "miniſtr"),    # ministrare, ministrat…
    ("minist",     "miniſt"),     # minister, ministerium, ministerio…
    ("magistr",    "magiſtr"),    # magistratus, magistratum, magistratui…
    ("registr",    "regiſtr"),    # registrum, registri…
    ("illustr",    "illuſtr"),    # illustris, illustrem…
    ("industri",   "induſtri"),   # industria, industriam…
    ("monstrat",   "monſtrat"),   # demonstratio, monstrat…
    ("demonstrat", "demonſtrat"),
    ("construc",   "conſtruc"),   # constructio…
    ("instruct",   "inſtruct"),   # instructio, instructus…
    ("restrict",   "reſtrict"),   # restrictio…
    ("distrinct",  "diſtrinct"),  # distinctio ya en LONG_S; cubre distrinctus…
    ("constr",     "conſtr"),     # constrictus, constringo…
    # nuevas raíces
    ("mensur",     "menſur"),     # mensura, commensurare, commensurationem…
    ("conscient",  "conſcient"),  # conscientia, conscientiam, conscientiae…
    ("aestimat",   "æſtimat"),    # aestimatione, aestimationem, aestimationis…
    ("rigoros",    "rigoroſ"),    # rigorosi, rigorosus, rigorosa…
    # cons- general (va al final: actúa solo si ninguna raíz más específica coincidió)
    ("cresc",      "creſc"),       # excrescere, decrescere, accrescere, increscere…
    ("sist",       "ſiſt"),        # consistit, subsistit, insistit, persistit…
    ("cons",       "conſ"),        # consurgit, consuetudo, consensus…
]

# ss medial → ſſ: aplica cuando ss no está en posición final absoluta
# (en latín del s. XVII las dos eses en posición medial son siempre largas)
_LONG_SS_RE = re.compile(r'ss(?=\w)', re.IGNORECASE)


def _apply_long_s_roots(text: str) -> str | None:
    """
    Aplica LONG_S_ROOTS y la regla ss→ſſ a `text` (forma normalizada).
    Devuelve la forma diplomática si hay cambio, o None si no aplica.
    Preserva mayúscula inicial.
    """
    lower = text.lower()
    result = lower

    # 1. Raíces con ſ
    for plain, diplo in LONG_S_ROOTS:
        if plain in result:
            result = result.replace(plain, diplo, 1)
            break  # una sola raíz por palabra

    # 2. ss medial → ſſ (sobre lo que ya haya transformado)
    result = _LONG_SS_RE.sub("ſſ", result)

    if result == lower:
        return None  # sin cambio

    # Restaurar mayúscula inicial si la tenía
    if text and text[0].isupper():
        result = result[0].upper() + result[1:]

    return result if result != text else None


def apply_long_s_to_split(left: str, right: str):
    """
    Aplica LONG_S (y como fallback LONG_S_ROOTS) a una palabra partida
    entre dos columnas. Reconstruye la palabra completa, busca la forma
    diplomática con ſ y distribuye las grafías entre left y right
    según la longitud original.
    Devuelve (orig_left, orig_right) o (None, None) si no hay cambio.
    """
    full = left + right
    key  = full.lower()
    if key in LONG_S:
        orig_full = LONG_S[key]
    else:
        orig_full = _apply_long_s_roots(full)
        if orig_full is None:
            return None, None
    if full and full[0].isupper():
        orig_full = orig_full[0].upper() + orig_full[1:]
    if orig_full == full:
        return None, None
    return orig_full[:len(left)], orig_full[len(left):]


# Grafemas originales del s. XVII que se sustituyen uno a uno
ORIG_CHARS = {
    "ſ": "s", "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe",
}


def classify_tag(text: str, expansion: str) -> str:
    """
    Devuelve 'abbr' u 'orig' para un par (texto_original, expansion).

    Regla 1 — termina en punto → abbr
      reip.  lib.  cap.  D.  n.
    Regla 2 — contiene macron → abbr
      pretiū (ū=m), omniū, definiū
    Regla 3 — expansión bastante más larga → abbr
      reip(5) → reipublicae(11): diferencia > 3
    Regla 4 — solo sustitución de grafemas conocidos → orig
      poteſtatem → potestatem  (ſ→s)
      æqualiter  → aequaliter  (æ→ae)
      vt         → ut          (v→u)
    """
    if not expansion:
        return "orig"  # sin expansión, tratar como orig

    # Caso especial: & siempre es abbr
    if text.strip() in ("&", "&amp;"):
        return "abbr"

    # Regla 1: termina en punto → abbr
    if text.rstrip().endswith("."):
        return "abbr"

    # Regla 2: contiene macron → abbr
    if any(c in text for c in MACRON_MAP):
        return "abbr"

    # Regla 3: expansión sustancialmente más larga → abbr
    # (diferencia > 3 caracteres, excluyendo puntuación)
    t_clean = text.rstrip(".")
    if len(expansion) - len(t_clean) > 3:
        return "abbr"

    # Regla 4: comprobar si es pura sustitución de grafemas
    # Normalizar el texto con sustituciones de grafemas y macrones
    normalized = text
    for orig_char, reg_char in ORIG_CHARS.items():
        normalized = normalized.replace(orig_char, reg_char)
    for macron, letters in MACRON_MAP.items():
        normalized = normalized.replace(macron, letters)
    normalized = normalized.rstrip(".")

    # Si la normalización produce la expansión (o muy similar) → orig
    if normalized.lower() == expansion.lower():
        return "orig"
    # Si difieren solo en 1-2 caracteres → orig (variante ortográfica menor)
    if abs(len(normalized) - len(expansion)) <= 1:
        return "orig"

    # Por defecto → abbr
    return "abbr"



# ── Extracción PAGE XML ───────────────────────────────────────────────────────

def parse_abbrev_tags(custom: str) -> list:
    tags = []
    for m in re.finditer(
        r"abbrev\s*\{[^}]*?offset:(\d+);[^}]*?length:(\d+);[^}]*?"
        r"(?:expansion:([^;}]+))?[^}]*?\}", custom
    ):
        expansion = (m.group(3) or "").strip().strip("'\"")
        tags.append({
            "offset": int(m.group(1)),
            "length": int(m.group(2)),
            "expansion": expansion,
        })
    return sorted(tags, key=lambda t: t["offset"])


def parse_structure_type(custom: str) -> str | None:
    """Extrae el tipo estructural de structure {type:XXX;} en el atributo custom."""
    m = re.search(r'structure\s*\{[^}]*?type:([^;}]+)', custom)
    return m.group(1).strip() if m else None


def parse_span_tags(custom: str, tag_name: str) -> list:
    """
    Extrae todos los spans de un tag dado del atributo custom de Transkribus.
    Soporta: sentence, index_entry, summary_item, textStyle, etc.
    Devuelve lista de {offset, length, continued, italic}.
    """
    spans = []
    pattern = rf'{re.escape(tag_name)}\s*\{{([^}}]*)\}}'
    for m in re.finditer(pattern, custom):
        body = m.group(1)
        mo = re.search(r'offset:(\d+)', body)
        ml = re.search(r'length:(\d+)', body)
        if not mo or not ml:
            continue
        spans.append({
            'offset':    int(mo.group(1)),
            'length':    int(ml.group(1)),
            'continued': 'continued:true' in body,
            'italic':    'italic:true' in body,
        })
    return sorted(spans, key=lambda s: s['offset'])


def extract_lines(page_xml_path: Path) -> list:
    tree = etree.parse(str(page_xml_path))
    root = tree.getroot()
    lines = []
    for tl in root.iter(f"{{{PAGE_NS}}}TextLine"):
        equiv = tl.find(f".//{{{PAGE_NS}}}TextEquiv/{{{PAGE_NS}}}Unicode")
        if equiv is None or not equiv.text:
            continue
        raw = equiv.text
        soft_hyphen = raw.rstrip().endswith("¬")
        text = raw.rstrip()[:-1].rstrip() if soft_hyphen else raw.rstrip()
        custom = tl.get("custom", "")
        parent = tl.getparent()
        region_id = parent.get("id", "") if parent is not None else ""
        m = re.search(r"readingOrder\s*\{index:(\d+)", custom)
        order = int(m.group(1)) if m else 999
        # Extraer x inicial desde Baseline
        baseline = tl.find(f"{{{PAGE_NS}}}Baseline")
        first_x = 0
        if baseline is not None:
            pts = baseline.get("points", "")
            if pts:
                first_x = int(pts.split()[0].split(",")[0])
        lines.append({
            "text":               text,
            "abbrevs":            parse_abbrev_tags(custom),
            "structure_type":     parse_structure_type(custom),
            "sentence_spans":     parse_span_tags(custom, "sentence"),
            "index_entry_spans":  parse_span_tags(custom, "index_entry"),
            "summary_item_spans": parse_span_tags(custom, "summary_item"),
            "italic_spans":       parse_span_tags(custom, "textStyle"),
            "region_id":          region_id,
            "reading_order":      order,
            "soft_hyphen":        soft_hyphen,
            "first_x":            first_x,
        })
    lines.sort(key=lambda l: (l["region_id"], l["reading_order"]))
    for i, line in enumerate(lines):
        line["line_n"] = i + 1
    return lines


# ── Segmentación por abbrev tags ──────────────────────────────────────────────

def apply_abbrev_tags(text: str, abbrevs: list) -> list:
    """
    Divide el texto en segmentos {text, expansion, is_abbrev}.
    Los offsets son posiciones de caracteres en el texto original.
    """
    if not abbrevs:
        return [{"text": text, "expansion": None, "is_abbrev": False}]
    segments = []
    pos = 0
    for tag in abbrevs:
        o, l, exp = tag["offset"], tag["length"], tag["expansion"]
        if pos < o:
            segments.append({"text": text[pos:o], "expansion": None, "is_abbrev": False})
        abbr_text = text[o: o + l]
        if abbr_text:
            segments.append({"text": abbr_text, "expansion": exp or None, "is_abbrev": True})
        pos = o + l
    if pos < len(text):
        segments.append({"text": text[pos:], "expansion": None, "is_abbrev": False})
    return segments


# ── Tokenizador ───────────────────────────────────────────────────────────────

TOKEN_RE = re.compile(
    r"(&amp;|&)"
    r"|(\[|\]|\(|\))"
    r"|([,;:?!])"
    r"|(\.\.\.|\.)"
    r"|([^\s,;:.?!\[\]()\-&]+(?:-[^\s,;:.?!\[\]()\-&]+)*)"
    r"|\s+", re.UNICODE
)

def tokenize(text: str) -> list:
    toks = []
    for m in TOKEN_RE.finditer(text):
        amp, bracket, punct, dot, word = m.groups()
        raw = m.group(0).strip()
        if not raw:
            continue
        if amp:       toks.append(("amp",  raw))
        elif bracket: toks.append(("pc",   raw))
        elif punct:   toks.append(("pc",   raw))
        elif dot:     toks.append(("dot",  raw))
        elif word:    toks.append(("word", raw))

    # Fusionar word+dot cuando forman abreviatura conocida
    result = []
    i = 0
    while i < len(toks):
        ttype, ttext = toks[i]
        if (ttype == "word"
                and i + 1 < len(toks)
                and toks[i+1][0] == "dot"
                and not ttext.isdigit()):
            candidate = ttext + "."
            if candidate in ABBREV_WITH_DOT or candidate.lower() in ABBREV_WITH_DOT:
                result.append(("abbrev_dot", candidate))
                i += 2
                continue
        result.append((ttype, ttext))
        i += 1
    return result


# ── Construcción TEI ──────────────────────────────────────────────────────────

