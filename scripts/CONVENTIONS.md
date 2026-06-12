# Script conventions

- **Shebang + module docstring** describing the orchestration and its outputs.
- **`from __future__ import annotations`** at the top.
- **Path bootstrap** (identical across scripts):
  ```python
  PROJECT_ROOT = Path(__file__).resolve().parent.parent
  for _path in (PROJECT_ROOT, PROJECT_ROOT / "src", PROJECT_ROOT.parent.parent):
      text = str(_path)
      if text not in sys.path:
          sys.path.insert(0, text)
  ```
- **Imports from `src.*`** carry `# noqa: E402` (they follow the path bootstrap).
- **`main()`** does the work and returns the produced path(s); guard with
  `if __name__ == "__main__": main()` (or `sys.exit(main())` for checks).
- **Numbered prefix** (`00_`) marks pipeline-ordered preflight steps;
  `z_`-prefixed scripts run late (manuscript hydration).
- **JSON outputs** use `indent=2, sort_keys=True` for deterministic diffs.
