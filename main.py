"""App Engine redirect shim. Every request 301s to the new static site."""

from flask import Flask, redirect

app = Flask(__name__)

NEW_BASE = "https://apwest.github.io/monkey-business"
DEAD_ROUTES = {"about", "contact"}
DEAD_PREFIXES = ("donate/", "vote/", "results/")


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>", methods=["GET", "POST"])
def shim(path: str):
    if path == "update":
        return "Gone.", 410

    if path in DEAD_ROUTES or any(path.startswith(p) for p in DEAD_PREFIXES):
        return redirect(f"{NEW_BASE}/", code=301)

    # /<id> and /random|/search resolve to /<id>/ etc on the new site —
    # redirect straight to the trailing-slash form to skip GH Pages' own 301.
    if path.isdigit() or path in ("random", "search"):
        return redirect(f"{NEW_BASE}/{path}/", code=301)

    return redirect(f"{NEW_BASE}/{path}" if path else f"{NEW_BASE}/", code=301)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
