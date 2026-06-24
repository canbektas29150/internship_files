from __future__ import annotations

import json
import sys
from agent_flow import generate_report


def main():
    if len(sys.argv) < 2:
        print('Kullanım: python app.py "Apple 3. çeyrekte nasıl bir şey yapar"')
        raise SystemExit(1)

    prompt = " ".join(sys.argv[1:])
    report = generate_report(prompt)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
