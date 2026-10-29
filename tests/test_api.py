import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


@pytest.mark.parametrize("path", ["/", "/column", "/column/run", "/column/report", "/beam", "/beam/run", "/beam/report"])
def test_pages(client, path):
    res = client.get(path)
    assert res.status_code == 200 and b"<!doctype html>" in res.data.lower()


def test_elements_and_meta(client):
    elements = client.get("/api/elements").get_json()
    assert [e["id"] for e in elements if e["status"] == "active"] == ["column", "beam"]
    meta = client.get("/api/meta").get_json()
    assert "C30/37" in [c["name"] for c in meta["concrete"]]
    assert len(meta["table4"]["F"]) == 11


def test_check_ok_and_invalid(client, example):
    res = client.post("/api/column/check", json=example)
    assert res.status_code == 200
    assert res.get_json()["summary"]["verdict"] == "pass"
    example["geometry"]["h"] = "abc"
    bad = client.post("/api/column/check", json=example)
    assert bad.status_code == 400 and "geometry.h" in bad.get_json()["errors"]


def test_pdf_download(client, example):
    res = client.post("/api/column/report.pdf", json=example)
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"
    assert "attachment" in res.headers["Content-Disposition"]
    assert res.data.startswith(b"%PDF") and len(res.data) > 20_000


def test_helpers(client):
    combo = client.post("/api/helpers/combination", json={"gk": 1000, "qk": 500, "category": "B"}).get_json()
    assert combo["value"] == pytest.approx(0.925 * 1.35 * 1000 + 1.5 * 500)
    creep = client.post("/api/helpers/creep", json={"concrete": "C30/37", "b": 300, "h": 300, "rh": 50, "t0": 28,
                                                    "cement": "R", "moment_ratio": 0.7}).get_json()
    assert creep["h0"] == 150 and creep["phi_inf"] == pytest.approx(2.40, abs=0.01)
    k = client.post("/api/helpers/stiffness", json={"col_width": 300, "col_depth": 300, "col_length": 3500,
                                                    "beams": []}).get_json()
    assert k["pinned"] is True

    analysis = client.post("/api/helpers/beam-analysis", json={
        "span": 6.0, "system": "simple",
        "loads": [{"type": "point", "W": 60, "x": 3.0}],
        "E_kpa": 30e6, "I_m4": 0.002
    }).get_json()
    assert analysis["abs_max_M_kNm"] == pytest.approx(90.0)
    assert analysis["abs_max_V_kN"] == pytest.approx(30.0)
    assert len(analysis["reactions"]) == 2
