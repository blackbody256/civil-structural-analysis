"""Result records shared by every element check."""
from dataclasses import asdict, dataclass, field

from .notation import plain, to_markup

PASS, FAIL, WARN, INFO, NA = "pass", "fail", "warn", "info", "na"


@dataclass
class CheckResult:
    id: str
    group: str
    title: str
    status: str
    result: str = ""                 # short outcome, e.g. "64.9 ≤ 88.2 kNm"
    value: float | None = None
    limit: float | None = None
    unit: str = ""
    utilisation: float | None = None
    working: list = field(default_factory=list)   # lines of the calculation
    refs: list = field(default_factory=list)      # [{"label": ..., "page": printed page}]
    note: str = ""
    target: str = ""                 # drawing part it relates to: cover, bars, links, section, elevation

    def to_dict(self):
        data = asdict(self)
        data["markup"] = {
            "result": to_markup(self.result),
            "working": [to_markup(line) for line in self.working],
            "note": to_markup(self.note),
        }
        data["working"] = [plain(line) for line in self.working]
        return data


def status_from(ok, warn=False):
    if not ok:
        return FAIL
    return WARN if warn else PASS


def summarise(checks):
    counts = {s: 0 for s in (PASS, FAIL, WARN, INFO, NA)}
    for c in checks:
        counts[c.status] += 1
    verdict = FAIL if counts[FAIL] else (WARN if counts[WARN] else PASS)
    return {"verdict": verdict, "counts": counts, "total": len(checks)}
