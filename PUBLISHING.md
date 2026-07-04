# Releasing kicad-mcp

Release artifacts are built and verified locally/CI; **publishing is a manual,
credentialed step** — nothing here pushes to a public index automatically except
the tag-triggered GitHub Actions workflow (which you opt into by pushing a tag).

## 1. Pre-flight (must be green)

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
```

Bump the version in `pyproject.toml`, `kicad_mcp/__init__.py`, and `server.json`,
and add a `CHANGELOG.md` entry. Keep them in sync.

## 2. Build + verify the package

```bash
python -m pip install --upgrade build twine
python -m build                 # → dist/kicad_mcp-<v>.tar.gz + .whl
twine check dist/*              # metadata sanity
```

Smoke the built wheel in a clean venv:

```bash
python -m venv /tmp/verify && /tmp/verify/bin/pip install dist/kicad_mcp-*.whl
/tmp/verify/bin/kicad-mcp --help 2>/dev/null || echo "(server runs over stdio)"
/tmp/verify/bin/python -c "import kicad_mcp, asyncio; from kicad_mcp.server import create_server; \
  print(len(asyncio.run(create_server().list_tools())), 'tools')"
```

## 3. Publish to PyPI (choose one)

**Trusted Publishing (recommended, no token).** Configure a PyPI publisher for
this repo (https://docs.pypi.org/trusted-publishers/), then:

```bash
git tag v0.1.0 && git push origin v0.1.0    # triggers .github/workflows/release.yml
```

**Manual.** `twine upload dist/*` with a PyPI API token.

Verify: `uvx kicad-mcp` (or `pipx run kicad-mcp`) starts the server.

## 4. Register in the MCP registry

`server.json` is the registry manifest. Publish it with the MCP registry CLI
(`mcp-publisher`) per https://github.com/modelcontextprotocol/registry — this
requires authenticating as the `io.github.<owner>` namespace owner.

## Cross-platform note

CI (`.github/workflows/ci.yml`) runs ruff + pytest on Linux/macOS/Windows ×
Python 3.10–3.13 with kicad-cli/IPC tests auto-skipped (KiCad isn't on runners).
A real `uvx kicad-mcp` smoke against KiCad 9 should be done manually on each OS
before announcing a release.
