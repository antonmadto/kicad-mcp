from __future__ import annotations

from kicad_mcp.utils.netlist import parse_netlist

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<export version="E">
  <components>
    <comp ref="R1"><value>10k</value><footprint>Resistor_SMD:R_0603_1608Metric</footprint></comp>
    <comp ref="R2"><value>1k</value><footprint>Resistor_SMD:R_0603_1608Metric</footprint></comp>
  </components>
  <nets>
    <net code="1" name="/N1">
      <node ref="R1" pin="2" pinfunction="~"/>
      <node ref="R2" pin="2"/>
    </net>
    <net code="2" name="unconnected-(R1-Pad1)">
      <node ref="R1" pin="1"/>
    </net>
  </nets>
</export>
"""


def test_parse_netlist(tmp_path):
    path = tmp_path / "netlist.xml"
    path.write_text(SAMPLE_XML)
    parsed = parse_netlist(path)

    refs = {c["reference"] for c in parsed["components"]}
    assert refs == {"R1", "R2"}

    nets = {n["name"]: n for n in parsed["nets"]}
    assert nets["/N1"]["node_count"] == 2
    nodes = sorted(node["reference"] for node in nets["/N1"]["nodes"])
    assert nodes == ["R1", "R2"]
    assert nets["/N1"]["nodes"][0]["pin"] == "2"
