"""
Language registry: maps each supported language to its Docker image
and the command used to run submitted code.

For interpreted languages (Python, JS) we run the code inline with -c / -e.
Compiled languages (Go, C++, Java) will need a compile-then-run flow,
added later.
"""

LANGUAGES = {
    "python": {
        "image": "python:3.12-slim",
        # python3 -c "<code>" runs the code string directly
        "cmd": lambda code: ["python3", "-c", code],
    },
    "javascript": {
        "image": "node:22-slim",
        # node -e "<code>" runs the code string directly
        "cmd": lambda code: ["node", "-e", code],
    },
}


def is_supported(language: str) -> bool:
    return language in LANGUAGES


def get_config(language: str):
    return LANGUAGES[language]


def supported_languages():
    return list(LANGUAGES.keys())