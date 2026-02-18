from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from extensions import db
from models import User, Clinica, Agendamento
from utils import save_image, verificar_conflito, verificar_dia_bloqueado

paciente_bp = Blueprint('paciente', __name__)

@paciente_bp.route('/painel/paciente', methods=['GET', 'POST'])
@login_required
def paciente_dashboard():
    if current_user.tipo != 'paciente': return redirect('/')
    erro, sucesso = None, None

    if request.method == 'POST':
        acao = request.form.get('acao')
        
        if acao == 'agendar':
            d_id = request.form.get('dentista')
            c_id = request.form.get('clinica_id_agendamento')
            data_dia = request.form.get('data_dia')
            data_hora = request.form.get('data_hora')
            
            try:
                dt = datetime.strptime(f"{data_dia}T{data_hora}", '%Y-%m-%dT%H:%M')
                agora = datetime.now()

                # REGRA 1: Bloqueio de 2h e Passado
                if dt < (agora + timedelta(hours=2)):
                    erro = "Agendamentos requerem 2h de antecedência e não podem ser no passado."
                
                # REGRA 2: Pós 18h bloqueia 8h e 9h de amanhã
                elif agora.hour >= 18 and dt.date() == (date.today() + timedelta(days=1)) and dt.hour in [8, 9]:
                    erro = "Os horários de 08:00 e 09:00 de amanhã já estão fechados para novos agendamentos."

                elif not verificar_conflito(d_id, dt) and not verificar_dia_bloqueado(d_id, dt):
                    db.session.add(Agendamento(
                        paciente_id=current_user.id, dentista_id=d_id, clinica_id=c_id, 
                        data_hora=dt, servico=request.form.get('motivo_visual'), status='Agendado'
                    ))
                    db.session.commit()
                    sucesso = "Agendado com sucesso!"
                else:
                    erro = "Horário indisponível (Ocupado ou Médico de folga)."
            except: erro = "Preencha todos os campos."

        elif acao == 'perfil':
            senha = request.form.get('senha')
            email = request.form.get('email').strip().lower()
            endereco = request.form.get('endereco')
            telefone = request.form.get('telefone')
            nome = request.form.get('nome')

            # VALIDAÇÕES OBRIGATÓRIAS
            if not email or not senha or not endereco or not nome or not telefone:
                erro = "Todos os campos (Nome, Email, Senha, Telefone e Endereço) são obrigatórios."
            elif len(senha) < 6:
                erro = "A senha deve ter no mínimo 6 caracteres para ser segura."
            else:
                current_user.nome = nome
                current_user.email = email
                current_user.telefone = telefone
                current_user.endereco = endereco
                current_user.set_senha(senha) # Atualiza a senha
                
                if 'foto_perfil' in request.files:
                    path = save_image(request.files['foto_perfil'])
                    if path: current_user.foto_perfil = path
                db.session.commit()
                sucesso = "Dados atualizados!"

    # --- BUSCA E ORDENAÇÃO ---
    agora = datetime.now()
    todas = Agendamento.query.filter_by(paciente_id=current_user.id).all()
    
    # Futuras: Dia 17 primeiro, depois 18...
    futuras = [c for c in todas if c.data_hora >= agora and c.status in ['Agendado', 'Confirmado', 'Em Andamento']]
    futuras.sort(key=lambda x: x.data_hora)

    # Prontuário: Mais recentes no TOPO (Ordem decrescente estável)
    passadas = [c for c in todas if c.data_hora < agora or c.status == 'Concluído' or ('Cancelado' in c.status)]
    passadas.sort(key=lambda x: x.data_hora, reverse=True)

    # Lista de horários ocupados para o "Cinza" no HTML
    ocupados = [
        {'d': a.dentista_id, 'dt': a.data_hora.strftime('%Y-%m-%d'), 'h': a.data_hora.strftime('%H:%M')} 
        for a in Agendamento.query.filter(Agendamento.status.notlike('Cancelado%')).all()
    ]

    return render_template('dash_paciente.html', 
                           futuras=futuras, 
                           passadas=passadas, 
                           ocupados=ocupados, # Enviando os ocupados
                           dentistas=User.query.filter_by(tipo='dentista').all(), 
                           clinicas=Clinica.query.all(),
                           erro=erro, sucesso=sucesso,
                           date=date, agora=agora) # Enviando agora para regra das 18h
from datetime import datetime, timedelta