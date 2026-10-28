"""Fixed sandbox entrypoint. Receives source and simulated stdin as bounded JSON."""
import io
import json
import sys


def main() -> None:
    payload = json.load(sys.stdin)
    source = payload.get("code")
    user_input = payload.get("stdin", "")
    if not isinstance(source, str) or not isinstance(user_input, str):
        raise ValueError("invalid execution payload")
    sys.stdin = io.StringIO(user_input)
    namespace = {"__name__": "__main__", "__file__": "<submission>"}
    exec(compile(source, "<submission>", "exec"), namespace, namespace)


if __name__ == "__main__":
    main()
