"""Groq transport and existing contract/approval integration; no real API key."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import requests
import yaml
from fastapi.testclient import TestClient

from src.api.main import app
from src.contracts.models import DataForgeContract
from src.copilot.service import (
    BedrockProvider, GroqProvider, ProposalRejected, ProviderUnavailable,
    configured_provider, configured_provider_name, propose,
)


class GroqCopilotTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            'DATAFORGE_COPILOT_PROVIDER': 'groq',
            'GROQ_API_KEY': 'gsk_private_test_key',
            'GROQ_MODEL_ID': 'openai/gpt-oss-120b',
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.response = MagicMock()
        self.response.status_code = 200
        self.response.content = b'{}'
        self.response.json.return_value = {'choices': [{
            'finish_reason': 'stop',
            'message': {'content': '{"rules":[],"transformations":[],"explanation":"Review."}'},
        }]}
        self.post = patch('src.copilot.service.requests.post', return_value=self.response).start()
        self.addCleanup(patch.stopall)
        with open('config/examples/olist.yaml', encoding='utf-8') as stream:
            self.contract = DataForgeContract.model_validate(yaml.safe_load(stream))

    def test_provider_selection_is_explicit_and_bedrock_remains_default(self):
        self.assertIsInstance(configured_provider(), GroqProvider)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(configured_provider_name(), 'bedrock')
            self.assertIsInstance(configured_provider(), BedrockProvider)
        with patch.dict(os.environ, {'DATAFORGE_COPILOT_PROVIDER': 'unknown'}):
            with self.assertRaises(ProviderUnavailable):
                configured_provider()

    def test_transport_sends_json_context_and_never_follows_redirects(self):
        context = {'requirement': 'Only existing columns', 'output_schema': {}}
        self.assertIn('Review.', GroqProvider().generate(context))
        args, kwargs = self.post.call_args
        self.assertEqual(args[0], 'https://api.groq.com/openai/v1/chat/completions')
        self.assertEqual(kwargs['headers']['Authorization'], 'Bearer gsk_private_test_key')
        self.assertEqual(json.loads(kwargs['json']['messages'][1]['content']), context)
        self.assertEqual(kwargs['json']['response_format'], {'type': 'json_object'})
        self.assertEqual(kwargs['json']['reasoning_effort'], 'low')
        self.assertFalse(kwargs['json']['include_reasoning'])
        self.assertFalse(kwargs['allow_redirects'])
        self.assertEqual(kwargs['timeout'], (5, 40))
        self.response.close.assert_called_once()

    def test_auth_rate_limit_server_errors_and_redirects_are_redacted(self):
        self.response.text = 'gsk_private_test_key private provider error'
        for status in (401, 403, 429, 500, 302):
            with self.subTest(status=status):
                self.response.status_code = status
                with patch('src.copilot.service.BedrockProvider.generate') as bedrock:
                    with self.assertRaises(ProviderUnavailable) as caught:
                        propose(self.contract, self.contract.datasets[0].code, 'test', None, 'llm')
                    bedrock.assert_not_called()
                self.assertNotIn('gsk_', str(caught.exception))
                self.assertNotIn('private provider error', str(caught.exception))

    def test_timeout_is_safe_and_not_retried(self):
        self.post.side_effect = requests.Timeout('private transport detail')
        with self.assertRaises(ProviderUnavailable) as caught:
            GroqProvider().generate({})
        self.post.assert_called_once()
        self.assertNotIn('private transport detail', str(caught.exception))

    def test_missing_or_multiline_key_never_calls_network(self):
        for key in ('', 'gsk_test\nprivate'):
            with patch.dict(os.environ, {'GROQ_API_KEY': key}):
                with self.assertRaises(ProviderUnavailable):
                    GroqProvider().generate({})
        self.post.assert_not_called()

    def test_malformed_truncated_refused_and_tool_responses_are_rejected(self):
        cases = [
            {}, {'choices': []},
            {'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]},
            {'choices': [{'finish_reason': 'stop', 'message': {'content': None}}]},
            {'choices': [{'finish_reason': 'stop', 'message': {'content': '{}', 'refusal': 'private'}}]},
            {'choices': [{'finish_reason': 'stop', 'message': {'content': '{}', 'tool_calls': [{}]}}]},
        ]
        for result in cases:
            with self.subTest(result=result):
                self.response.json.return_value = result
                with self.assertRaises(ProposalRejected):
                    GroqProvider().generate({})
        self.response.json.side_effect = ValueError('private invalid body')
        with self.assertRaises(ProposalRejected) as caught:
            GroqProvider().generate({})
        self.assertNotIn('private', str(caught.exception))

    def test_model_configuration_still_passes_full_contract_validation(self):
        raw = json.dumps({'rules': [{'name': 'invalid', 'rule': 'not_null',
            'column': 'invented_column', 'severity': 'critical'}],
            'transformations': [], 'explanation': 'Review.'})
        self.response.json.return_value['choices'][0]['message']['content'] = raw
        with self.assertRaises(ProposalRejected):
            propose(self.contract, self.contract.datasets[0].code, 'test', None, 'llm')

    def test_deterministic_mode_never_calls_groq(self):
        propose(self.contract, self.contract.datasets[0].code, 'test', None, 'deterministic')
        self.post.assert_not_called()

    @patch('src.api.main.register_contract')
    @patch('src.api.main.get_latest_profile', return_value=None)
    @patch('src.api.main.get_active_contract')
    @patch('src.api.main.connect_postgres')
    def test_api_labels_groq_and_persists_only_after_explicit_approval(self, connect, active, profile, register):
        active.return_value = {'contract': self.contract, 'source_id': 1}
        client = TestClient(app)
        payload = dict(client_code=self.contract.client.code, project_code=self.contract.project.code,
                       source_code=self.contract.source.code, dataset_code=self.contract.datasets[0].code,
                       requirement='Propose a rule', mode='llm')
        preview = client.post('/api/copilot/suggest', json=payload)
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.json()['provider'], 'groq')
        register.assert_not_called()
        denied = client.post('/api/copilot/approve', json={
            'token': preview.json()['token'], 'approved': False})
        self.assertEqual(denied.status_code, 422)
        register.assert_not_called()
        register.return_value = {'contract_id': 8, 'revision': 2}
        approved = client.post('/api/copilot/approve', json={
            'token': preview.json()['token'], 'approved': True})
        self.assertEqual(approved.status_code, 200, approved.text)
        register.assert_called_once()


class GroqPrivateConfigurationTests(unittest.TestCase):
    def test_atomic_configuration_is_private_and_rejects_injected_lines(self):
        spec = importlib.util.spec_from_file_location('groq_setup', 'scripts/aws/configure_groq.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env.copilot'
            module.write_configuration(path, 'gsk_test_secret', 'openai/gpt-oss-120b')
            previous = path.read_text()
            self.assertIn('DATAFORGE_COPILOT_PROVIDER=groq', previous)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            for key, model in [('gsk_test\nINJECT=1', 'model'), ('gsk_test', 'model\nINJECT=1')]:
                with self.assertRaises(ValueError):
                    module.write_configuration(path, key, model)
                self.assertEqual(path.read_text(), previous)
