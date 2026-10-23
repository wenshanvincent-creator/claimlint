import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers()
    build = sub.add_parser("build")
    build.add_argument("--output")
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int)
    return parser.parse_args()
