"""Drive a whole conversation and print the grammar report.

One command to exercise everything the backend does so far: sessions, context,
persistence, transcripts and grammar analysis.

    uv run python scripts/demo.py
    uv run python scripts/demo.py --audio samples/user_turn.wav
    uv run python scripts/demo.py --url http://127.0.0.1:8000

The scripted lines contain deliberate mistakes (past tense, adverb form,
subject-verb agreement, articles) so the analysis has something real to find.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

SCRIPT = [
    "Hello, my name is Adarsh and I am from Kerala.",
    "I go to college yesterday and it was very good.",
    "The teacher explained the lesson very good, so I am thinking about it.",
    "My friend he go to the same college and we ate a apple together.",
    "Do you remember what my name is and where I am from?",
]


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def _request(self, method, path, data=None, headers=None):
        req = urllib.request.Request(
            f"{self.base}{path}", data=data, method=method,
            headers=headers or {},
        )
        try:
            body = urllib.request.urlopen(req).read()
        except urllib.error.HTTPError as exc:
            raise ApiError(exc.code, exc.read().decode("utf-8", "replace")) from exc
        except urllib.error.URLError as exc:
            raise ApiError(0, f"Could not reach {self.base}: {exc.reason}") from exc
        return body

    def get_json(self, path):
        return json.loads(self._request("GET", path))

    def get_text(self, path):
        return self._request("GET", path).decode("utf-8")

    def post_json(self, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else b""
        return json.loads(self._request(
            "POST", path, data, {"Content-Type": "application/json"}
        ))

    def post_file(self, path, file_path: Path):
        boundary = uuid.uuid4().hex
        body = b"".join([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; '
            f'filename="{file_path.name}"\r\n'.encode(),
            b"Content-Type: audio/wav\r\n\r\n",
            file_path.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ])
        return json.loads(self._request(
            "POST", path, body,
            {"Content-Type": f"multipart/form-data; boundary={boundary}"},
        ))


class ApiError(Exception):
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body}")


def rule(title: str) -> None:
    print(f"\n{'=' * 68}\n{title}\n{'=' * 68}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--audio", type=Path, default=None,
                        help="Send this WAV as an extra spoken turn.")
    parser.add_argument("--keep-open", action="store_true",
                        help="Do not end the session.")
    args = parser.parse_args()

    api = Api(args.url)

    try:
        health = api.get_json("/health")
    except ApiError as exc:
        print(f"Backend not reachable: {exc.body}", file=sys.stderr)
        print("Start it with: uv run uvicorn app.main:app --reload --port 8000",
              file=sys.stderr)
        return 1

    rule("PROVIDERS")
    for role, name in health["providers"].items():
        print(f"  {role:8} {name}")
    print(f"  ffmpeg   {'available' if health['ffmpeg'] else 'MISSING'}")

    session = api.post_json("/api/v1/sessions")
    session_id = session["id"]
    rule(f"CONVERSATION  (session {session_id})")

    for i, line in enumerate(SCRIPT, 1):
        turn = api.post_json(
            f"/api/v1/sessions/{session_id}/turns/text", {"text": line}
        )
        print(f"\n[{i}] you : {line}")
        print(f"    ai  : {turn['reply_text']}")
        print(f"    ctx={turn['history_messages']} msgs  "
              f"tts={turn['tts_provider']}  {turn['timings_ms']}")

    if args.audio:
        if not args.audio.is_file():
            print(f"\nNo such audio file: {args.audio}", file=sys.stderr)
        else:
            turn = api.post_file(f"/api/v1/sessions/{session_id}/turns", args.audio)
            print(f"\n[audio] heard: {turn['transcript']}")
            print(f"        ai   : {turn['reply_text']}")
            print(f"        ctx={turn['history_messages']} msgs  "
                  f"{turn['timings_ms']}")

    if not args.keep_open:
        ended = api.post_json(f"/api/v1/sessions/{session_id}/end")
        print(f"\nsession ended: {ended['status']}, "
              f"{ended['turn_count']} turns, "
              f"{ended['duration_seconds']:.1f}s")

    rule("TRANSCRIPT")
    print(api.get_text(f"/api/v1/sessions/{session_id}/transcript?format=text"))

    rule("GRAMMAR ANALYSIS")
    try:
        report = api.post_json(f"/api/v1/sessions/{session_id}/analysis/grammar")
    except ApiError as exc:
        print(f"Analysis failed: {exc.body}", file=sys.stderr)
        return 1

    print(f"provider           {report['provider']}")
    print(f"grammar score      {report['grammar_score']}/100")
    print(f"sentences analysed {report['sentences_analyzed']}")
    print(f"words analysed     {report['words_analyzed']}")
    print(f"issues found       {report['issue_count']}")

    for i, issue in enumerate(report["issues"], 1):
        print(f"\n  {i}. [{issue['category']}] confidence "
              f"{issue['confidence']:.2f}")
        print(f"     was : {issue['original']}")
        print(f"     fix : {issue['corrected']}")
        print(f"     why : {issue['explanation']}")

    if not report["issues"]:
        print("\n  No grammar issues found.")

    rule("NEXT")
    print(f"  session id : {session_id}")
    print(f"  transcript : {args.url}/api/v1/sessions/{session_id}/transcript")
    print(f"  analysis   : {args.url}/api/v1/sessions/{session_id}/analysis/grammar")
    print(f"  api docs   : {args.url}/docs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
