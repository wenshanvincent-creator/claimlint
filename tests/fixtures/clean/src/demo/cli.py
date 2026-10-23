import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int)
    return parser.parse_args()
