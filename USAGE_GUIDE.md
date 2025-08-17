# 🚀 KOL批处理使用指南

## 快速开始

### 第一步：配置数据库连接

1. 复制环境变量模板：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入你的Supabase数据库连接信息：
```env
SUPABASE_DSN=postgresql://your_user:your_password@your_host:your_port/your_database
```

### 第二步：运行批处理

有两种运行方式：

#### 方式1：交互式运行（推荐）
```bash
python run_batch_processor.py
```
程序会提示你输入KOL ID文件路径，然后开始处理。

#### 方式2：命令行运行
```bash
python batch_kol_processor.py "/Users/xubowen/Downloads/filtered KOL ID.csv" --output-dir batch_outputs --batch-size 1000
```

## 处理流程

1. **读取KOL ID文件**: 自动检测CSV格式并提取KOL ID
2. **分批处理**: 将70000+个ID分成70+个批次，每批1000个ID
3. **数据库查询**: 对每批ID执行优化的SQL查询
4. **导出CSV**: 每批结果保存为单独的CSV文件
5. **合并结果**: 所有批次结果合并为最终的大CSV文件

## 输出结果

- `batch_outputs/`: 包含所有批次的CSV文件
  - `batch_001_kol_data.csv`
  - `batch_002_kol_data.csv`
  - ...
- `batch_outputs/final_kol_data_YYYYMMDD_HHMMSS.csv`: 最终合并的文件

## 数据字段

每个输出CSV包含以下字段：
- `kol_id`: KOL唯一标识
- `channel`: 频道名称
- `video_id`: 视频ID
- `play_count`: 播放次数
- `comment_count`: 评论数
- `share_count`: 分享数
- `collect_count`: 收藏数
- `created_at`: 创建时间
- `digg_count`: 点赞数
- `followers_count`: 粉丝数

## 注意事项

1. **文件格式**: KOL ID文件应该是CSV格式，包含有效的UUID格式的KOL ID
2. **数据库权限**: 确保数据库连接有足够权限访问 `kols` 和 `influencer_videos` 表
3. **处理时间**: 70000个ID大约需要1-2小时处理时间，取决于网络和数据库性能
4. **磁盘空间**: 确保有足够的磁盘空间存储输出文件

## 故障排除

### 数据库连接问题
- 检查 `.env` 文件中的连接字符串是否正确
- 确认网络连接和数据库服务状态

### 文件读取问题
- 确认KOL ID文件路径正确
- 检查文件权限和格式

### 内存问题
- 减小批次大小（使用 `--batch-size 500`）
- 确保系统有足够的可用内存

## 监控进度

程序会输出详细的日志信息，包括：
- 当前处理的批次
- 每批次的查询时间
- 找到的记录数量
- 错误和警告信息

示例输出：
```
2024-08-07 10:30:15 - batch_kol_processor - INFO - Processing batch 1/75
2024-08-07 10:30:20 - batch_kol_processor - INFO - Batch 1: Query executed in 3.45s, retrieved 15420 records
2024-08-07 10:30:21 - batch_kol_processor - INFO - Batch 1: Exported 15420 records to batch_outputs/batch_001_kol_data.csv
```
