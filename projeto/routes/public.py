from flask import Blueprint, render_template
from models import User, Clinica, Portfolio, ConfigSite # Adicionei Portfolio aqui

# 1. Cria o Blueprint
public_bp = Blueprint('public', __name__) 

# 2. Define as rotas
# CORREÇÃO: Mudei de '/home' para '/' para ser a página inicial
@public_bp.route('/')
def home():
    config = ConfigSite.query.first() or ConfigSite()
    dentistas = User.query.filter_by(tipo='dentista').all()
    return render_template('home.html', content=config, dentistas=dentistas)

@public_bp.route('/unidades')
def unidades():
    lista_clinicas = Clinica.query.all()
    if not lista_clinicas:
        lista_clinicas = [
            Clinica(nome='Matriz Jardins', bairro='Jardins', endereco_completo='Rua Oscar Freire, 500, São Paulo', telefone='(11) 3003-0000'),
            Clinica(nome='Unidade Faria Lima', bairro='Itaim Bibi', endereco_completo='Av. Brig. Faria Lima, 2000, São Paulo', telefone='(11) 3003-0001'),
            Clinica(nome='Unidade Alphaville', bairro='Barueri', endereco_completo='Alameda Rio Negro, 100, Barueri', telefone='(11) 3003-0002')
        ]
    return render_template('unidades.html', clinicas=lista_clinicas)

@public_bp.route('/portfolio')
def portfolio_publico():
    return render_template('portfolio.html', posts=Portfolio.query.filter_by(aprovado=True).all())

@public_bp.route('/profissionais')
def lista_profissionais():
    return render_template('profissionais.html', dentistas=User.query.filter_by(tipo='dentista').all())