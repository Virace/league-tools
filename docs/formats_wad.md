# WAD文件格式解析

## 概述

WAD文件是英雄联盟使用的存档格式，类似于ZIP压缩包，用于打包游戏资源文件。WAD文件支持多种压缩算法和版本，包含文件索引、数据区域和可选的子块结构。

## 文件结构

### 基本格式
```
WAD文件
├── 文件头
│   ├── 标识 (RW / 1WAD)
│   ├── 版本号 (1/2/3)
│   ├── 文件数量
│   └── 版本特定数据
├── 文件索引表
│   ├── 文件条目1 (路径哈希、偏移、大小等)
│   ├── 文件条目2
│   └── ...
├── 子块索引表 (v3)
└── 文件数据区域
    ├── 文件1数据 (可能压缩)
    ├── 文件2数据
    └── ...
```

### 版本差异

#### 版本1 (V1)
- 基础的文件存档格式
- 简单的文件索引结构
- 基本压缩支持

#### 版本2 (V2)
- 增加了更多的文件属性
- 改进的压缩算法支持
- 扩展的文件类型标识

#### 版本3 (V3)
- 支持子块 (Subchunk) 结构
- 增强的完整性验证 (SHA-256)
- 更复杂的文件分割机制

## 数据结构

### WADSection (文件条目)
```python
@dataclass
class WADSection:
    """表示WAD文件中的单个文件条目"""
    
    path_hash: int              # 文件路径的哈希值
    offset: int                 # 文件数据偏移量
    compressed_size: int        # 压缩后大小
    size: int                   # 原始大小
    type: int                   # 文件类型/压缩类型
    duplicate: bool = False     # 是否为重复条目
    first_subchunk_index: Optional[int] = None  # 第一个子块索引 (v3)
    sha256: Optional[int] = None                # SHA-256哈希前8字节 (v3)
    
    # 计算属性
    subchunk_count: int         # 子块数量 (从type字段计算)
    path: Optional[str]         # 解析后的文件路径
```

### 文件类型常量
```python
# 压缩类型
TYPE_UNCOMPRESSED = 0       # 无压缩
TYPE_GZIP = 1              # GZIP压缩
TYPE_FILE_REDIRECTION = 2   # 文件重定向
TYPE_ZSTD = 3              # Zstandard压缩

# 子块相关
SUBCHUNK_MASK = 0xF0       # 子块数量掩码
TYPE_MASK = 0x0F           # 类型掩码
```

## 解析逻辑

### 文件头分析器
```python
class WadHeaderAnalyzer(SectionNoId):
    """WAD文件头分析器"""
    
    def _read(self):
        # 读取标志和版本
        signature = self._data.customize('<2s')  # 2字节标志
        major = self._data.customize('<B')       # 主版本号
        minor = self._data.customize('<B')       # 次版本号
        
        # 根据版本调用对应的处理方法
        if major == 1:
            self._v1()
        elif major == 2:
            self._v2()  
        elif major == 3:
            self._v3()
```

### 版本特定处理

#### V1处理
```python
def _v1(self):
    """处理版本1的WAD文件"""
    # V1结构相对简单
    self.file_count = self._data.customize('<H')  # 文件数量 (16位)
    # 直接跳转到文件索引
```

#### V2处理  
```python
def _v2(self):
    """处理版本2的WAD文件"""
    # V2增加了ECDSA签名
    self.ecdsa = self._data.bytes(256)           # ECDSA签名 (256字节)
    self.checksum = self._data.customize('<Q')    # 校验和 (64位)
    self.file_count = self._data.customize('<H')  # 文件数量 (16位)
```

#### V3处理
```python
def _v3(self):
    """处理版本3的WAD文件"""
    # V3支持更大的文件数量和子块
    self.ecdsa = self._data.bytes(256)           # ECDSA签名
    self.checksum = self._data.customize('<Q')    # 校验和
    self.file_count = self._data.customize('<L')  # 文件数量 (32位)
```

### 文件索引解析
```python
def _read_file_entries(self):
    """读取文件索引条目"""
    for i in range(self.file_count):
        if self.major == 1:
            # V1格式: 16字节每条目
            path_hash = self._data.customize('<Q')
            offset = self._data.customize('<L')
            compressed_size = self._data.customize('<L')
            size = compressed_size  # V1没有分离的原始大小
            file_type = TYPE_UNCOMPRESSED
            
        elif self.major in [2, 3]:
            # V2/V3格式: 24字节每条目
            path_hash = self._data.customize('<Q')
            offset = self._data.customize('<L')
            compressed_size = self._data.customize('<L')
            size = self._data.customize('<L')
            file_type = self._data.customize('<B')
            duplicate = self._data.customize('<B') == 1
            first_subchunk_index = self._data.customize('<H')
            
            if self.major == 3:
                sha256 = self._data.customize('<Q')  # SHA-256前8字节
```

### 解压缩处理
```python
def _decompress_data(self, data: bytes, file_type: int) -> bytes:
    """根据文件类型解压数据"""
    
    if file_type == TYPE_UNCOMPRESSED:
        return data
    
    elif file_type == TYPE_GZIP:
        import gzip
        return gzip.decompress(data)
    
    elif file_type == TYPE_ZSTD:
        import zstandard as zstd
        dctx = zstd.ZstdDecompressor()
        return dctx.decompress(data)
    
    elif file_type == TYPE_FILE_REDIRECTION:
        # 文件重定向，数据包含重定向路径
        return data.decode('utf-8')
```

### 子块处理 (V3)
```python
def _decompress_subchunks(self, file: WADSection, data: bytes) -> bytes:
    """处理子块分割的文件"""
    
    if file.subchunk_count == 0:
        # 没有子块，直接解压
        return self._decompress_data(data, file.type)
    
    # 读取子块信息
    subchunks = []
    for i in range(file.subchunk_count):
        subchunk_info = self.subchunk_table[file.first_subchunk_index + i]
        subchunks.append(subchunk_info)
    
    # 重组子块数据
    full_data = b''
    for subchunk in subchunks:
        subchunk_data = data[subchunk.offset:subchunk.offset + subchunk.size]
        full_data += self._decompress_data(subchunk_data, subchunk.type)
    
    return full_data
```

## 使用方法

### 基础解析
```python
from league_tools.formats.wad import WAD

# 解析WAD文件
try:
    wad = WAD('data.wad')
    
    # 获取基本信息
    print(f"WAD版本: {wad.major}.{wad.minor}")
    print(f"文件数量: {wad.file_count}")
    print(f"支持的压缩类型: {wad.supported_types}")
    
    # 遍历文件条目
    for file_section in wad.files:
        print(f"文件哈希: {file_section.path_hash}")
        print(f"  偏移: {file_section.offset}")
        print(f"  原始大小: {file_section.size}")
        print(f"  压缩大小: {file_section.compressed_size}")
        print(f"  类型: {file_section.type}")
        print(f"  子块数: {file_section.subchunk_count}")

except FileNotFoundError:
    print("WAD文件未找到")
except Exception as e:
    print(f"解析失败: {e}")
```

### 文件提取

#### 按路径提取
```python
# 提取特定文件
target_paths = [
    'assets/characters/ahri/skins/base/audio/ahri_base_vo_events.bnk',
    'assets/sounds/music/champion_select.ogg'
]

extracted = wad.extract(target_paths, out_dir='extracted/')

for path in extracted:
    print(f"已提取: {path}")
```

#### 按文件条目提取
```python
# 直接使用文件条目提取
for file_section in wad.files:
    if file_section.size > 1000000:  # 提取大于1MB的文件
        try:
            output_path = f"large_files/{file_section.path_hash}.dat"
            wad.extract_by_section(file_section, output_path)
            print(f"已提取大文件: {output_path}")
        except Exception as e:
            print(f"提取失败: {e}")
```

#### 批量提取
```python
# 提取所有特定类型的文件
bnk_files = []
ogg_files = []

# 使用路径哈希表 (如果有的话)
hashtable = {
    'path/to/file1.bnk': 'extracted_name1.bnk',
    'path/to/file2.ogg': 'extracted_name2.ogg'
}

extracted = wad.extract_hash(hashtable, out_dir='extracted_by_hash/')
print(f"通过哈希表提取了 {len(extracted)} 个文件")
```

### 路径哈希计算
```python
# 计算文件路径的哈希值
file_path = "assets/characters/ahri/skins/base/audio/events.bnk"
path_hash = WAD.get_hash(file_path)
print(f"路径 '{file_path}' 的哈希值: {path_hash}")

# 在WAD中查找对应文件
for file_section in wad.files:
    if file_section.path_hash == path_hash:
        print(f"找到文件: 偏移 {file_section.offset}, 大小 {file_section.size}")
        break
```

### 高级功能示例

#### WAD文件分析器
```python
class WADAnalyzer:
    def __init__(self, wad_path):
        self.wad = WAD(wad_path)
        self.stats = {}
    
    def analyze_compression(self):
        """分析压缩情况"""
        type_stats = {}
        total_original = 0
        total_compressed = 0
        
        for file_section in self.wad.files:
            file_type = file_section.type
            if file_type not in type_stats:
                type_stats[file_type] = {
                    'count': 0,
                    'original_size': 0,
                    'compressed_size': 0
                }
            
            type_stats[file_type]['count'] += 1
            type_stats[file_type]['original_size'] += file_section.size
            type_stats[file_type]['compressed_size'] += file_section.compressed_size
            
            total_original += file_section.size
            total_compressed += file_section.compressed_size
        
        # 计算压缩率
        overall_ratio = (1 - total_compressed / total_original) * 100 if total_original > 0 else 0
        
        self.stats['compression'] = {
            'by_type': type_stats,
            'total_original': total_original,
            'total_compressed': total_compressed,
            'compression_ratio': overall_ratio
        }
        
        return self.stats['compression']
    
    def find_duplicates(self):
        """查找重复文件"""
        duplicates = []
        for file_section in self.wad.files:
            if file_section.duplicate:
                duplicates.append(file_section)
        
        self.stats['duplicates'] = duplicates
        return duplicates
    
    def analyze_subchunks(self):
        """分析子块使用情况 (V3)"""
        if self.wad.major < 3:
            return None
        
        subchunk_stats = {
            'files_with_subchunks': 0,
            'max_subchunks': 0,
            'total_subchunks': 0
        }
        
        for file_section in self.wad.files:
            if file_section.subchunk_count > 0:
                subchunk_stats['files_with_subchunks'] += 1
                subchunk_stats['total_subchunks'] += file_section.subchunk_count
                subchunk_stats['max_subchunks'] = max(
                    subchunk_stats['max_subchunks'], 
                    file_section.subchunk_count
                )
        
        self.stats['subchunks'] = subchunk_stats
        return subchunk_stats
    
    def generate_report(self):
        """生成分析报告"""
        compression = self.analyze_compression()
        duplicates = self.find_duplicates()
        subchunks = self.analyze_subchunks()
        
        report = []
        report.append(f"WAD文件分析报告")
        report.append("=" * 40)
        report.append(f"版本: {self.wad.major}.{self.wad.minor}")
        report.append(f"文件总数: {self.wad.file_count}")
        
        # 压缩分析
        report.append(f"\n压缩分析:")
        report.append(f"  总原始大小: {compression['total_original']:,} 字节")
        report.append(f"  总压缩大小: {compression['total_compressed']:,} 字节")
        report.append(f"  压缩率: {compression['compression_ratio']:.1f}%")
        
        for file_type, stats in compression['by_type'].items():
            type_ratio = (1 - stats['compressed_size'] / stats['original_size']) * 100 if stats['original_size'] > 0 else 0
            report.append(f"  类型 {file_type}: {stats['count']} 文件, 压缩率 {type_ratio:.1f}%")
        
        # 重复文件
        report.append(f"\n重复文件: {len(duplicates)} 个")
        
        # 子块分析 (V3)
        if subchunks:
            report.append(f"\n子块分析:")
            report.append(f"  使用子块的文件: {subchunks['files_with_subchunks']}")
            report.append(f"  总子块数: {subchunks['total_subchunks']}")
            report.append(f"  最大子块数: {subchunks['max_subchunks']}")
        
        return "\n".join(report)

# 使用分析器
analyzer = WADAnalyzer('champions.wad')
report = analyzer.generate_report()
print(report)
```

#### 文件搜索工具
```python
class WADSearcher:
    def __init__(self, wad, hashtable=None):
        self.wad = wad
        self.hashtable = hashtable or {}
        self.reverse_hash = {v: k for k, v in self.hashtable.items()}
    
    def search_by_size(self, min_size=None, max_size=None):
        """按文件大小搜索"""
        results = []
        for file_section in self.wad.files:
            if min_size and file_section.size < min_size:
                continue
            if max_size and file_section.size > max_size:
                continue
            results.append(file_section)
        return results
    
    def search_by_type(self, file_type):
        """按文件类型搜索"""
        results = []
        for file_section in self.wad.files:
            if file_section.type == file_type:
                results.append(file_section)
        return results
    
    def search_by_extension(self, extension):
        """按文件扩展名搜索 (需要哈希表)"""
        results = []
        for file_section in self.wad.files:
            if file_section.path_hash in self.reverse_hash:
                path = self.reverse_hash[file_section.path_hash]
                if path.lower().endswith(extension.lower()):
                    results.append((file_section, path))
        return results
    
    def find_largest_files(self, count=10):
        """查找最大的文件"""
        sorted_files = sorted(self.wad.files, key=lambda f: f.size, reverse=True)
        return sorted_files[:count]

# 使用搜索器
searcher = WADSearcher(wad, hashtable)

# 查找大于10MB的文件
large_files = searcher.search_by_size(min_size=10*1024*1024)
print(f"找到 {len(large_files)} 个大于10MB的文件")

# 查找所有BNK文件
bnk_files = searcher.search_by_extension('.bnk')
print(f"找到 {len(bnk_files)} 个BNK文件")

# 查找最大的10个文件
largest = searcher.find_largest_files(10)
for i, file_section in enumerate(largest, 1):
    print(f"{i}. 大小: {file_section.size:,} 字节, 哈希: {file_section.path_hash}")
```

## 错误处理

### 常见异常
```python
from league_tools.formats.wad import MalformedSubchunkError

try:
    wad = WAD('corrupted.wad')
    
    # 尝试提取文件
    for file_section in wad.files:
        try:
            wad.extract_by_section(file_section, f"output/{file_section.path_hash}.dat")
        except MalformedSubchunkError as e:
            print(f"子块损坏: {e}")
        except Exception as e:
            print(f"提取失败: {e}")

except FileNotFoundError:
    print("WAD文件不存在")
except struct.error:
    print("WAD文件格式损坏")
except Exception as e:
    print(f"未知错误: {e}")
```

### 数据完整性验证
```python
def verify_wad_integrity(wad):
    """验证WAD文件完整性"""
    issues = []
    
    # 检查版本兼容性
    if wad.major not in [1, 2, 3]:
        issues.append(f"不支持的版本: {wad.major}.{wad.minor}")
    
    # 检查文件数量一致性
    if len(wad.files) != wad.file_count:
        issues.append(f"文件数量不匹配: 头部{wad.file_count} vs 实际{len(wad.files)}")
    
    # 检查文件偏移
    for i, file_section in enumerate(wad.files):
        if file_section.offset < 0:
            issues.append(f"文件{i} 偏移量无效: {file_section.offset}")
        
        if file_section.compressed_size < 0:
            issues.append(f"文件{i} 压缩大小无效: {file_section.compressed_size}")
        
        if file_section.size < 0:
            issues.append(f"文件{i} 原始大小无效: {file_section.size}")
    
    # V3特定检查
    if wad.major == 3:
        for i, file_section in enumerate(wad.files):
            if file_section.subchunk_count > 0:
                if file_section.first_subchunk_index is None:
                    issues.append(f"文件{i} 子块索引缺失")
    
    return issues

# 验证文件
issues = verify_wad_integrity(wad)
if issues:
    print("发现以下问题:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("WAD文件完整性验证通过")
```

## 性能优化

### 内存管理
```python
# 大文件的流式处理
def extract_large_file_stream(wad, file_section, output_path, chunk_size=1024*1024):
    """流式提取大文件，避免占用过多内存"""
    
    with open(output_path, 'wb') as out_file:
        remaining = file_section.compressed_size
        wad._data.seek(file_section.offset, 0)
        
        while remaining > 0:
            chunk = min(chunk_size, remaining)
            data = wad._data.bytes(chunk)
            
            if file_section.type != 0:  # 需要解压
                data = wad._decompress_data(data, file_section.type)
            
            out_file.write(data)
            remaining -= chunk
            
            # 显示进度
            progress = (file_section.compressed_size - remaining) / file_section.compressed_size * 100
            print(f"\r提取进度: {progress:.1f}%", end='')
        
        print()  # 换行
```

### 批量操作优化
```python
def batch_extract_optimized(wad, file_sections, output_dir, max_workers=4):
    """多线程批量提取文件"""
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    def extract_single(file_section):
        try:
            output_path = output_dir / f"{file_section.path_hash}.dat"
            wad.extract_by_section(file_section, output_path)
            return file_section.path_hash, True, None
        except Exception as e:
            return file_section.path_hash, False, str(e)
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(extract_single, fs) for fs in file_sections]
        
        for future in futures:
            hash_val, success, error = future.result()
            results.append((hash_val, success, error))
            
            if success:
                print(f"✓ 提取成功: {hash_val}")
            else:
                print(f"✗ 提取失败: {hash_val} - {error}")
    
    success_count = sum(1 for _, success, _ in results if success)
    print(f"批量提取完成: {success_count}/{len(file_sections)} 成功")
    
    return results
```

## 总结

WAD文件格式是英雄联盟资源管理的核心，提供了高效的文件打包和压缩功能：

1. **多版本支持** - 兼容V1/V2/V3三个版本格式
2. **灵活的压缩** - 支持无压缩、GZIP、Zstandard等算法
3. **子块机制** - V3版本支持大文件分块存储
4. **完整性验证** - SHA-256哈希确保数据完整性
5. **高效索引** - 基于哈希的快速文件定位
6. **批量操作** - 支持大规模文件提取和处理

该解析器为英雄联盟资源提取和分析工具提供了完整的WAD文件处理能力。