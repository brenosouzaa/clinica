import os
from flask import Flask
from extensions import db, login_manager
# IMPORTANTE: Importamos as tabelas do arquivo models.py. 
# Se você escrever "class User" aqui de novo, vai dar o erro de tabela duplicada.
from models import User, Clinica, Portfolio, ConfigSite, Agendamento, Folga, Prontuario
from utils import setup_upload_folder, limpar_telefone_filter

# Importa as rotas
from routes.auth import auth_bp
from routes.public import public_bp
from routes.admin import admin_bp
from routes.dentista import dentista_bp
from routes.paciente import paciente_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://postgres:123789ab@localhost/clinica')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Configurações
setup_upload_folder(app)
app.jinja_env.filters['limpar_telefone'] = limpar_telefone_filter

# Registra Rotas
app.register_blueprint(auth_bp)
app.register_blueprint(public_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(dentista_bp)
app.register_blueprint(paciente_bp)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Inicialização do Banco
with app.app_context():
    db.create_all()
    
    # Cria Clínica Padrão
    if not Clinica.query.first():
        db.session.add(Clinica(nome='Matriz Jardins', bairro='Jardins', endereco_completo='Rua Oscar Freire, 500', telefone='(11) 3333-4444'))
        db.session.commit()

    # Cria Usuários Padrão
    if not User.query.filter_by(email='admin@sistema.com').first():
        admin = User(nome='Admin', email='admin@sistema.com', tipo='admin'); admin.set_senha('123')
        dr = User(nome='Dr. House', email='house@med.com', tipo='dentista', especialidade='Cirurgião', telefone='11999999999'); dr.set_senha('123')
        paciente = User(nome='Paciente Teste', email='paciente@teste.com', tipo='paciente', telefone='11988888888'); paciente.set_senha('123')
        db.session.add_all([admin, dr, paciente])
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)