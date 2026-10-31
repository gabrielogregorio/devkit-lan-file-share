"""English is the source text and the key; PT_BR holds the Brazilian Portuguese line."""

from server.settings import SETTINGS

PT_BR = {
    "phone to PC files": "arquivos do celular pro PC",
    "{name}: on air (port {port})": "{name}: no ar (porta {port})",
    "{name}: starting…": "{name}: ligando…",
    "{name}: off": "{name}: desligado",
    "On": "Ligado",
    "On the phone: {ip}:{port}": "No celular: {ip}:{port}",
    "Address: {ip}:{port}": "Endereço: {ip}:{port}",
    "Open panel": "Abrir painel",
    "Phone not paired yet? Scan this in the app, or just open it: it finds this PC on the Wi-Fi.":
        "Celular ainda não pareado? Leia isto no app, ou só abra o app: ele acha este PC no Wi-Fi.",
    "Turn it on to pair the phone": "Ligue pra parear o celular",
    "Received": "Recebidos",
    "Nothing received yet. On the phone, tap Share and pick LAN File Share.":
        "Nada recebido ainda. No celular, toque em Compartilhar e escolha LAN File Share.",
    "Change folder": "Trocar pasta",
    "Keys": "Chaves",
    "Pairing makes a new key; old ones keep working until you revoke them.":
        "Parear gera uma chave nova; as antigas seguem valendo até você revogar.",
    "current": "atual",
    "old": "antiga",
    "revoked": "revogada",
    "Revoke": "Revogar",
    "{label} · created {created} · last used {used}": "{label} · criada {created} · último uso {used}",
    "Change password": "Trocar senha",
    "Open folder": "Abrir pasta",
    "Folder: {folder}": "Pasta: {folder}",
    "Choose folder…": "Escolher pasta…",
    "Change password…": "Trocar senha…",
    "Choose": "Escolher",
    "Cancel": "Cancelar",
    "Save": "Salvar",
    "New password (type the same one in the phone app):": "Senha nova (digite a mesma no app do celular):",
    "View log": "Ver log",
    "Install python3-segno to show the QR code.": "Instale o python3-segno pra mostrar o QR code.",
    "{name} did not start": "{name} não subiu",
    "exited with code {code}; see the log": "saiu com código {code}; veja o log",
}


def tr(text: str, language: str = SETTINGS.language, **values: object) -> str:
    line = PT_BR.get(text, text) if language == "pt-BR" else text

    return line.format(**values) if values else line
