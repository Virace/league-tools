# 🐍 Sparse is better than dense.
# 🐼 稀疏优于稠密
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2025/5/10 12:00
# @Update  : 2025/8/4 9:24
# @Detail  : wwiser工具封装


import json
import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Optional

import urllib3
from loguru import logger

from league_tools.utils.type_hints import StrPath


class Singleton(type):
    """
    线程安全的单例元类

    使用方式:
    ```
    class MyClass(metaclass=Singleton):
        pass
    ```
    """

    _instances = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    # super(Singleton, cls)
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class WwiserManager(metaclass=Singleton):
    """
    wwiser工具管理器（单例模式）

    用于调用wwiser处理BNK文件并解析结果

    鸣谢:
    - @bnnm/wwiser (https://github.com/bnnm/wwiser)
    """

    # GitHub API URL
    GITHUB_API_URL = "https://api.github.com/repos/bnnm/wwiser/releases/latest"
    # 期望的wwiser版本
    EXPECTED_VERSION = "20250928"

    def __init__(
        self, wwiser_path: Optional[StrPath] = None, auto_download: bool = True
    ):
        """
        初始化wwiser管理器

        :param wwiser_path: wwiser.pyz的路径或包含wwiser.pyz的目录，如果为None则尝试自动查找
        :param auto_download: 如果未找到wwiser，是否自动从GitHub下载
        """
        self.wwiser_path = self._find_wwiser(wwiser_path)
        self.python_exe = "python"  # 可配置

        # 如果未找到wwiser并启用了自动下载，尝试下载
        if not self.wwiser_path and auto_download:
            self.wwiser_path = self.download_wwiser()

        # 验证版本
        if self.wwiser_path:
            self._validate_version()

    def _find_wwiser(self, wwiser_path: Optional[StrPath]) -> Optional[Path]:
        """
        查找wwiser.pyz文件

        按照优先级查找：
        1. 用户显式指定路径/文件
        2. 环境变量 WWISER_PATH
        3. 常见位置

        :param wwiser_path: 指定的wwiser路径或文件
        :return: 有效的wwiser路径或None
        """
        # 1. 用户显式指定
        if wwiser_path:
            path = Path(wwiser_path)
            found_path = self._resolve_wwiser_path(path, "用户指定")
            if found_path:
                return found_path

        # 2. 环境变量 WWISER_PATH
        env_path = os.environ.get("WWISER_PATH")
        if env_path:
            path = Path(env_path)
            found_path = self._resolve_wwiser_path(path, "环境变量")
            if found_path:
                return found_path

        # 3. 常见位置查找
        common_locations = [
            Path.cwd() / "wwiser.pyz",
            Path.cwd() / "tools" / "wwiser.pyz",
            Path.home() / "wwiser" / "wwiser.pyz",
            Path(__file__).parent / "wwiser.pyz",
            Path(__file__).parent.parent.parent / "tools" / "wwiser.pyz",
        ]

        for location in common_locations:
            if location.exists():
                logger.info(f"在常见位置找到wwiser: {location}")
                return location

        logger.warning("未找到wwiser.pyz")
        return None

    def _resolve_wwiser_path(self, path: Path, source: str) -> Optional[Path]:
        """
        解析wwiser路径，判断是文件还是目录

        :param path: 待解析的路径
        :param source: 路径来源描述
        :return: wwiser.pyz文件路径或None
        """
        if not path.exists():
            logger.debug(f"{source}路径不存在: {path}")
            return None

        if path.is_file():
            # 检查是否为wwiser.pyz文件
            if path.name == "wwiser.pyz":
                logger.info(f"使用{source}的wwiser文件: {path}")
                return path
            else:
                logger.warning(f"{source}指定的文件不是wwiser.pyz: {path}")
                return None
        elif path.is_dir():
            # 在目录中查找wwiser.pyz
            wwiser_file = path / "wwiser.pyz"
            if wwiser_file.exists():
                logger.info(f"在{source}目录中找到wwiser: {wwiser_file}")
                return wwiser_file
            else:
                logger.debug(f"{source}目录中未找到wwiser.pyz: {path}")
                return None
        else:
            logger.warning(f"{source}路径既不是文件也不是目录: {path}")
            return None

    def _validate_version(self) -> None:
        """
        验证wwiser版本是否符合期望

        如果版本不匹配，给出警告但不影响执行
        """
        try:
            current_version = self.get_version()
            if current_version:
                if current_version != self.EXPECTED_VERSION:
                    logger.warning(
                        f"当前wwiser版本 ({current_version}) 与期望版本 ({self.EXPECTED_VERSION}) 不匹配。"
                        f"WwiserHIRC基于版本 {self.EXPECTED_VERSION} 设计，XML格式可能存在差异。"
                    )
                else:
                    logger.info(f"wwiser版本验证通过: {current_version}")
            else:
                logger.warning("无法获取wwiser版本信息，跳过版本验证")
        except Exception as e:
            logger.warning(f"版本验证失败: {e}，但不影响正常使用")

    def download_wwiser(
        self, output_dir: Optional[StrPath] = None, version: str = "latest"
    ) -> Optional[Path]:
        """
        从GitHub下载wwiser

        :param output_dir: 输出目录，如果为None则使用工具目录
        :param version: 版本号，默认为latest
        :return: 下载的wwiser路径或None
        """
        # 创建HTTP连接池管理器
        http = urllib3.PoolManager()

        # 默认保存到工具目录
        if not output_dir:
            output_dir = Path(__file__).parent
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "wwiser.pyz"

        # 备用CDN基础URL
        ghfast_cdn = "https://ghfast.top/"

        try:
            # 尝试获取最新release信息
            download_url = None

            if version == "latest":
                try:
                    logger.info("尝试获取GitHub最新版本信息...")
                    response = http.request("GET", self.GITHUB_API_URL, timeout=5)

                    if response.status != 200:
                        raise urllib3.exceptions.HTTPError(f"HTTP {response.status}")

                    # 解析JSON响应
                    release_info = json.loads(response.data.decode("utf-8"))

                    # 获取版本号和下载URL
                    version = release_info.get("tag_name", "").strip("v")

                    # 找到wwiser.pyz资源
                    assets = release_info.get("assets", [])
                    for asset in assets:
                        if asset.get("name") == "wwiser.pyz":
                            download_url = asset.get("browser_download_url")
                            break

                    logger.info(f"找到最新版本: {version}")
                except (
                    urllib3.exceptions.HTTPError,
                    urllib3.exceptions.RequestError,
                    ValueError,
                    json.JSONDecodeError,
                ) as e:
                    logger.warning(f"获取GitHub版本信息失败: {e}")
                    logger.warning("将尝试使用备用方式下载")

                    # 如果不知道版本，使用已知的最新版本
                    version = self.EXPECTED_VERSION

            # 如果没有获取到下载URL，构建一个
            if not download_url and version:
                # 首先尝试使用jsdelivr CDN
                logger.info(f"使用版本 {version} 构建下载链接")
                github_url = f"https://github.com/bnnm/wwiser/releases/download/v{version}/wwiser.pyz"
                download_url = github_url

            if not download_url:
                logger.error("无法获取wwiser下载链接")
                logger.info("请手动下载wwiser.pyz并放置在以下目录之一:")
                for loc in [Path.cwd(), Path.cwd() / "tools", Path(__file__).parent]:
                    logger.info(f" - {loc}")
                return None

            # 下载文件
            logger.info(f"开始下载 wwiser.pyz: {download_url}")

            # 尝试直接从GitHub下载
            try:
                response = http.request("GET", download_url, timeout=5)

                if response.status != 200:
                    raise urllib3.exceptions.HTTPError(f"HTTP {response.status}")

                # 文件下载成功
                with open(output_path, "wb") as f:
                    f.write(response.data)
                logger.info(f"wwiser.pyz 下载完成: {output_path}")
                return output_path
            except (urllib3.exceptions.HTTPError, urllib3.exceptions.RequestError) as e:
                logger.warning(f"从GitHub下载失败: {e}")

                # 尝试使用ghfast CDN
                try:
                    logger.info("尝试使用备用CDN下载...")
                    ghfast_url = f"{ghfast_cdn}{download_url}"
                    logger.debug(f"备用下载链接: {ghfast_url}")

                    response = http.request("GET", ghfast_url, timeout=10)

                    if response.status != 200:
                        raise urllib3.exceptions.HTTPError(f"HTTP {response.status}")

                    with open(output_path, "wb") as f:
                        f.write(response.data)

                    logger.info(f"使用备用CDN下载成功: {output_path}")
                    return output_path
                except (
                    urllib3.exceptions.HTTPError,
                    urllib3.exceptions.RequestError,
                ) as e:
                    logger.error(f"从备用CDN下载失败: {e}")

            logger.error("所有下载尝试均失败")
            logger.info("请手动下载wwiser.pyz并放置在以下目录之一:")
            for loc in [Path.cwd(), Path.cwd() / "tools", Path(__file__).parent]:
                logger.info(f" - {loc}")
            return None

        except Exception as e:
            logger.error(f"下载wwiser过程中发生错误: {e}")
            logger.info("请手动下载wwiser.pyz并放置在以下目录之一:")
            for loc in [Path.cwd(), Path.cwd() / "tools", Path(__file__).parent]:
                logger.info(f" - {loc}")
            return None

    def process_single_file(
        self,
        bnk_file: StrPath,
        output_file: Optional[StrPath] = None,
        dump_type: str = "xml",
    ) -> Optional[Path]:
        """
        处理单个BNK文件

        :param bnk_file: BNK文件路径
        :param output_file: 输出文件路径（不含后缀），默认为None（自动生成）
        :param dump_type: 输出格式，默认为xml，支持 txt|xml|xsl|xsl_s
        :return: 生成的文件路径或None（如果处理失败）
        """
        if not self.wwiser_path:
            logger.error("wwiser未找到，无法处理")
            return None

        bnk_path = Path(bnk_file)
        if not bnk_path.exists():
            logger.error(f"BNK文件不存在: {bnk_path}")
            return None

        # 默认输出到同一目录，wwiser会自动添加后缀
        if not output_file:
            output_file = bnk_path.with_suffix("")  # 不加后缀，让wwiser自己添加
        else:
            # 确保没有多余的后缀
            output_file = Path(output_file).with_suffix("")

        try:
            cmd = [
                self.python_exe,
                str(self.wwiser_path),
                "-d",
                dump_type,
                "-dn",
                str(output_file),
                str(bnk_path),
            ]

            logger.debug(f"执行命令: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True, text=True)

            # 检查生成的文件
            # 由于wwiser会自动添加后缀，我们需要检查可能的输出文件
            expected_output = None

            # 根据dump_type确定可能的后缀
            suffix = ".txt" if dump_type == "txt" else ".xml"
            expected_output = Path(f"{output_file}{suffix}")

            if expected_output.exists():
                logger.info(f"成功生成文件: {expected_output}")
                return expected_output
            else:
                logger.error(f"处理成功但未找到输出文件: {expected_output}")
                return None

        except subprocess.CalledProcessError as e:
            logger.error(f"处理文件失败: {e.stderr}")
            return None

    def process_directory(
        self,
        directory: StrPath,
        pattern: str = "*.bnk",
        output_file: Optional[StrPath] = None,
        recursive: bool = False,
    ) -> Optional[Path]:
        """
        处理目录中的BNK文件

        :param directory: 包含BNK文件的目录
        :param pattern: 文件匹配模式
        :param output_file: 合并输出的文件路径（不含后缀），默认为None
        :param recursive: 是否递归处理子目录
        :return: 生成的文件路径或None
        """
        if not self.wwiser_path:
            logger.error("wwiser未找到，无法处理")
            return None

        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            logger.error(f"无效的目录: {dir_path}")
            return None

        # 检查目录中是否有匹配的文件
        if recursive:
            file_check = list(dir_path.glob(f"**/{pattern}"))
        else:
            file_check = list(dir_path.glob(pattern))

        if not file_check:
            logger.warning(f"目录 {dir_path} 中未找到匹配的BNK文件")
            return None

        logger.info(f"找到 {len(file_check)} 个BNK文件")

        # 默认输出文件，不添加后缀
        if not output_file:
            output_file = dir_path / "wwiser_output"
        else:
            # 确保没有后缀
            output_file = Path(output_file).with_suffix("")

        try:
            # 使用wwiser的目录处理功能
            cmd = [
                self.python_exe,
                str(self.wwiser_path),
                "-d",
                "xml",  # 使用xml格式
                "-dn",
                str(output_file),
            ]

            # 添加递归参数
            if recursive:
                cmd.append("-r")

            # 添加文件模式路径（支持通配符）
            if recursive:
                cmd.append(str(dir_path / "**" / pattern))
            else:
                cmd.append(str(dir_path / pattern))

            logger.debug(f"执行命令: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True, text=True)

            # 检查生成的文件
            expected_output = Path(f"{output_file}.xml")  # 输出为xml文件

            if expected_output.exists():
                logger.info(f"成功生成合并XML: {expected_output}")
                return expected_output
            else:
                logger.error(f"处理成功但未找到输出文件: {expected_output}")
                return None

        except subprocess.CalledProcessError as e:
            logger.error(f"批量处理失败: {e.stderr}")
            return None

    def get_version(self) -> Optional[str]:
        """
        获取当前wwiser版本

        :return: 版本字符串或None
        """
        if not self.wwiser_path:
            logger.error("wwiser未找到，无法获取版本")
            return None

        try:
            # wwiser没有--version选项，使用-h获取帮助信息中的版本
            cmd = [self.python_exe, str(self.wwiser_path), "-h"]

            result = subprocess.run(cmd, check=True, capture_output=True, text=True)

            # 从帮助信息中解析版本，通常格式为 "wwiser v20241210 - Wwise .bnk parser by bnnm"
            help_text = result.stdout.strip()
            version_match = re.search(r"wwiser\s+v(\d+)", help_text)

            if version_match:
                version_info = version_match.group(1)
                logger.debug(f"检测到wwiser版本: {version_info}")
                return version_info
            else:
                logger.warning("无法从帮助信息中解析版本号")
                return None

        except subprocess.CalledProcessError as e:
            logger.error(f"获取wwiser版本失败: {e.stderr}")
            return None
