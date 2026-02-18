import os
import re
from werkzeug.utils import secure_filename
from datetime import datetime
from models import Agendamento, Folga, User

# Configuração que você usava no app.py
UPLOAD_FOLDER = 'static/uploads'

def setup_upload_folder(app):
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def validar_email(email):
    if not email: return False
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email) is not None

def save_image(file):
    if file and file.filename:
        filename = secure_filename(file.filename)
        nome_final = f"{datetime.now().timestamp()}_{filename}"
        caminho = os.path.join(UPLOAD_FOLDER, nome_final)
        file.save(caminho)
        return f"/static/uploads/{nome_final}"
    return None

def verificar_conflito(dentista_id, data_hora_nova):
    conflito = Agendamento.query.filter(
        Agendamento.dentista_id == dentista_id,
        Agendamento.data_hora == data_hora_nova,
        Agendamento.status.notlike('Cancelado%')
    ).first()
    return conflito is not None

def verificar_dia_bloqueado(dentista_id, data_obj):
    # 1. Verifica folga avulsa
    folga = Folga.query.filter_by(dentista_id=dentista_id, data=data_obj.date()).first()
    if folga: return True
    # 2. Verifica folga semanal
    dentista = User.query.get(dentista_id)
    if dentista and dentista.dia_folga_semanal:
        dias_bloqueados = dentista.dia_folga_semanal.split(',')
        if str(data_obj.weekday()) in dias_bloqueados:
            return True
    return False

def limpar_telefone_filter(s):
    if not s: return ""
    return "".join(filter(str.isdigit, s))