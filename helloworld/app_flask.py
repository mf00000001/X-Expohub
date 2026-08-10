"""
HelloWorld Flask 实现

启动方式: flask --app app_flask run --host 0.0.0.0 --port 5000
或: python app_flask.py
"""

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def hello():
    """返回 Hello World 问候消息"""
    return {"message": "Hello, World!"}


@app.route("/api/health")
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "ok",
        "service": "HelloWorld-Flask",
        "version": "1.0.0",
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
