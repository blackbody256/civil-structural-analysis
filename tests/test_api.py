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
    assert [e["id"] for e in elements if e["status"] == "active"] == ["column", "beam", "slab"]
    meta = client.get("/api/meta").get_json()
    assert "C30/37" in [c["name"] for c in meta["concrete"]]
    assert len(meta["table4"]["F"]) == 11


def test_slab_api_and_pdf(client):
    slab_payload = {
        "project": {"name": "Test Slab", "ref": "S1"},
        "slab": {"type": "one_way", "h": 175},
        "materials": {"concrete": "C30/37", "fyk": 500, "ductility": "B", "dg": 20},
        "span": {"l": 4.5, "supports": [{"x": 0, "type": "pin"}, {"x": 4.5, "type": "roller"}]},
        "reinforcement": {
            "bottom_x_dia": 12, "bottom_x_s": 200,
            "bottom_y_dia": 10, "bottom_y_s": 300,
            "top_x_dia": "none", "top_x_s": 200,
            "top_y_dia": "none", "top_y_s": 200,
            "cover": 25, "delta_c_dev": 10,
        },
        "actions": {
            "mode": "analysis", "gk": 1.5, "qk": 2.5, "self_weight": True,
            "category": "B", "loads": [], "pattern": True, "partitions": True,
        },
        "stiffness": {"E_method": "concrete"},
        "durability": {"exposure": "XC1", "cement_group": "All", "fire_period": "R60"},
    }
    # 200 OK check
    res = client.post("/api/slab/check", json=slab_payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["summary"]["verdict"] == "pass"
    assert "strip" in data["plots"]["figures"]
    assert "diagrams" in data["plots"]["figures"]

    # 400 Bad request on invalid input
    bad_payload = dict(slab_payload, slab={"type": "one_way", "h": -10})
    bad_res = client.post("/api/slab/check", json=bad_payload)
    assert bad_res.status_code == 400
    assert "slab.h" in bad_res.get_json()["errors"]

    # PDF download starts with %PDF
    pdf_res = client.post("/api/slab/report.pdf", json=slab_payload)
    assert pdf_res.status_code == 200
    assert pdf_res.mimetype == "application/pdf"
    assert pdf_res.data.startswith(b"%PDF")
    assert len(pdf_res.data) > 20_000

    # Live analysis endpoint returns figures
    live_res = client.post("/api/slab/analysis", json=slab_payload)
    assert live_res.status_code == 200
    live_data = live_res.get_json()
    assert "diagrams" in live_data["figures"]
    assert "loading" in live_data["figures"]

    # Live analysis error
    live_bad = client.post("/api/slab/analysis", json=bad_payload)
    assert live_bad.status_code == 400
    assert "slab.h" in live_bad.get_json()["errors"]


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


