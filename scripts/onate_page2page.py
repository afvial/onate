from pypdf import PdfReader, PdfWriter
import os

def extraer_paginas(ruta_pdf, pagina_inicio, pagina_fin, numero_inicial, carpeta_salida):
    ruta_pdf = os.path.expanduser(ruta_pdf)   # <-- añade esta línea
    carpeta_salida = os.path.expanduser(carpeta_salida)
    os.makedirs(carpeta_salida, exist_ok=True)
    reader = PdfReader(ruta_pdf)
    
    nn = numero_inicial
    for i in range(pagina_inicio - 1, pagina_fin):
        writer = PdfWriter()
        writer.add_page(reader.pages[i])
        
        nombre = f"pg_63_{nn:02d}.pdf"
        salida = os.path.join(carpeta_salida, nombre)
        with open(salida, "wb") as f:
            writer.write(f)
        print(f"Guardada: {nombre}  (página PDF {i+1})")
        
        nn += 1
    
    print(f"\n✅ {pagina_fin - pagina_inicio + 1} páginas guardadas en '{carpeta_salida}/'")

# Uso:
extraer_paginas(
    "~/Documents/contractibus/De_Contractibus_Tomi_Tres.pdf",
    pagina_inicio=63,
    pagina_fin=101,
    numero_inicial=33,
    carpeta_salida="~/Documents/contractibus/tractatus 21/disp63"
)
