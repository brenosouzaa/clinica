import urllib.parse
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import desc, or_
from extensions import db
from models import User, Clinica, Agendamento, Folga, Portfolio, Prontuario
from utils import save_image, verificar_conflito, verificar_dia_bloqueado

dentista_bp = Blueprint('dentista', __name__)

@dentista_bp.route('/painel/dentista', methods=['GET', 'POST'])
@login_required
def dentista_dashboard():
    if current_user.tipo != 'dentista': return redirect('/')
    
    # --- AJUSTE DE FUSO HORÁRIO (-23.57, -46.67 / São Paulo) ---
    # UTC-3 fixo para garantir precisão
    agora_br = datetime.utcnow() - timedelta(hours=3)
    hoje_br = agora_br.date()

    active_tab = request.args.get('tab', 'agenda')
    erro, sucesso, whatsapp_link = None, None, None
    afetados_whatsapp = []
    
    paciente_em_atendimento = None
    historico_paciente = []
    lista_historico_geral = []

    # 1. HISTÓRICO GERAL
    query_hist = Agendamento.query.filter_by(dentista_id=current_user.id).order_by(desc(Agendamento.data_hora))
    busca_geral = request.args.get('busca_geral')
    filtro_ano = request.args.get('filtro_ano')
    filtro_mes = request.args.get('filtro_mes')
    filtro_data = request.args.get('filtro_data')

    if busca_geral:
        query_hist = query_hist.join(User, Agendamento.paciente_id == User.id).filter(
            or_(User.nome.ilike(f'%{busca_geral}%'), User.email.ilike(f'%{busca_geral}%'), User.telefone.ilike(f'%{busca_geral}%'))
        )
    if filtro_data: query_hist = query_hist.filter(db.func.date(Agendamento.data_hora) == filtro_data)
    else:
        if filtro_ano: query_hist = query_hist.filter(db.extract('year', Agendamento.data_hora) == filtro_ano)
        if filtro_mes: query_hist = query_hist.filter(db.extract('month', Agendamento.data_hora) == filtro_mes)
    
    lista_historico_geral = query_hist.all()

    # 2. SALA DE ATENDIMENTO
    id_paciente_str = request.args.get('id_paciente')
    if id_paciente_str and str(id_paciente_str).isdigit():
        id_pac = int(id_paciente_str)
        paciente_em_atendimento = User.query.get(id_pac)
        if paciente_em_atendimento:
            historico_paciente = Agendamento.query.filter_by(paciente_id=id_pac).order_by(desc(Agendamento.data_hora)).all()
            active_tab = 'atendimento'
        else:
            active_tab = 'agenda'

    if request.method == 'POST':
        acao = request.form.get('acao')

        if acao == 'iniciar_consulta':
            agendamento = Agendamento.query.get(request.form.get('id_agendamento'))
            if agendamento:
                agendamento.status = 'Em Andamento'
                db.session.commit()
                return redirect(url_for('dentista.dentista_dashboard', tab='atendimento', id_paciente=agendamento.paciente_id))

        elif acao == 'nao_compareceu':
            agendamento = Agendamento.query.get(request.form.get('id_agendamento'))
            if agendamento:
                agendamento.status = 'Não Compareceu'
                db.session.commit()
                sucesso = "Status atualizado."

        elif acao == 'finalizar_consulta':
            agendamento = Agendamento.query.get(request.form.get('id_agendamento'))
            if agendamento:
                if not Prontuario.query.filter_by(agendamento_id=agendamento.id).first():
                    db.session.add(Prontuario(
                        agendamento_id=agendamento.id, queixa=request.form.get('queixa'), 
                        procedimento=request.form.get('procedimento'), evolucao=request.form.get('evolucao'), 
                        proximos_passos=request.form.get('proximos_passos')
                    ))
                agendamento.status = 'Concluído'
                
                # Agendar Retorno
                r_data = request.form.get('retorno_data')
                r_hora = request.form.get('retorno_hora')
                if r_data and r_hora:
                    try:
                        dt = datetime.strptime(f"{r_data}T{r_hora}", '%Y-%m-%dT%H:%M')
                        
                        # Verifica se a data é hoje em BRASÍLIA
                        if dt.date() == hoje_br:
                            # Se for hoje, aplica regra de 2h baseada na hora BRASÍLIA
                            if dt < (agora_br + timedelta(hours=2)):
                                sucesso = "Finalizado (Retorno FALHOU: Mínimo 2h de antecedência)."
                                dt = None # Invalida para não agendar

                        if dt:
                            # Verifica Bloqueio de Data Específica
                            bloqueio_dia = Folga.query.filter_by(dentista_id=current_user.id, data=dt.date()).first()
                            
                            # Verifica Folga Fixa Semanal
                            dia_semana = str(dt.weekday()) # 0=Seg
                            dias_folga = current_user.dia_folga_semanal.split(',') if current_user.dia_folga_semanal else []
                            
                            if bloqueio_dia or (dia_semana in dias_folga):
                                sucesso = "Finalizado (Retorno falhou: Data Bloqueada ou Folga Fixa)."
                            elif not verificar_conflito(current_user.id, dt):
                                cid = agendamento.clinica_id 
                                db.session.add(Agendamento(
                                    paciente_id=agendamento.paciente_id, 
                                    dentista_id=current_user.id,
                                    clinica_id=cid,
                                    data_hora=dt, 
                                    servico="Retorno", 
                                    tipo_consulta="Retorno", 
                                    status="Confirmado"
                                ))
                                sucesso = "Finalizado e retorno agendado."
                            else:
                                sucesso = "Finalizado (Retorno falhou: Horário ocupado)."
                    except: pass
                else:
                    sucesso = "Consulta finalizada com sucesso."
                
                db.session.commit()
                return redirect(url_for('dentista.dentista_dashboard', tab='agenda'))

        elif acao == 'cancelar_consulta':
            c = Agendamento.query.get(request.form.get('id_agendamento'))
            if c:
                c.status = 'Cancelado (Pendente Aviso)' # Marca como pendente para aparecer no histórico
                db.session.commit()
                sucesso = "Cancelado. O paciente apareceu na lista de pendências de aviso."

        elif acao == 'marcar_como_avisado':
            # Remove da lista de pendências (altera status final)
            c = Agendamento.query.get(request.form.get('id_agendamento'))
            if c:
                c.status = 'Cancelado (Avisado)'
                db.session.commit()
                sucesso = "Marcado como avisado."
                active_tab = 'emergencia'

        elif acao == 'agendar':
            d_id = request.form.get('dentista_selecionado')
            c_id = request.form.get('clinica_id_agendamento') 
            
            if not d_id or not c_id:
                erro = "Selecione a Clínica e o Especialista."
            else:
                try:
                    dt = datetime.strptime(f"{request.form.get('data_dia')}T{request.form.get('data_hora')}", '%Y-%m-%dT%H:%M')
                    
                    # Validações com Hora Brasil
                    if dt < agora_br:
                        erro = "Data/Hora no passado."
                    elif dt < (agora_br + timedelta(hours=2)):
                        erro = "Mínimo 2 horas de antecedência."
                    elif agora_br.hour >= 18:
                        amanha = hoje_br + timedelta(days=1)
                        if dt.date() == amanha and dt.hour in [8, 9]:
                            erro = "Horários de 08h e 09h de amanhã indisponíveis (Regra das 18h)."
                        else:
                            # Tenta agendar se passou nas regras de tempo
                            if not verificar_conflito(d_id, dt) and not verificar_dia_bloqueado(d_id, dt):
                                db.session.add(Agendamento(paciente_id=current_user.id, dentista_id=d_id, clinica_id=c_id, data_hora=dt, servico=request.form.get('tipo_consulta'), status='Agendado'))
                                db.session.commit()
                                sucesso = "Agendado!"
                            else:
                                erro = "Horário ocupado ou dia bloqueado."
                    # Validação normal
                    elif not verificar_conflito(d_id, dt) and not verificar_dia_bloqueado(d_id, dt):
                        db.session.add(Agendamento(paciente_id=current_user.id, dentista_id=d_id, clinica_id=c_id, data_hora=dt, servico=request.form.get('tipo_consulta'), status='Agendado'))
                        db.session.commit()
                        sucesso = "Agendado!"
                    else:
                        erro = "Horário ocupado ou dia bloqueado."
                        
                except Exception as e:
                    erro = f"Erro: {str(e)}"

        elif acao == 'bloqueio_semanal':
             active_tab = 'emergencia'
             dias = request.form.getlist('dia_semana')
             
             if request.form.get('operacao') == 'limpar' or not dias: 
                 current_user.dia_folga_semanal = None
                 sucesso = "Folgas semanais removidas."
             else: 
                 current_user.dia_folga_semanal = ",".join(dias)
                 
                 # Varre agendas futuras para cancelar
                 inicio_hoje = datetime.combine(hoje_br, datetime.min.time())
                 futuras = Agendamento.query.filter(
                     Agendamento.dentista_id == current_user.id, 
                     Agendamento.data_hora >= inicio_hoje, 
                     Agendamento.status.notlike('Cancelado%')
                 ).all()
                 
                 count = 0
                 for ag in futuras:
                     if str(ag.data_hora.weekday()) in dias:
                         ag.status = 'Cancelado (Pendente Aviso)' # Joga para o histórico de aviso
                         count += 1
                 
                 sucesso = f"Folgas salvas. {count} consultas canceladas (verifique a lista de avisos)."
             
             db.session.commit()

        elif acao == 'bloqueio':
             active_tab = 'emergencia'
             try:
                data_bloq = datetime.strptime(request.form.get('data_bloqueio'), '%Y-%m-%d').date()
                db.session.add(Folga(data=data_bloq, motivo=request.form.get('motivo'), dentista_id=current_user.id))
                
                inicio = datetime.combine(data_bloq, datetime.min.time())
                fim = datetime.combine(data_bloq, datetime.max.time())
                
                afetadas = Agendamento.query.filter(
                    Agendamento.dentista_id == current_user.id, 
                    Agendamento.data_hora >= inicio, 
                    Agendamento.data_hora <= fim, 
                    Agendamento.status.notlike('Cancelado%')
                ).all()
                
                for c in afetadas:
                    c.status = 'Cancelado (Pendente Aviso)' # Joga para o histórico de aviso
                
                db.session.commit()
                sucesso = f"Dia bloqueado. {len(afetadas)} consultas foram canceladas e requerem aviso."
             except Exception as e: 
                 erro = f"Erro: {str(e)}"

        elif acao == 'excluir_bloqueio':
             Folga.query.filter_by(id=request.form.get('id_bloqueio')).delete(); db.session.commit(); sucesso = "Removido."

        elif acao == 'portfolio':
             f = request.files.get('foto')
             if f:
                 path = save_image(f)
                 db.session.add(Portfolio(titulo=request.form.get('titulo'), descricao=request.form.get('descricao'), imagem_arquivo=path, dentista_id=current_user.id))
                 db.session.commit()
                 sucesso = "Publicado."

        elif acao == 'perfil':
            current_user.nome = request.form.get('nome'); current_user.telefone = request.form.get('telefone')
            current_user.especialidade = request.form.get('especialidade'); current_user.bio = request.form.get('bio')
            cid_raw = request.form.get('clinica_id')
            if cid_raw and cid_raw.isdigit(): current_user.clinica_id = int(cid_raw)
            if request.form.get('senha'):
               current_user.set_senha(request.form.get('senha'))
            if 'foto_perfil' in request.files:
                p = save_image(request.files['foto_perfil'])
                if p: current_user.foto_perfil = p
            db.session.commit(); sucesso = "Salvo."

    # Dados Finais
    todas = Agendamento.query.filter_by(dentista_id=current_user.id).order_by(Agendamento.data_hora).all()
    agenda_hoje = [a for a in todas if a.data_hora.date() == hoje_br and not a.status.startswith('Cancelado')]
    agenda_futura = [a for a in todas if a.data_hora.date() > hoje_br and not a.status.startswith('Cancelado')]
    
    # LISTA DE PENDÊNCIAS DE AVISO (Para a aba Bloqueio)
    pendentes_aviso = Agendamento.query.filter_by(dentista_id=current_user.id, status='Cancelado (Pendente Aviso)').order_by(Agendamento.data_hora).all()
    
    todos_dentistas = User.query.filter_by(tipo='dentista').all()
    folgas_lista = Folga.query.filter_by(dentista_id=current_user.id).order_by(Folga.data.desc()).all()
    agendamentos_ocupados = [{'dentista_id': a.dentista_id, 'data': a.data_hora.strftime('%Y-%m-%d'), 'hora': a.data_hora.strftime('%H:%M')} for a in Agendamento.query.filter(Agendamento.status.notlike('Cancelado%')).all()]
    
    return render_template('dash_dentista.html', 
                        agenda_hoje=agenda_hoje, 
                        agenda_futura=agenda_futura, 
                        clinicas=Clinica.query.all(), 
                        todos_dentistas=todos_dentistas, 
                        posts=Portfolio.query.filter_by(dentista_id=current_user.id).all(), 
                        erro=erro, sucesso=sucesso, 
                        pendentes_aviso=pendentes_aviso, # Nova lista para o HTML
                        active_tab=active_tab, 
                        paciente_atendimento=paciente_em_atendimento, 
                        historico_paciente=historico_paciente, 
                        historico_geral=lista_historico_geral, 
                        folgas=folgas_lista, 
                        agendamentos_ocupados=agendamentos_ocupados,
                        data_atual=agora_br, 
                        date=date)