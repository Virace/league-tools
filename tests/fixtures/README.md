# 测试样本目录说明

- `tests/fixtures/external/`: 由提取脚本生成或手动补充的二进制样本（BIN/BNK/WPK/WAD 等）。

约定：
- 默认优先执行 `scripts/extract_wad_fixtures.py` 自动提取样本。
- 提取脚本失败时，先排查并修复 WAD 解包逻辑或路径模板错误（脚本依赖当前 WAD 解包能力）。
- 若短期内无法修复，可使用 Obsidian（https://github.com/Crauzer/Obsidian）手动提取并补充到 `tests/fixtures/external/`。
- 单元测试与报告以 `tests/fixtures/external/manifest.json` 中已提取成功的英雄清单为准。

## VALORANT 本地专项验证

收集样本与运行测试是两个步骤。当前先使用本地已经提取的文件，后续再接入自动收集脚本；样本继续被 Git 忽略。

在 `tests/fixtures/external/valorant/` 准备：

- `SB_Weapons_Base.bnk`：真实、未裁剪的原始 BNK。
- `layer.xml`：官方 wwiser 输出，可保留完整单个 bank，或仅保留两个 Layer 和选定事件的完整子图。
- `layer-reference.json`：从官方 wwiser 输出核验的 `bank_sha256`、`layers`（父对象和子对象 ID）及 `event_to_file_ids`。

已有真实样本使用 Wwise 145，两个事件为 `Play_Wp_Knife_Equip_1P` 和 `Play_Wp_Knife_Hit_Confirm`，分别对应 8、19 个文件媒体 ID。预期不能来自原生解析器自己的输出。

发布前显式要求本地样本，缺文件时失败：

```powershell
uv run pytest -q tests/test_valorant_hirc.py --require-valorant-fixtures
```

`--fixture-output` 可指定样本父目录。普通无外部样本的测试环境会跳过这些案例；跳过不能当成本地发布验证通过。
