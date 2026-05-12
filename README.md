# skill-car

`skill-car` 是用于查询深圳大学城无界学城穿梭巴士的 Codex skill 仓库。

## 仓库结构

```text
skill-car/
├── README.md
└── skills/
    └── university-town-bus/
        ├── SKILL.md
        ├── agents/
        │   └── openai.yaml
        └── scripts/
            └── bus.py
```

## 当前 skill

| Skill | 入口 | 用途 |
| --- | --- | --- |
| `university-town-bus` | `skills/university-town-bus/SKILL.md` | 查询无界学城穿梭巴士路线、站点、到站预测和车辆 GPS |

## 安装

先安装 `skills-installer`：

```bash
npm install -g skills-installer
```

安装本仓库中的 skill：

```bash
skills-installer install https://github.com/40lin/skill-car/tree/main/skills/university-town-bus --client codex
```

如果没有全局安装，也可以使用 `npx`：

```bash
npx skills-installer install https://github.com/40lin/skill-car/tree/main/skills/university-town-bus --client codex
```

本地开发时，在仓库根目录运行：

```bash
skills-installer install ./skills/university-town-bus --client codex --project
```

安装后重启 Codex，或开启新的 Codex 会话。

## 使用示例

安装后可以直接在 Codex 中点名 skill：

```text
使用 $university-town-bus 查询全部线路。
使用 $university-town-bus 看无界学城一号线现在到哈工大信息楼还有多久。
使用 $university-town-bus 查无界学城二号线（顺时针方向）车在哪里。
```

也可以直接运行内置脚本：

```bash
python skills/university-town-bus/scripts/bus.py meta
python skills/university-town-bus/scripts/bus.py lines
python skills/university-town-bus/scripts/bus.py line "无界学城一号线"
python skills/university-town-bus/scripts/bus.py predict "无界学城一号线" --station-name "哈工大信息楼"
python skills/university-town-bus/scripts/bus.py vehicles "无界学城一号线"
```

## 注意事项

- 脚本只依赖 Python 3 标准库。
- 默认使用公开移动端参数 `tenantId=2009511491423047680` 和 `qrCodeId=2011322258011197440`。
- 匿名 token 会在每次运行时通过接口动态获取，不会保存账号、密码、Cookie 或长期凭据。
- 巴士状态和车辆位置是实时数据，非营运时间返回“非营运时间”属于正常情况。
