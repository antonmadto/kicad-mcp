"""Impedance-analysis tools (Phase 7): analyze_impedance, calculate_impedance.

``analyze_impedance`` reads a board's routed geometry + stackup and reports the
characteristic impedance of each (layer, width) configuration, comparing against
any impedance targets the user declared via set_design_context. ``calculate_
impedance`` is a stackup-free calculator for what-if geometry. Both are quasi-
static estimates (Hammerstad-Jensen microstrip / IPC-2141 stripline / NatSemi
coupled) — a field solver is still the sign-off authority.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import TYPE_CHECKING

from kicad_mcp.context import AppContext
from kicad_mcp.review_engine import impedance as imp

from . import review
from ._common import resolve

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_MAX_NETS_PER_CONFIG = 20


def _r(x, n: int = 3):
    return round(x, n) if x is not None else None


def analyze_impedance_impl(
    ctx: AppContext, project: str, *, net: str | None = None, diff_gap_mm: float | None = None
) -> dict:
    model = review._build_model(ctx, project)
    a = imp.analyze_model(model, diff_gap_mm=diff_gap_mm)

    if not a.configs and not a.diffs:
        return {
            "source": model.source,
            "stackup_source": a.stackup_source,
            "configs": [],
            "assumptions": ["board has no routed traces"],
            "summary_markdown": "No traces to analyze.",
        }

    configs, diffs, verdicts = a.configs, a.diffs, a.verdicts
    if net is not None:
        want = net.lstrip("/")
        stem_of: dict[str, str | None] = {}
        for d in a.diffs:
            for nc in d.net_codes:
                nm = model.nets.get(nc)
                if nm:
                    stem_of[nm.name.lstrip("/")] = d.stem
        keys = {want}
        stem = stem_of.get(want)
        if stem:
            keys.add(stem.lstrip("/"))
        configs = [
            c
            for c in a.configs
            if any(
                model.nets.get(nc) and model.nets[nc].name.lstrip("/") in keys
                for nc in c.net_codes
            )
        ]
        diffs = [d for d in a.diffs if (d.stem or "").lstrip("/") in keys]
        verdicts = [v for v in a.verdicts if v.key in keys]

    verdict_by_key = {v.key: v for v in verdicts}

    def _config_dict(r: imp.ImpedanceResult) -> dict:
        names = [
            model.nets[nc].name
            for nc in r.net_codes
            if nc in model.nets and model.nets[nc].name
        ]
        nets_list = []
        for nm in names[:_MAX_NETS_PER_CONFIG]:
            entry: dict = {"net": nm}
            v = verdict_by_key.get(nm.lstrip("/"))
            if v is not None and v.kind == "single_ended":
                entry["target_ohms"] = v.target_ohms
                entry["deviation_pct"] = _r(v.deviation_pct, 1)
                entry["verdict"] = v.verdict
            nets_list.append(entry)
        return {
            "config_id": f"{r.layer} {'diff' if r.kind == 'differential' else 'se'} "
            f"w{r.width_mm:.2f}",
            "kind": r.kind,
            "layer": r.layer,
            "model": r.model,
            "width_mm": r.width_mm,
            "total_len_mm": _r(r.total_len_mm),
            "z0_ohms": _r(r.z0_ohms),
            "z_diff_ohms": _r(r.z_diff_ohms),
            "eps_eff": _r(r.eps_eff),
            "prop_delay_ps_per_mm": _r(r.prop_delay_ps_per_mm),
            "confidence": r.confidence,
            "assumptions": list(r.assumptions),
            "geometry": r.inputs,
            "nets": nets_list,
            "net_count": len(names),
            "nets_omitted": max(0, len(names) - _MAX_NETS_PER_CONFIG),
        }

    def _diff_dict(r: imp.ImpedanceResult) -> dict:
        d: dict = {
            "stem": r.stem,
            "layer": r.layer,
            "s_mm": r.inputs.get("S_mm"),
            "z_diff_ohms": _r(r.z_diff_ohms),
            "z0_se_ohms": _r(r.z0_ohms),
            "confidence": r.confidence,
            "assumptions": list(r.assumptions),
        }
        v = verdict_by_key.get((r.stem or "").lstrip("/"))
        if v is not None and v.kind == "differential":
            d["target_ohms"] = v.target_ohms
            d["deviation_pct"] = _r(v.deviation_pct, 1)
            d["verdict"] = v.verdict
        return d

    def _verdict_dict(v: imp.TargetVerdict) -> dict:
        d = asdict(v)
        d["computed_ohms"] = _r(v.computed_ohms)
        d["deviation_pct"] = _r(v.deviation_pct, 1)
        d["assumptions"] = list(v.assumptions)
        return d

    config_dicts = [_config_dict(r) for r in configs]
    diff_dicts = [_diff_dict(r) for r in diffs]
    all_results = configs + diffs
    assumptions = sorted({a_ for r in all_results for a_ in r.assumptions})
    modes_used = sorted({r.model for r in all_results if r.model != "none"})

    result = {
        "source": model.source,
        "stackup_source": a.stackup_source,
        "configs": config_dicts,
        "diff_pairs": diff_dicts,
        "comparison": [_verdict_dict(v) for v in verdicts],
        "targets_unmatched": list(a.unmatched),
        "assumptions": assumptions,
        "modes_used": modes_used,
        "summary_markdown": _summary_markdown(
            config_dicts, diff_dicts, assumptions, a.stackup_source
        ),
    }

    from kicad_mcp import history

    history.record(
        resolve(ctx, project).directory,
        "impedance",
        {"configs": len(config_dicts), "targets": len(verdicts)},
    )
    return result


def _geometry_recap(c: dict) -> str:
    g = c["geometry"]
    if c["model"] in ("microstrip", "coupled_microstrip"):
        geom = f"W={g.get('W_mm')} H={g.get('H_mm')} T={g.get('T_mm')} er={g.get('er')}"
    elif c["model"] in ("stripline", "coupled_stripline"):
        geom = f"W={g.get('W_mm')} b={g.get('b_mm')} T={g.get('T_mm')} er={g.get('er')}"
    else:
        geom = f"W={g.get('W_mm')}"
    z = c.get("z_diff_ohms") if c["kind"] == "differential" else c.get("z0_ohms")
    zlabel = "Z_diff" if c["kind"] == "differential" else "Z0"
    ztxt = f"{z} Ω" if z is not None else "undefined"
    return (
        f"{c['model']} · {geom} → {zlabel}={ztxt}, "
        f"{c['prop_delay_ps_per_mm']} ps/mm ({c['confidence']} confidence)"
    )


def _summary_markdown(
    config_dicts: list[dict], diff_dicts: list[dict], assumptions: list[str], stackup_source: str
) -> str:
    lines = [
        "# Impedance analysis",
        "",
        f"Stackup source: **{stackup_source}**. "
        f"{len(config_dicts)} single-ended config(s), {len(diff_dicts)} differential pair(s).",
        "",
    ]
    shown = config_dicts[:5]
    for c in shown:
        lines.append(f"### {c['config_id']}")
        lines.append(_geometry_recap(c))
        targeted = [n for n in c["nets"] if "verdict" in n]
        if targeted:
            lines.append("")
            lines.append("| net | target | actual | dev | status |")
            lines.append("| --- | --- | --- | --- | --- |")
            for n in targeted:
                lines.append(
                    f"| {n['net']} | {n['target_ohms']} Ω | {c['z0_ohms']} Ω | "
                    f"{n['deviation_pct']}% | {n['verdict']} |"
                )
        lines.append("")
    if len(config_dicts) > 5:
        lines.append(f"... and {len(config_dicts) - 5} more single-ended config(s).")
        lines.append("")
    for d in diff_dicts:
        lines.append(f"### {d['layer']} diff (pair {d['stem']})")
        z = f"{d['z_diff_ohms']} Ω" if d["z_diff_ohms"] is not None else "undefined"
        recap = (
            f"coupled · Z_diff={z}, per-leg Z0={d['z0_se_ohms']} Ω "
            f"({d['confidence']} confidence)"
        )
        if "verdict" in d:
            recap += (
                f" — target {d['target_ohms']} Ω, {d['deviation_pct']}% → **{d['verdict']}**"
            )
        lines.append(recap)
        lines.append("")
    if assumptions:
        lines.append("**Assumptions used**")
        for a_ in assumptions:
            lines.append(f"- {a_}")
    return "\n".join(lines)


def calculate_impedance_impl(
    ctx: AppContext,
    *,
    width_mm: float,
    height_mm: float,
    epsilon_r: float,
    thickness_mm: float = 0.035,
    mode: str = "microstrip",
    spacing_mm: float | None = None,
    plane_spacing_mm: float | None = None,
) -> dict:
    def _pos(name: str, value: float) -> None:
        if not (math.isfinite(value) and value > 0):
            raise ValueError(f"{name} must be a positive finite number of mm, got {value!r}.")

    _pos("width_mm", width_mm)
    _pos("height_mm", height_mm)
    _pos("epsilon_r", epsilon_r)
    _pos("thickness_mm", thickness_mm)
    if spacing_mm is not None:
        _pos("spacing_mm", spacing_mm)
    if mode not in ("microstrip", "stripline"):
        raise ValueError(f"mode must be 'microstrip' or 'stripline', got {mode!r}.")
    if mode == "stripline" and plane_spacing_mm is None:
        raise ValueError("stripline mode requires plane_spacing_mm (the plane-to-plane b).")
    if plane_spacing_mm is not None:
        _pos("plane_spacing_mm", plane_spacing_mm)

    is_diff = spacing_mm is not None
    if mode == "microstrip":
        z0, eps = imp.microstrip_z0_eps(width_mm, height_mm, epsilon_r, thickness_mm)
        z_diff = imp.diff_z0_microstrip(z0, spacing_mm, height_mm) if is_diff else None
        model_name = "coupled_microstrip" if is_diff else "microstrip"
        inputs = {
            "W_mm": width_mm,
            "H_mm": height_mm,
            "T_mm": thickness_mm,
            "er": epsilon_r,
        }
    else:
        z0 = imp.stripline_z0(width_mm, plane_spacing_mm, epsilon_r, thickness_mm)
        eps = epsilon_r
        z_diff = imp.diff_z0_stripline(z0, spacing_mm, plane_spacing_mm) if is_diff else None
        model_name = "coupled_stripline" if is_diff else "stripline"
        inputs = {
            "W_mm": width_mm,
            "b_mm": plane_spacing_mm,
            "T_mm": thickness_mm,
            "er": epsilon_r,
        }
    if is_diff:
        inputs["S_mm"] = spacing_mm

    result = imp.ImpedanceResult(
        kind="differential" if is_diff else "single_ended",
        layer="(ad-hoc)",
        model=model_name,
        width_mm=width_mm,
        z0_ohms=z0,
        z_diff_ohms=z_diff,
        eps_eff=eps,
        prop_delay_ps_per_mm=imp.prop_delay_ps_per_mm(eps),
        confidence="high",
        assumptions=(),
        inputs=inputs,
    )
    d = asdict(result)
    z = z_diff if is_diff else z0
    zlabel = "Z_diff" if is_diff else "Z0"
    ztxt = f"{z:.1f} Ω" if z is not None else "undefined (out of model range)"
    d["summary_markdown"] = (
        f"{model_name}: {zlabel} = {ztxt}, eps_eff = {eps:.3f}, "
        f"{result.prop_delay_ps_per_mm:.2f} ps/mm."
    )
    return d


def register(mcp: FastMCP, ctx: AppContext) -> None:
    @mcp.tool()
    def analyze_impedance(
        project: str, net: str | None = None, diff_gap_mm: float | None = None
    ) -> dict:
        """Compute the characteristic impedance of a board's routed traces.

        Uses the Hammerstad-Jensen microstrip / IPC-2141 stripline / NatSemi
        coupled models over the board's stackup, grouped by (layer, width). Pass
        or omit ``diff_gap_mm`` to override the differential edge gap when routing
        does not reveal it. pass/fail is reported ONLY for nets whose target
        impedance was declared via set_design_context; everything else is
        reported as a quasi-static estimate with a confidence level.
        """
        return analyze_impedance_impl(ctx, project, net=net, diff_gap_mm=diff_gap_mm)

    @mcp.tool()
    def calculate_impedance(
        width_mm: float,
        height_mm: float,
        epsilon_r: float,
        thickness_mm: float = 0.035,
        mode: str = "microstrip",
        spacing_mm: float | None = None,
        plane_spacing_mm: float | None = None,
    ) -> dict:
        """Stackup-free impedance calculator for what-if geometry.

        Hammerstad-Jensen microstrip (needs height_mm to the reference plane) or
        IPC-2141 symmetric stripline (needs plane_spacing_mm = plane-to-plane b).
        Supply spacing_mm (edge-to-edge gap) to also get the NatSemi coupled
        differential impedance. No board or targets involved — a pure calculator.
        """
        return calculate_impedance_impl(
            ctx,
            width_mm=width_mm,
            height_mm=height_mm,
            epsilon_r=epsilon_r,
            thickness_mm=thickness_mm,
            mode=mode,
            spacing_mm=spacing_mm,
            plane_spacing_mm=plane_spacing_mm,
        )
