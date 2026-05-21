#!/usr/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

uv sync --group docs
uv build

WHEEL=$(ls dist/nimbus-*.whl | head -1)
mkdir -p docs/demos

for script in examples/*.py; do
    name=$(basename "$script" .py)
    title=$(python3 -c "print('$name'.replace('_', ' ').title())")
    uv run panel convert "$script" \
        --to pyodide \
        --out "docs/pyodide/$name/" \
        --requirements "$WHEEL" holoviews param
    cat > "docs/demos/$name.md" << MDEOF
# $title

<iframe
  src="../../pyodide/$name/$name.html"
  style="width:100%; height:82vh; border:none; border-radius:4px; box-shadow:0 2px 8px rgba(0,0,0,0.15);"
  title="$title"
  loading="lazy"></iframe>
MDEOF
done

python3 - <<'PYEOF'
import yaml, os
demos = sorted(f[:-3] for f in os.listdir('docs/demos') if f.endswith('.md'))
with open('mkdocs.yml') as f:
    config = yaml.safe_load(f)
demos_nav = [{n.replace('_', ' ').title(): f'demos/{n}.md'} for n in demos]
nav = [x for x in config['nav'] if not (isinstance(x, dict) and 'Demos' in x)]
api_idx = next(i for i, x in enumerate(nav) if isinstance(x, dict) and 'API Reference' in x)
nav.insert(api_idx, {'Demos': demos_nav})
config['nav'] = nav
with open('mkdocs.yml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
PYEOF

if [ "${1:-}" = "--build" ]; then
    uv run mkdocs build --strict
else
    uv run mkdocs serve
fi
