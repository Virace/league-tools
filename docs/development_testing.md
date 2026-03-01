# 开发测试说明（单元测试 + 真实样本链路）

本文面向项目开发者，目标是让“改完代码后做完整验证”可重复、可追溯。

## 1. 适用范围

- 单元测试（纯逻辑/解析器行为）
- 联合测试（基于真实提取样本）
- 完整链路测试（`WAD -> BIN -> BNK/WPK -> XML -> 事件映射 -> WEM`）

## 2. 约束与前置条件

- 真实链路测试依赖本地游戏目录（`Champions` 路径）。
- 需要可用的 `wwiser.pyz`（脚本支持自动下载，也可手工指定）。

目录约定（示例）：

```bash
<游戏根目录>: .../英雄联盟 或 .../League of Legends
<Champions目录>: <游戏根目录>/Game/DATA/FINAL/Champions
```

## 3. 测试分层与推荐执行顺序

### 3.1 快速回归（每次改动后至少执行）

```bash
uv run pytest -q
```

### 3.2 已有样本联合测试（不重新提取）

```bash
uv run pytest -q \
  tests/test_audio_fixture_integrity.py \
  tests/test_fixture_manifest.py
```

说明：

- 执行 `tests/test_audio_fixture_integrity.py` 时会自动生成完整链路报告：
  - `tests/fixtures/external/full_chain_report.json`
- 同一次测试中多个英雄（例如 `--fixture-sample-size 2`）会写入同一个报告文件的 `champions` 数组。

### 3.3 完整链路测试（推荐，优先级最高）

让 pytest 在会话启动前自动提取真实样本，然后执行联合测试：

```bash
uv run pytest -q \
  tests/test_audio_fixture_integrity.py \
  tests/test_fixture_manifest.py \
  --prepare-fixtures \
  --fixture-game-root "<Champions目录>" \
  --fixture-locale zh_CN \
  --fixture-skin 1 \
  --fixture-sample-size 5
```

说明：

- `--fixture-sample-size 5` 表示收集 5 个“完整样本英雄”。
- 脚本默认 `allow_incomplete=False`，不完整样本会跳过，不会进入清单。

## 4. 提取脚本完整用法（`scripts/extract_wad_fixtures.py`）

### 4.1 直接提取（不通过 pytest 钩子）

```bash
uv run python scripts/extract_wad_fixtures.py \
  --game-root "<Champions目录>" \
  --locale zh_CN \
  --skin 1 \
  --sample-size 5 \
  --output tests/fixtures/external
```

### 4.2 常用场景命令

单英雄复现（定位某个英雄问题）：

```bash
uv run python scripts/extract_wad_fixtures.py \
  --game-root "<Champions目录>" \
  --champion Urgot \
  --locale zh_CN \
  --skin 1 \
  --output tests/fixtures/external
```

随机抽样（可复现）：

```bash
uv run python scripts/extract_wad_fixtures.py \
  --game-root "<Champions目录>" \
  --sample-size 5 \
  --shuffle \
  --seed 20260301
```

### 4.3 参数说明（完整）

- `--champion`：单英雄模式（如 `Aatrox`）；不传则多英雄模式
- `--skin`：皮肤编号，默认 `1`
- `--locale`：区域，默认 `zh_CN`
- `--sample-size`：多英雄模式抽样数量，默认 `5`
- `--seed`：随机种子（与 `--shuffle` 配合可复现）
- `--shuffle`：打乱候选英雄顺序
- `--champion-source`：候选来源，支持 `hardcoded/communitydragon/local`
- `--champion-summary-url`：`communitydragon` 模式的数据地址
- `--allow-incomplete`：允许不完整样本（默认不允许）
- `--game-root`：必填，`Champions` WAD 目录
- `--output`：输出目录，默认 `tests/fixtures/external`
- `--include-root-bin`：额外提取 `root.bin`
- `--no-generate-xml`：不生成 XML
- `--no-clean`：不清空输出目录
- `--wwiser-path`：显式指定 `wwiser.pyz` 路径或目录
- `--no-auto-download-wwiser`：禁用自动下载 wwiser
- `--keep-temp`：保留中间临时目录

## 5. pytest 自动提取参数（`tests/conftest.py`）

当使用 `--prepare-fixtures` 时，可用以下参数：

- `--fixture-game-root`（也可用环境变量 `LEAGUE_TOOLS_GAME_ROOT`）
- `--fixture-output`
- `--fixture-locale`（也可用 `LEAGUE_TOOLS_FIXTURE_LOCALE`）
- `--fixture-skin`（也可用 `LEAGUE_TOOLS_FIXTURE_SKIN`）
- `--fixture-sample-size`（也可用 `LEAGUE_TOOLS_FIXTURE_SAMPLE_SIZE`）
- `--fixture-seed`（也可用 `LEAGUE_TOOLS_FIXTURE_SEED`）
- `--fixture-no-xml`
- `--fixture-include-root-bin`
- `--fixture-no-clean`
- `--fixture-no-auto-download-wwiser`

## 6. “完整链路已通过”的判定标准

至少满足以下条件：

1. `tests/test_audio_fixture_integrity.py` 与 `tests/test_fixture_manifest.py` 全部通过。
2. `tests/fixtures/external/manifest.json` 中每个英雄都满足：
   - `missing` 为空数组
   - 存在 `bin/sfx_audio_bnk/sfx_events_bnk/vo_audio_bnk/vo_events_bnk/vo_audio_wpk`
   - `xml` 列表存在且包含 4 个文件
3. 全量回归通过：`uv run pytest -q`

### 6.1 完整链路报告文件（关键核验）

报告路径：

```text
tests/fixtures/external/full_chain_report.json
```

报告包含：

- 顶层元信息：`schema_version`、`generated_at`、`manifest_meta`
- `champions`：每个英雄一条聚合记录
  - `bin`：类别、事件数量、引用 bank 文件、SFX/VO 事件名
  - `bnk`：版本/ID/支持性、WEM ID 列表、events bank 的 HIRC 摘要
  - `wpk`：声明文件数、提取文件数、WEM ID 列表
  - `mapping`：
    - `sfx_event_to_file_ids`
    - `vo_event_to_file_ids`

`mapping` 的最新结构（已精简）：

- `source_file_ids`：源文件 ID 全量集合（SFX 来自对应 audio BNK；VO 来自对应 WPK）
- `event_to_file_ids`：事件名为 key，value 为命中的 ID 列表
  - 结构示例：`"Play_sfx_ZoeSkin01_Homeguard_intro": [153363794]`
- `unmatched_source_file_ids`：源 ID 中未命中任何事件名的 ID 列表

可选快速检查（查看每个英雄的未命中源 ID 数量）：

```bash
uv run python - <<'PY'
import json
from pathlib import Path

p = Path("tests/fixtures/external/full_chain_report.json")
obj = json.loads(p.read_text(encoding="utf-8"))

for c in obj.get("champions", []):
    name = c.get("champion")
    sfx = c.get("mapping", {}).get("sfx_event_to_file_ids", {})
    vo = c.get("mapping", {}).get("vo_event_to_file_ids", {})
    print(
        name,
        "sfx_unmatched=", len(sfx.get("unmatched_source_file_ids", [])),
        "vo_unmatched=", len(vo.get("unmatched_source_file_ids", [])),
    )
PY
```

可选快速检查（读取 manifest）：

```bash
uv run python - <<'PY'
import json
from pathlib import Path
p = Path("tests/fixtures/external/manifest.json")
obj = json.loads(p.read_text(encoding="utf-8"))
required = ["bin","sfx_audio_bnk","sfx_events_bnk","vo_audio_bnk","vo_events_bnk","vo_audio_wpk"]
ok = True
for c in obj.get("champions", []):
    files = c.get("files", {})
    miss = [k for k in required if not files.get(k)]
    xml = files.get("xml", [])
    if miss or c.get("missing") or not isinstance(xml, list) or len(xml) < 4:
        ok = False
    print(c.get("champion"), "missing_keys=", miss, "missing_field=", c.get("missing"), "xml_count=", len(xml) if isinstance(xml, list) else -1)
print("all_complete=", ok)
PY
```

## 7. 改动类型与最低测试要求

- 仅文档/注释修改：`pytest -q` 可选执行。
- 仅纯函数或解析小逻辑改动：至少执行 `pytest -q`。
- 涉及 `WAD/BIN/BNK/WPK` 解析、路径模板、`audio_mapper`、`_HIRC`、`wwiser` 交互：
  - 必须执行完整链路测试（3.3）
  - 然后执行全量回归（3.1）

## 8. 常见问题

- 错误：缺少 `--fixture-game-root`
  - 原因：未传参数且未设置 `LEAGUE_TOOLS_GAME_ROOT`
- 日志出现大量 `[MISS]`
  - 含义：候选路径未命中，脚本会继续回退尝试；最终以 `manifest` 与 pytest 结果判定
- `wwiser` 版本告警
  - 当前为告警非阻断，但应关注 XML 结构漂移风险，建议与项目期望版本对齐
