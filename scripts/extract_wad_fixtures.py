#!/usr/bin/env python3
"""
从英雄联盟 WAD 文件提取测试样本（用于 pytest 前置准备）。

资源来源规则：
- base WAD（不带 locale）：bin + sfx
- locale WAD（带 locale）：vo（优先固定的 vo/en_us 路径）

关键特性：
- 默认清空输出目录后再生成（可关闭）
- 默认生成 XML（调用 wwiser 处理提取到的 bnk）
- 支持多英雄抽样（默认 5，按候选顺序；可选打乱）
- 文件名统一加英雄前缀，避免 `skin0.bin` 冲突
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from loguru import logger

from league_tools.formats import WAD
from league_tools.utils.wwiser import WwiserManager

CHAMPION_SUMMARY_URL = (
    "https://raw.communitydragon.org/latest/"
    "plugins/rcp-be-lol-game-data/global/default/v1/champion-summary.json"
)

# 由 champion-summary.json（2026-03-01）整理的别名快照。
# 需要更新时可切到 communitydragon 模式重新拉取，再覆盖该列表。
HARDCODED_CHAMPION_POOL = [
    "Annie",
    "Olaf",
    "Galio",
    "TwistedFate",
    "XinZhao",
    "Urgot",
    "Leblanc",
    "Vladimir",
    "FiddleSticks",
    "Kayle",
    "MasterYi",
    "Alistar",
    "Ryze",
    "Sion",
    "Sivir",
    "Soraka",
    "Teemo",
    "Tristana",
    "Warwick",
    "Nunu",
    "MissFortune",
    "Ashe",
    "Tryndamere",
    "Jax",
    "Morgana",
    "Zilean",
    "Singed",
    "Evelynn",
    "Twitch",
    "Karthus",
    "Chogath",
    "Amumu",
    "Rammus",
    "Anivia",
    "Shaco",
    "DrMundo",
    "Sona",
    "Kassadin",
    "Irelia",
    "Janna",
    "Gangplank",
    "Corki",
    "Karma",
    "Taric",
    "Veigar",
    "Trundle",
    "Swain",
    "Caitlyn",
    "Blitzcrank",
    "Malphite",
    "Katarina",
    "Nocturne",
    "Maokai",
    "Renekton",
    "JarvanIV",
    "Elise",
    "Orianna",
    "MonkeyKing",
    "Brand",
    "LeeSin",
    "Vayne",
    "Rumble",
    "Cassiopeia",
    "Skarner",
    "Heimerdinger",
    "Nasus",
    "Nidalee",
    "Udyr",
    "Poppy",
    "Gragas",
    "Pantheon",
    "Ezreal",
    "Mordekaiser",
    "Yorick",
    "Akali",
    "Kennen",
    "Garen",
    "Leona",
    "Malzahar",
    "Talon",
    "Riven",
    "KogMaw",
    "Shen",
    "Lux",
    "Xerath",
    "Shyvana",
    "Ahri",
    "Graves",
    "Fizz",
    "Volibear",
    "Rengar",
    "Varus",
    "Nautilus",
    "Viktor",
    "Sejuani",
    "Fiora",
    "Ziggs",
    "Lulu",
    "Draven",
    "Hecarim",
    "Khazix",
    "Darius",
    "Jayce",
    "Lissandra",
    "Diana",
    "Quinn",
    "Syndra",
    "AurelionSol",
    "Kayn",
    "Zoe",
    "Zyra",
    "Kaisa",
    "Seraphine",
    "Gnar",
    "Zac",
    "Yasuo",
    "Velkoz",
    "Taliyah",
    "Camille",
    "Akshan",
    "Belveth",
    "Braum",
    "Jhin",
    "Kindred",
    "Zeri",
    "Jinx",
    "TahmKench",
    "Briar",
    "Viego",
    "Senna",
    "Lucian",
    "Zed",
    "Kled",
    "Ekko",
    "Qiyana",
    "Vi",
    "Aatrox",
    "Nami",
    "Azir",
    "Yuumi",
    "Samira",
    "Thresh",
    "Illaoi",
    "RekSai",
    "Ivern",
    "Kalista",
    "Bard",
    "Rakan",
    "Xayah",
    "Ornn",
    "Sylas",
    "Neeko",
    "Aphelios",
    "Rell",
    "Pyke",
    "Vex",
    "Yone",
    "Ambessa",
    "Mel",
    "Yunara",
    "Sett",
    "Lillia",
    "Gwen",
    "Renata",
    "Aurora",
    "Nilah",
    "KSante",
    "Smolder",
    "Milio",
    "Zaahen",
    "Hwei",
    "Naafiri",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从 WAD 提取测试样本")
    parser.add_argument(
        "--champion",
        default=None,
        help="单英雄模式（如 Aatrox）。不传则走多英雄模式。",
    )
    parser.add_argument("--skin", type=int, default=1, help="皮肤编号（默认 1）")
    parser.add_argument("--locale", default="zh_CN", help="区域（默认 zh_CN）")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=5,
        help="抽样英雄数量（多英雄模式下生效，默认 5）",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="随机种子（传入后会打乱候选列表，便于复现）",
    )
    parser.add_argument(
        "--shuffle",
        action="store_true",
        help="打乱候选英雄顺序（默认不打乱）",
    )
    parser.add_argument(
        "--champion-source",
        choices=["hardcoded", "communitydragon", "local"],
        default="hardcoded",
        help="多英雄模式候选来源：hardcoded/communitydragon/local（默认 hardcoded）",
    )
    parser.add_argument(
        "--champion-summary-url",
        default=CHAMPION_SUMMARY_URL,
        help="communitydragon 模式下的 champion-summary 地址",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="允许不完整样本（默认要求每个英雄样本完整）",
    )
    parser.add_argument(
        "--game-root",
        required=True,
        help="Champions WAD 目录（如 .../Game/DATA/FINAL/Champions）",
    )
    parser.add_argument(
        "--output",
        default="tests/fixtures/external",
        help="输出目录（默认 tests/fixtures/external）",
    )
    parser.add_argument(
        "--include-root-bin",
        action="store_true",
        help="额外提取 root.bin（默认不提取）",
    )
    parser.add_argument(
        "--no-generate-xml",
        action="store_true",
        help="不生成 XML（默认会生成）",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="不清空输出目录（默认会清空）",
    )
    parser.add_argument(
        "--wwiser-path",
        default=None,
        help="可选：显式指定 wwiser.pyz 路径或目录",
    )
    parser.add_argument(
        "--no-auto-download-wwiser",
        action="store_true",
        help="禁用自动下载 wwiser",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="保留中间提取目录（默认自动清理）",
    )
    return parser.parse_args()


def skin_candidates(skin: int) -> list[tuple[str, str]]:
    """
    返回 [(目录名, 文件标记)] 候选，按优先级排列。
    """
    if skin == 0:
        return [
            ("base", "base"),
            ("skin00", "skin00"),
            ("skin0", "skin0"),
        ]
    return [
        (f"skin{skin:02d}", f"skin{skin:02d}"),
        (f"skin{skin}", f"skin{skin}"),
    ]


def _extract_first(
    wad: WAD,
    rel_paths: Iterable[str],
    out_dir: Path,
    label: str,
) -> Optional[Path]:
    for rel_path in rel_paths:
        result = wad.extract([rel_path], out_dir=out_dir, raw=False)[0]
        if result is not None:
            logger.info(f"[OK] {label}: {rel_path}")
            return Path(result)
    logger.warning(f"[MISS] {label}: 所有候选路径均未命中")
    return None


def _copy_to(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def _prefixed_name(champion: str, filename: str) -> str:
    champion = champion.lower()
    if filename.lower().startswith(f"{champion}_"):
        return filename
    return f"{champion}_{filename}"


def _discover_champions(champions_dir: Path, locale: str) -> list[str]:
    """
    扫描目录并返回同时存在 base/locale WAD 的英雄列表。
    """
    base = set()
    locale_set = set()
    suffix = ".wad.client"

    for item in champions_dir.glob(f"*{suffix}"):
        name = item.name[: -len(suffix)]
        if "." in name:
            champion, loc = name.rsplit(".", 1)
            if loc.lower() == locale.lower():
                locale_set.add(champion)
        else:
            base.add(name)

    return sorted(base & locale_set)


def _fetch_champion_aliases(url: str) -> list[str]:
    req = Request(url, headers={"User-Agent": "league-tools/wad-fixtures"})
    with urlopen(req, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    aliases = []
    for item in data:
        if not isinstance(item, dict):
            continue
        champion_id = item.get("id")
        alias = item.get("alias")
        if not isinstance(champion_id, int) or champion_id <= 0:
            continue
        if not alias or alias == "None" or str(alias).startswith("Ruby_"):
            continue
        if alias not in aliases:
            aliases.append(alias)
    return aliases


def _resolve_multi_champion_candidates(
    champions_dir: Path, args: argparse.Namespace
) -> list[str]:
    local_available = _discover_champions(champions_dir, args.locale)
    if not local_available:
        return []

    if args.champion_source == "local":
        source_candidates = local_available
    elif args.champion_source == "communitydragon":
        try:
            source_candidates = _fetch_champion_aliases(args.champion_summary_url)
            if not source_candidates:
                raise ValueError("champion-summary 返回为空")
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                f"communitydragon 英雄列表获取失败，将回退 hardcoded：{type(exc).__name__}: {exc}"
            )
            source_candidates = HARDCODED_CHAMPION_POOL
    else:
        source_candidates = HARDCODED_CHAMPION_POOL

    local_by_lower = {name.lower(): name for name in local_available}
    seen = set()
    candidates = []
    for name in source_candidates:
        local_name = local_by_lower.get(name.lower())
        if local_name is None or local_name in seen:
            continue
        seen.add(local_name)
        candidates.append(local_name)
    if not candidates:
        logger.warning("候选来源与本地可用 WAD 无交集，将回退本地扫描结果")
        candidates = local_available

    if args.shuffle or args.seed is not None:
        rng = random.Random(args.seed)
        rng.shuffle(candidates)

    return candidates


def _vo_path_candidates(
    champion: str, locale: str, skin_dir: str, skin_tag: str, suffix: str
) -> list[str]:
    """
    VO 路径候选：
    - 优先 en_us（实际常见固定）
    - 回退 locale（部分资源可能跟随区域）
    """
    return [
        f"assets/sounds/wwise2016/vo/en_us/characters/{champion}/skins/{skin_dir}/{champion}_{skin_tag}_{suffix}",
        f"assets/sounds/wwise2016/vo/{locale}/characters/{champion}/skins/{skin_dir}/{champion}_{skin_tag}_{suffix}",
    ]


def _sfx_path_candidates(champion: str, skin_dir: str, skin_tag: str, suffix: str) -> list[str]:
    return [
        f"assets/sounds/wwise2016/sfx/characters/{champion}/skins/{skin_dir}/{champion}_{skin_tag}_{suffix}",
    ]


def _ensure_output_dirs(out_root: Path, clean: bool) -> dict[str, Path]:
    if clean and out_root.exists():
        shutil.rmtree(out_root)

    dirs = {
        "bin": out_root / "bin",
        "bnk": out_root / "bnk",
        "wpk": out_root / "wpk",
        "xml": out_root / "xml",
        "wad": out_root / "wad",
    }
    out_root.mkdir(parents=True, exist_ok=True)
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
        gitkeep = path / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()

    gitkeep_root = out_root / ".gitkeep"
    if not gitkeep_root.exists():
        gitkeep_root.touch()

    return dirs


def _extract_for_champion(
    champion_orig: str,
    args: argparse.Namespace,
    dirs: dict[str, Path],
    work_dir: Path,
    wm: Optional[WwiserManager],
) -> dict:
    champion = champion_orig.lower()
    locale = args.locale.lower()

    champions_dir = Path(args.game_root)
    wad_base_path = champions_dir / f"{champion_orig}.wad.client"
    wad_locale_path = champions_dir / f"{champion_orig}.{args.locale}.wad.client"

    entry = {
        "champion": champion_orig,
        "skin": args.skin,
        "files": {},
        "missing": [],
        "_generated_abs": [],
    }

    if not wad_base_path.exists():
        entry["missing"].append(f"base_wad_missing:{wad_base_path}")
        return entry

    if not wad_locale_path.exists():
        logger.warning(f"[{champion_orig}] 区域 WAD 不存在，VO 将回退 base WAD")

    logger.info(f"[{champion_orig}] base WAD:   {wad_base_path}")
    logger.info(f"[{champion_orig}] locale WAD: {wad_locale_path}")

    wad_base = WAD(wad_base_path)
    wad_vo = WAD(wad_locale_path) if wad_locale_path.exists() else wad_base

    # 1) BIN（来自基础WAD）
    bin_rel = f"data/characters/{champion}/skins/skin{args.skin}.bin"
    skin_bin = _extract_first(wad_base, [bin_rel], work_dir, f"{champion_orig} skin bin")
    if skin_bin:
        dst = _copy_to(skin_bin, dirs["bin"] / _prefixed_name(champion, skin_bin.name))
        entry["files"]["bin"] = str(dst.relative_to(Path(args.output)))
        entry["_generated_abs"].append(str(dst))
    else:
        entry["missing"].append("bin")

    if args.include_root_bin:
        root_rel = f"data/characters/{champion}/skins/root.bin"
        root_bin = _extract_first(wad_base, [root_rel], work_dir, f"{champion_orig} root bin")
        if root_bin:
            dst = _copy_to(root_bin, dirs["bin"] / _prefixed_name(champion, root_bin.name))
            entry["files"]["root_bin"] = str(dst.relative_to(Path(args.output)))
            entry["_generated_abs"].append(str(dst))
        else:
            entry["missing"].append("root_bin")

    # 2) SFX（来自基础WAD）
    sfx_audio = None
    sfx_events = None
    for skin_dir, skin_tag in skin_candidates(args.skin):
        if sfx_audio is None:
            sfx_audio = _extract_first(
                wad_base,
                _sfx_path_candidates(champion, skin_dir, skin_tag, "sfx_audio.bnk"),
                work_dir,
                f"{champion_orig} sfx audio ({skin_dir})",
            )
        if sfx_events is None:
            sfx_events = _extract_first(
                wad_base,
                _sfx_path_candidates(champion, skin_dir, skin_tag, "sfx_events.bnk"),
                work_dir,
                f"{champion_orig} sfx events ({skin_dir})",
            )
        if sfx_audio and sfx_events:
            break

    extracted_bnks: list[Path] = []
    if sfx_audio:
        dst = _copy_to(sfx_audio, dirs["bnk"] / _prefixed_name(champion, sfx_audio.name))
        extracted_bnks.append(dst)
        entry["files"]["sfx_audio_bnk"] = str(dst.relative_to(Path(args.output)))
        entry["_generated_abs"].append(str(dst))
    else:
        entry["missing"].append("sfx_audio_bnk")
    if sfx_events:
        dst = _copy_to(sfx_events, dirs["bnk"] / _prefixed_name(champion, sfx_events.name))
        extracted_bnks.append(dst)
        entry["files"]["sfx_events_bnk"] = str(dst.relative_to(Path(args.output)))
        entry["_generated_abs"].append(str(dst))
    else:
        entry["missing"].append("sfx_events_bnk")

    # 3) VO（来自 locale WAD，优先 en_us 路径）
    vo_audio_bnk = None
    vo_audio_wpk = None
    vo_events_bnk = None
    for skin_dir, skin_tag in skin_candidates(args.skin):
        if vo_audio_bnk is None:
            vo_audio_bnk = _extract_first(
                wad_vo,
                _vo_path_candidates(champion, locale, skin_dir, skin_tag, "vo_audio.bnk"),
                work_dir,
                f"{champion_orig} vo audio bnk ({skin_dir})",
            )
        if vo_audio_wpk is None:
            vo_audio_wpk = _extract_first(
                wad_vo,
                _vo_path_candidates(champion, locale, skin_dir, skin_tag, "vo_audio.wpk"),
                work_dir,
                f"{champion_orig} vo audio wpk ({skin_dir})",
            )
        if vo_events_bnk is None:
            vo_events_bnk = _extract_first(
                wad_vo,
                _vo_path_candidates(champion, locale, skin_dir, skin_tag, "vo_events.bnk"),
                work_dir,
                f"{champion_orig} vo events bnk ({skin_dir})",
            )
        if vo_audio_bnk and vo_audio_wpk and vo_events_bnk:
            break

    if vo_audio_bnk:
        dst = _copy_to(vo_audio_bnk, dirs["bnk"] / _prefixed_name(champion, vo_audio_bnk.name))
        extracted_bnks.append(dst)
        entry["files"]["vo_audio_bnk"] = str(dst.relative_to(Path(args.output)))
        entry["_generated_abs"].append(str(dst))
    else:
        entry["missing"].append("vo_audio_bnk")
    if vo_events_bnk:
        dst = _copy_to(vo_events_bnk, dirs["bnk"] / _prefixed_name(champion, vo_events_bnk.name))
        extracted_bnks.append(dst)
        entry["files"]["vo_events_bnk"] = str(dst.relative_to(Path(args.output)))
        entry["_generated_abs"].append(str(dst))
    else:
        entry["missing"].append("vo_events_bnk")
    if vo_audio_wpk:
        dst = _copy_to(vo_audio_wpk, dirs["wpk"] / _prefixed_name(champion, vo_audio_wpk.name))
        entry["files"]["vo_audio_wpk"] = str(dst.relative_to(Path(args.output)))
        entry["_generated_abs"].append(str(dst))
    else:
        entry["missing"].append("vo_audio_wpk")

    # 4) XML（默认开启）：对提取到的所有 bnk 生成
    if not args.no_generate_xml:
        if wm is None:
            entry["missing"].append("xml_wwiser_unavailable")
        else:
            xml_files = []
            for bnk_file in extracted_bnks:
                xml_file = wm.process_single_file(bnk_file)
                if xml_file and Path(xml_file).exists():
                    xml_src = Path(xml_file)
                    dst = _copy_to(
                        xml_src, dirs["xml"] / _prefixed_name(champion, xml_src.name)
                    )
                    if xml_src != dst:
                        xml_src.unlink(missing_ok=True)
                    xml_files.append(str(dst.relative_to(Path(args.output))))
                    entry["_generated_abs"].append(str(dst))
            if xml_files:
                entry["files"]["xml"] = xml_files
            else:
                entry["missing"].append("xml")

    return entry


def main() -> int:
    args = parse_args()

    champions_dir = Path(args.game_root)
    out_root = Path(args.output)
    dirs = _ensure_output_dirs(out_root, clean=not args.no_clean)

    if args.keep_temp:
        work_dir = out_root / "_tmp_extract"
        work_dir.mkdir(parents=True, exist_ok=True)
    else:
        tmp_root = Path(tempfile.mkdtemp(prefix="wad-fixtures-", dir="/tmp"))
        work_dir = tmp_root / "extract"
        work_dir.mkdir(parents=True, exist_ok=True)

    if args.champion:
        candidate_champions = [args.champion]
    else:
        candidate_champions = _resolve_multi_champion_candidates(champions_dir, args)
        if not candidate_champions:
            logger.error(f"在 {champions_dir} 未发现可用于 locale={args.locale} 的英雄 WAD")
            return 1

    logger.info(
        f"准备提取：mode={'single' if args.champion else 'sample'}, "
        f"source={args.champion_source}, shuffle={args.shuffle or args.seed is not None}, "
        f"seed={args.seed}, candidates={candidate_champions}, skin={args.skin}, "
        f"locale={args.locale}, allow_incomplete={args.allow_incomplete}"
    )

    wm: Optional[WwiserManager] = None
    if not args.no_generate_xml:
        wm = WwiserManager(
            wwiser_path=args.wwiser_path,
            auto_download=not args.no_auto_download_wwiser,
        )
        if not wm.wwiser_path:
            logger.warning("未找到 wwiser，XML 生成将跳过")
            wm = None

    manifest = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "game_root": str(champions_dir),
        "locale": args.locale,
        "skin": args.skin,
        "champion_source": args.champion_source,
        "shuffle": args.shuffle or args.seed is not None,
        "seed": args.seed,
        "champions": [],
    }

    all_copied = 0
    target_count = 1 if args.champion else args.sample_size
    selected_count = 0

    for champion in candidate_champions:
        if selected_count >= target_count:
            break

        entry = _extract_for_champion(champion, args, dirs, work_dir, wm)
        is_complete = len(entry["missing"]) == 0

        if not args.allow_incomplete and not is_complete:
            for file_path in entry.get("_generated_abs", []):
                Path(file_path).unlink(missing_ok=True)
            logger.warning(f"[{champion}] 样本不完整，已跳过: {entry['missing']}")
            continue

        entry.pop("_generated_abs", None)
        manifest["champions"].append(entry)
        all_copied += len(entry["files"])
        selected_count += 1

    manifest_path = out_root / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    logger.info(f"提取完成，清单：{manifest_path}")

    if not args.keep_temp:
        shutil.rmtree(work_dir.parent, ignore_errors=True)

    if selected_count < target_count:
        logger.error(f"可用完整样本不足：需要 {target_count}，实际 {selected_count}")
        return 1

    if all_copied == 0:
        logger.warning("未提取到任何文件，请检查参数或补充路径模板")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
