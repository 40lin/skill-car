---
name: university-town-bus
description: 查询深圳大学城无界学城穿梭巴士实时信息。适用于用户询问大学城巴士、无界学城穿梭巴士、全部线路、发车时间、到站预测、车辆位置、车在哪里、站点或车辆 GPS 等问题。
---

# 无界学城穿梭巴士 Skill

## 概览

使用这个 skill 查询深圳大学城无界学城穿梭巴士移动端接口，并回答路线、站点、发车时间、到站预测和实时车辆位置相关问题。

该 skill 是自包含的。运行时辅助脚本是 `scripts/bus.py`，只依赖 Python 3 标准库；每次运行都会通过公开移动端接口获取新的匿名访问 token，不保存账号、密码、Cookie 或长期凭据。

## 快速开始

在本 skill 目录下运行：

```bash
python scripts/bus.py meta
python scripts/bus.py lines
python scripts/bus.py line "无界学城一号线"
python scripts/bus.py predict "无界学城一号线" --station-name "哈工大信息楼"
python scripts/bus.py vehicles "无界学城一号线"
python scripts/bus.py answer "无界学城一号线现在车在哪里？"
```

需要机器可读结果时，在支持的子命令后追加 `--format json`。

## 数据来源

- 移动端站点：`https://predict.ipubtrans.com/mobile`
- 默认 `tenantId`：`2009511491423047680`
- 默认 `qrCodeId`：`2011322258011197440`
- 匿名 token 接口：`POST /mobile/login/guise`

不要在 skill 中硬编码用户账号、密码、Cookie 或长期 token。让 `bus.py` 在每次运行时调用 `login/guise` 获取匿名 token。

如需切换到其他租户或二维码，可传入 `--tenant-id` / `--qr-code-id`，或设置环境变量：

```bash
UNIVERSITY_TOWN_BUS_TENANT_ID=...
UNIVERSITY_TOWN_BUS_QR_CODE_ID=...
```

## 使用流程

1. 用户问“有哪些路线”“全部线路”“大学城巴士路线”等宽泛问题时，运行 `python scripts/bus.py lines`。
2. 用户指定某条线路时，运行 `python scripts/bus.py line "<线路名或ID>"`。
3. 用户问到站时间、还有多久、某站预测时，运行 `python scripts/bus.py predict "<线路名或ID>" --station-name "<站点名>"`。
4. 用户问“车在哪里”“车辆位置”“GPS”等问题时，运行 `python scripts/bus.py vehicles "<线路名或ID>"`；如果接口没有返回在途车辆，直接说明当前没有车辆 GPS。
5. 用户用自然语言提问时，优先运行 `python scripts/bus.py answer "<用户问题>"`，该命令会返回适合直接回复用户的中文 Markdown。

## 回答规范

- 默认使用中文回答。
- 尽量说明线路名、当前运营状态、查询站点和下一班到站预测。
- 如果接口返回 `非营运时间` 或 `暂未发车`，这是正常业务状态，不要当作错误。
- 如果车辆 GPS 为空，说明“当前接口没有返回在途车辆 GPS”。
- 简要标注来源，例如“来源：无界学城穿梭巴士移动端接口。”
- 在最终查询输出中包含移动端查看链接：`https://predict.ipubtrans.com/mobile?tenantId=2009511491423047680&qrCodeId=2011322258011197440#/pages/home/index`，并提示用户点进去可以查看更清楚的信息。
- 提醒用户实时数据可能快速变化。

## 接口说明

辅助脚本封装了以下已验证接口：

- `POST /mobile/getQrName`：获取二维码名称和默认地图中心经纬度。
- `POST /mobile/line/list`：查询全部线路。
- `POST /mobile/line/info`：查询线路站点、轨迹、公告和发车时间。
- `GET /mobile/predict/first/station/line?keys=...`：查询线路级预测和运营状态。
- `GET /mobile/predict/more/station/line`：查询某个站点的到站预测。
- `POST /mobile/predict/line/vehList`：查询线路车辆 GPS。
