def render(text, *, width=80):
    return text[:width]


def positional(value, /, required, *, mode):
    return value, required, mode
