import sys
import json
from mcp_validator import validate
from mcp_executor import run

def main():
    raw = sys.stdin.read()

    validated = validate(raw)
    result = run(validated)

    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
