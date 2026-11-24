import json
import re
import subprocess
from pathlib import Path

print("=== PRUEBAS: cuestionario.html ===")

pagina = Path("cuestionario.html").read_text(encoding="utf-8")
inicio = pagina.index('<script src="municipios_ine.js"></script>')
fin = pagina.rindex("</script>") + len("</script>")
script = pagina[inicio:fin]
navegador = next((
    ruta for ruta in (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    )
    if ruta.exists()
), None)
assert navegador is not None, "Hace falta Edge o Chrome para ejecutar el cuestionario."

harness = Path("_test_cuestionario.html")
harness.write_text(
    """<!DOCTYPE html><html><body>
<pre id="resultado"></pre>
<div id="card"></div><div id="steps"></div><table id="dictTable"></table>
<tbody id="dictBody"></tbody><div id="emptyDict"></div><div id="dictamen"></div>
<div id="fileStatus"></div><button id="downloadBtn"></button>
"""
    + script
    + """
<script>
const casos = [];
function probar(nombre, condicion) { casos.push({ nombre: nombre, ok: !!condicion }); }
const provincia = resolver({ id: 1, tipo: "texto" }, "lo desconozco");
probar("provincia desconocida", provincia && provincia.valor === "D" && provincia.presumido);
probar("provincia invalida", resolver({ id: 1, tipo: "texto" }, "Atlantis") === null);
probar("jaen", resolver({ id: 1, tipo: "texto" }, "jaén").valor === "D");
probar("superficie limite", resolver({ id: 2, tipo: "texto" }, "10") === null);
probar("superficie valida", resolver({ id: 2, tipo: "texto" }, "85,5").valor === 85.5);
probar("anio bajo", resolver({ id: 4, tipo: "texto" }, "1799") === null);
probar("anio actual", resolver({ id: 4, tipo: "texto" }, "2026").valor === 2026);
respuestas[1] = resolver({ id: 1, tipo: "texto" }, "Jaén");
respuestas[4] = resolver({ id: 4, tipo: "texto" }, "1978");
const municipio = resolver({ id: 11, tipo: "texto" }, "jaen");
probar("nombre oficial", municipio.contestacion === "Jaén");
const fachada = resolver({ id: 5, tipo: "opcion", opciones: [["Lo desconozco", "", null]] }, 0);
probar("sin aislamiento en 1978", fachada.valor === false && fachada.presumido);
document.getElementById("resultado").textContent = JSON.stringify(casos);
</script></body></html>""",
    encoding="utf-8",
)

try:
    proceso = subprocess.run(
        [
            str(navegador),
            "--headless=new",
            "--disable-gpu",
            "--virtual-time-budget=4000",
            "--dump-dom",
            harness.resolve().as_uri(),
        ],
        check=False,
        capture_output=True,
        timeout=40,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    hallado = re.search(r'<pre id="resultado">(.*?)</pre>', proceso.stdout, flags=re.S)
    assert hallado, (proceso.stdout[-800:] or proceso.stderr[-800:])
    bruto = hallado.group(1).strip()
    casos = json.loads(bruto)
    fallos = [caso["nombre"] for caso in casos if not caso["ok"]]
    assert not fallos, fallos
    print("[OK] La pagina rechaza los limites y guarda los supuestos de provincia, superficie, ano y municipio.")
finally:
    harness.unlink(missing_ok=True)

print("=== TODAS LAS PRUEBAS DE cuestionario.html HAN FINALIZADO ===")
