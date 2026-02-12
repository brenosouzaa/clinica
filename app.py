import os
import re
import urllib.parse
import random 
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, date, timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave_premium_2026'

# --- SUA CONEXÃO ORIGINAL (MANTIDA) ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:123789ab@localhost/clinica'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuração de Uploads
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- FILTRO PERSONALIZADO ---
@app.template_filter('limpar_telefone')
def limpar_telefone_filter(s):
    if not s:
        return ""
    return "".join(filter(str.isdigit, s))

# --- FUNÇÕES DE VALIDAÇÃO E UPLOAD ---
def validar_email(email):
    if not email: return False
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email) is not None

# Nova função para salvar imagens no servidor
def save_image(file):
    if file and file.filename:
        filename = secure_filename(file.filename)
        # Adiciona timestamp para evitar nomes duplicados
        nome_final = f"{datetime.now().timestamp()}_{filename}"
        caminho = os.path.join(app.config['UPLOAD_FOLDER'], nome_final)
        file.save(caminho)
        return f"/static/uploads/{nome_final}"
    return None

# --- MODELOS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    senha = db.Column(db.String(100)) 
    tipo = db.Column(db.String(20)) 
    
    telefone = db.Column(db.String(20))
    endereco = db.Column(db.String(200))
    # Alterado para permitir nulo (para dentistas sem foto inicial)
    foto_perfil = db.Column(db.String(200), nullable=True, default='https://cdn-icons-png.flaticon.com/512/149/149071.png')
    especialidade = db.Column(db.String(100))
    bio = db.Column(db.Text)

class Clinica(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    endereco_completo = db.Column(db.String(300))
    bairro = db.Column(db.String(100))
    telefone = db.Column(db.String(20))
    # Novos campos para o horário:
    horario_abertura = db.Column(db.String(5), default="08:00")
    horario_fechamento = db.Column(db.String(5), default="18:00")

class Agendamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_hora = db.Column(db.DateTime)
    servico = db.Column(db.String(100))
    observacoes = db.Column(db.Text)
    tipo_consulta = db.Column(db.String(50), default='Avaliação') 
    status = db.Column(db.String(50), default='Agendado') 
    
    paciente_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    dentista_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    clinica_id = db.Column(db.Integer, db.ForeignKey('clinica.id'))
    
    paciente = db.relationship('User', foreign_keys=[paciente_id], backref='consultas_paciente')
    dentista = db.relationship('User', foreign_keys=[dentista_id], backref='consultas_dentista')
    clinica = db.relationship('Clinica')

class Folga(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date)
    motivo = db.Column(db.String(200))
    dentista_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Portfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100))
    descricao = db.Column(db.Text)
    imagem_arquivo = db.Column(db.String(500))
    aprovado = db.Column(db.Boolean, default=True)
    dentista_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    dentista = db.relationship('User', backref=db.backref('meus_posts', order_by='Portfolio.id.desc()'))

class ConfigSite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Home e Banner
    titulo_principal = db.Column(db.String(200), default="Design de Sorrisos")
    cor_titulo = db.Column(db.String(20), default="#1A1A1A")
    titulo_destaque = db.Column(db.String(200), default="Ultra Realista.")
    cor_destaque = db.Column(db.String(20), default="#C6A87C")
    subtitulo = db.Column(db.String(500), default="Tecnologia, arte e hospitalidade.")
    cor_subtitulo = db.Column(db.String(20), default="#666666")
    img_agendamento = db.Column(db.String(500), default="https://images.unsplash.com/photo-1606811971618-4486d14f3f99?q=80&w=1000")
    img_especialistas = db.Column(db.String(500), default="https://images.unsplash.com/photo-1622253692010-333f2da6031d?q=80&w=500")
    
    # Seção: Sua Próxima Visita
    titulo_visita = db.Column(db.String(200), default="Sua Próxima Visita")
    desc_visita = db.Column(db.String(500), default="Prepare-se para uma experiência única.")
    img_visita = db.Column(db.String(500), default="https://images.unsplash.com/photo-1609840114035-3c981b782dfe?q=80&w=500")
    
    # Seção: Mapa
    titulo_mapa = db.Column(db.String(200), default="Nossas Unidades")
    desc_mapa = db.Column(db.String(500), default="Localização privilegiada e fácil acesso.")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- REGRAS ---
def verificar_conflito(dentista_id, data_hora_nova):
    conflito = Agendamento.query.filter(
        Agendamento.dentista_id == dentista_id,
        Agendamento.data_hora == data_hora_nova,
        Agendamento.status.notlike('Cancelado%')
    ).first()
    return conflito is not None

def verificar_dia_bloqueado(dentista_id, data_obj):
    folga = Folga.query.filter_by(dentista_id=dentista_id, data=data_obj.date()).first()
    return folga is not None

def validar_horario_comercial(data_obj):
    return None

# --- ROTAS GERAIS ---

@app.route('/')
def home():
    # ATUALIZADO: Passa os dentistas reais para a home
    return render_template('home.html', 
                           content=ConfigSite.query.first() or ConfigSite(), 
                           dentistas=User.query.filter_by(tipo='dentista').all())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        user = User.query.filter_by(email=email).first()
        if user and user.senha == senha:
            login_user(user)
            if user.tipo == 'admin': return redirect('/painel/admin')
            if user.tipo == 'dentista': return redirect('/painel/dentista')
            return redirect('/painel/paciente')
        else:
            flash('Login inválido.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        senha = request.form.get('senha')
        metodo = request.form.get('metodo_envio') # 'email' ou 'whatsapp'
        
        # 1. VALIDAÇÃO DUPLA (EMAIL OU TELEFONE) - ATUALIZADO
        user_existente = User.query.filter((User.email == email) | (User.telefone == telefone)).first()
        
        if user_existente:
            flash('Este E-mail ou Telefone já está cadastrado.')
            return redirect(url_for('register'))
        
        # 2. GERAÇÃO DO CÓDIGO
        codigo = str(random.randint(100000, 999999))
        session['temp_user'] = {'nome': nome, 'email': email, 'telefone': telefone, 'senha': senha, 'codigo': codigo}
        
        # 3. SCRIPTS DE ENVIO SIMULADO - ATUALIZADO
        print("\n" + "="*60)
        if metodo == 'email':
            print(f"📧 [SIMULAÇÃO DE ENVIO DE E-MAIL PARA: {email}]")
            print("-" * 60)
            print(f"Assunto: Bem-vindo ao L'Odontologie - Acesso Exclusivo")
            print("-" * 60)
            print(f"Prezado(a) {nome},")
            print("\nÉ uma imensa satisfação recebê-lo em nossa clínica.")
            print("Para validar sua adesão ao nosso quadro de membros exclusivos,")
            print("por favor utilize o código de segurança abaixo:")
            print(f"\n✨ {codigo} ✨")
            print("\nEstamos prontos para oferecer a excelência que o seu sorriso merece.")
            print("\nAtenciosamente,")
            print("Equipe L'Odontologie.")
        else:
            print(f"📱 [SIMULAÇÃO DE ENVIO WHATSAPP PARA: {telefone}]")
            print("-" * 60)
            print(f"L'Odontologie: Olá {nome}, seu código de acesso é {codigo}.")
        print("="*60 + "\n")
        
        return redirect(url_for('confirmar_codigo'))
    
    return render_template('register.html')

@app.route('/confirmar-codigo', methods=['GET', 'POST'])
def confirmar_codigo():
    if 'temp_user' not in session: return redirect(url_for('register'))
    
    if request.method == 'POST':
        codigo_digitado = request.form.get('codigo')
        if codigo_digitado == session['temp_user']['codigo']:
            dados = session['temp_user']
            novo_user = User(
                nome=dados['nome'], email=dados['email'], 
                telefone=dados['telefone'], senha=dados['senha'], tipo='paciente'
            )
            db.session.add(novo_user)
            db.session.commit()
            
            session.pop('temp_user', None)
            flash('Conta criada com sucesso! Faça login.')
            return redirect(url_for('login'))
        else:
            flash('Código incorreto.')
            
    return render_template('confirm_code.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_request():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            codigo = str(random.randint(100000, 999999))
            print(f"\n >>> RECUPERAÇÃO SENHA PARA {user.nome}: {codigo} <<<\n")
            session['reset_temp'] = {'user_id': user.id, 'codigo': codigo, 'email': user.email}
            flash('Código enviado para seu WhatsApp!')
            return redirect(url_for('reset_confirm'))
        else:
            flash('E-mail não encontrado.')
            
    return render_template('reset_request.html')

@app.route('/reset-confirm', methods=['GET', 'POST'])
def reset_confirm():
    if 'reset_temp' not in session: return redirect(url_for('login'))
        
    if request.method == 'POST':
        codigo_digitado = request.form.get('codigo')
        nova_senha = request.form.get('senha')
        
        if codigo_digitado == session['reset_temp']['codigo']:
            user = User.query.get(session['reset_temp']['user_id'])
            user.senha = nova_senha
            db.session.commit()
            session.pop('reset_temp', None)
            flash('Senha alterada! Entre agora.')
            return redirect(url_for('login'))
        else:
            flash('Código incorreto.')
            
    return render_template('reset_confirm.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')

# --- ROTA DE UNIDADES ---
@app.route('/unidades')
def unidades():
    lista_clinicas = Clinica.query.all()
    if not lista_clinicas:
        lista_clinicas = [
            Clinica(nome='Matriz Jardins', bairro='Jardins', endereco_completo='Rua Oscar Freire, 500, São Paulo', telefone='(11) 3003-0000'),
            Clinica(nome='Unidade Faria Lima', bairro='Itaim Bibi', endereco_completo='Av. Brig. Faria Lima, 2000, São Paulo', telefone='(11) 3003-0001'),
            Clinica(nome='Unidade Alphaville', bairro='Barueri', endereco_completo='Alameda Rio Negro, 100, Barueri', telefone='(11) 3003-0002')
        ]
    return render_template('unidades.html', clinicas=lista_clinicas)

@app.route('/portfolio')
def portfolio_publico():
    return render_template('portfolio.html', posts=Portfolio.query.filter_by(aprovado=True).all())

@app.route('/profissionais')
def lista_profissionais():
    return render_template('profissionais.html', dentistas=User.query.filter_by(tipo='dentista').all())

# --- DENTISTA ---
@app.route('/painel/dentista', methods=['GET', 'POST'])
@login_required
def dentista_dashboard():
    if current_user.tipo != 'dentista': return redirect('/')
    
    erro = None
    sucesso = None
    whatsapp_link = None
    afetados_whatsapp = []
    active_tab = 'agenda'

    if request.method == 'POST':
        acao = request.form.get('acao')

        if acao == 'cancelar_consulta':
            active_tab = 'agenda'
            id_agendamento = request.form.get('id_agendamento')
            consulta = Agendamento.query.get(id_agendamento)
            if consulta and consulta.dentista_id == current_user.id:
                consulta.status = 'Cancelado pelo Dentista'
                db.session.commit()
                tel_limpo = ''.join(filter(str.isdigit, consulta.paciente.telefone or ''))
                msg = f"Olá {consulta.paciente.nome}, sua consulta do dia {consulta.data_hora.strftime('%d/%m às %H:%M')} precisou ser cancelada. Por favor, acesse para reagendar."
                whatsapp_link = f"https://wa.me/55{tel_limpo}?text={urllib.parse.quote(msg)}"
                sucesso = "Consulta cancelada."
            else: erro = "Erro ao cancelar."

        elif acao == 'bloqueio':
            active_tab = 'emergencia'
            data_str = request.form.get('data_bloqueio')
            motivo = request.form.get('motivo')
            try:
                data_bloq = datetime.strptime(data_str, '%Y-%m-%d').date()
                db.session.add(Folga(data=data_bloq, motivo=motivo, dentista_id=current_user.id))
                
                inicio = datetime.combine(data_bloq, datetime.min.time())
                fim = datetime.combine(data_bloq, datetime.max.time())
                consultas = Agendamento.query.filter(
                    Agendamento.dentista_id == current_user.id,
                    Agendamento.data_hora >= inicio, 
                    Agendamento.data_hora <= fim,
                    Agendamento.status.notlike('Cancelado%')
                ).all()
                
                count = 0
                for c in consultas:
                    c.status = 'Cancelado (Emergência)'
                    count += 1
                    tel = ''.join(filter(str.isdigit, c.paciente.telefone or ''))
                    msg = f"Olá {c.paciente.nome}, devido a um imprevisto ({motivo}), cancelamos os atendimentos de {data_bloq.strftime('%d/%m')}. Por favor, remarque."
                    afetados_whatsapp.append({'nome': c.paciente.nome, 'link': f"https://wa.me/55{tel}?text={urllib.parse.quote(msg)}"})
                
                db.session.commit()
                sucesso = f"Dia bloqueado. {count} consultas canceladas."
            except: erro = "Erro ao bloquear."

        elif acao == 'agendar':
            active_tab = 'agendar'
            termo = request.form.get('termo_busca')
            paciente = User.query.filter_by(email=termo, tipo='paciente').first()
            if not paciente:
                paciente = User.query.filter_by(telefone=termo, tipo='paciente').first()

            if not paciente:
                erro = "Paciente não encontrado (Busque por Email ou Telefone)."
            else:
                data_str = f"{request.form.get('data_dia')}T{request.form.get('data_hora')}"
                try:
                    data_obj = datetime.strptime(data_str, '%Y-%m-%dT%H:%M')
                    if verificar_conflito(current_user.id, data_obj):
                        erro = "Horário ocupado."
                    else:
                        novo = Agendamento(
                            paciente_id=paciente.id, dentista_id=current_user.id, clinica_id=1,
                            data_hora=data_obj, servico=request.form.get('servico'),
                            observacoes=request.form.get('observacoes'),
                            tipo_consulta=request.form.get('tipo_consulta'), status='Confirmado'
                        )
                        db.session.add(novo)
                        db.session.commit()
                        sucesso = f"Agendado para {paciente.nome}!"
                except: erro = "Data inválida."

        elif acao == 'portfolio':
            active_tab = 'portfolio'
            file = request.files.get('foto')
            if file and file.filename != '':
                # ALTERADO: Usa função save_image
                path = save_image(file)
                db.session.add(Portfolio(titulo=request.form.get('titulo'), descricao=request.form.get('descricao'), imagem_arquivo=path, dentista_id=current_user.id))
                db.session.commit()
                sucesso = "Publicado."
            else: erro = "Erro na foto."

        elif acao == 'perfil':
            active_tab = 'perfil'
            current_user.nome = request.form.get('nome')
            current_user.telefone = request.form.get('telefone')
            current_user.especialidade = request.form.get('especialidade')
            current_user.bio = request.form.get('bio')
            s = request.form.get('senha')
            if s and s.strip(): current_user.senha = s
            if 'foto_perfil' in request.files:
                # ALTERADO: Usa função save_image
                path = save_image(request.files['foto_perfil'])
                if path: current_user.foto_perfil = path
            db.session.commit()
            sucesso = "Perfil salvo."

    hoje = date.today()
    todas = Agendamento.query.filter_by(dentista_id=current_user.id).order_by(Agendamento.data_hora).all()
    agenda_hoje = [a for a in todas if a.data_hora.date() == hoje and not a.status.startswith('Cancelado')]
    agenda_futura = [a for a in todas if a.data_hora.date() > hoje and not a.status.startswith('Cancelado')]

    return render_template('dash_dentista.html', agenda_hoje=agenda_hoje, agenda_futura=agenda_futura, clinicas=Clinica.query.all(), posts=Portfolio.query.filter_by(dentista_id=current_user.id).all(), erro=erro, sucesso=sucesso, afetados=afetados_whatsapp, whatsapp_link=whatsapp_link, active_tab=active_tab)

# --- PACIENTE ---
@app.route('/painel/paciente', methods=['GET', 'POST'])
@login_required
def paciente_dashboard():
    if current_user.tipo != 'paciente': return redirect('/')
    erro, sucesso = None, None

    if request.method == 'POST':
        acao = request.form.get('acao')
        if acao == 'agendar':
            d_id = request.form.get('dentista')
            dt_str = f"{request.form.get('data_dia')}T{request.form.get('data_hora')}"
            try:
                dt_obj = datetime.strptime(dt_str, '%Y-%m-%dT%H:%M')
                if Folga.query.filter_by(dentista_id=d_id, data=dt_obj.date()).first(): erro = "Dia bloqueado."
                elif verificar_conflito(d_id, dt_obj): erro = "Horário indisponível."
                else:
                    db.session.add(Agendamento(paciente_id=current_user.id, dentista_id=d_id, clinica_id=1, data_hora=dt_obj, servico=request.form.get('motivo_visual'), status='Agendado'))
                    db.session.commit()
                    sucesso = "Agendado!"
            except: erro = "Erro."
        elif acao == 'cancelar':
            a = Agendamento.query.get(request.form.get('id_agendamento'))
            if a and a.paciente_id == current_user.id:
                a.status = 'Cancelado pelo Paciente'
                db.session.commit()
                sucesso = "Cancelado."
        elif acao == 'perfil':
            current_user.nome = request.form.get('nome')
            current_user.telefone = request.form.get('telefone')
            current_user.endereco = request.form.get('endereco')
            novo_email = request.form.get('email')
            if novo_email != current_user.email:
                if not User.query.filter_by(email=novo_email).first():
                    current_user.email = novo_email
                else: erro = "Email já em uso."
            
            s = request.form.get('senha')
            if s: current_user.senha = s
            if 'foto_perfil' in request.files:
                # ALTERADO: Usa função save_image
                path = save_image(request.files['foto_perfil'])
                if path: current_user.foto_perfil = path
            if not erro: 
                db.session.commit()
                sucesso = "Salvo."

    agora = datetime.now()
    todas = Agendamento.query.filter_by(paciente_id=current_user.id).order_by(Agendamento.data_hora).all()
    futuras = [c for c in todas if c.data_hora >= agora and not c.status.startswith('Cancelado')]
    passadas = [c for c in todas if c.data_hora < agora or c.status.startswith('Cancelado')]
    
    return render_template('dash_paciente.html', futuras=futuras, passadas=passadas, dentistas=User.query.filter_by(tipo='dentista').all(), clinicas=Clinica.query.all(), erro=erro, sucesso=sucesso)

# --- ADMIN ---
@app.route('/painel/admin', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.tipo != 'admin': return redirect('/')
    
    config = ConfigSite.query.first() or ConfigSite()
    sucesso = None
    erro = None
    afetados_whatsapp = []
    active_tab = 'dashboard'

    if request.method == 'POST':
        acao = request.form.get('acao')

        # 1. CONFIGURAÇÕES DO SITE (ATUALIZADO COM UPLOAD DE IMAGEM)
        if acao == 'config_site':
            active_tab = 'site'
            config.titulo_principal = request.form.get('titulo_principal')
            config.cor_titulo = request.form.get('cor_titulo')
            config.titulo_destaque = request.form.get('titulo_destaque')
            config.cor_destaque = request.form.get('cor_destaque')
            config.subtitulo = request.form.get('subtitulo')
            config.cor_subtitulo = request.form.get('cor_subtitulo')
            config.titulo_visita = request.form.get('titulo_visita')
            config.desc_visita = request.form.get('desc_visita')
            config.titulo_mapa = request.form.get('titulo_mapa')
            config.desc_mapa = request.form.get('desc_mapa')
            
            # ATUALIZADO: Uploads de Imagens (Salva Arquivo)
            if 'img_agendamento' in request.files:
                path = save_image(request.files['img_agendamento'])
                if path: config.img_agendamento = path
            
            if 'img_especialistas' in request.files:
                path = save_image(request.files['img_especialistas'])
                if path: config.img_especialistas = path

            if 'img_visita' in request.files:
                path = save_image(request.files['img_visita'])
                if path: config.img_visita = path

            db.session.add(config)
            db.session.commit()
            sucesso = "Design do site atualizado com sucesso."

        # 2. CADASTRAR DENTISTA (ATUALIZADO: SEM FOTO)
        elif acao == 'cadastrar_dentista':
            active_tab = 'equipe'
            email = request.form.get('email')
            if User.query.filter_by(email=email).first():
                erro = "Este e-mail já está em uso."
            else:
                novo = User(
                    nome=request.form.get('nome'), email=email, senha=request.form.get('senha'),
                    telefone=request.form.get('telefone'), especialidade=request.form.get('especialidade'),
                    tipo='dentista', bio="Especialista L'Odontologie.",
                    # ATUALIZADO: Começa sem foto (None)
                    foto_perfil=None 
                )
                db.session.add(novo)
                db.session.commit()
                sucesso = "Novo especialista contratado."

        # 3. CADASTRAR PACIENTE (NOVO)
        elif acao == 'cadastrar_paciente':
            active_tab = 'pacientes'
            if User.query.filter_by(email=request.form.get('email')).first():
                erro = "E-mail já existe."
            else:
                novo = User(
                    nome=request.form.get('nome'), email=request.form.get('email'),
                    senha=request.form.get('senha'), tipo='paciente',
                    telefone=request.form.get('telefone'),
                    foto_perfil="https://cdn-icons-png.flaticon.com/512/149/149071.png"
                )
                db.session.add(novo)
                db.session.commit()
                sucesso = "Paciente cadastrado com sucesso."

        # 4. EXCLUIR USUÁRIO
        elif acao == 'excluir_user':
            uid = request.form.get('id_user')
            user_tipo = request.form.get('tipo_user')
            active_tab = 'equipe' if user_tipo == 'dentista' else 'pacientes'
            User.query.filter_by(id=uid).delete()
            db.session.commit()
            sucesso = "Usuário removido."

        # 5. ADMIN AGENDAR (ATUALIZADO)
        elif acao == 'admin_agendar':
            active_tab = 'agenda'
            termo = request.form.get('termo_busca')
            dentista_id = request.form.get('dentista_id')
            data_str = f"{request.form.get('data')}T{request.form.get('hora')}"
            
            paciente = User.query.filter((User.email == termo) | (User.telefone == termo)).first()
            
            if not paciente:
                erro = "Paciente não encontrado! Verifique o e-mail ou telefone."
            else:
                try:
                    data_obj = datetime.strptime(data_str, '%Y-%m-%dT%H:%M')
                    if verificar_conflito(dentista_id, data_obj):
                        erro = "Horário ocupado para este dentista."
                    elif verificar_dia_bloqueado(dentista_id, data_obj):
                        erro = "Este profissional não atenderá nesta data (Folga)."
                    else:
                        novo = Agendamento(
                            paciente_id=paciente.id, 
                            dentista_id=dentista_id, 
                            clinica_id=1,
                            data_hora=data_obj, 
                            servico=request.form.get('servico'),
                            tipo_consulta=request.form.get('tipo_consulta'),
                            observacoes=request.form.get('observacoes'),
                            status='Agendado'
                        )
                        db.session.add(novo)
                        db.session.commit()
                        sucesso = f"Agendado para {paciente.nome}!"
                except: erro = "Erro na data/hora."

        # 6. BLOQUEAR AGENDA / FOLGA (COM WHATSAPP)
        elif acao == 'admin_bloquear':
            active_tab = 'agenda'
            dentista_id = request.form.get('dentista_id')
            data_str = request.form.get('data_bloqueio')
            motivo = request.form.get('motivo_bloqueio')
            
            try:
                data_bloq = datetime.strptime(data_str, '%Y-%m-%d').date()
                db.session.add(Folga(data=data_bloq, motivo=motivo, dentista_id=dentista_id))
                
                inicio = datetime.combine(data_bloq, datetime.min.time())
                fim = datetime.combine(data_bloq, datetime.max.time())
                consultas_afetadas = Agendamento.query.filter(
                    Agendamento.dentista_id == dentista_id,
                    Agendamento.data_hora >= inicio, 
                    Agendamento.data_hora <= fim,
                    Agendamento.status.notlike('Cancelado%')
                ).all()
                
                count = 0
                for c in consultas_afetadas:
                    c.status = 'Cancelado (Folga Administrativa)'
                    count += 1
                    
                    if c.paciente.telefone:
                        tel_limpo = "".join(filter(str.isdigit, c.paciente.telefone))
                        msg_texto = f"Olá {c.paciente.nome}, informamos que sua consulta do dia {c.data_hora.strftime('%d/%m às %H:%M')} foi cancelada devido a {motivo}. Entre em contato para reagendar."
                        link_wa = f"https://wa.me/55{tel_limpo}?text={urllib.parse.quote(msg_texto)}"
                        afetados_whatsapp.append({'nome': c.paciente.nome, 'link': link_wa, 'hora': c.data_hora.strftime('%H:%M')})

                db.session.commit()
                sucesso = f"Dia bloqueado e {count} consultas canceladas."
            except: 
                erro = "Erro ao bloquear data."

        # 7. CANCELAR CONSULTA INDIVIDUAL (ATUALIZADO: GERA LINK WHATSAPP)
        elif acao == 'cancelar_consulta':
            active_tab = 'agenda'
            consulta = Agendamento.query.get(request.form.get('id_agendamento'))
            if consulta:
                consulta.status = 'Cancelado pela Administração'
                
                # Gera link para notificação individual
                if consulta.paciente.telefone:
                    tel_limpo = "".join(filter(str.isdigit, consulta.paciente.telefone))
                    msg_texto = f"Olá {consulta.paciente.nome}, sua consulta de {consulta.data_hora.strftime('%d/%m às %H:%M')} foi cancelada pela clínica. Favor entrar em contato."
                    link_wa = f"https://wa.me/55{tel_limpo}?text={urllib.parse.quote(msg_texto)}"
                    # Adiciona na lista de afetados para aparecer na caixa amarela
                    afetados_whatsapp.append({'nome': consulta.paciente.nome, 'link': link_wa, 'hora': consulta.data_hora.strftime('%H:%M')})
                
                db.session.commit()
                sucesso = "Consulta cancelada."
        
        # 8. CLINICAS
        # 8. CLINICAS (ATUALIZADO PARA SALVAR HORÁRIOS)
        elif acao == 'nova_clinica':
            active_tab = 'clinicas'
            nova = Clinica(
                nome=request.form.get('nome'), 
                endereco_completo=request.form.get('endereco'), 
                bairro=request.form.get('bairro'), 
                telefone=request.form.get('telefone'),
                horario_abertura=request.form.get('horario_abertura'), # Novo
                horario_fechamento=request.form.get('horario_fechamento') # Novo
            )
            db.session.add(nova)
            db.session.commit()
            sucesso = "Nova unidade inaugurada com horários definidos."
        elif acao == 'excluir_clinica':
            active_tab = 'clinicas'
            Clinica.query.filter_by(id=request.form.get('id_clinica')).delete()
            db.session.commit()
            sucesso = "Unidade removida."

    # --- ESTATÍSTICAS ---
    agora = datetime.now()
    semana_atras = agora - timedelta(days=7)
    mes_atras = agora - timedelta(days=30)
    
    q_base = Agendamento.query.filter(Agendamento.status.notlike('Cancelado%'))
    q_canceladas = Agendamento.query.filter(Agendamento.status.like('Cancelado%'))
    
    stats = {
        'hoje': q_base.filter(db.func.date(Agendamento.data_hora) == date.today()).count(),
        'total_concluidas': q_base.filter(Agendamento.data_hora < agora).count(),
        'semana_concluidas': q_base.filter(Agendamento.data_hora >= semana_atras, Agendamento.data_hora < agora).count(),
        'mes_concluidas': q_base.filter(Agendamento.data_hora >= mes_atras, Agendamento.data_hora < agora).count(),
        
        'total_canceladas': q_canceladas.count(),
        'semana_canceladas': q_canceladas.filter(Agendamento.data_hora >= semana_atras).count(),
        'mes_canceladas': q_canceladas.filter(Agendamento.data_hora >= mes_atras).count(),
        
        'dentistas': User.query.filter_by(tipo='dentista').count(),
        'pacientes': User.query.filter_by(tipo='paciente').count()
    }

    return render_template('dash_admin.html', 
                           config=config, 
                           dentistas=User.query.filter_by(tipo='dentista').all(), 
                           pacientes=User.query.filter_by(tipo='paciente').order_by(User.id.desc()).all(),
                           consultas=Agendamento.query.order_by(Agendamento.data_hora.desc()).limit(50).all(), 
                           clinicas=Clinica.query.all(),
                           stats=stats,
                           sucesso=sucesso, erro=erro, active_tab=active_tab,
                           afetados=afetados_whatsapp)

# --- INICIALIZAÇÃO ---
with app.app_context():
    db.create_all()
    if not User.query.filter_by(email='admin@sistema.com').first():
        db.session.add(User(nome='Admin', email='admin@sistema.com', senha='123', tipo='admin'))
        db.session.add(User(nome='Dr. House', email='house@med.com', senha='123', tipo='dentista', especialidade='Cirurgião', telefone='11999999999', bio='Expert.'))
        # Paciente Exemplo (Sem CPF)
        db.session.add(User(nome='Paciente Teste', email='paciente@teste.com', senha='123', tipo='paciente', telefone='11988888888'))
        db.session.add(Clinica(nome='Matriz Jardins', bairro='Jardins', endereco_completo='Rua Oscar Freire, 500', telefone='(11) 3333-4444'))
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')