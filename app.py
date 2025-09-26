import os
from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv

from fare_service import compute_trip

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-me")


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        start_address = request.form.get("start_address", "").strip()
        end_address = request.form.get("end_address", "").strip()
        if not start_address or not end_address:
            flash("Please enter both start and dropoff addresses.", "error")
            return redirect(url_for("index"))
        try:
            result = compute_trip(start_address, end_address)
            return render_template(
                "index.html",
                start_address=start_address,
                end_address=end_address,
                result={
                    "distance_km": f"{result['distance_km']:.2f}",
                    "duration_min": f"{result['duration_min']:.1f}",
                    "fare_rm": f"{result['fare_rm']:.2f}",
                },
            )
        except Exception as e:
            flash(str(e), "error")
            return redirect(url_for("index"))

    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
