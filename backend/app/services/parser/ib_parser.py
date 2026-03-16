from app.services.parser.base_parser import parse_csv


def parse(path: str):
    return parse_csv(path)
