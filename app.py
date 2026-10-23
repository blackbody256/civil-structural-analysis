"""Local web app: Eurocode 2 element checks following 'How to Design Concrete Structures
using Eurocode 2'. Run with `.venv/bin/python app.py` and open http://127.0.0.1:5000.
"""
import io
import math
import re
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory

from ec2 import actions, creep, durability, fire, tables
from ec2 import slenderness as sl
from ec2.beam import check_beam
from ec2.column import check_column
from ec2.inputs import ValidationError
from ec2.elements import ELEMENTS
from ec2.materials import BAR_SIZES, CONCRETE_TABLE, DUCTILITY_CLASSES, LINK_SIZES, Concrete
from ec2.references import GUIDE, PDF_PAGE_OFFSET
from reports.beam_pdf import build_beam_pdf
from reports.column_pdf import build_column_pdf

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
GUIDE_PDF = ROOT / "How-to-design-concrete-structures-using-Eurocode-2.pdf"

app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")

# element: (check function, PDF builder)
ELEMENT_HANDLERS = {
    "column": (check_column, build_column_pdf),
    "beam": (check_beam, build_beam_pdf),
}

PAGES = {"/": "index.html"}
for _element in ELEMENT_HANDLERS:
    PAGES[f"/{_element}"] = f"{_element}.html"
    PAGES[f"/{_element}/run"] = "run.html"
    PAGES[f"/{_element}/report"] = "report.html"


def _page(name):
    return lambda: send_from_directory(STATIC, name)


for route, filename in PAGES.items():
    app.add_url_rule(route, "page" + (route.replace("/", "_") if route != "/" else "_home"), _page(filename))


@app.get("/reference/guide.pdf")
def guide_pdf():
    if not GUIDE_PDF.exists():
        abort(404)
    return send_file(GUIDE_PDF, mimetype="application/pdf")


@app.get("/api/elements")
def api_elements():
    return jsonify(ELEMENTS)


@app.get("/api/meta")
def api_meta():
    return jsonify({
        "concrete": [{"name": n, "fck": v[0], "fck_cube": v[1], "fctm": v[2], "Ecm": v[3]}
                     for n, v in CONCRETE_TABLE.items()],
        "bar_sizes": BAR_SIZES,
        "link_sizes": LINK_SIZES,
        "ductility": [{"id": k, "k": v[0], "eps_uk": v[1]} for k, v in DUCTILITY_CLASSES.items()],
        "exposure": [{"id": r["id"], "classes": r["classes"], "example": r["example"],
                      "groups": list(r["groups"]), "note": r.get("note", "")}
                     for r in durability.rows_for("vertical")],
        "exposure_all": [{"id": r["id"], "classes": r["classes"], "example": r["example"],
                          "groups": list(r["groups"]), "note": r.get("note", "")}
                         for r in durability.EXPOSURE_ROWS],
        "fire_periods": fire.FIRE_PERIODS,
        "fig5_cases": [{"id": k, "label": v[0], "F": v[1]} for k, v in sl.FIG5_CASES.items()],
        "psi_categories": actions.categories(),
        "table4": {"k": [None if math.isinf(k) else k for k in tables.TABLE4_K],
                   "F": tables.TABLE4_F.tolist()},
        "references": {k: {"label": v[0], "page": v[1]} for k, v in GUIDE.items()},
        "pdf_page_offset": PDF_PAGE_OFFSET,
        "guide_available": GUIDE_PDF.exists(),
    })


def _payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Expected a JSON object.")
    return data


def _handlers(element):
    if element not in ELEMENT_HANDLERS:
        abort(404)
    return ELEMENT_HANDLERS[element]


@app.post("/api/<element>/check")
def api_check(element):
    check, _ = _handlers(element)
    try:
        return jsonify(check(_payload()))
    except ValidationError as exc:
        return jsonify({"errors": exc.errors}), 400


@app.post("/api/<element>/report.pdf")
def api_pdf(element):
    check, build = _handlers(element)
    try:
        report = check(_payload())
    except ValidationError as exc:
        return jsonify({"errors": exc.errors}), 400
    ref = re.sub(r"[^A-Za-z0-9_-]+", "-", report["project"].get("ref") or element).strip("-") or element
    return send_file(io.BytesIO(build(report)), mimetype="application/pdf", as_attachment=True,
                     download_name=f"EC2-{element}-check-{ref}.pdf")


def _num(data, key, default=None):
    try:
        return float(data.get(key, default))
    except (TypeError, ValueError):
        abort(400, description=f"'{key}' must be a number.")


@app.post("/api/helpers/combination")
def api_combination():
    data = _payload()
    category = data.get("category", "B")
    if category not in tables.PSI_CATEGORIES:
        abort(400, description="Unknown imposed load category.")
    expression = "6.10" if data.get("expression") == "6.10" else "6.10ab"
    return jsonify(actions.uls_combination(_num(data, "gk", 0), _num(data, "qk", 0), category, expression))


@app.post("/api/helpers/creep")
def api_creep():
    data = _payload()
    concrete = data.get("concrete")
    if concrete not in CONCRETE_TABLE:
        abort(400, description="Unknown concrete class.")
    b, h = _num(data, "b"), _num(data, "h")
    h0 = 2 * b * h / (2 * (b + h))
    cement = data.get("cement", "R") if data.get("cement") in creep.CEMENT_ALPHA else "R"
    result = creep.effective_creep_ratio(Concrete.from_class(concrete).fcm, h0, _num(data, "rh", 50),
                                         _num(data, "t0", 28), cement, _num(data, "moment_ratio", 0.7))
    return jsonify({**result, "h0": h0})


@app.post("/api/helpers/stiffness")
def api_stiffness():
    """k for one column end from the beams framing in the plane of bending (PD 6687)."""
    data = _payload()
    width, depth, lc = _num(data, "col_width"), _num(data, "col_depth"), _num(data, "col_length")
    beams = []
    for beam in data.get("beams", []):
        bb, hb, span = (float(beam.get(k, 0) or 0) for k in ("b", "h", "span"))
        if bb > 0 and hb > 0 and span > 0:
            beams.append((bb * hb**3 / 12, span))
    k = sl.stiffness_k(width * depth**3 / 12, lc, beams)
    return jsonify({"k": None if math.isinf(k) else k, "pinned": math.isinf(k)})


@app.errorhandler(400)
def bad_request(err):
    return jsonify({"error": getattr(err, "description", "Bad request")}), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
