import os
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask, redirect, render_template, request, session, url_for

from app.components.retriever import create_qa_chain

app = Flask(__name__)
app.secret_key = os.urandom(24)

from markupsafe import Markup


def nl2br(text):
    return Markup(text.replace("\n", "<br>\n"))


app.jinja_env.filters["nl2br"] = nl2br


@app.route("/", methods=["GET", "POST"])
def index():
    if "messages" not in session:
        session["messages"] = []

    if request.method == "POST":
        user_input = request.form.get("prompt")

        if user_input:
            messages = session["messages"]
            messages.append({"role": "user", "content": user_input})
            session["messages"] = messages

            try:
                qa_chain = create_qa_chain()
                response = qa_chain.invoke({"query": user_input})
                result = response.get("result", "Sorry, I couldn't find an answer.")

                messages.append({"role": "assistant", "content": result})
                session["messages"] = messages

            except Exception as e:
                error_message = (
                    f"An error occurred while processing your request: {str(e)}"
                )
                return render_template(
                    "index.html", messages=session["messages"], error=error_message
                )
        return redirect(url_for("index"))
    return render_template("index.html", messages=session["messages"])


@app.route("/clear", methods=["POST"])
def clear():
    session.pop("messages", None)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
