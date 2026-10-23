# Demo

```sh
demo build --old-output result.txt
demo serve --output result.txt
```

The renamed API was `demo.rendr()`.

```python
from demo import render

render("hello", columns=80)
```

Set `DEMO_OLD_TOKEN`.

See [guide](docs/missing.md) or [missing section](#old-title).
