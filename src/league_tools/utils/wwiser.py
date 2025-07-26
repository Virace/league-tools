# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2025/5/10 12:00
# @Update  : 2025/7/15 21:35
# @Detail  : wwiser工具封装

import re
import subprocess
from pathlib import Path
from typing import Optional

import requests
from loguru import logger

from league_tools.utils.type_hints import StrPath


class WwiserManager:
    """
    wwiser工具管理器
    
    用于调用wwiser处理BNK文件并解析结果
    
    鸣谢:
    - @bnnm/wwiser (https://github.com/bnnm/wwiser)
    """

    # GitHub API URL
    GITHUB_API_URL = "https://api.github.com/repos/bnnm/wwiser/releases/latest"

    def __init__(self, wwiser_path: Optional[StrPath] = None, auto_download: bool = True):
        """
        初始化wwiser管理器
        
        :param wwiser_path: wwiser.pyz的路径，如果为None则尝试自动查找
        :param auto_download: 如果未找到wwiser，是否自动从GitHub下载
        """
        self.wwiser_path = self._find_wwiser(wwiser_path)
        self.python_exe = 'python'  # 可配置

        # 如果未找到wwiser并启用了自动下载，尝试下载
        if not self.wwiser_path and auto_download:
            self.wwiser_path = self.download_wwiser()

    def _find_wwiser(self, wwiser_path: Optional[StrPath]) -> Optional[Path]:
        """
        查找wwiser.pyz文件
        
        如果指定了路径，验证该路径；否则在常见位置查找
        
        :param wwiser_path: 指定的wwiser路径
        :return: 有效的wwiser路径或None
        """
        if wwiser_path:
            path = Path(wwiser_path)
            if path.exists():
                logger.info(f"使用指定的wwiser: {path}")
                return path

        # 常见位置查找
        common_locations = [
            Path.cwd() / "wwiser.pyz",
            Path.cwd() / "tools" / "wwiser.pyz",
            Path.home() / "wwiser" / "wwiser.pyz",
            Path(__file__).parent / "wwiser.pyz",
            Path(__file__).parent.parent.parent / "tools" / "wwiser.pyz",
            # 添加更多可能的位置
        ]

        for location in common_locations:
            if location.exists():
                logger.info(f"在 {location} 找到wwiser")
                return location

        logger.warning("未找到wwiser.pyz")
        return None

    def download_wwiser(self, output_dir: Optional[StrPath] = None, version: str = "latest") -> Optional[Path]:
        """
        从GitHub下载wwiser
        
        :param output_dir: 输出目录，如果为None则使用工具目录
        :param version: 版本号，默认为latest
        :return: 下载的wwiser路径或None
        """
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
                    response = requests.get(self.GITHUB_API_URL, timeout=5)
                    response.raise_for_status()
                    release_info = response.json()
                    
                    # 获取版本号和下载URL
                    version = release_info.get("tag_name", "").strip("v")
                    
                    # 找到wwiser.pyz资源
                    assets = release_info.get("assets", [])
                    for asset in assets:
                        if asset.get("name") == "wwiser.pyz":
                            download_url = asset.get("browser_download_url")
                            break
                    
                    logger.info(f"找到最新版本: {version}")
                except (requests.RequestException, ValueError) as e:
                    logger.warning(f"获取GitHub版本信息失败: {e}")
                    logger.warning("将尝试使用备用方式下载")
                    
                    # 如果不知道版本，使用已知的最新版本
                    version = "20241210"  # 硬编码一个已知的最新版本
            
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
                response = requests.get(download_url, timeout=5)
                response.raise_for_status()
                # 文件下载成功
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"wwiser.pyz 下载完成: {output_path}")
                return output_path
            except requests.RequestException as e:
                logger.warning(f"从GitHub下载失败: {e}")
                
                # 尝试使用ghfast CDN
                try:
                    logger.info("尝试使用备用CDN下载...")
                    ghfast_url = f"{ghfast_cdn}{download_url}"
                    logger.debug(f"备用下载链接: {ghfast_url}")
                    
                    response = requests.get(ghfast_url, timeout=10)
                    response.raise_for_status()
                    
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                        
                    logger.info(f"使用备用CDN下载成功: {output_path}")
                    return output_path
                except requests.RequestException as e:
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

    def process_single_file(self, bnk_file: StrPath, output_file: Optional[StrPath] = None,
                            dump_type: str = "xml") -> Optional[Path]:
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
                "-d", dump_type,
                "-dn", str(output_file),
                str(bnk_path)
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

    def process_directory(self, directory: StrPath, pattern: str = "*.bnk",
                          output_file: Optional[StrPath] = None, recursive: bool = False) -> Optional[Path]:
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
                "-d", "xml",  # 使用xml格式
                "-dn", str(output_file)
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
            cmd = [
                self.python_exe,
                str(self.wwiser_path),
                "-h"
            ]

            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # 从帮助信息中解析版本，通常格式为 "wwiser v20241210 - Wwise .bnk parser by bnnm"
            help_text = result.stdout.strip()
            version_match = re.search(r'wwiser\s+v(\d+)', help_text)
            
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

