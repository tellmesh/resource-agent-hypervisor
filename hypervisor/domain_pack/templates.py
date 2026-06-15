from __future__ import annotations


def package_name(domain_id: str) -> str:
    return f"app.{domain_id}.v1"


def generic_proto(domain_id: str) -> str:
    pkg = package_name(domain_id)
    return f"""syntax = "proto3";

package {pkg};

message RunTaskCommand {{
  string input = 1;
}}

message TaskRequested {{
  string input = 1;
  int64 requested_at = 2;
}}

message TaskCompleted {{
  string result_id = 1;
  string output = 2;
  int64 completed_at = 3;
}}

message TaskResultView {{
  string result_id = 1;
  string output = 2;
}}
"""


def weather_proto() -> str:
    return """syntax = "proto3";

package app.weather.v1;

message GenerateWeatherMapCommand {
  string place = 1;
  int32 days = 2;
  string forecast_model = 3;
  string output_mime_type = 4;
  bool publish_as_url = 5;
}

message WeatherMapGenerationRequested {
  string place = 1;
  int32 days = 2;
  string forecast_model = 3;
  int64 requested_at = 4;
}

message WeatherMapGenerated {
  string place = 1;
  int32 days = 2;
  string html_url = 3;
  string html_content_hash = 4;
  int64 generated_at = 5;
}

message ForecastDataView {
  string place = 1;
  int32 days = 2;
  string model = 3;
  string forecast_json = 4;
}

message WeatherMapHtmlView {
  string place = 1;
  int32 days = 2;
  string html_url = 3;
  string mime_type = 4;
  string generated_at = 5;
}
"""


def weather_handler() -> str:
    return """from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def handler(payload: dict) -> dict:
    place = payload.get("place", "unknown")
    days = int(payload.get("days", 14))
    model = payload.get("forecast_model") or payload.get("model") or "auto"
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Weather map {place}</title></head><body>"
        f"<h1>Weather map: {place}</h1><p>Forecast horizon: {days} days</p>"
        f"<p>Model: {model}</p><div id='map'>Generated placeholder map view.</div>"
        "</body></html>"
    )
    digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
    url = f"/artifacts/weather-map/{place}/forecast/{days}/index.html"
    return {
        "ok": True,
        "place": place,
        "days": days,
        "model": model,
        "html_url": url,
        "html_content_hash": digest,
        "mime_type": "text/html",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "html": html,
    }
"""


def generic_handler() -> str:
    return """from __future__ import annotations


def handler(payload: dict) -> dict:
    return {"ok": True, "payload": payload, "message": "Generated domain handler stub"}
"""
