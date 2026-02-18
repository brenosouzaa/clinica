from datetime import datetime, timedelta, date
import urllib.parse
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import extract, func
from extensions import db
from models import User, Clinica, Agendamento, ConfigSite
from utils import save_image

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/painel/admin', methods=['GET', 'POST'])
@login_required
def dash_admin():
    if current_user.tipo != 'admin':
        return redirect(url_for('public.home'))

    active_tab = request.args.get('tab') or request.form.get('tab') or 'dashboard'
    link_wpp = None
    nome_cancelado = None
    
    # Variáveis essenciais para mostrar mensagens no HTML
    erro = None
    sucesso = None

    # --- LÓGICA DE POST ---
    if request.method == 'POST':
        acao = request.form.get('acao')
        
        if acao == 'cadastrar_dentista':
            try:
                # 1. Coleta os dados
                nome = request.form.get('nome')
                email = request.form.get('email').strip().lower() # Limpa espaços e minúsculo
                senha = request.form.get('senha')
                especialidade = request.form.get('especialidade')
                telefone = request.form.get('telefone')
                clinica_input = request.form.get('clinica_id')

                # 2. Validações básicas
                if not nome or not email or not senha:
                    erro = "Preencha todos os campos obrigatórios (Nome, Email, Senha)."
                else:
                    # 3. Verifica duplicidade
                    if User.query.filter_by(email=email).first():
                        erro = 'Erro: Este e-mail já está cadastrado no sistema.'
                    else:
                        # 4. Converte Clinica ID com segurança
                        clinica_id = int(clinica_input) if clinica_input and clinica_input.strip() else None

                        # 5. Cria e Salva
                        novo_dentista = User(
                            nome=nome,
                            email=email,
                            tipo='dentista',
                            clinica_id=clinica_id,
                            especialidade=especialidade,
                            telefone=telefone
                        )
                        novo_dentista.set_senha(senha)
                        
                        db.session.add(novo_dentista)
                        db.session.commit()
                        sucesso = 'Especialista cadastrado com sucesso!'
                
                active_tab = 'equipe'
                
            except Exception as e:
                db.session.rollback() # Destrava o banco
                erro = f"Erro técnico ao salvar: {str(e)}" # Mostra o erro real na tela
                print(f"ERRO PYTHON: {e}")
                active_tab = 'equipe'

        elif acao == 'nova_clinica':
            try:
                nova = Clinica(
                    nome=request.form.get('nome'),
                    bairro=request.form.get('bairro'),
                    endereco_completo=request.form.get('endereco'),
                    telefone=request.form.get('telefone')
                )
                db.session.add(nova)
                db.session.commit()
                sucesso = 'Unidade criada com sucesso!'
                active_tab = 'clinicas'
            except Exception as e:
                db.session.rollback()
                erro = f"Erro ao criar unidade: {str(e)}"
            
        elif acao == 'admin_agendar':
            try:
                p_busca = request.form.get('termo_busca')
                paciente = User.query.filter(
                    (User.email == p_busca) | (User.nome.ilike(f"%{p_busca}%")) | (User.telefone.like(f"%{p_busca}%"))
                ).filter_by(tipo='paciente').first()
                
                if paciente:
                    dt_str = f"{request.form.get('data')} {request.form.get('hora')}"
                    dt_obj = datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
                    
                    c_id = request.form.get('clinica_id')
                    d_id = request.form.get('dentista_id')
                    
                    novo_ag = Agendamento(
                        paciente_id=paciente.id,
                        dentista_id=int(d_id) if d_id else None,
                        clinica_id=int(c_id) if c_id else None, 
                        data_hora=dt_obj,
                        servico=request.form.get('servico'),
                        status='Confirmado', 
                        tipo_consulta='Agendamento Admin'
                    )
                    db.session.add(novo_ag)
                    db.session.commit()
                    sucesso = 'Agendamento realizado!'
                else:
                    erro = 'Paciente não encontrado.'
                active_tab = 'agenda'
            except Exception as e:
                db.session.rollback()
                erro = f"Erro no agendamento: {str(e)}"
            
        elif acao == 'cancelar_consulta':
            try:
                ag = Agendamento.query.get(request.form.get('id_agendamento'))
                if ag:
                    ag.status = 'Cancelado pelo Admin'
                    db.session.commit()
                    
                    paciente = ag.paciente
                    nome_cancelado = paciente.nome
                    if paciente.telefone:
                        phone = paciente.telefone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
                        msg = f"Olá {paciente.nome}, sua consulta de {ag.servico} ({ag.data_hora.strftime('%d/%m às %H:%M')}) foi cancelada."
                        link_wpp = f"https://wa.me/55{phone}?text={msg}"
                    
                    sucesso = 'Consulta cancelada.'
            except Exception as e:
                db.session.rollback()
                erro = f"Erro ao cancelar: {str(e)}"
                
        elif acao == 'excluir_user':
            try:
                u = User.query.get(request.form.get('id_user'))
                if u:
                    db.session.delete(u)
                    db.session.commit()
                    sucesso = 'Usuário removido.'
                else:
                    erro = 'Usuário não encontrado.'
            except Exception as e:
                db.session.rollback()
                erro = f"Erro ao excluir usuário: {str(e)}"
            active_tab = 'equipe'
            
        elif acao == 'excluir_clinica':
            try:
                c = Clinica.query.get(request.form.get('id_clinica'))
                if c:
                    db.session.delete(c)
                    db.session.commit()
                    sucesso = 'Clínica removida.'
            except Exception as e:
                db.session.rollback()
                erro = f"Erro ao excluir clínica: {str(e)}"
            active_tab = 'clinicas'
            
        elif acao == 'config_site':
            if 'img_agendamento' in request.files:
                save_image(request.files['img_agendamento'])
            
            # --- SALVAR TEXTOS E OUTRAS IMAGENS (NOVIDADE) ---
            config = ConfigSite.query.first()
            if not config:
                config = ConfigSite()
                db.session.add(config)

            # Textos
            config.titulo_principal = request.form.get('titulo_principal')
            config.titulo_destaque = request.form.get('titulo_destaque')
            config.subtitulo = request.form.get('subtitulo')
            
            # Novos campos (se existirem no seu modelo e html)
            if request.form.get('titulo_mapa'): config.titulo_mapa = request.form.get('titulo_mapa')
            if request.form.get('desc_mapa'): config.desc_mapa = request.form.get('desc_mapa')

            # Imagens
            if 'img_especialistas' in request.files:
                p = save_image(request.files['img_especialistas'])
                if p: config.img_especialistas = p
            
            if 'img_visita' in request.files:
                p = save_image(request.files['img_visita'])
                if p: config.img_visita = p

            db.session.commit()
            sucesso = 'Configurações salvas.'
            active_tab = 'site'

    # --- ESTATÍSTICAS ---
   # --- ESTATÍSTICAS E FILTRO (CORRIGIDO) ---
    hoje = datetime.now().date()
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    inicio_mes = hoje.replace(day=1)
    inicio_ano = hoje.replace(month=1, day=1)

    filtro_dash = request.args.get('filtro_unidade_dash')
    
    # Queries Iniciais
    query_ag = Agendamento.query
    query_dt = User.query.filter_by(tipo='dentista') # Pega todos os dentistas

    if filtro_dash and filtro_dash != "":
        # Filtra agendamentos
        query_ag = query_ag.join(User, Agendamento.dentista_id == User.id).filter(User.clinica_id == filtro_dash)
        # Filtra dentistas (AQUI ESTAVA O PROBLEMA ANTES)
        query_dt = query_dt.filter_by(clinica_id=filtro_dash)

    lista_ag = query_ag.all()
    
    # Conta a equipe filtrada
    total_equipe_filtrada = query_dt.count()
    
    stats = {
        'hoje': sum(1 for c in lista_ag if c.data_hora.date() == hoje and 'Cancelado' not in c.status),
        'total_concluidas': sum(1 for c in lista_ag if c.status == 'Concluído'),
        'total_canceladas': sum(1 for c in lista_ag if 'Cancelado' in c.status),
        'semana_concluidas': sum(1 for c in lista_ag if c.status == 'Concluído' and c.data_hora.date() >= inicio_semana),
        'mes_concluidas': sum(1 for c in lista_ag if c.status == 'Concluído' and c.data_hora.date() >= inicio_mes),
        'ano_concluidas': sum(1 for c in lista_ag if c.status == 'Concluído' and c.data_hora.date() >= inicio_ano),
        'semana_canceladas': sum(1 for c in lista_ag if 'Cancelado' in c.status and c.data_hora.date() >= inicio_semana),
        'mes_canceladas': sum(1 for c in lista_ag if 'Cancelado' in c.status and c.data_hora.date() >= inicio_mes),
        'ano_canceladas': sum(1 for c in lista_ag if 'Cancelado' in c.status and c.data_hora.date() >= inicio_ano),
        'equipe_ativa': total_equipe_filtrada # Passa o valor correto para o HTML
    }
    # --- HISTÓRICO GERAL ---
    from sqlalchemy.orm import aliased
    Paciente = aliased(User)
    Dentista = aliased(User)

    query_hist = db.session.query(Agendamento).join(Dentista, Agendamento.dentista_id == Dentista.id).join(Paciente, Agendamento.paciente_id == Paciente.id).order_by(Agendamento.data_hora.desc())
    
    if request.args.get('filtro_clinica'):
        query_hist = query_hist.filter(Dentista.clinica_id == request.args.get('filtro_clinica'))
    if request.args.get('filtro_medico'):
        query_hist = query_hist.filter(Agendamento.dentista_id == request.args.get('filtro_medico'))
    
    if request.args.get('filtro_data'):
        try:
            dt_f = datetime.strptime(request.args.get('filtro_data'), '%Y-%m-%d').date()
            query_hist = query_hist.filter(Agendamento.data_hora >= dt_f, Agendamento.data_hora < dt_f + timedelta(days=1))
        except: pass
    elif request.args.get('filtro_mes'):
        try:
            ano_mes = request.args.get('filtro_mes').split('-')
            query_hist = query_hist.filter(extract('year', Agendamento.data_hora) == int(ano_mes[0]), extract('month', Agendamento.data_hora) == int(ano_mes[1]))
        except: pass
    elif request.args.get('filtro_ano'):
        try:
            query_hist = query_hist.filter(extract('year', Agendamento.data_hora) == int(request.args.get('filtro_ano')))
        except: pass

    filtro_status = request.args.get('filtro_status')
    if filtro_status:
        if filtro_status == 'agendados': query_hist = query_hist.filter(Agendamento.status.in_(['Agendado', 'Confirmado', 'Em Andamento', 'Agendado (Admin)']))
        elif filtro_status == 'concluidos': query_hist = query_hist.filter(Agendamento.status == 'Concluído')
        elif filtro_status == 'cancelados': query_hist = query_hist.filter(Agendamento.status.ilike('%Cancelado%'))

    if request.args.get('busca_paciente'):
        termo = request.args.get('busca_paciente')
        if termo.isdigit():
            query_hist = query_hist.filter((Paciente.id == int(termo)) | (Paciente.telefone.like(f"%{termo}%")))
        else:
            query_hist = query_hist.filter((Paciente.nome.ilike(f"%{termo}%")) | (Paciente.email.ilike(f"%{termo}%")))

    historico_global = query_hist.all()

    # --- AGENDA GLOBAL ---
    query_agenda = Agendamento.query.filter(Agendamento.data_hora >= datetime.now()).order_by(Agendamento.data_hora)
    filtro_agenda = request.args.get('filtro_agenda_clinica')
    if filtro_agenda and filtro_agenda != "":
        query_agenda = query_agenda.join(User, Agendamento.dentista_id == User.id).filter(User.clinica_id == filtro_agenda)
        if request.args.get('tab') == 'agenda': active_tab = 'agenda'

    # DADOS PARA O HTML
    # Pega todos os dentistas para a aba equipe (ignora filtro da dashboard)
    dentistas_geral = User.query.filter_by(tipo='dentista').all()
    
    dentistas_js = [{'id': d.id, 'nome': d.nome, 'clinica_id': d.clinica_id} for d in dentistas_geral]
    ocupados_admin = [{'d': str(a.dentista_id), 'dt': a.data_hora.strftime('%Y-%m-%d'), 'h': a.data_hora.strftime('%H:%M')} for a in Agendamento.query.filter(Agendamento.data_hora >= datetime.now()).all() if 'Cancelado' not in a.status]

    return render_template('dash_admin.html', 
                           stats=stats,
                           consultas=query_agenda.all(),
                           historico_global=historico_global,
                           dentistas=dentistas_geral, 
                           dentistas_js=dentistas_js,
                           ocupados_admin=ocupados_admin,
                           clinicas=Clinica.query.all(),
                           config=ConfigSite.query.first(),
                           active_tab=active_tab,
                           link_wpp=link_wpp,
                           nome_cancelado=nome_cancelado,
                           erro=erro,        # IMPORTANTE: Envia erro para o HTML
                           sucesso=sucesso)  # IMPORTANTE: Envia sucesso para o HTML