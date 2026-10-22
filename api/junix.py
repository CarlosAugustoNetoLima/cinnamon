import hmac
import json
import os
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlencode, urlparse

JUNIX_BASE_URL = os.environ.get('JUNIX_BASE_URL', 'https://junixapi.imobflow.com.br')
JUNIX_USERNAME = os.environ.get('JUNIX_USERNAME', '')
JUNIX_PASSWORD = os.environ.get('JUNIX_PASSWORD', '')
JUNIX_ID_PRODUTO = os.environ.get('JUNIX_ID_PRODUTO', '')
RESPONDI_WEBHOOK_TOKEN = os.environ.get('RESPONDI_WEBHOOK_TOKEN', '')
RESPONDI_FORM_ID = os.environ.get('RESPONDI_FORM_ID', '')
JUNIX_DRY_RUN = os.environ.get('JUNIX_DRY_RUN') == '1'
TIMEOUT = 8

_token_cache = {'valor': None, 'expira_em': 0.0}


def log(evento, **campos):
    print(json.dumps({'evento': evento, **campos}, ensure_ascii=False))


def autorizado(token):
    return bool(RESPONDI_WEBHOOK_TOKEN) and bool(token) and hmac.compare_digest(token, RESPONDI_WEBHOOK_TOKEN)


def texto_de(valor):
    if isinstance(valor, dict):
        return ' '.join(str(v) for v in valor.values() if v)
    if isinstance(valor, list):
        return ', '.join(str(v) for v in valor)
    return str(valor) if valor is not None else ''


def identificar_ramo(resposta):
    valor = texto_de(resposta).lower()
    if 'investidor' in valor:
        return 'Investidor'
    if 'corretor' in valor:
        return 'Corretor'
    return ''


def montar_lead(corpo):
    respondente = corpo.get('respondent', {})
    utms = respondente.get('respondent_utms') or {}

    dados = {}
    qualificacao = []
    ramo = ''

    for item in respondente.get('raw_answers', []):
        pergunta = item.get('question', {})
        tipo = pergunta.get('question_type', '')
        titulo = pergunta.get('question_title', '')
        resposta = item.get('answer')

        if tipo == 'radio' and titulo == 'Você é...':
            ramo = identificar_ramo(resposta)
            continue

        if tipo in ('name', 'phone', 'email'):
            dados[tipo] = texto_de(resposta)
            continue

        if tipo in ('thankyou', 'statement'):
            continue

        texto = texto_de(resposta)
        if texto.strip():
            qualificacao.append('%s: %s' % (titulo, texto))

    canal = ('Site - %s' % ramo) if ramo else 'Site'
    telefone = dados.get('phone', '')

    return {
        'IdExterno': respondente.get('respondent_id', ''),
        'Nome': dados.get('name', ''),
        'Email': dados.get('email', ''),
        'Telefone': telefone,
        'Celular': telefone,
        'IdProduto': JUNIX_ID_PRODUTO,
        'CanalTipo': canal,
        'Origem': canal,
        'Midia': utms.get('utm_source', ''),
        'Mensagem': '\n'.join(qualificacao),
    }


def obter_token(forcar=False):
    agora = time.time()
    if not forcar and _token_cache['valor'] and agora < _token_cache['expira_em']:
        return _token_cache['valor']

    corpo = urlencode({
        'username': JUNIX_USERNAME,
        'password': JUNIX_PASSWORD,
        'grant_type': 'password',
    }).encode('utf-8')
    requisicao = urllib.request.Request(
        JUNIX_BASE_URL + '/api/token',
        data=corpo,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    with urllib.request.urlopen(requisicao, timeout=TIMEOUT) as resposta:
        dados = json.loads(resposta.read())

    _token_cache['valor'] = dados['access_token']
    _token_cache['expira_em'] = agora + int(dados.get('expires_in', 3600)) - 60
    return _token_cache['valor']


def enviar_lead(lead, tentativas=2):
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            token = obter_token(forcar=tentativa > 1)
            requisicao = urllib.request.Request(
                JUNIX_BASE_URL + '/api/lead/incluir',
                data=json.dumps(lead).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer %s' % token,
                },
                method='POST',
            )
            with urllib.request.urlopen(requisicao, timeout=TIMEOUT) as resposta:
                dados = json.loads(resposta.read())
            return bool(dados.get('OK')), dados
        except urllib.error.HTTPError as erro:
            ultimo_erro = {'status_http': erro.code, 'corpo': erro.read().decode('utf-8', 'replace')}
            if erro.code != 401:
                break
        except (urllib.error.URLError, OSError) as erro:
            ultimo_erro = {'erro_rede': str(erro)}

    return False, ultimo_erro


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        query = parse_qs(urlparse(self.path).query)
        token = (query.get('token') or [''])[0]
        if not autorizado(token):
            self._responder(401, {'ok': False})
            return

        tamanho = int(self.headers.get('Content-Length', 0))
        corpo_bruto = self.rfile.read(tamanho) if tamanho else b''
        try:
            corpo = json.loads(corpo_bruto or b'{}')
        except ValueError:
            self._responder(400, {'ok': False})
            return

        formulario = corpo.get('form', {})
        respondente = corpo.get('respondent', {})

        if RESPONDI_FORM_ID and formulario.get('form_id') != RESPONDI_FORM_ID:
            self._responder(200, {'ok': True, 'ignorado': 'formulario'})
            return
        if respondente.get('status') != 'completed':
            self._responder(200, {'ok': True, 'ignorado': 'incompleto'})
            return

        lead = montar_lead(corpo)

        if JUNIX_DRY_RUN:
            log('lead_simulado', id_externo=lead['IdExterno'], canal=lead['CanalTipo'])
            self._responder(200, {'ok': True, 'simulado': True})
            return

        sucesso, resposta_junix = enviar_lead(lead)
        log(
            'lead_enviado' if sucesso else 'lead_falhou',
            id_externo=lead['IdExterno'],
            canal=lead['CanalTipo'],
            resposta_junix=resposta_junix,
        )
        self._responder(200, {'ok': True, 'entregue': sucesso})

    def _responder(self, status, payload):
        corpo = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)
