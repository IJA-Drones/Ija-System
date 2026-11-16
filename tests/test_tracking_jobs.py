import unittest
from concurrent.futures import Future
from unittest.mock import patch

from flask import Flask

from app.modules.veiculos.tracking_jobs import request_history_refresh
from app.modules.veiculos.tracking_period import parse_tracking_period


class FakeExecutor:
    def __init__(self):
        self.futures = []

    def submit(self, *args):
        future = Future()
        self.futures.append(future)
        return future


class TrackingJobsTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.executor = FakeExecutor()
        self.app.extensions['tracking_history_executor'] = self.executor
        self.context = self.app.app_context()
        self.context.push()
        self.period = parse_tracking_period({'date': '2026-10-07'})

    def tearDown(self):
        self.context.pop()

    def test_returns_immediately_and_deduplicates_polling_while_work_is_pending(self):
        result, status = request_history_refresh(1, self.period)
        self.assertEqual(status, 202)
        self.assertTrue(result['busy'])
        self.assertEqual(request_history_refresh(1, self.period)[1], 202)
        self.assertEqual(len(self.executor.futures), 1)
        self.executor.futures[0].set_result({'vehicles': 1, 'inserted': 2000})
        result, status = request_history_refresh(1, self.period)
        self.assertEqual(status, 200)
        self.assertEqual(result['inserted'], 2000)
        self.assertEqual(len(self.executor.futures), 1)

    def test_a_slow_success_is_cached_from_its_completion_instead_of_restarting(self):
        now = [0]
        with patch('app.modules.veiculos.tracking_jobs.monotonic', side_effect=lambda: now[0]):
            request_history_refresh(1, self.period)
            now[0] = 180
            self.executor.futures[0].set_result({'vehicles': 1, 'inserted': 20})
            now[0] = 181
            self.assertEqual(request_history_refresh(1, self.period)[1], 200)
            self.assertEqual(len(self.executor.futures), 1)
            now[0] = 241
            self.assertEqual(request_history_refresh(1, self.period)[1], 202)
            self.assertEqual(len(self.executor.futures), 2)

    def test_queue_is_bounded_while_a_provider_stalls(self):
        for vehicle_id in range(1, 5):
            request_history_refresh(vehicle_id, self.period)
        result, status = request_history_refresh(5, self.period)
        self.assertEqual(status, 202)
        self.assertEqual(result['state'], 'queued')
        self.assertEqual(len(self.executor.futures), 4)

    def test_worker_errors_do_not_disclose_provider_messages(self):
        request_history_refresh(1, self.period)
        self.executor.futures[0].set_exception(RuntimeError('private-test-credential'))
        result, status = request_history_refresh(1, self.period)
        self.assertEqual(status, 502)
        self.assertNotIn('private-test-credential', str(result))
