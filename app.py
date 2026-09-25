import json
from pathlib import Path
from flask import Flask,request,jsonify,send_from_directory
from scanner import load_signals,SUBS

app=Flask(__name__,static_folder="static")

@app.get("/")
def home(): return send_from_directory("static","index.html")

@app.get("/api/signals")
def signals(): return jsonify(load_signals())

@app.post("/api/subscribe")
def subscribe():
 sub=request.get_json()
 old=json.loads(SUBS.read_text()) if SUBS.exists() else []
 if sub not in old: old.append(sub)
 SUBS.write_text(json.dumps(old,ensure_ascii=False,indent=2))
 return jsonify({"ok":True})

@app.get("/api/vapid-public-key")
def vapid():
 import os
 return jsonify({"key":os.getenv("VAPID_PUBLIC_KEY","")})

if __name__=="__main__": app.run(host="0.0.0.0",port=8000)
