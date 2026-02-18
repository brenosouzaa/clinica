import random
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, login_required, logout_user, current_user
from extensions import db
from models import User

# 1. Cria o Blueprint
auth_bp = Blueprint('auth', __name__)

# 2. Define as rotas
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        senha = request.form.get('senha')
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_senha(senha):
            login_user(user)
            if user.tipo == 'admin': return redirect('/painel/admin')
            if user.tipo == 'dentista': return redirect('/painel/dentista')
            return redirect('/painel/paciente')
        else:
            flash('Login inválido.')

    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email').strip().lower()
        telefone = request.form.get('telefone')
        senha = request.form.get('senha')
        metodo = request.form.get('metodo_envio') # 'email' ou 'whatsapp'
        
        # 1. Validação Dupla
        user_existente = User.query.filter((User.email == email) | (User.telefone == telefone)).first()
        
        if user_existente:
            flash('Este E-mail ou Telefone já está cadastrado.')
            return redirect(url_for('auth.register'))
        
        # 2. Geração do Código
        codigo = str(random.randint(100000, 999999))
        session['temp_user'] = {'nome': nome, 'email': email, 'telefone': telefone, 'senha': senha, 'codigo': codigo}
        
        # 3. Scripts de Envio Simulado
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
        
        return redirect(url_for('auth.confirmar_codigo'))
    
    return render_template('register.html')

@auth_bp.route('/confirmar-codigo', methods=['GET', 'POST'])
def confirmar_codigo():
    if 'temp_user' not in session: return redirect(url_for('auth.register'))
    
    if request.method == 'POST':
        codigo_digitado = request.form.get('codigo')
        if codigo_digitado == session['temp_user']['codigo']:
            dados = session['temp_user']
            
            novo_user = User(
                nome=dados['nome'], 
                email=dados['email'], 
                telefone=dados['telefone'], 
                tipo='paciente'
            )
            novo_user.set_senha(dados['senha'])

            db.session.add(novo_user)
            db.session.commit()
            
            session.pop('temp_user', None)
            flash('Conta criada com sucesso! Faça login.')
            return redirect(url_for('auth.login'))
        else:
            flash('Código incorreto.')
            
    return render_template('confirm_code.html')

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_request():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        user = User.query.filter_by(email=email).first()
        
        if user:
            codigo = str(random.randint(100000, 999999))
            print(f"\n >>> RECUPERAÇÃO SENHA PARA {user.nome}: {codigo} <<<\n")
            session['reset_temp'] = {'user_id': user.id, 'codigo': codigo, 'email': user.email}
            flash('Código enviado para seu WhatsApp!')
            return redirect(url_for('auth.reset_confirm'))
        else:
            flash('E-mail não encontrado.')
            
    return render_template('reset_request.html')

@auth_bp.route('/reset-confirm', methods=['GET', 'POST'])
def reset_confirm():
    if 'reset_temp' not in session: return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        codigo_digitado = request.form.get('codigo')
        nova_senha = request.form.get('senha')
        
        if codigo_digitado == session['reset_temp']['codigo']:
            user = User.query.get(session['reset_temp']['user_id'])
            user.set_senha(nova_senha)
            db.session.commit()
            session.pop('reset_temp', None)
            flash('Senha alterada! Entre agora.')
            return redirect(url_for('auth.login'))
        else:
            flash('Código incorreto.')
            
    return render_template('reset_confirm.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')