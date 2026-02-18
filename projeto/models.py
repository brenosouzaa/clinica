from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    senha = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.String(20))
    telefone = db.Column(db.String(20))
    endereco = db.Column(db.String(200))
    foto_perfil = db.Column(db.String(200), nullable=True, default='https://cdn-icons-png.flaticon.com/512/149/149071.png')
    especialidade = db.Column(db.String(100))
    bio = db.Column(db.Text)
    dia_folga_semanal = db.Column(db.String(50), nullable=True) 
    clinica_id = db.Column(db.Integer, db.ForeignKey('clinica.id'), nullable=True)
    clinica_trabalho = db.relationship('Clinica', foreign_keys=[clinica_id])

    def set_senha(self, senha):
        self.senha = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha, senha)

    def get_historico_json(self):
        from models import Agendamento # Importação local para evitar ciclo
        dados = []
        consultas = Agendamento.query.filter_by(paciente_id=self.id, status='Concluído').order_by(Agendamento.data_hora.desc()).all()
        for c in consultas:
            dados.append({
                'data_hora': c.data_hora.strftime('%d/%m/%Y às %H:%M'),
                'servico': c.servico,
                'medico': c.dentista.nome if c.dentista else 'Não informado',
                'queixa': c.prontuario.queixa if c.prontuario else '-',
                'procedimento': c.prontuario.procedimento if c.prontuario else '-',
                'evolucao': c.prontuario.evolucao if c.prontuario else 'Sem anotações.',
                'proximos_passos': c.prontuario.proximos_passos if c.prontuario else '-'
            })
        return json.dumps(dados)

class Clinica(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    endereco_completo = db.Column(db.String(300))
    bairro = db.Column(db.String(100))
    telefone = db.Column(db.String(20))
    horario_abertura = db.Column(db.String(5), default="08:00")
    horario_fechamento = db.Column(db.String(5), default="18:00")

class Agendamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    dentista_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    clinica_id = db.Column(db.Integer, db.ForeignKey('clinica.id', ondelete='CASCADE'), nullable=False)
    data_hora = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50))
    servico = db.Column(db.String(100))
    tipo_consulta = db.Column(db.String(50))

    paciente = db.relationship('User', foreign_keys=[paciente_id], backref=db.backref('consultas_paciente', passive_deletes=True))
    dentista = db.relationship('User', foreign_keys=[dentista_id], backref=db.backref('consultas_dentista', passive_deletes=True))
    clinica = db.relationship('Clinica')

class Prontuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    agendamento_id = db.Column(db.Integer, db.ForeignKey('agendamento.id'))
    queixa = db.Column(db.Text)
    procedimento = db.Column(db.Text)
    evolucao = db.Column(db.Text)
    proximos_passos = db.Column(db.Text)
    data_registro = db.Column(db.DateTime, default=datetime.now)
    agendamento = db.relationship('Agendamento', backref=db.backref('prontuario', uselist=False))

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
    titulo_principal = db.Column(db.String(200), default="Design de Sorrisos")
    cor_titulo = db.Column(db.String(20), default="#1A1A1A")
    titulo_destaque = db.Column(db.String(200), default="Ultra Realista.")
    cor_destaque = db.Column(db.String(20), default="#C6A87C")
    subtitulo = db.Column(db.String(500), default="Tecnologia, arte e hospitalidade.")
    cor_subtitulo = db.Column(db.String(20), default="#666666")
    img_agendamento = db.Column(db.String(500), default="https://images.unsplash.com/photo-1606811971618-4486d14f3f99?q=80&w=1000")
    img_especialistas = db.Column(db.String(500), default="https://images.unsplash.com/photo-1622253692010-333f2da6031d?q=80&w=500")
    titulo_visita = db.Column(db.String(200), default="Sua Próxima Visita")
    desc_visita = db.Column(db.String(500), default="Prepare-se para uma experiência única.")
    img_visita = db.Column(db.String(500), default="https://images.unsplash.com/photo-1609840114035-3c981b782dfe?q=80&w=500")
    titulo_mapa = db.Column(db.String(200), default="Nossas Unidades")
    desc_mapa = db.Column(db.String(500), default="Localização privilegiada e fácil acesso.")
    