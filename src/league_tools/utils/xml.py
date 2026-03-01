# -*- coding: utf-8 -*-
# @Author  : Virace
# @Email   : Virace@aliyun.com
# @Site    : x-item.com
# @Software: PyCharm
# @Create  : 2025/5/15 10:30
# @Update  : 2025/5/4 8:15
# @Detail  : 

from pathlib import Path
from typing import Dict, Optional, Generator, Callable, Union
from lxml import etree


class MultiRootXmlParser:
    """支持多根节点XML解析器
    
    专门用于解析包含多个根节点的XML文件，使用内存高效的分块读取方法，
    适用于处理大型XML文件，也兼容标准的单根节点XML。
    """
    
    def __init__(self, default_chunk_size: int = 1024*1024):
        """初始化解析器
        
        :param default_chunk_size: 默认分块大小，单位字节，默认1MB
        """
        self.default_chunk_size = default_chunk_size
        self.default_parser_options = {
            'recover': True,  # 尝试从错误中恢复
            'huge_tree': True  # 支持大型XML树
        }
    
    def iter_roots(self, xml_path: Union[str, Path], 
                   filter_func: Optional[Callable[[Dict], bool]] = None,
                   chunk_size: Optional[int] = None,
                   parser_options: Optional[Dict] = None) -> Generator[etree._Element, None, None]:
        """迭代处理XML文件中的所有根节点
        
        :param xml_path: XML文件路径
        :param filter_func: 可选的过滤函数，决定是否处理某个根节点
        :param chunk_size: 每次读取的块大小，单位字节
        :param parser_options: lxml解析器选项
        :yield: XML根节点元素
        """
        # 参数初始化
        xml_path = Path(xml_path)
        if not xml_path.exists():
            raise FileNotFoundError(f"文件不存在: {xml_path}")
        
        chunk_size = chunk_size or self.default_chunk_size
        parser_options = parser_options or self.default_parser_options
        
        # 小文件处理（5MB以下）
        if xml_path.stat().st_size < 5 * 1024 * 1024:
            yield from self._process_small_file(xml_path, filter_func, parser_options)
            return
            
        # 大文件分块处理
        yield from self._process_large_file(xml_path, filter_func, chunk_size, parser_options)
    
    def _process_small_file(self, xml_path: Path, 
                           filter_func: Optional[Callable[[Dict], bool]], 
                           parser_options: Dict) -> Generator[etree._Element, None, None]:
        """处理小型XML文件
        
        尝试使用常规解析方法处理文件，如果失败则回退到分块处理。
        
        :param xml_path: XML文件路径
        :param filter_func: 节点过滤函数
        :param parser_options: 解析器选项
        :yield: XML根节点元素
        """
        try:
            # 使用标准解析方法
            parser = etree.XMLParser(**parser_options)
            tree = etree.parse(str(xml_path), parser)
            root = tree.getroot()
            
            # 情况1: 文件有单一根节点，但内部包含多个<root>元素
            roots = root.findall(".//root")
            if roots and root.tag != 'root':
                for root_elem in roots:
                    if not self._should_process_node(root_elem, filter_func):
                        continue
                    yield root_elem
                return
            
            # 情况2: 单根节点文件，且根节点就是<root>
            if root.tag == 'root':
                if self._should_process_node(root, filter_func):
                    yield root
                return
            
            # 情况3: 根节点包含多个<root>子元素
            for child in root:
                if child.tag == 'root' and self._should_process_node(child, filter_func):
                    yield child
                
        except Exception:
            # 常规方法失败，回退到分块处理
            yield from self._process_large_file(xml_path, filter_func, self.default_chunk_size, parser_options)
    
    def _process_large_file(self, xml_path: Path, 
                           filter_func: Optional[Callable[[Dict], bool]], 
                           chunk_size: int,
                           parser_options: Dict) -> Generator[etree._Element, None, None]:
        """分块处理大型XML文件
        
        :param xml_path: XML文件路径
        :param filter_func: 节点过滤函数
        :param chunk_size: 分块大小
        :param parser_options: 解析器选项
        :yield: XML根节点元素
        """
        buffer = b""
        parser = etree.XMLParser(**parser_options)
        end_tag = b"</root>"
        end_len = len(end_tag)

        with open(xml_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                buffer += chunk

                # 持续从缓冲区提取完整的 <root>...</root> 片段
                while True:
                    start_pos = buffer.find(b"<root")
                    if start_pos == -1:
                        # 保留末尾数据，避免标签跨块被截断
                        if len(buffer) > 1024:
                            buffer = buffer[-1024:]
                        break

                    if start_pos > 0:
                        buffer = buffer[start_pos:]

                    end_pos = buffer.find(end_tag)
                    if end_pos == -1:
                        break

                    end_pos += end_len
                    root_bytes = buffer[:end_pos]
                    buffer = buffer[end_pos:]

                    try:
                        root_elem = etree.fromstring(root_bytes, parser=parser)
                    except Exception:
                        root_elem = None

                    if root_elem is not None and self._should_process_node(root_elem, filter_func):
                        yield root_elem
    
    def _find_root_start(self, buffer: bytes) -> Optional[tuple]:
        """在缓冲区中寻找根节点的开始
        
        :param buffer: 数据缓冲区
        :return: 处理后的状态元组或None
        """
        start_pos = buffer.find(b'<root')
        if start_pos == -1:
            # 保留尾部数据以防标签被分割
            if len(buffer) > 1024:
                return (buffer[-1024:], False, b"")
            return None
        
        # 找到开始标签
        new_buffer = buffer[start_pos:]
        return (new_buffer, True, new_buffer)
    
    def _find_root_end(self, buffer: bytes, root_data: bytes) -> Optional[tuple]:
        """在缓冲区中寻找根节点的结束
        
        :param buffer: 数据缓冲区
        :param root_data: 当前根节点数据
        :return: 处理后的状态元组或None
        """
        end_pos = buffer.find(b'</root>')
        if end_pos == -1:
            return None
            
        # 找到结束标签
        end_pos += 7  # 包含</root>标签长度
        complete_root_data = buffer[:end_pos]
        new_buffer = buffer[end_pos:]
        
        # 解析根节点
        root_elem = None
        try:
            root_elem = etree.fromstring(complete_root_data, 
                                         parser=etree.XMLParser(**self.default_parser_options))
        except Exception:
            # 解析失败，跳过此节点
            pass
            
        return (new_buffer, False, b"", root_elem)
    
    def _should_process_node(self, node: etree._Element, 
                            filter_func: Optional[Callable[[Dict], bool]]) -> bool:
        """判断是否应处理某个节点
        
        :param node: XML节点
        :param filter_func: 过滤函数
        :return: 是否应处理
        """
        if filter_func is None:
            return True
        try:
            return filter_func(node.attrib)
        except Exception:
            return False


# 使用案例
if __name__ == "__main__":
    # 创建解析器实例
    parser = MultiRootXmlParser()
    xml_file = "../data/banks.xml"
    
    # 示例: 遍历所有根节点
    print("\n===== 遍历XML根节点 =====")
    root_count = 0
    for root in parser.iter_roots(xml_file):
        root_count += 1
        if root_count <= 5:  # 只显示前5个
            print(f"根节点 #{root_count}: {root.get('filename', '未知')}")
    print(f"总计: {root_count} 个根节点")
    
    # 示例: 使用过滤器只处理特定文件
    print("\n===== 使用过滤器筛选节点 =====")
    def events_filter(attributes):
        return 'filename' in attributes and 'events' in attributes['filename']
    
    event_count = 0
    for root in parser.iter_roots(xml_file, filter_func=events_filter):
        event_count += 1
        if event_count <= 3:  # 只显示前3个
            print(f"事件文件: {root.get('filename')}")
    print(f"总计找到 {event_count} 个事件文件")

