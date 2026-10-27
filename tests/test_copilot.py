"""Copilot safety and API integration tests; no paid provider or database required."""
import json
import os
import unittest
from unittest.mock import MagicMock, patch

import yaml
from fastapi.testclient import TestClient
from src.api.main import app
from src.contracts.models import DataForgeContract
from src.copilot.service import BedrockProvider, ProviderUnavailable, propose, seal, unseal


class CopilotTests(unittest.TestCase):
    def setUp(self):
        with open('config/examples/olist.yaml', encoding='utf-8') as stream:
            self.contract = DataForgeContract.model_validate(yaml.safe_load(stream))
        self.dataset = self.contract.datasets[0]
        self.column = self.dataset.schema_[0].name
        self.output = {'rules': [{'name': 'copilot_required', 'rule': 'not_null',
                                 'column': self.column, 'severity': 'warning'}],
                       'transformations': [{'operation': 'trim', 'column': self.column}],
                       'explanation': 'Review candidate rules.'}
        self.provider = MagicMock()
        self.provider.generate.return_value = json.dumps(self.output)
        self.client = TestClient(app)
        self.payload = dict(client_code=self.contract.client.code, project_code=self.contract.project.code,
                            source_code=self.contract.source.code, dataset_code=self.dataset.code,
                            requirement='El identificador es obligatorio')

    def test_provider_receives_schema_profile_intent_and_supported_schema(self):
        proposal, result = propose(self.contract, self.dataset.code, 'required',
            {'row_count': 5, 'columns': {self.column: {'null_count': 2, 'sample_values': ['private']}}},
            'llm', self.provider)
        context = self.provider.generate.call_args.args[0]
        self.assertEqual(context['requirement'], 'required')
        self.assertEqual(context['profiling']['columns'][self.column], {'null_count': 2})
        self.assertIn('output_schema', context)
        self.assertEqual(proposal.rules[0].severity.value, 'warning')
        self.assertEqual(len(result.datasets[0].quality.rules), len(self.dataset.quality.rules) + 1)
        self.assertNotIn('copilot_required', [r.name for r in self.dataset.quality.rules])

    def test_reject_invalid_unsupported_and_unknown_columns(self):
        for raw in ['not json', '{}', '```json\n{}\n```',
                    json.dumps({**self.output, 'code': 'print(1)'}),
                    json.dumps({**self.output, 'transformations': [{'operation': 'python', 'column': self.column}]}),
                    json.dumps({**self.output, 'rules': [{**self.output['rules'][0], 'column': 'invented'}]}),
                    json.dumps({**self.output, 'rules': [{**self.output['rules'][0], 'severity': 'fatal'}]})]:
            with self.subTest(raw=raw):
                self.provider.generate.return_value = raw
                with self.assertRaises(ValueError):
                    propose(self.contract, self.dataset.code, 'required', None, 'llm', self.provider)

    def test_duplicate_rules_rejected(self):
        self.output['rules'] *= 2
        self.provider.generate.return_value = json.dumps(self.output)
        with self.assertRaises(ValueError):
            propose(self.contract, self.dataset.code, 'required', None, 'llm', self.provider)

    def test_rejection_explains_category_without_echoing_model_values(self):
        from src.copilot.service import ProposalRejected
        cases = [
            ('private model response', 'valid JSON'),
            (json.dumps({**self.output, 'rules': [{
                'name': 'test', 'rule': 'less_than_or_equal',
                'column': self.column, 'severity': 'critical', 'max_value': 8,
            }]}), 'invalid parameters'),
            (json.dumps({**self.output, 'rules': [{
                **self.output['rules'][0], 'rule': 'private_unsupported_operation',
            }]}), 'unsupported operation'),
            (json.dumps({**self.output, 'rules': [{
                **self.output['rules'][0], 'column': 'private_unknown_column',
            }]}), 'dataset schema'),
        ]
        for raw, expected in cases:
            with self.subTest(expected=expected):
                self.provider.generate.return_value = raw
                with self.assertRaises(ProposalRejected) as caught:
                    propose(self.contract, self.dataset.code, 'required', None, 'llm', self.provider)
                self.assertIn(expected, str(caught.exception))
                self.assertNotIn('private_', str(caught.exception))

    def test_explicit_fallback_never_calls_provider(self):
        proposal, _ = propose(self.contract, self.dataset.code, 'anything', None, 'deterministic', self.provider)
        self.provider.generate.assert_not_called()
        self.assertIn('not interpreted', proposal.explanation)

    def test_tampered_and_expired_tokens_rejected(self):
        token = seal(self.contract, self.contract)
        self.assertEqual(unseal(token)[0], self.contract)
        with self.assertRaises(ValueError):
            unseal(token + 'x')
        with patch('src.copilot.service.time.time', return_value=9999999999):
            with self.assertRaises(ValueError):
                unseal(token)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_provider_configuration_is_clear(self):
        with self.assertRaises(ProviderUnavailable):
            BedrockProvider().generate({})

    @patch('src.copilot.service.boto3.client')
    @patch.dict(os.environ, {'DATAFORGE_COPILOT_MODEL_ID': 'test-model'})
    def test_bedrock_adapter_and_truncation(self, factory):
        client = factory.return_value
        client.converse.return_value = {'stopReason': 'end_turn', 'output': {'message': {'content': [{'text': '{}'}]}}}
        self.assertEqual(BedrockProvider().generate({'test': True}), '{}')
        self.assertEqual(client.converse.call_args.kwargs['modelId'], 'test-model')
        client.converse.return_value['stopReason'] = 'max_tokens'
        with self.assertRaises(ValueError):
            BedrockProvider().generate({})

    @patch('src.api.main.register_contract')
    @patch('src.api.main.get_latest_profile', return_value=None)
    @patch('src.api.main.get_active_contract')
    @patch('src.api.main.connect_postgres')
    @patch('src.copilot.service.BedrockProvider.generate')
    def test_preview_approval_persistence_and_stale_conflict(self, generate, connect, active, profile, register):
        generate.return_value = json.dumps(self.output)
        active.return_value = {'contract': self.contract, 'source_id': 1}
        preview = self.client.post('/api/copilot/suggest', json=self.payload)
        self.assertEqual(preview.status_code, 200, preview.text)
        register.assert_not_called()
        token = preview.json()['token']
        denied = self.client.post('/api/copilot/approve', json={'token': token, 'approved': False})
        self.assertEqual(denied.status_code, 422)
        register.assert_not_called()
        register.return_value = {'contract_id': 8, 'revision': 2}
        approved = self.client.post('/api/copilot/approve', json={'token': token, 'approved': True})
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()['contract_id'], 8)
        register.assert_called_once()
        active.return_value = {'contract': preview.json()['contract'], 'source_id': 1}
        stale = self.client.post('/api/copilot/approve', json={'token': token, 'approved': True})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(register.call_count, 1)

    @patch('src.api.main.get_latest_profile', return_value=None)
    @patch('src.api.main.get_active_contract')
    @patch('src.api.main.connect_postgres')
    @patch('src.copilot.service.BedrockProvider.generate')
    def test_invalid_output_api_and_provider_failure_never_silent_fallback(self, generate, connect, active, profile):
        active.return_value = {'contract': self.contract, 'source_id': 1}
        generate.return_value = 'unsafe output'
        rejected = self.client.post('/api/copilot/suggest', json=self.payload)
        self.assertEqual(rejected.status_code, 422)
        self.assertIn('valid JSON', rejected.json()['detail'])
        self.assertNotIn('unsafe output', rejected.text)
        generate.side_effect = ProviderUnavailable('Bedrock unavailable')
        self.assertEqual(self.client.post('/api/copilot/suggest', json=self.payload).status_code, 503)
        self.payload['mode'] = 'deterministic'
        self.assertEqual(self.client.post('/api/copilot/suggest', json=self.payload).json()['provider'], 'deterministic')


class CopilotPersistenceConcurrencyTests(unittest.TestCase):
    def test_base_revision_is_checked_inside_registration_lock(self):
        from src.api.control_plane import register_contract, ControlPlaneConflictError
        with open('config/examples/olist.yaml', encoding='utf-8') as stream:
            contract = DataForgeContract.model_validate(yaml.safe_load(stream))
        conn = MagicMock()
        with patch('src.api.control_plane._upsert_client', return_value=1), \
             patch('src.api.control_plane._upsert_project', return_value=2), \
             patch('src.api.control_plane._upsert_source', return_value=3), \
             patch('src.api.control_plane._lock_source_configuration') as lock, \
             patch('src.api.control_plane.get_active_contract', return_value={'contract': contract}) as active, \
             patch('src.api.control_plane._persist_contract_revision') as persist:
            def read(*args, **kwargs):
                lock.assert_called_once_with(conn, 3)
                return {'contract': contract}
            active.side_effect = read
            with self.assertRaises(ControlPlaneConflictError):
                register_contract(conn, contract, expected_base_hash='stale')
            persist.assert_not_called()
