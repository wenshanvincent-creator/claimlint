from claimlint.docs_parser import anchors, parse_text


def test_claim_locations_for_multiline_inline_links_and_fences():
    text = """# Hello

First `demo.first` then
second `demo.second` and [missing][ref].

[ref]: absent.md

```python
import demo
demo.call()
```
"""
    claims = parse_text(text, "README.md")
    assert [(c.kind, c.line) for c in claims] == [
        ("heading", 1),
        ("inline", 3),
        ("inline", 4),
        ("link", 4),
        ("code", 9),
    ]
    assert next(c.target for c in claims if c.kind == "link") == "absent.md"


def test_ignore_applies_to_next_block_not_whole_document():
    text = """<!-- claimlint: ignore DP002 -->
`demo.one`

`demo.two`
"""
    first, second = parse_text(text, "README.md")
    assert first.ignored == {"DP002"}
    assert not second.ignored


def test_duplicate_unicode_and_explicit_anchors():
    text = '# Hello\n\n# Hello\n\n# 你好\n\n<a id="manual"></a>\n'
    assert anchors(parse_text(text, "README.md"), text) == {"hello", "hello-1", "你好", "manual"}


def test_anchor_collisions_and_html_code_samples():
    text = '# A\n\n# A\n\n# A-1\n\n```html\n<a id="fake"></a>\n```\n'
    assert anchors(parse_text(text, "README.md"), text) == {"a", "a-1", "a-1-1"}
