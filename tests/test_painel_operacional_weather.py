import unittest
from unittest.mock import patch

import requests
from flask import Flask

from app.modules.painel_operacional import service


class PainelOperacionalWeatherTests(unittest.TestCase):
    def setUp(self):
        service.WEATHER_CACHE.clear()
        self.app = Flask(__name__)
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        service.WEATHER_CACHE.clear()
        self.ctx.pop()

    def test_weather_429_returns_unavailable_context(self):
        class Response:
            def raise_for_status(self):
                raise requests.HTTPError("429 Too Many Requests")

        with patch.object(service.requests, "get", return_value=Response()):
            weather = service._fetch_weather(-23.5145766, -46.434624)

        self.assertEqual(weather["source_status"], "unavailable")
        self.assertEqual(weather["description"], "Clima temporariamente indisponível.")

        risk = service._risk_level(weather)
        self.assertEqual(risk["level"], "warning")
        self.assertEqual(risk["label"], "Atenção")

    def test_weather_uses_fresh_cache_before_calling_api(self):
        service._store_weather_cache(
            -23.5145766,
            -46.434624,
            {
                "temperature": 24,
                "wind_speed": 3,
                "wind_gusts": 8,
                "rain": 0,
                "precipitation": 0,
                "weather_code": 2,
                "description": "Parcialmente nublado",
                "source_status": "live",
            },
        )

        with patch.object(service.requests, "get", side_effect=AssertionError("API should not be called")):
            weather = service._fetch_weather(-23.5145766, -46.434624)

        self.assertEqual(weather["source_status"], "cached")
        self.assertEqual(weather["temperature"], 24)

    def test_weather_uses_stale_cache_after_api_limit(self):
        service.WEATHER_CACHE[service._weather_cache_key(-23.5145766, -46.434624)] = {
            "saved_at": service.time() - service.WEATHER_CACHE_TTL_SECONDS - 1,
            "weather": {
                "temperature": 22,
                "wind_speed": 4,
                "wind_gusts": 9,
                "rain": 0,
                "precipitation": 0,
                "weather_code": 2,
                "description": "Parcialmente nublado",
                "source_status": "live",
            },
        }

        class Response:
            def raise_for_status(self):
                raise requests.HTTPError("429 Too Many Requests")

        with patch.object(service.requests, "get", return_value=Response()):
            weather = service._fetch_weather(-23.5145766, -46.434624)

        self.assertEqual(weather["source_status"], "stale")
        self.assertEqual(weather["temperature"], 22)
        self.assertIn("última leitura disponível", weather["description"])


if __name__ == "__main__":
    unittest.main()
