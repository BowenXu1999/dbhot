# KOL影响力分析流水线 - 使用指南

## 概述

这是一个端到端的KOL影响力分析流水线，包含以下功能：
1. 数据库连接和数据提取
2. 批处理大规模数据
3. 影响力评分计算
4. 结果排名和报告生成

## 文件结构

```
python-supabase-template/
├── end_to_end_pipeline.py      # 主流水线脚本
├── run_pipeline.py             # 快速运行脚本
├── db_reader.py                # 数据库读取模块
├── batch_kol_processor.py      # 批处理模块
├── filtered_kol_ids.csv        # 输入KOL ID文件
├── pipeline_outputs/           # 输出目录
│   ├── batch_data/            # 批处理中间数据
│   ├── top_2000_kol_rankings_*.csv  # 排名结果
│   └── pipeline_summary_report_*.txt # 汇总报告
└── pipeline.log               # 执行日志
```

## 使用方法

### 方法1: 使用快速运行脚本

```bash
# 使用默认的filtered_kol_ids.csv文件
python run_pipeline.py

# 指定自定义KOL ID文件
python run_pipeline.py your_kol_file.csv
```

### 方法2: 直接运行主脚本

```bash
python end_to_end_pipeline.py
```

### 方法3: 在Python中使用

```python
from end_to_end_pipeline import KOLAnalysisPipeline

# 创建流水线实例
pipeline = KOLAnalysisPipeline(
    kol_csv_path="your_kol_ids.csv",
    output_dir="results"
)

# 运行完整流水线
success = pipeline.run_complete_pipeline()
```

## 流水线步骤

### 步骤1: 输入验证
- 检查KOL ID CSV文件是否存在
- 验证文件格式和内容

### 步骤2: 数据库连接
- 建立PostgreSQL/Supabase连接
- 测试连接可用性

### 步骤3: 批处理数据提取
- 将KOL ID分批处理（默认1000个一批）
- 从数据库提取相关视频数据
- 合并所有批次结果

### 步骤4: 影响力评分计算
- 数据预处理和清洗
- 计算各项指标（播放量、互动率等）
- 应用影响力评分算法
- 生成排名结果

### 步骤5: 报告生成
- 创建汇总统计报告
- 保存前2000名KOL排名
- 生成执行日志

## 影响力评分算法

```
influence_potential_score = 
  0.3 × log(followers_count + 1) +
  0.4 × z_avg_post_score +
  0.2 × z_vol_play +
  0.1 × interaction_rate
```

其中：
- `followers_count`: 粉丝数量
- `z_avg_post_score`: 标准化的平均帖子评分
- `z_vol_play`: 标准化的播放量波动性
- `interaction_rate`: 平均互动率

## 输入文件格式

KOL ID CSV文件应包含一列，格式如下：

```csv
kol_id
d7f116e3-475e-47de-b1e8-13625ad7a870
9cdc7270-3dcb-466f-8139-bbb6797f091b
4699feb3-f82f-4fed-9f50-197ba835840e
...
```

## 输出文件

### 1. 排名结果文件
`pipeline_outputs/top_2000_kol_rankings_YYYYMMDD_HHMMSS.csv`

包含字段：
- `kol_id`: KOL唯一标识
- `rank`: 排名（1-2000）
- `influence_potential_score`: 影响力评分

### 2. 汇总报告
`pipeline_outputs/pipeline_summary_report_YYYYMMDD_HHMMSS.txt`

包含：
- 执行统计信息
- 前20名KOL列表
- 文件路径信息

### 3. 执行日志
`pipeline.log`

记录详细的执行过程和错误信息

## 环境要求

### Python包依赖
```bash
pip install pandas numpy psycopg[binary] python-dotenv
```

### 数据库配置
需要在`.env`文件中配置数据库连接信息：

```env
DATABASE_HOST=your_host
DATABASE_PORT=5432
DATABASE_NAME=your_database
DATABASE_USER=your_user
DATABASE_PASSWORD=your_password
```

## 性能优化

### 批处理大小
- 默认批处理大小：1000个KOL ID
- 可根据内存和网络情况调整

### 内存使用
- 流水线采用批处理方式，避免内存溢出
- 建议可用内存 >= 4GB

### 执行时间
- 处理78,000个KOL约需要30-60分钟
- 时间取决于数据库性能和网络延迟

## 错误处理

### 常见错误及解决方案

1. **数据库连接失败**
   - 检查网络连接
   - 验证数据库凭据
   - 确认数据库服务正在运行

2. **内存不足**
   - 减小批处理大小
   - 增加系统内存
   - 清理其他占用内存的程序

3. **文件权限错误**
   - 确保有写入权限
   - 检查输出目录是否存在

4. **数据格式错误**
   - 验证输入CSV文件格式
   - 检查KOL ID是否为有效UUID

## 监控和调试

### 查看执行日志
```bash
tail -f pipeline.log
```

### 检查中间结果
批处理的中间文件保存在 `pipeline_outputs/batch_data/` 目录

### 重新运行失败的步骤
可以修改 `end_to_end_pipeline.py` 来单独运行特定步骤

## 扩展功能

### 自定义评分算法
修改 `step4_analyze_influence_scores` 方法中的权重参数

### 添加新的数据源
扩展 `batch_kol_processor.py` 来支持更多数据表

### 输出格式定制
修改报告生成逻辑来支持其他格式（JSON、Excel等）

## 技术支持

如有问题，请查看：
1. `pipeline.log` 执行日志
2. GitHub Issues
3. 项目文档

---
Created by GitHub Copilot
Date: 2025-08-07
