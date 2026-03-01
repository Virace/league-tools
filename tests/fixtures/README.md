# 测试样本目录说明

- `tests/fixtures/external/`: 由提取脚本生成或手动补充的二进制样本（BIN/BNK/WPK/WAD 等）。

约定：
- 默认优先执行 `scripts/extract_wad_fixtures.py` 自动提取样本。
- 提取脚本失败时，先排查并修复 WAD 解包逻辑或路径模板错误（脚本依赖当前 WAD 解包能力）。
- 若短期内无法修复，可使用 Obsidian（https://github.com/Crauzer/Obsidian）手动提取并补充到 `tests/fixtures/external/`。
- 单元测试与报告以 `tests/fixtures/external/manifest.json` 中已提取成功的英雄清单为准。
