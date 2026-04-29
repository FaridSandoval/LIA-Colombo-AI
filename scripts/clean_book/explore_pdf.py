"""Encontrar la página que contiene 'Before viewing'."""
import pdfplumber

with pdfplumber.open("data/raw/sym2.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        if "Before viewing" in text:
            print(f"Encontrado en página {i + 1}")
            # Mostrar distribución de x0
            from collections import Counter
            x0_buckets = Counter(
                round(c["x0"] / 10) * 10
                for c in page.chars
                if c["size"] < 15
            )
            print(f"\nDistribución x0 de pág {i + 1}:")
            for x in sorted(x0_buckets.keys()):
                bar = "#" * min(x0_buckets[x] // 5, 60)
                print(f"  x0 ~{x:>4}px: {x0_buckets[x]:>4}  {bar}")
            break  # solo la primera ocurrencia