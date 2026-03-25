from flask import Flask, request

app = Flask(__name__)

@app.route('/callback', methods=['POST'])
def callback():
    data = request.json
    if 'type' not in data:
        return 'not vk'
    if data['type'] == 'confirmation':
        return 'ВАША_СТРОКА_ПОДТВЕРЖДЕНИЯ'  # Замените на вашу строку подтверждения
    return 'ok'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
