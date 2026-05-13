import argparse
import datetime as dt
import html
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if _stream is not None:
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            try:
                setattr(sys, _stream_name, io.TextIOWrapper(_stream.buffer, encoding="utf-8", line_buffering=True))
            except Exception:
                pass

DEFAULT_BASE_URL = "https://predict.ipubtrans.com"
DEFAULT_TENANT_ID = "2009511491423047680"
DEFAULT_QR_CODE_ID = "2011322258011197440"
DEFAULT_USER_AGENT = "skill-car-university-town-bus/0.1"
DEFAULT_VIEW_PATH = "/mobile"
DEFAULT_VIEW_HASH = "#/pages/home/index"

STATUS_TEXT = {
    1: "运营中",
    2: "暂未发车",
    3: "非营运时间",
}

ARRIVE_STATUS_TEXT = {
    1: "已到站",
    2: "预计到达",
    3: "即将到达",
}


class BusApiError(RuntimeError):
    pass


def int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_text(value):
    return re.sub(r"\s+", "", str(value or "")).lower()


def clean_html(value):
    text = html.unescape(str(value or ""))
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = re.sub(r"(?i)<p[^>]*>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def format_distance_meters(value):
    try:
        distance = float(value)
    except (TypeError, ValueError):
        return ""
    if distance <= 0:
        return ""
    if distance >= 1000:
        return f"{distance / 1000:.1f}公里"
    if distance == int(distance):
        return f"{int(distance)}米"
    return f"{distance:.0f}米"


def format_distance_km(value):
    try:
        distance = float(value)
    except (TypeError, ValueError):
        return ""
    if distance <= 0:
        return ""
    return f"{distance:.1f}公里"


def status_text(status):
    numeric = int_or_none(status)
    return STATUS_TEXT.get(numeric, f"未知状态({status})")


def arrive_text(item):
    arrive_status = int_or_none(item.get("arriveStatus"))
    interval = item.get("interval")
    if arrive_status == 1:
        return "已到站"
    if arrive_status == 2:
        minutes = minutes_from_seconds(interval)
        return f"约{minutes}分钟" if minutes is not None else "预计到达"
    if arrive_status == 3:
        return "即将到达"
    return ARRIVE_STATUS_TEXT.get(arrive_status, "到站状态未知")


def minutes_from_seconds(value):
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    if seconds < 60:
        return 1
    return int((seconds + 59) // 60)


class BusClient:
    def __init__(self, base_url, tenant_id, qr_code_id, timeout):
        self.base_url = base_url.rstrip("/")
        self.tenant_id = tenant_id
        self.qr_code_id = qr_code_id
        self.timeout = timeout
        self.token = None
        self._meta = None

    def make_url(self, path, params=None):
        if not path.startswith("/"):
            path = "/" + path
        url = self.base_url + path
        if params:
            query = urllib.parse.urlencode(params, doseq=True)
            url = url + "?" + query
        return url

    def view_url(self):
        query = urllib.parse.urlencode({"tenantId": self.tenant_id, "qrCodeId": self.qr_code_id})
        return f"{self.base_url}{DEFAULT_VIEW_PATH}?{query}{DEFAULT_VIEW_HASH}"

    def headers(self, content_type=None, include_token=True):
        headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": DEFAULT_USER_AGENT,
            "tenantId": self.tenant_id,
            "qrCodeId": self.qr_code_id,
            "Referer": f"{self.base_url}/mobile?tenantId={self.tenant_id}&qrCodeId={self.qr_code_id}",
        }
        if include_token:
            headers["token"] = self.token or ""
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def request_json(self, method, path, params=None, form=None, json_data=None, include_token=True):
        method = method.upper()
        body = None
        content_type = None
        if method == "POST":
            if form is not None:
                body = urllib.parse.urlencode(form).encode("utf-8")
                content_type = "application/x-www-form-urlencoded;charset=UTF-8"
            elif json_data is not None:
                body = json.dumps(json_data, ensure_ascii=False).encode("utf-8")
                content_type = "application/json"
            else:
                body = b""
                content_type = "application/json"

        url = self.make_url(path, params)
        request = urllib.request.Request(
            url,
            data=body,
            headers=self.headers(content_type=content_type, include_token=include_token),
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")[:800]
            raise BusApiError(f"{method} {url} failed: HTTP {exc.code}: {raw}") from exc
        except urllib.error.URLError as exc:
            raise BusApiError(f"{method} {url} failed: {exc.reason}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BusApiError(f"{method} {url} returned invalid JSON: {raw[:800]}") from exc
        return data

    def call(self, method, path, params=None, form=None, json_data=None, include_token=True):
        data = self.request_json(method, path, params=params, form=form, json_data=json_data, include_token=include_token)
        if data.get("returnCode") != 200:
            raise BusApiError(f"{path} returned {data.get('returnCode')}: {data.get('returnInfo')}")
        return data.get("returnData")

    def ensure_token(self):
        if self.token:
            return self.token
        data = self.call("POST", "/mobile/login/guise", include_token=True)
        token = (data or {}).get("token")
        if not token:
            raise BusApiError("anonymous login succeeded but no token was returned")
        self.token = token
        return token

    def meta(self):
        if self._meta is None:
            self.ensure_token()
            self._meta = self.call("POST", "/mobile/getQrName")
        return dict(self._meta or {})

    def lines(self, lng=None, lat=None, use_default_location=True):
        self.ensure_token()
        if use_default_location and (lng is None or lat is None):
            meta = self.meta()
            lng = meta.get("defaultLng") if lng is None else lng
            lat = meta.get("defaultLat") if lat is None else lat
        return self.call("POST", "/mobile/line/list", form={"lng": "" if lng is None else lng, "lat": "" if lat is None else lat}) or []

    def line_info(self, line_id):
        self.ensure_token()
        return self.call("POST", "/mobile/line/info", form={"lineId": line_id}) or {}

    def first_predictions(self, keys):
        self.ensure_token()
        if isinstance(keys, (list, tuple)):
            keys = ",".join(str(item) for item in keys if item)
        return self.call("GET", "/mobile/predict/first/station/line", params={"keys": keys or ""}) or []

    def station_prediction(self, line_id, station_id):
        self.ensure_token()
        return self.call(
            "GET",
            "/mobile/predict/more/station/line",
            params={"stationId": station_id, "lineId": line_id},
        ) or {}

    def vehicles(self, line_id):
        self.ensure_token()
        return self.call("POST", "/mobile/predict/line/vehList", form={"lineId": line_id}) or []


def attach_line_predictions(client, lines):
    keys = []
    for line in lines:
        line_id = line.get("id") or line.get("lineId")
        station_id = line.get("nearbyStationId")
        if line_id and station_id:
            keys.append(f"{line_id}_{station_id}")
    predictions = client.first_predictions(keys) if keys else []
    by_key = {}
    for item in predictions:
        key = f"{item.get('lineId')}_{item.get('stationId')}"
        by_key[key] = item
    enriched = []
    for line in lines:
        copied = dict(line)
        key = f"{line.get('id') or line.get('lineId')}_{line.get('nearbyStationId')}"
        prediction = by_key.get(key)
        if prediction:
            copied["prediction"] = prediction
            copied["status"] = prediction.get("status")
        enriched.append(copied)
    return enriched


def find_line(lines, query):
    needle = normalize_text(query)
    if not needle:
        raise BusApiError("line name or id is required")
    exact = []
    partial = []
    for line in lines:
        candidates = [
            line.get("id"),
            line.get("lineId"),
            line.get("lineCode"),
            line.get("lineAlias"),
        ]
        normalized_candidates = [normalize_text(value) for value in candidates if value]
        if needle in normalized_candidates:
            exact.append(line)
        elif any(needle in value or value in needle for value in normalized_candidates):
            partial.append(line)
    matches = exact or partial
    if not matches:
        raise BusApiError(f"未找到线路：{query}")
    if len(matches) > 1 and not exact:
        names = "、".join(line.get("lineCode") or line.get("id") or "未命名线路" for line in matches)
        raise BusApiError(f"线路名称不够具体，匹配到多个候选：{names}")
    return matches[0]


def find_station(stations, query):
    needle = normalize_text(query)
    if not needle:
        return None
    exact = []
    partial = []
    for station in stations:
        station_id = station.get("stationId") or station.get("id")
        station_name = station.get("stationName") or station.get("name")
        candidates = [station_id, station_name]
        normalized = [normalize_text(value) for value in candidates if value]
        if needle in normalized:
            exact.append(station)
        elif any(needle in value or value in needle for value in normalized):
            partial.append(station)
    matches = exact or partial
    return matches[0] if matches else None


def extract_station_name(query, stations):
    compact_query = normalize_text(query)
    candidates = []
    for station in stations:
        name = station.get("stationName") or station.get("name")
        normalized = normalize_text(name)
        if normalized and normalized in compact_query:
            candidates.append((len(normalized), name))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def build_lines_payload(client, lng=None, lat=None):
    meta = client.meta()
    lines = attach_line_predictions(client, client.lines(lng=lng, lat=lat))
    return {
        "meta": meta,
        "view_url": client.view_url(),
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "count": len(lines),
        "lines": lines,
    }


def build_line_payload(client, line_query, station_name=None, selected_line=None, detail=None):
    if selected_line is None:
        lines = client.lines(use_default_location=False)
        selected_line = find_line(lines, line_query)
    line_id = selected_line.get("id") or selected_line.get("lineId")
    if detail is None:
        detail = client.line_info(line_id)
    stations = detail.get("stations") or []

    selected_station = None
    if station_name:
        selected_station = find_station(stations, station_name)
        if selected_station is None:
            raise BusApiError(f"线路中未找到站点：{station_name}")
    if selected_station is None and selected_line.get("nearbyStationId"):
        selected_station = find_station(stations, selected_line.get("nearbyStationId"))
    if selected_station is None and stations:
        selected_station = stations[0]

    station_prediction = None
    if selected_station:
        station_prediction = client.station_prediction(line_id, selected_station.get("stationId"))

    vehicles = client.vehicles(line_id)
    return {
        "view_url": client.view_url(),
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "line": selected_line,
        "detail": detail,
        "selected_station": selected_station,
        "station_prediction": station_prediction,
        "vehicles": vehicles,
    }


def build_predict_payload(client, line_query, station_name=None, selected_line=None, detail=None):
    if selected_line is None:
        lines = client.lines(use_default_location=False)
        selected_line = find_line(lines, line_query)
    line_id = selected_line.get("id") or selected_line.get("lineId")
    if detail is None:
        detail = client.line_info(line_id)
    stations = detail.get("stations") or []
    selected_station = find_station(stations, station_name) if station_name else None
    if station_name and selected_station is None:
        raise BusApiError(f"线路中未找到站点：{station_name}")
    if selected_station is None and selected_line.get("nearbyStationId"):
        selected_station = find_station(stations, selected_line.get("nearbyStationId"))
    if selected_station is None and stations:
        selected_station = stations[0]
    prediction = client.station_prediction(line_id, selected_station.get("stationId")) if selected_station else None
    return {
        "view_url": client.view_url(),
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "line": selected_line,
        "selected_station": selected_station,
        "station_prediction": prediction,
    }


def build_vehicles_payload(client, line_query, selected_line=None):
    if selected_line is None:
        lines = client.lines(use_default_location=False)
        selected_line = find_line(lines, line_query)
    line_id = selected_line.get("id") or selected_line.get("lineId")
    return {
        "view_url": client.view_url(),
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "line": selected_line,
        "vehicles": client.vehicles(line_id),
    }


def footer_lines(payload, realtime=True):
    view_url = payload.get("view_url") or f"{DEFAULT_BASE_URL}{DEFAULT_VIEW_PATH}?tenantId={DEFAULT_TENANT_ID}&qrCodeId={DEFAULT_QR_CODE_ID}{DEFAULT_VIEW_HASH}"
    lines = [
        f"更新时间：{payload.get('generated_at')}",
        f"查看更清楚的信息：{view_url}",
    ]
    source = "来源：无界学城穿梭巴士移动端接口"
    if realtime:
        source += "，实时数据可能很快变化"
    lines.append(source + "。")
    return lines


def format_prediction(prediction, stations=None):
    if not prediction:
        return "暂无预测数据"
    status = int_or_none(prediction.get("status"))
    if status != 1:
        return status_text(status)
    trips = prediction.get("list") or []
    if not trips:
        return "运营中，暂无可展示班次"
    station_by_id = {}
    for station in stations or []:
        station_by_id[station.get("stationId")] = station
    parts = []
    for item in trips[:3]:
        station = station_by_id.get(item.get("stationId")) or {}
        station_name = item.get("nextStationName") or station.get("stationName")
        distance = format_distance_meters(item.get("mileage"))
        station_count = item.get("stationNumInterval")
        extra = []
        if station_count not in (None, ""):
            extra.append(f"{station_count}站")
        if distance:
            extra.append(distance)
        if station_name:
            extra.append(f"车辆近 {station_name}")
        veh_code = item.get("vehCode")
        prefix = f"{veh_code} " if veh_code else ""
        suffix = f"（{' / '.join(extra)}）" if extra else ""
        parts.append(prefix + arrive_text(item) + suffix)
    return "；".join(parts)


def format_lines_markdown(payload):
    meta = payload.get("meta") or {}
    lines = payload.get("lines") or []
    title = meta.get("qrName") or "无界学城穿梭巴士"
    output = [f"**{title}全部路线**", ""]
    if not lines:
        output.append("当前没有查询到路线。")
    for line in lines:
        prediction = line.get("prediction") or {}
        status = status_text(prediction.get("status") if prediction else line.get("status"))
        eta = format_prediction(prediction) if prediction else status
        distance = format_distance_km(line.get("mileage"))
        distance_text = f"，距离约 {distance}" if distance else ""
        output.append(
            f"- {line.get('lineCode') or line.get('id')}: "
            f"{line.get('beginStationName')} - {line.get('endStationName')}，"
            f"候车站 {line.get('nearbyStationName') or '--'}{distance_text}，当前 {eta or status}"
        )
    output.extend(["", *footer_lines(payload)])
    return "\n".join(output)


def format_line_markdown(payload):
    detail = payload.get("detail") or {}
    line = payload.get("line") or {}
    selected_station = payload.get("selected_station") or {}
    prediction = payload.get("station_prediction") or {}
    vehicles = payload.get("vehicles") or []
    stations = detail.get("stations") or []
    title = detail.get("lineCode") or line.get("lineCode") or line.get("id")
    output = [f"**{title}**", ""]
    output.append(f"方向：{detail.get('beginStationName') or line.get('beginStationName')} - {detail.get('endStationName') or line.get('endStationName')}")
    mileage = format_distance_km(detail.get("mileage") or line.get("mileage"))
    if mileage:
        output.append(f"里程：{mileage}")
    if selected_station:
        output.append(f"查询站点：{selected_station.get('stationName')}")
    output.append(f"当前预测：{format_prediction(prediction, stations=stations)}")
    output.append("")
    output.append("**站点**")
    for station in stations:
        marker = " <- 当前查询站点" if station.get("stationId") == selected_station.get("stationId") else ""
        output.append(f"- {station.get('stationSort')}. {station.get('stationName')}{marker}")
    notice = clean_html(detail.get("notice"))
    if notice:
        output.extend(["", "**公告 / 发车时间**", notice])
    output.extend(["", "**车辆位置**"])
    if vehicles:
        for vehicle in vehicles:
            output.append("- " + format_vehicle(vehicle))
    else:
        output.append("- 当前接口没有返回在途车辆 GPS。")
    output.extend(["", *footer_lines(payload)])
    return "\n".join(output)


def format_predict_markdown(payload):
    line = payload.get("line") or {}
    station = payload.get("selected_station") or {}
    prediction = payload.get("station_prediction") or {}
    output = [
        f"**{line.get('lineCode') or line.get('id')} 到站预测**",
        "",
        f"站点：{station.get('stationName') or station.get('stationId') or '--'}",
        f"状态：{format_prediction(prediction)}",
        "",
        *footer_lines(payload),
    ]
    return "\n".join(output)


def format_vehicle(vehicle):
    gps = vehicle.get("gps") if isinstance(vehicle.get("gps"), dict) else {}
    lng = gps.get("lng") or vehicle.get("lng")
    lat = gps.get("lat") or vehicle.get("lat")
    direction = gps.get("direction") or vehicle.get("direction")
    parts = []
    if vehicle.get("vehCode"):
        parts.append(str(vehicle.get("vehCode")))
    if vehicle.get("sort"):
        parts.append(f"站序 {vehicle.get('sort')}")
    if lng and lat:
        parts.append(f"GPS {lng},{lat}")
    if direction not in (None, ""):
        parts.append(f"方向角 {direction}")
    return "，".join(parts) if parts else json.dumps(vehicle, ensure_ascii=False, sort_keys=True)


def format_vehicles_markdown(payload):
    line = payload.get("line") or {}
    vehicles = payload.get("vehicles") or []
    output = [f"**{line.get('lineCode') or line.get('id')} 车辆位置**", ""]
    if not vehicles:
        output.append("当前接口没有返回在途车辆 GPS。")
    else:
        for vehicle in vehicles:
            output.append("- " + format_vehicle(vehicle))
    output.extend(["", *footer_lines(payload)])
    return "\n".join(output)


def answer_query(client, query):
    lines = client.lines(use_default_location=False)
    broad_terms = ["全部", "所有", "路线", "线路", "有哪些", "列表"]
    location_terms = ["在哪", "哪里", "位置", "gps", "车辆", "车在哪"]
    predict_terms = ["多久", "几分钟", "到站", "预测", "班次", "发车"]

    try:
        selected = find_line(lines, query)
    except BusApiError:
        selected = None

    if selected is None or any(term in normalize_text(query) for term in broad_terms) and not any(normalize_text(line.get("lineCode")) in normalize_text(query) for line in lines):
        lines_payload = build_lines_payload(client)
        return format_lines_markdown(lines_payload)

    compact_query = normalize_text(query)
    if any(normalize_text(term) in compact_query for term in location_terms):
        return format_vehicles_markdown(build_vehicles_payload(client, selected.get("id") or selected.get("lineId"), selected_line=selected))

    detail = client.line_info(selected.get("id") or selected.get("lineId"))
    station_name = extract_station_name(query, detail.get("stations") or [])
    if any(normalize_text(term) in compact_query for term in predict_terms):
        predict_payload = build_predict_payload(
            client,
            selected.get("id") or selected.get("lineId"),
            station_name=station_name,
            selected_line=selected,
            detail=detail,
        )
        return format_predict_markdown(predict_payload)
    line_payload = build_line_payload(
        client,
        selected.get("id") or selected.get("lineId"),
        station_name=station_name,
        selected_line=selected,
        detail=detail,
    )
    return format_line_markdown(line_payload)


def write_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def make_client(args):
    tenant_id = args.tenant_id or os.environ.get("UNIVERSITY_TOWN_BUS_TENANT_ID") or DEFAULT_TENANT_ID
    qr_code_id = args.qr_code_id or os.environ.get("UNIVERSITY_TOWN_BUS_QR_CODE_ID") or DEFAULT_QR_CODE_ID
    return BusClient(args.base_url, tenant_id, qr_code_id, args.timeout)


def add_common_arguments(parser):
    parser.add_argument("--base-url", default=os.environ.get("UNIVERSITY_TOWN_BUS_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--tenant-id", default=None)
    parser.add_argument("--qr-code-id", default=None)
    parser.add_argument("--timeout", type=int, default=15)


def add_format_argument(parser):
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")


def build_parser():
    parser = argparse.ArgumentParser(prog="bus.py")
    add_common_arguments(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    meta_parser = subparsers.add_parser("meta")
    add_format_argument(meta_parser)

    lines_parser = subparsers.add_parser("lines")
    lines_parser.add_argument("--lng", default=None)
    lines_parser.add_argument("--lat", default=None)
    add_format_argument(lines_parser)

    line_parser = subparsers.add_parser("line")
    line_parser.add_argument("line")
    line_parser.add_argument("--station-name", default=None)
    add_format_argument(line_parser)

    predict_parser = subparsers.add_parser("predict")
    predict_parser.add_argument("line")
    predict_parser.add_argument("--station-name", default=None)
    add_format_argument(predict_parser)

    vehicles_parser = subparsers.add_parser("vehicles")
    vehicles_parser.add_argument("line")
    add_format_argument(vehicles_parser)

    answer_parser = subparsers.add_parser("answer")
    answer_parser.add_argument("query")
    answer_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    client = make_client(args)
    try:
        if args.command == "meta":
            payload = {
                "meta": client.meta(),
                "view_url": client.view_url(),
                "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            }
            if args.format == "json":
                write_json(payload)
            else:
                meta = payload["meta"]
                print(f"**{meta.get('qrName') or '无界学城穿梭巴士'}**")
                print("")
                print(f"- 默认经度：{meta.get('defaultLng')}")
                print(f"- 默认纬度：{meta.get('defaultLat')}")
                print("")
                print(f"查看更清楚的信息：{payload['view_url']}")
        elif args.command == "lines":
            payload = build_lines_payload(client, lng=args.lng, lat=args.lat)
            print(json.dumps(payload, ensure_ascii=False, indent=2) if args.format == "json" else format_lines_markdown(payload))
        elif args.command == "line":
            payload = build_line_payload(client, args.line, station_name=args.station_name)
            print(json.dumps(payload, ensure_ascii=False, indent=2) if args.format == "json" else format_line_markdown(payload))
        elif args.command == "predict":
            payload = build_predict_payload(client, args.line, station_name=args.station_name)
            print(json.dumps(payload, ensure_ascii=False, indent=2) if args.format == "json" else format_predict_markdown(payload))
        elif args.command == "vehicles":
            payload = build_vehicles_payload(client, args.line)
            print(json.dumps(payload, ensure_ascii=False, indent=2) if args.format == "json" else format_vehicles_markdown(payload))
        elif args.command == "answer":
            if args.format == "json":
                write_json({"query": args.query, "answer": answer_query(client, args.query)})
            else:
                print(answer_query(client, args.query))
    except BusApiError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
