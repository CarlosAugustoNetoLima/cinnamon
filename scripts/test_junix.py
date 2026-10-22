import json
import os
import sys
import unittest
from io import BytesIO
from unittest import mock
from urllib.error import HTTPError, URLError

os.environ['RESPONDI_WEBHOOK_TOKEN'] = 'segredo-teste'
os.environ['JUNIX_ID_PRODUTO'] = '99'
os.environ['JUNIX_USERNAME'] = 'usuario-teste'
os.environ['JUNIX_PASSWORD'] = 'senha-teste'

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'api'))
import junix


def payload(ramo_valor, extra=None):
    respostas = [
        {'question': {'question_title': 'Você é...', 'question_type': 'radio'}, 'answer': [ramo_valor]},
        {'question': {'question_title': 'Qual seu nome?', 'question_type': 'name'}, 'answer': 'Maria Teste'},
        {'question': {'question_title': 'Qual seu whatsapp', 'question_type': 'phone'}, 'answer': '63999998888'},
    ]
    respostas.extend(extra or [])
    return {
        'form': {'form_id': 'RwKMw19v', 'form_name': 'CINNAMON STUDIOS'},
        'respondent': {
            'respondent_id': 'uuid-teste-123',
            'status': 'completed',
            'respondent_utms': {'utm_source': 'instagram'},
            'raw_answers': respostas,
        },
    }


class TestMontarLead(unittest.TestCase):
    def test_ramo_investidor(self):
        lead = junix.montar_lead(payload('🏠 Investidor(a) buscando oportunidade', extra=[
            {'question': {'question_title': 'Qual faixa de investimento você tem disponível?', 'question_type': 'radio'}, 'answer': ['Acima de R$ 500 mil']},
        ]))
        self.assertEqual(lead['Nome'], 'Maria Teste')
        self.assertEqual(lead['Telefone'], '63999998888')
        self.assertEqual(lead['Celular'], '63999998888')
        self.assertEqual(lead['CanalTipo'], 'Site - Investidor')
        self.assertEqual(lead['Midia'], 'instagram')
        self.assertIn('faixa de investimento', lead['Mensagem'])

    def test_ramo_corretor(self):
        lead = junix.montar_lead(payload('🤝 Corretor(a) / Imobiliária buscando parceria'))
        self.assertEqual(lead['CanalTipo'], 'Site - Corretor')

    def test_resposta_estruturada_nao_quebra(self):
        corpo = payload('🏠 Investidor(a) buscando oportunidade')
        corpo['respondent']['raw_answers'][1]['answer'] = {'primeiro': 'Maria', 'ultimo': 'Teste'}
        lead = junix.montar_lead(corpo)
        self.assertIn('Maria', lead['Nome'])


class TestAutorizado(unittest.TestCase):
    def test_token_correto(self):
        self.assertTrue(junix.autorizado('segredo-teste'))

    def test_token_incorreto(self):
        self.assertFalse(junix.autorizado('errado'))

    def test_token_vazio(self):
        self.assertFalse(junix.autorizado(''))


class TestEnviarLead(unittest.TestCase):
    def setUp(self):
        junix._token_cache['valor'] = None
        junix._token_cache['expira_em'] = 0.0

    def _ok(self, corpo):
        contexto = mock.MagicMock()
        contexto.__enter__.return_value.read.return_value = json.dumps(corpo).encode('utf-8')
        return contexto

    def _erro_http(self, status):
        return HTTPError('https://junixapi.imobflow.com.br', status, 'erro', {}, BytesIO(b'{}'))

    @mock.patch.object(junix.urllib.request, 'urlopen')
    def test_sucesso_com_token_em_cache(self, urlopen):
        junix._token_cache['valor'] = 'token-valido'
        junix._token_cache['expira_em'] = junix.time.time() + 3600
        urlopen.return_value = self._ok({'OK': True, 'Mensagem': 'ok'})

        sucesso, _ = junix.enviar_lead({'Nome': 'Teste'})

        self.assertTrue(sucesso)
        self.assertEqual(urlopen.call_count, 1)

    @mock.patch.object(junix.urllib.request, 'urlopen')
    def test_token_expirado_renova_e_reenvia(self, urlopen):
        urlopen.side_effect = [
            self._ok({'access_token': 'expirado', 'expires_in': 3600}),
            self._erro_http(401),
            self._ok({'access_token': 'novo', 'expires_in': 3600}),
            self._ok({'OK': True}),
        ]

        sucesso, _ = junix.enviar_lead({'Nome': 'Teste'})

        self.assertTrue(sucesso)
        self.assertEqual(urlopen.call_count, 4)

    @mock.patch.object(junix.urllib.request, 'urlopen')
    def test_erro_de_validacao_nao_tenta_de_novo(self, urlopen):
        urlopen.side_effect = [
            self._ok({'access_token': 'valido', 'expires_in': 3600}),
            self._erro_http(400),
        ]

        sucesso, resposta = junix.enviar_lead({'Nome': 'Teste'})

        self.assertFalse(sucesso)
        self.assertEqual(resposta['status_http'], 400)
        self.assertEqual(urlopen.call_count, 2)

    @mock.patch.object(junix.urllib.request, 'urlopen')
    def test_falha_de_rede_esgota_tentativas(self, urlopen):
        junix._token_cache['valor'] = 'token-valido'
        junix._token_cache['expira_em'] = junix.time.time() + 3600
        urlopen.side_effect = URLError('sem conexão')

        sucesso, _ = junix.enviar_lead({'Nome': 'Teste'})

        self.assertFalse(sucesso)
        self.assertEqual(urlopen.call_count, 2)


if __name__ == '__main__':
    unittest.main()
