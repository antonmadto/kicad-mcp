"""Controlled-impedance analysis — quasi-static Z0/Z_diff/eps_eff/prop-delay.

Two halves separated below: a pure-math core (only ``math``, trivially golden-
testable) and a model-extraction layer that turns board geometry + stackup into
per-configuration impedance results. The dependency is one-directional
(impedance -> model), never the reverse.

Microstrip is the full Hammerstad-Jensen model (a line-exact port of KiCad 9's
microstrip.cpp): copper thickness enters via the normalized-width correction
``_du`` and eps_eff genuinely depends on T. Stripline is IPC-2141A symmetric
(strip centered). Coupled impedance uses the NatSemi ``(1 - k·exp(-c·S/geom))``
fit — good to ±5–10 % vs a 2-D field solver, worse for S < H; every result is a
quasi-static estimate, not a substitute for KiCad's even/odd solver at sign-off.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# --- pure math ---------------------------------------------------------------

_ZF0 = 376.730313668  # free-space wave impedance η0 (KiCad units.h)
_E = math.e
_PI = math.pi
_C_MM_PER_NS = 299.792458
_PS_PER_MM_VACUUM = 1000.0 / _C_MM_PER_NS  # 3.335640951981521; delay = this·sqrt(eps_eff)
_DEFAULT_ER = 4.3  # FR-4; flagged as ASSUMPTION when used
_DEFAULT_T_MM = 0.035  # 1 oz copper
_DEFAULT_H_MM = 0.2  # dielectric height fallback (matches crosstalk._DEFAULT_H_MM)
_FAB_TOL = 0.10  # ±10% standard controlled-impedance fab tolerance
_INFO_TOL = 0.05  # 5–10% band → INFO


def _du(x, t, er):
    if t <= 0:
        return 0.0
    d = (t / _PI) * math.log(1 + (4 * _E / t) * math.tanh(math.sqrt(6.517 * x)) ** 2)
    return 0.5 * d * (1 + 1.0 / math.cosh(math.sqrt(er - 1)))


def _z0air(x):
    f = 6 + (2 * _PI - 6) * math.exp(-((30.666 / x) ** 0.7528))
    return (_ZF0 / (2 * _PI)) * math.log(f / x + math.sqrt(1 + (2.0 / x) ** 2))


def microstrip_z0_eps(w_mm, h_mm, er, t_mm=_DEFAULT_T_MM):
    """Hammerstad-Jensen microstrip (KiCad microstrip.cpp port). Returns (Z0|None, eps_eff).

    Valid 0.01<=W/H<=100, er 1..15, T/H<~0.5. Degenerate -> (None, max(er,1)).
    """
    if w_mm <= 0 or h_mm <= 0 or er < 1:
        return None, max(er, 1.0)
    u = w_mm / h_mm
    tn = t_mm / h_mm
    u1 = u + _du(u, tn, 1.0)
    ur = u + _du(u, tn, er)
    zh1 = _z0air(u1)
    zhr = _z0air(ur)
    a = (
        1
        + (1 / 49) * math.log((ur**4 + (ur / 52) ** 2) / (ur**4 + 0.432))
        + (1 / 18.7) * math.log(1 + (ur / 18.1) ** 3)
    )
    b = 0.564 * ((er - 0.9) / (er + 3.0)) ** 0.053
    q_inf = (1 + 10 / ur) ** (-a * b)
    q_t = (2 * math.log(2) / _PI) * (tn / math.sqrt(ur))
    q = q_inf - q_t
    eps_eff_t = 0.5 * (er + 1) + 0.5 * q * (er - 1)
    eps_eff = eps_eff_t * (zh1 / zhr) ** 2
    z0 = zhr / math.sqrt(eps_eff_t)
    return z0, eps_eff


def microstrip_z0(w_mm, h_mm, er, t_mm=_DEFAULT_T_MM):
    return microstrip_z0_eps(w_mm, h_mm, er, t_mm)[0]


def microstrip_eps_eff(w_mm, h_mm, er, t_mm=_DEFAULT_T_MM):
    return microstrip_z0_eps(w_mm, h_mm, er, t_mm)[1]


def stripline_z0(w_mm, b_mm, er, t_mm=_DEFAULT_T_MM):
    """IPC-2141A symmetric (centered) stripline. eps_eff=er exactly. Valid W/(b-T)<0.35.

    Returns None on degenerate/out-of-range (arg<=1 -> non-physical).
    """
    if w_mm <= 0 or b_mm <= 0 or er < 1:
        return None
    arg = 4 * b_mm / (0.67 * _PI * (0.8 * w_mm + t_mm))
    if arg <= 1.0:
        return None
    return (60.0 / math.sqrt(er)) * math.log(arg)


def diff_z0_microstrip(z0_se, s_mm, h_mm):
    if z0_se is None or h_mm <= 0:
        return None
    return 2 * z0_se * (1 - 0.48 * math.exp(-0.96 * s_mm / h_mm))


def diff_z0_stripline(z0_se, s_mm, b_mm):
    if z0_se is None or b_mm <= 0:
        return None
    return 2 * z0_se * (1 - 0.347 * math.exp(-2.9 * s_mm / b_mm))


def prop_delay_ps_per_mm(eps_eff):
    return _PS_PER_MM_VACUUM * math.sqrt(max(eps_eff, 1.0))


# --- model extraction --------------------------------------------------------

from . import geometry as geo  # noqa: E402
from .model import CopperLayer, DesignModel  # noqa: E402
from .rules.crosstalk import _MIN_OVERLAP_MM  # noqa: E402  (=5.0; the same sustained-run gate)
from .rules.transmission import _diff_pairs  # noqa: E402

# Copied (not imported from return_path) to keep rules from depending on this module.
_PLANE_ROLES = {"ground_plane", "power_plane", "mixed_plane"}

# Confidence lattice: any missing datum drops the level; verdicts act on high/medium only.
_CONF = {"high": 2, "medium": 1, "low": 0}
_CONF_NAME = {2: "high", 1: "medium", 0: "low"}

# Assumption strings surfaced verbatim; stackup_source keys off the er/H ones.
_A_ER = "eps_r defaulted to 4.3 (FR-4); board stores no dielectric constant"
_A_T = "copper thickness defaulted to 35 µm (1 oz)"
_A_H = "dielectric height unknown, assumed 0.2 mm"
_A_CENTERED = "stripline assumed centered between planes"
_A_DIFF_OVERRIDE = "differential spacing from diff_gap_mm override"
_A_DIFF_NONE = "differential spacing not derivable from routing; supply diff_gap_mm"


def _floor(conf: str, level: str) -> str:
    return _CONF_NAME[min(_CONF[conf], _CONF[level])]


@dataclass(frozen=True)
class TraceConfig:
    layer: str
    width_mm: float
    net_codes: tuple[int, ...]
    total_len_mm: float


@dataclass(frozen=True)
class ImpedanceResult:
    kind: str  # 'single_ended' | 'differential'
    layer: str
    model: str  # microstrip|stripline|coupled_microstrip|coupled_stripline|none
    width_mm: float
    z0_ohms: float | None  # single-ended char impedance (diff: the per-leg SE value)
    z_diff_ohms: float | None  # differential only
    eps_eff: float
    prop_delay_ps_per_mm: float
    confidence: str  # 'high'|'medium'|'low'
    assumptions: tuple[str, ...] = ()
    inputs: dict = field(default_factory=dict)  # echo W,H|b,T,er,S used (mm/unitless)
    net_codes: tuple[int, ...] = ()
    stem: str | None = None
    total_len_mm: float = 0.0


@dataclass(frozen=True)
class TargetVerdict:
    key: str
    kind: str
    target_ohms: float
    computed_ohms: float | None
    deviation_pct: float | None
    verdict: str  # 'pass'|'info'|'fail'|'unknown'
    confidence: str
    model: str
    layer: str | None
    assumptions: tuple[str, ...]


@dataclass(frozen=True)
class ImpedanceAnalysis:
    configs: list[ImpedanceResult]
    diffs: list[ImpedanceResult]
    verdicts: list[TargetVerdict]
    unmatched: list[str]
    stackup_source: str  # 'board'|'assumed'|'unavailable'


def trace_configs(model: DesignModel, ndigits: int = 3) -> list[TraceConfig]:
    """Group routed tracks by (layer, width): each group is one impedance config."""
    groups: dict[tuple[str, float], dict] = {}
    for t in model.tracks:
        if t.width <= 0:
            continue
        key = (t.layer, round(t.width, ndigits))
        g = groups.setdefault(key, {"len": 0.0, "nets": set()})
        g["len"] += t.length
        g["nets"].add(t.net_code)
    out = [
        TraceConfig(
            layer=layer,
            width_mm=width,
            net_codes=tuple(sorted(g["nets"])),
            total_len_mm=g["len"],
        )
        for (layer, width), g in groups.items()
    ]
    out.sort(key=lambda c: (c.layer, c.width_mm))
    return out


def reference_planes(
    model: DesignModel, layer_name: str
) -> tuple[CopperLayer | None, CopperLayer | None]:
    """(plane_above, plane_below) for a signal layer, nearest plane in each direction.

    A plane layer is not a signal layer, so it has no reference of its own. Scans
    beyond direct neighbours so a signal buried under a signal-then-plane still
    finds its plane; a ground plane is preferred on distance ties (which a linear
    stack never actually produces).
    """
    layers = sorted(model.copper_layers, key=lambda c: c.stack_index)
    idx = next((i for i, ly in enumerate(layers) if ly.name == layer_name), None)
    if idx is None or layers[idx].role in _PLANE_ROLES:
        return None, None

    def nearest(indices) -> CopperLayer | None:
        planes = [layers[i] for i in indices if layers[i].role in _PLANE_ROLES]
        planes.sort(key=lambda c: 0 if c.role == "ground_plane" else 1)
        return planes[0] if planes else None

    above = nearest(range(idx - 1, -1, -1))
    below = nearest(range(idx + 1, len(layers)))
    return above, below


def _dielectric_span(
    model: DesignModel, cu_a: str, cu_b: str
) -> tuple[float | None, float | None]:
    """(dielectric thickness, eps_r) of the non-copper layers between two copper layers.

    Thickness is summed; eps_r is thickness-weighted (unweighted if some layers
    carry an eps_r but no thickness). Works even when the two planes are not
    adjacent in the stack.
    """
    pos = {}
    for i, ly in enumerate(model.stackup):
        if ly.is_copper and ly.name in (cu_a, cu_b) and ly.name not in pos:
            pos[ly.name] = i
    if cu_a not in pos or cu_b not in pos:
        return None, None
    lo, hi = sorted((pos[cu_a], pos[cu_b]))
    between = [ly for ly in model.stackup[lo + 1 : hi] if not ly.is_copper]
    thick = sum(ly.thickness_mm or 0.0 for ly in between)
    er_layers = [ly for ly in between if ly.epsilon_r is not None]
    er: float | None = None
    if er_layers:
        weights = [ly.thickness_mm for ly in er_layers]
        if all(w and w > 0 for w in weights):
            er = sum(ly.epsilon_r * ly.thickness_mm for ly in er_layers) / sum(weights)
        else:
            er = sum(ly.epsilon_r for ly in er_layers) / len(er_layers)
    return (thick or None), er


def _copper_thickness(model: DesignModel, layer: str) -> float | None:
    for ly in model.stackup:
        if ly.name == layer and ly.is_copper:
            return ly.thickness_mm
    return None


def analyze_config(
    model: DesignModel, cfg: TraceConfig, *, diff_gap_mm: float | None = None
) -> ImpedanceResult:
    """Single-ended Z0 for one (layer, width) config, given its reference plane(s)."""
    above, below = reference_planes(model, cfg.layer)
    w = cfg.width_mm
    assumptions: list[str] = []
    conf = "high"

    def result(model_name, z0, eps, inputs) -> ImpedanceResult:
        return ImpedanceResult(
            kind="single_ended",
            layer=cfg.layer,
            model=model_name,
            width_mm=w,
            z0_ohms=z0,
            z_diff_ohms=None,
            eps_eff=eps,
            prop_delay_ps_per_mm=prop_delay_ps_per_mm(eps),
            confidence=conf,
            assumptions=tuple(assumptions),
            inputs=inputs,
            net_codes=cfg.net_codes,
            stem=None,
            total_len_mm=cfg.total_len_mm,
        )

    if above is None and below is None:
        assumptions.append(f"no reference plane adjacent to {cfg.layer}; Z0 undefined")
        conf = "low"
        return result("none", None, 1.0, {"W_mm": round(w, 4)})

    t = _copper_thickness(model, cfg.layer)
    if t is None:
        t = _DEFAULT_T_MM
        assumptions.append(_A_T)

    if above is not None and below is not None:
        # Both planes → stripline (strip assumed centered).
        b, er = _dielectric_span(model, above.name, below.name)
        if b is None:
            b = _DEFAULT_H_MM
            assumptions.append(_A_H)
            conf = _floor(conf, "low")
        if er is None:
            er = _DEFAULT_ER
            assumptions.append(_A_ER)
            conf = _floor(conf, "medium")
        if not _is_centered(model, cfg.layer, above, below):
            assumptions.append(_A_CENTERED)
        z0 = stripline_z0(w, b, er, t)
        if z0 is None:
            conf = _floor(conf, "low")
        return result(
            "stripline",
            z0,
            er,
            {"W_mm": round(w, 4), "b_mm": round(b, 4), "T_mm": t, "er": er},
        )

    # Exactly one plane → microstrip.
    plane = below if below is not None else above
    h, er = _dielectric_span(model, cfg.layer, plane.name)
    if h is None:
        sig_cu = model.copper_layer(cfg.layer)
        plane_cu = model.copper_layer(plane.name)
        if below is not None and sig_cu and sig_cu.dielectric_to_next_mm:
            h = sig_cu.dielectric_to_next_mm
        elif above is not None and plane_cu and plane_cu.dielectric_to_next_mm:
            h = plane_cu.dielectric_to_next_mm
        if h is None:
            h = _DEFAULT_H_MM
            assumptions.append(_A_H)
            conf = _floor(conf, "low")
    if er is None:
        er = _DEFAULT_ER
        assumptions.append(_A_ER)
        conf = _floor(conf, "medium")
    u = w / h
    if not (0.01 <= u <= 100):
        assumptions.append(f"W/H={u:.3g} outside model validity range")
        conf = _floor(conf, "medium")
    z0, eps = microstrip_z0_eps(w, h, er, t)
    if z0 is None:
        conf = _floor(conf, "low")
    return result(
        "microstrip",
        z0,
        eps,
        {"W_mm": round(w, 4), "H_mm": round(h, 4), "T_mm": t, "er": er, "W_over_H": round(u, 4)},
    )


def _is_centered(model: DesignModel, signal: str, above: CopperLayer, below: CopperLayer) -> bool:
    top, _ = _dielectric_span(model, above.name, signal)
    bot, _ = _dielectric_span(model, signal, below.name)
    if top is None or bot is None or top + bot <= 0:
        return True  # cannot tell; do not nag
    return abs(top - bot) / (top + bot) <= 0.10


def diff_spacing_mm(
    model: DesignModel, p_code: int, n_code: int, layer: str
) -> float | None:
    """Overlap-weighted centreline separation of a P/N pair on ``layer``.

    Requires a sustained parallel run (>= _MIN_OVERLAP_MM total) or returns None.
    The caller subtracts the trace width to get the edge-to-edge gap.
    """
    p_tracks = [t for t in model.tracks if t.net_code == p_code and t.layer == layer]
    n_tracks = [t for t in model.tracks if t.net_code == n_code and t.layer == layer]
    total_overlap = 0.0
    weighted_perp = 0.0
    for pt in p_tracks:
        for nt in n_tracks:
            parallel, perp, overlap = geo.segment_parallel_proximity(
                pt.start, pt.end, nt.start, nt.end
            )
            if parallel and overlap > 0:
                total_overlap += overlap
                weighted_perp += perp * overlap
    if total_overlap < _MIN_OVERLAP_MM:
        return None
    return weighted_perp / total_overlap


def _dominant_layer_width(
    model: DesignModel, net_code: int, ndigits: int = 3
) -> tuple[str, float] | None:
    by_key: dict[tuple[str, float], float] = {}
    for t in model.tracks:
        if t.net_code != net_code or t.width <= 0:
            continue
        key = (t.layer, round(t.width, ndigits))
        by_key[key] = by_key.get(key, 0.0) + t.length
    if not by_key:
        return None
    (layer, width), _ = max(by_key.items(), key=lambda kv: kv[1])
    return layer, width


def _analyze_diff(
    model: DesignModel, p: int, n: int, stem: str, *, diff_gap_mm: float | None
) -> ImpedanceResult | None:
    lw = _dominant_layer_width(model, p)
    if lw is None:
        return None
    layer, width = lw
    se = analyze_config(model, TraceConfig(layer, width, (p,), 0.0))
    assumptions = list(se.assumptions)
    conf = se.confidence
    inputs = dict(se.inputs)

    perp = diff_spacing_mm(model, p, n, layer)
    s: float | None
    if perp is not None:
        s = max(perp - width, 0.0)
    elif diff_gap_mm is not None:
        s = diff_gap_mm
        assumptions.append(_A_DIFF_OVERRIDE)
        conf = _floor(conf, "medium")
    else:
        s = None
        assumptions.append(_A_DIFF_NONE)

    dmodel = {
        "microstrip": "coupled_microstrip",
        "stripline": "coupled_stripline",
        "none": "none",
    }[se.model]
    z_diff = None
    if s is not None and se.z0_ohms is not None:
        if se.model == "microstrip":
            z_diff = diff_z0_microstrip(se.z0_ohms, s, se.inputs["H_mm"])
        elif se.model == "stripline":
            z_diff = diff_z0_stripline(se.z0_ohms, s, se.inputs["b_mm"])
    if s is not None:
        inputs["S_mm"] = round(s, 4)

    total_len = model.net_length_mm(p) + model.net_length_mm(n)
    return ImpedanceResult(
        kind="differential",
        layer=layer,
        model=dmodel,
        width_mm=width,
        z0_ohms=se.z0_ohms,
        z_diff_ohms=z_diff,
        eps_eff=se.eps_eff,
        prop_delay_ps_per_mm=se.prop_delay_ps_per_mm,
        confidence=conf,
        assumptions=tuple(assumptions),
        inputs=inputs,
        net_codes=(p, n),
        stem=stem,
        total_len_mm=total_len,
    )


def _stackup_source(model: DesignModel, results: list[ImpedanceResult]) -> str:
    if not model.stackup:
        return "unavailable"
    for r in results:
        if _A_ER in r.assumptions or _A_H in r.assumptions:
            return "assumed"
    return "board"


def analyze_model(model: DesignModel, *, diff_gap_mm: float | None = None) -> ImpedanceAnalysis:
    configs = [analyze_config(model, cfg) for cfg in trace_configs(model)]
    diffs: list[ImpedanceResult] = []
    for p, n, stem in _diff_pairs(model):
        has_p = any(t.net_code == p for t in model.tracks)
        has_n = any(t.net_code == n for t in model.tracks)
        if not (has_p and has_n):
            continue
        r = _analyze_diff(model, p, n, stem, diff_gap_mm=diff_gap_mm)
        if r is not None:
            diffs.append(r)
    source = _stackup_source(model, configs + diffs)
    prelim = ImpedanceAnalysis(configs, diffs, [], [], source)
    verdicts, unmatched = evaluate_targets(model, prelim)
    return ImpedanceAnalysis(configs, diffs, verdicts, unmatched, source)


def _net_len_in(model: DesignModel, net_code: int, layer: str, width: float, ndigits=3) -> float:
    w = round(width, ndigits)
    return sum(
        t.length
        for t in model.tracks
        if t.net_code == net_code and t.layer == layer and round(t.width, ndigits) == w
    )


def evaluate_targets(
    model: DesignModel, analysis: ImpedanceAnalysis
) -> tuple[list[TargetVerdict], list[str]]:
    """Compare each user-declared target impedance against the routed geometry.

    A net's dominant config is the (layer, width) carrying its greatest routed
    length. Only high/medium-confidence, non-None results yield a pass/info/fail;
    everything else is 'unknown' (never a false failure).
    """
    by_net: dict[str, ImpedanceResult] = {}
    best_len: dict[str, float] = {}
    for r in analysis.configs:
        for nc in r.net_codes:
            net = model.nets.get(nc)
            if net is None:
                continue
            name = net.name.lstrip("/")
            if not name:
                continue
            length = _net_len_in(model, nc, r.layer, r.width_mm)
            if name not in by_net or length > best_len[name]:
                by_net[name] = r
                best_len[name] = length
    by_stem = {r.stem: r for r in analysis.diffs if r.stem}

    verdicts: list[TargetVerdict] = []
    unmatched: list[str] = []
    for k, target in model.context.target_impedances.items():
        key = k.lstrip("/")
        if key in by_stem:
            r = by_stem[key]
            kind = "differential"
            computed = r.z_diff_ohms
        elif key in by_net:
            r = by_net[key]
            kind = "single_ended"
            computed = r.z0_ohms
        else:
            unmatched.append(key)
            continue
        if computed is None or r.confidence == "low":
            verdict = "unknown"
            dev = None
        else:
            dev = (computed - target) / target * 100.0
            if abs(dev) <= _INFO_TOL * 100:  # ≤5% → within premium fab tolerance
                verdict = "pass"
            elif abs(dev) <= _FAB_TOL * 100:  # 5–10% → eating the margin
                verdict = "info"
            else:  # >10% → outside a standard controlled-impedance build
                verdict = "fail"
        verdicts.append(
            TargetVerdict(
                key=key,
                kind=kind,
                target_ohms=target,
                computed_ohms=computed,
                deviation_pct=dev,
                verdict=verdict,
                confidence=r.confidence,
                model=r.model,
                layer=r.layer,
                assumptions=r.assumptions,
            )
        )
    return verdicts, unmatched
