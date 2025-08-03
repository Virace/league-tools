# WPK文件格式解析

## 概述

WPK文件是英雄联盟使用的音频资源封装格式，专门用于打包多个WEM音频文件。WPK文件提供了简单高效的音频文件集合管理，支持文件名存储和批量音频提取功能。

## 文件结构

### 基本格式
```
WPK文件
├── 文件头
│   ├── 魔数标识 ('r3d2')
│   ├── 版本号 (uint32)  
│   └── 文件数量 (uint32)
├── 文件偏移表
│   ├── 文件1偏移 (uint32)
│   ├── 文件2偏移 (uint32)
│   └── ...
└── 文件数据区域
    ├── 文件1
    │   ├── 数据偏移 (uint32)
    │   ├── 数据长度 (uint32)
    │   ├── 文件名长度 (uint32)
    │   ├── 文件名 (UTF-16编码)
    │   └── WEM音频数据
    ├── 文件2
    └── ...
```

### 格式特点

1. **固定文件头** - 使用'r3d2'作为魔数标识
2. **两级索引** - 偏移表 + 文件内部结构
3. **UTF-16文件名** - 支持Unicode文件名
4. **WEM音频格式** - 专门存储Wwise音频文件
5. **简单结构** - 相比WAD格式更加简洁

## 数据结构

### WemFile (音频文件)
```python
@dataclass
class WemFile:
    """WEM音频文件数据类"""
    
    id: int                          # WEM文件ID
    offset: int                      # 在源文件中的偏移
    length: int                      # 文件长度
    filename: Optional[str] = None   # 文件名 (从WPK中读取)
    data: Optional[bytes] = None     # 文件数据
    
    def save_file(self, path, wem=True, vgmstream_cli=None):
        """保存WEM文件，可选转换为其他音频格式"""
```

### WPK解析器
```python
class WPK(SectionNoId):
    """WPK文件解析器"""
    
    # 核心属性
    version: int                     # WPK文件版本
    file_count: int                  # 包含的文件数量  
    offsets: List[int]               # 文件偏移表
    files: List[WemFile]             # 解析出的WEM文件列表
    
    # 文件头标识
    FILE_HEADER = b"r3d2"
```

## 解析逻辑

### 文件头解析
```python
def _read(self):
    """解析WPK文件内容"""
    
    # 1. 验证文件头
    file_header = self._data.customize('<4s')
    if file_header != self.FILE_HEADER:
        raise WPKHeaderError(f"无效的WPK文件头: {file_header}")
    
    # 2. 读取版本和文件数量
    self.version = self._data.customize('<L')
    self.file_count = self._data.customize('<L')
    
    logger.debug(f"WPK版本: {self.version}, 文件数量: {self.file_count}")
```

### 偏移表解析
```python
def _read_offset_table(self):
    """读取文件偏移表"""
    self.offsets = []
    
    for i in range(self.file_count):
        offset = self._data.customize('<L')
        self.offsets.append(offset)
        logger.trace(f"文件 {i+1} 偏移: {offset}")
```

### 文件数据解析
```python  
def _read_file_data(self):
    """解析每个WEM文件的数据"""
    self.files = []
    
    for i, offset in enumerate(self.offsets):
        try:
            # 跳转到文件位置
            self._data.seek(offset, 0)
            
            # 读取文件头信息
            data_offset = self._data.customize('<L')    # 数据相对偏移
            data_length = self._data.customize('<L')    # 数据长度
            filename_length = self._data.customize('<L') # 文件名长度(UTF-16字符数)
            
            # 读取UTF-16编码的文件名
            filename_bytes = self._data.bytes(filename_length * 2)
            filename = filename_bytes.decode('utf-16le').rstrip('\0')
            
            # 计算实际数据位置
            actual_data_offset = offset + data_offset
            
            # 读取WEM数据
            self._data.seek(actual_data_offset, 0)
            wem_data = self._data.bytes(data_length)
            
            # 创建WemFile对象
            wem_file = WemFile(
                id=i,  # 使用索引作为ID
                offset=actual_data_offset,
                length=data_length,
                filename=filename,
                data=wem_data
            )
            
            self.files.append(wem_file)
            logger.debug(f"解析文件 {i+1}: {filename} ({data_length} 字节)")
            
        except Exception as e:
            logger.error(f"解析文件 {i+1} 时出错: {str(e)}")
            raise WPKFormatError(f"文件 {i+1} 解析失败: {str(e)}")
```

## 使用方法

### 基础解析
```python
from league_tools.formats.wpk import WPK

# 解析WPK文件
try:
    wpk = WPK('audio_pack.wpk')
    
    # 获取基本信息  
    print(f"WPK版本: {wpk.version}")
    print(f"文件数量: {wpk.file_count}")
    
    # 遍历WEM文件
    for i, wem_file in enumerate(wpk.files):
        print(f"文件 {i+1}:")
        print(f"  文件名: {wem_file.filename}")
        print(f"  大小: {wem_file.length:,} 字节")
        print(f"  偏移: {wem_file.offset}")

except WPKHeaderError as e:
    print(f"文件头错误: {e}")
except WPKFormatError as e:
    print(f"格式错误: {e}")
except FileNotFoundError:
    print("WPK文件未找到")
```

### 文件提取

#### 提取所有WEM文件
```python
# 提取所有音频文件
wem_files = wpk.extract_files()

import os
output_dir = 'extracted_wem'
os.makedirs(output_dir, exist_ok=True)

for wem_file in wem_files:
    # 使用原始文件名
    if wem_file.filename:
        output_path = os.path.join(output_dir, wem_file.filename)
    else:
        output_path = os.path.join(output_dir, f"file_{wem_file.id}.wem")
    
    # 保存WEM文件
    wem_file.save_file(output_path)
    print(f"已提取: {output_path}")
```

#### 选择性提取
```python
# 按文件名模式提取
import fnmatch

pattern = "*.wem"  # 提取所有WEM文件
# pattern = "*voice*"  # 提取包含voice的文件

for wem_file in wpk.files:
    if wem_file.filename and fnmatch.fnmatch(wem_file.filename.lower(), pattern.lower()):
        output_path = f"filtered/{wem_file.filename}"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        wem_file.save_file(output_path)
        print(f"已提取匹配文件: {output_path}")
```

#### 按大小过滤提取
```python
# 提取大于特定大小的文件
min_size = 100 * 1024  # 100KB

large_files = [wem for wem in wpk.files if wem.length > min_size]
print(f"找到 {len(large_files)} 个大于 {min_size:,} 字节的文件")

for wem_file in large_files:
    output_path = f"large_files/{wem_file.filename or f'file_{wem_file.id}.wem'}"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    wem_file.save_file(output_path)
```

### 音频格式转换

#### 使用vgmstream转换
```python
# 需要安装vgmstream工具
vgmstream_path = "vgmstream-cli.exe"  # Windows
# vgmstream_path = "vgmstream-cli"    # Linux/Mac

for wem_file in wpk.files:
    # 转换为OGG格式
    base_name = wem_file.filename.rsplit('.', 1)[0] if wem_file.filename else f"file_{wem_file.id}"
    ogg_path = f"converted/{base_name}.ogg"
    
    try:
        # save_file方法会自动调用vgmstream进行转换
        wem_file.save_file(ogg_path, wem=False, vgmstream_cli=vgmstream_path)
        print(f"已转换: {ogg_path}")
    except Exception as e:
        print(f"转换失败 {wem_file.filename}: {e}")
```

#### 批量转换
```python
def batch_convert_wpk(wpk_path, output_dir, target_format='ogg', vgmstream_cli=None):
    """批量转换WPK中的音频文件"""
    
    wpk = WPK(wpk_path)
    os.makedirs(output_dir, exist_ok=True)
    
    success_count = 0
    error_count = 0
    
    for wem_file in wpk.files:
        try:
            # 生成输出文件名
            if wem_file.filename:
                base_name = wem_file.filename.rsplit('.', 1)[0]
            else:
                base_name = f"file_{wem_file.id}"
            
            output_path = os.path.join(output_dir, f"{base_name}.{target_format}")
            
            # 转换文件
            if target_format == 'wem':
                wem_file.save_file(output_path, wem=True)
            else:
                wem_file.save_file(output_path, wem=False, vgmstream_cli=vgmstream_cli)
            
            success_count += 1
            print(f"✓ {output_path}")
            
        except Exception as e:
            error_count += 1
            print(f"✗ {wem_file.filename or f'file_{wem_file.id}'}: {e}")
    
    print(f"\n转换完成: {success_count} 成功, {error_count} 失败")
    return success_count, error_count

# 使用批量转换
batch_convert_wpk('audio_pack.wpk', 'converted_audio', 'ogg', 'vgmstream-cli')
```

### 高级功能示例

#### WPK文件分析器
```python
class WPKAnalyzer:
    def __init__(self, wpk_path):
        self.wpk = WPK(wpk_path)
        self.stats = {}
    
    def analyze_file_sizes(self):
        """分析文件大小分布"""
        sizes = [wem.length for wem in self.wpk.files]
        
        self.stats['sizes'] = {
            'total_files': len(sizes),
            'total_size': sum(sizes),
            'avg_size': sum(sizes) / len(sizes) if sizes else 0,
            'min_size': min(sizes) if sizes else 0,
            'max_size': max(sizes) if sizes else 0,
            'median_size': sorted(sizes)[len(sizes)//2] if sizes else 0
        }
        
        return self.stats['sizes']
    
    def analyze_file_names(self):
        """分析文件名模式"""
        extensions = {}
        patterns = {}
        
        for wem_file in self.wpk.files:
            if not wem_file.filename:
                continue
            
            # 统计扩展名
            ext = wem_file.filename.split('.')[-1].lower()
            extensions[ext] = extensions.get(ext, 0) + 1
            
            # 分析文件名模式 (简单分类)
            filename_lower = wem_file.filename.lower()
            if 'voice' in filename_lower or 'vo' in filename_lower:
                patterns['voice'] = patterns.get('voice', 0) + 1
            elif 'sfx' in filename_lower or 'sound' in filename_lower:
                patterns['sfx'] = patterns.get('sfx', 0) + 1
            elif 'music' in filename_lower or 'bgm' in filename_lower:
                patterns['music'] = patterns.get('music', 0) + 1
            else:
                patterns['other'] = patterns.get('other', 0) + 1
        
        self.stats['filenames'] = {
            'extensions': extensions,
            'patterns': patterns
        }
        
        return self.stats['filenames']
    
    def find_largest_files(self, count=10):
        """查找最大的文件"""
        sorted_files = sorted(self.wpk.files, key=lambda f: f.length, reverse=True)
        return sorted_files[:count]
    
    def find_smallest_files(self, count=10):
        """查找最小的文件"""
        sorted_files = sorted(self.wpk.files, key=lambda f: f.length)
        return sorted_files[:count]
    
    def generate_report(self):
        """生成分析报告"""
        size_stats = self.analyze_file_sizes()
        name_stats = self.analyze_file_names()
        largest = self.find_largest_files(5)
        
        report = []
        report.append(f"WPK文件分析报告")
        report.append("=" * 40)
        report.append(f"版本: {self.wpk.version}")
        report.append(f"文件数量: {self.wpk.file_count}")
        
        # 大小统计
        report.append(f"\n文件大小统计:")
        report.append(f"  总大小: {size_stats['total_size']:,} 字节")
        report.append(f"  平均大小: {size_stats['avg_size']:,.0f} 字节")
        report.append(f"  最大文件: {size_stats['max_size']:,} 字节")
        report.append(f"  最小文件: {size_stats['min_size']:,} 字节")
        
        # 文件名统计
        report.append(f"\n文件扩展名:")
        for ext, count in name_stats['extensions'].items():
            report.append(f"  .{ext}: {count} 个文件")
        
        report.append(f"\n文件类型分布:")
        for pattern, count in name_stats['patterns'].items():
            report.append(f"  {pattern}: {count} 个文件")
        
        # 最大文件
        report.append(f"\n最大的5个文件:")
        for i, wem_file in enumerate(largest, 1):
            name = wem_file.filename or f"file_{wem_file.id}"
            report.append(f"  {i}. {name}: {wem_file.length:,} 字节")
        
        return "\n".join(report)

# 使用分析器
analyzer = WPKAnalyzer('audio_pack.wpk')
report = analyzer.generate_report()
print(report)

# 保存报告
with open('wpk_analysis.txt', 'w', encoding='utf-8') as f:
    f.write(report)
```

#### WPK文件比较工具
```python
class WPKComparator:
    def __init__(self, wpk1_path, wpk2_path):
        self.wpk1 = WPK(wpk1_path)
        self.wpk2 = WPK(wpk2_path)
    
    def compare_file_lists(self):
        """比较两个WPK的文件列表"""
        files1 = {wem.filename for wem in self.wpk1.files if wem.filename}
        files2 = {wem.filename for wem in self.wpk2.files if wem.filename}
        
        return {
            'common': files1 & files2,
            'only_in_first': files1 - files2,
            'only_in_second': files2 - files1
        }
    
    def compare_file_sizes(self):
        """比较相同文件的大小差异"""
        files1_dict = {wem.filename: wem.length for wem in self.wpk1.files if wem.filename}
        files2_dict = {wem.filename: wem.length for wem in self.wpk2.files if wem.filename}
        
        size_diffs = {}
        for filename in files1_dict:
            if filename in files2_dict:
                diff = files2_dict[filename] - files1_dict[filename]
                if diff != 0:
                    size_diffs[filename] = {
                        'file1_size': files1_dict[filename],
                        'file2_size': files2_dict[filename],
                        'difference': diff
                    }
        
        return size_diffs
    
    def generate_comparison_report(self):
        """生成比较报告"""
        file_comparison = self.compare_file_lists()
        size_comparison = self.compare_file_sizes()
        
        report = []
        report.append("WPK文件比较报告")
        report.append("=" * 40)
        report.append(f"文件1: {self.wpk1.file_count} 个文件")
        report.append(f"文件2: {self.wpk2.file_count} 个文件")
        
        report.append(f"\n文件列表比较:")
        report.append(f"  共同文件: {len(file_comparison['common'])} 个")
        report.append(f"  仅在文件1: {len(file_comparison['only_in_first'])} 个")
        report.append(f"  仅在文件2: {len(file_comparison['only_in_second'])} 个")
        
        if file_comparison['only_in_first']:
            report.append(f"\n仅在文件1中的文件:")
            for filename in sorted(file_comparison['only_in_first']):
                report.append(f"    {filename}")
        
        if file_comparison['only_in_second']:
            report.append(f"\n仅在文件2中的文件:")
            for filename in sorted(file_comparison['only_in_second']):
                report.append(f"    {filename}")
        
        if size_comparison:
            report.append(f"\n大小有差异的文件:")
            for filename, info in size_comparison.items():
                report.append(f"    {filename}:")
                report.append(f"      文件1: {info['file1_size']:,} 字节")
                report.append(f"      文件2: {info['file2_size']:,} 字节")
                report.append(f"      差异: {info['difference']:+,} 字节")
        
        return "\n".join(report)

# 使用比较器
comparator = WPKComparator('old_audio.wpk', 'new_audio.wpk')
comparison_report = comparator.generate_comparison_report()
print(comparison_report)
```

## 错误处理

### 异常类型
```python
from league_tools.formats.wpk import WPKError, WPKHeaderError, WPKFormatError

try:
    wpk = WPK('audio.wpk')
    
    # 尝试提取文件
    for wem_file in wpk.files:
        try:
            wem_file.save_file(f"output/{wem_file.filename}")
        except IOError as e:
            print(f"保存文件失败 {wem_file.filename}: {e}")
        except Exception as e:
            print(f"未知错误 {wem_file.filename}: {e}")

except WPKHeaderError as e:
    print(f"WPK文件头错误: {e}")
except WPKFormatError as e:
    print(f"WPK格式错误: {e}")
except FileNotFoundError:
    print("WPK文件不存在")
except Exception as e:
    print(f"解析WPK文件时发生未知错误: {e}")
```

### 数据验证
```python
def validate_wpk(wpk):
    """验证WPK文件的完整性"""
    issues = []
    
    # 检查基本属性
    if wpk.file_count != len(wpk.files):
        issues.append(f"文件数量不匹配: 头部{wpk.file_count} vs 实际{len(wpk.files)}")
    
    if wpk.file_count != len(wpk.offsets):
        issues.append(f"偏移表长度不匹配: {len(wpk.offsets)} vs {wpk.file_count}")
    
    # 检查每个文件
    for i, wem_file in enumerate(wpk.files):
        if wem_file.length <= 0:
            issues.append(f"文件{i+1} 长度无效: {wem_file.length}")
        
        if wem_file.offset < 0:
            issues.append(f"文件{i+1} 偏移无效: {wem_file.offset}")
        
        if not wem_file.data:
            issues.append(f"文件{i+1} 数据缺失")
        elif len(wem_file.data) != wem_file.length:
            issues.append(f"文件{i+1} 数据长度不匹配: {len(wem_file.data)} vs {wem_file.length}")
    
    return issues

# 验证文件
issues = validate_wpk(wpk)
if issues:
    print("发现以下问题:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("WPK文件验证通过")
```

## 性能优化

### 内存优化
```python
def extract_wpk_streaming(wpk_path, output_dir, process_callback=None):
    """流式处理WPK文件，减少内存占用"""
    
    # 只解析头部，不加载所有文件数据
    with open(wpk_path, 'rb') as f:
        # 手动解析头部
        header = f.read(4)
        if header != b'r3d2':
            raise WPKHeaderError("无效的WPK文件头")
        
        version = int.from_bytes(f.read(4), 'little')
        file_count = int.from_bytes(f.read(4), 'little')
        
        # 读取偏移表
        offsets = []
        for _ in range(file_count):
            offset = int.from_bytes(f.read(4), 'little')
            offsets.append(offset)
        
        os.makedirs(output_dir, exist_ok=True)
        
        # 逐个处理文件
        for i, offset in enumerate(offsets):
            f.seek(offset)
            
            # 读取文件信息
            data_offset = int.from_bytes(f.read(4), 'little')
            data_length = int.from_bytes(f.read(4), 'little')
            filename_length = int.from_bytes(f.read(4), 'little')
            
            # 读取文件名
            filename_bytes = f.read(filename_length * 2)
            filename = filename_bytes.decode('utf-16le').rstrip('\0')
            
            # 读取并保存文件数据
            f.seek(offset + data_offset)
            
            output_path = os.path.join(output_dir, filename)
            with open(output_path, 'wb') as out_f:
                # 分块读取避免大文件占用过多内存
                remaining = data_length
                chunk_size = 1024 * 1024  # 1MB chunks
                
                while remaining > 0:
                    chunk = min(chunk_size, remaining)
                    data = f.read(chunk)
                    out_f.write(data)
                    remaining -= chunk
            
            if process_callback:
                process_callback(i + 1, file_count, filename)
        
        print(f"流式提取完成: {file_count} 个文件")

# 使用流式提取
def progress_callback(current, total, filename):
    progress = current / total * 100
    print(f"\r进度: {progress:.1f}% ({current}/{total}) - {filename}", end='')

extract_wpk_streaming('large_audio.wpk', 'streaming_output', progress_callback)
```

### 并发处理
```python
def parallel_wpk_processing(wpk_paths, output_base_dir, max_workers=4):
    """并发处理多个WPK文件"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def process_single_wpk(wpk_path):
        try:
            wpk_name = os.path.basename(wpk_path).replace('.wpk', '')
            output_dir = os.path.join(output_base_dir, wpk_name)
            
            wpk = WPK(wpk_path)
            extracted_count = len(wpk.extract_files())
            
            for wem_file in wpk.files:
                if wem_file.filename:
                    output_path = os.path.join(output_dir, wem_file.filename)
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    wem_file.save_file(output_path)
            
            return wpk_path, True, extracted_count, None
            
        except Exception as e:
            return wpk_path, False, 0, str(e)
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_path = {executor.submit(process_single_wpk, path): path for path in wpk_paths}
        
        # 收集结果
        for future in as_completed(future_to_path):
            path, success, count, error = future.result()
            results.append((path, success, count, error))
            
            if success:
                print(f"✓ {os.path.basename(path)}: 提取了 {count} 个文件")
            else:
                print(f"✗ {os.path.basename(path)}: {error}")
    
    success_count = sum(1 for _, success, _, _ in results if success)
    total_files = sum(count for _, success, count, _ in results if success)
    
    print(f"\n并发处理完成:")
    print(f"  成功: {success_count}/{len(wpk_paths)} 个WPK文件")
    print(f"  总提取: {total_files} 个音频文件")
    
    return results

# 使用并发处理
wpk_files = ['audio1.wpk', 'audio2.wpk', 'audio3.wpk']
results = parallel_wpk_processing(wpk_files, 'parallel_output')
```

## 总结

WPK文件格式是英雄联盟音频资源的重要组成部分，提供了专门的WEM音频文件封装功能：

1. **简洁高效** - 相比WAD格式更加专注于音频文件管理
2. **UTF-16文件名** - 支持国际化的文件名存储
3. **直接音频访问** - 专门针对WEM音频文件优化
4. **批量处理能力** - 支持大量音频文件的集中管理
5. **格式转换支持** - 配合vgmstream实现多种音频格式转换
6. **完整性验证** - 提供文件完整性检查功能

该解析器为英雄联盟音频提取、分析和转换工具提供了专业的WPK文件处理能力，特别适合音频资源的批量操作需求。