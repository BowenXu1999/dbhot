# Python Supabase Template

A comprehensive Python template for connecting to and processing data from Supabase PostgreSQL database, specifically designed to work with `kols` and `influencer_videos` tables. Includes batch processing capabilities for large-scale data extraction.

## Features

- Simple database connection using connection pooling
- Fetch data from `kols` and `influencer_videos` tables
- **Batch processing for large KOL ID datasets (70K+ records)**
- Export data to CSV format with automatic concatenation
- Built-in error handling and logging
- Environment variable configuration
- Retry logic for robust database operations

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   Copy the example file and configure your database connection:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your database connection details:
   ```env
   SUPABASE_DSN=postgresql://user:password@host:port/database
   # OR alternatively:
   DATABASE_URL=postgresql://user:password@host:port/database
   
   # Optional connection pool settings
   DB_POOL_MIN=1
   DB_POOL_MAX=10
   DB_CONNECT_TIMEOUT=30
   ```

3. **Run the application as follows:**
   ```bash
   # Basic usage
   python main.py
   
   # Batch processing for large KOL datasets
   python run_batch_processor.py
   ```

## Batch Processing Workflow

For processing large KOL ID files (70K+ records), this template includes a specialized batch processor:

### Features:
- **Automatic file splitting**: Divides large KOL ID files into manageable batches (default: 1000 IDs per batch)
- **Optimized queries**: Uses temporary tables for efficient batch processing
- **CSV export**: Each batch is exported to a separate CSV file
- **Automatic concatenation**: All batch results are combined into a final CSV file
- **Error handling**: Robust error handling with retry logic and cleanup

### Usage:

1. **Quick start:**
   ```bash
   python run_batch_processor.py
   ```

2. **Command line usage:**
   ```bash
   python batch_kol_processor.py /path/to/filtered_kol_id.csv --output-dir batch_outputs --batch-size 1000
   ```

3. **Programmatic usage:**
   ```python
   from batch_kol_processor import BatchKOLProcessor
   
   processor = BatchKOLProcessor(
       input_csv_path="/path/to/filtered_kol_id.csv",
       output_dir="batch_outputs",
       batch_size=1000
   )
   
   final_file = processor.run()
   print(f"Final output: {final_file}")
   ```

### The Batch Query

For each batch of KOL IDs, the processor executes this optimized query:

```sql
CREATE TEMP TABLE batch_N_kol_ids AS
SELECT unnest(ARRAY['kol_id1', 'kol_id2', ...]::uuid[]) AS kol_id;

SELECT
    iv.kol_id,
    iv.channel,
    iv.video_id,
    iv.play_count,
    iv.comment_count,
    iv.share_count,
    iv.collect_count,
    iv.created_at,
    iv.digg_count,
    k.followers_count
FROM influencer_videos iv
INNER JOIN batch_N_kol_ids t ON iv.kol_id = t.kol_id
JOIN kols k ON iv.kol_id = k.id AND iv.channel = k.channel
ORDER BY iv.kol_id, iv.video_id;

DROP TABLE batch_N_kol_ids;
```

## Regular Usage

The main script demonstrates how to:

- Test database connectivity
- Get summary statistics for your data
- Fetch sample data from both tables
- Export data to CSV files

### Using the DataFetcher class

```python
from main import DataFetcher

fetcher = DataFetcher()

# Test connection
if fetcher.test_connection():
    # Get all KOLs (or limit with limit=10)
    kols = fetcher.get_kols(limit=10)
    
    # Get recent videos (optionally filter by kol_id)
    videos = fetcher.get_influencer_videos(limit=20, kol_id=123)
    
    # Get videos with descriptions
    videos_with_desc = fetcher.get_videos_with_descriptions(limit=50, min_length=20)
    
    # Get summary statistics
    summary = fetcher.get_kol_video_summary()
    
    # Export to CSV
    fetcher.export_to_csv(kols, 'my_kols.csv')

fetcher.close()
```

## Database Tables

This template is designed to work with:

- **kols**: Contains influencer/KOL information
- **influencer_videos**: Contains video content with metadata including:
  - `id`, `video_id`, `kol_id`
  - `title`, `generated_description`
  - `channel`, `sub_channel`
  - `play_count`, `digg_count`, `comment_count`, `share_count`
  - `create_time`, `tags`

## Files

- `main.py`: Main application with DataFetcher class for basic operations
- `batch_kol_processor.py`: Batch processor for large-scale KOL data extraction
- `run_batch_processor.py`: Simple runner script for batch processing
- `db_reader.py`: Database connection manager with connection pooling
- `requirements.txt`: Python dependencies
- `.env.example`: Example environment variables file
- `.env`: Environment variables (create this file from .env.example)

## Error Handling

The application includes:
- Connection retry logic
- Graceful error handling
- Comprehensive logging
- Connection pool management

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SUPABASE_DSN` or `DATABASE_URL` | PostgreSQL connection string | Required |
| `DB_POOL_MIN` | Minimum connections in pool | 1 |
| `DB_POOL_MAX` | Maximum connections in pool | 10 |
| `DB_CONNECT_TIMEOUT` | Connection timeout in seconds | 30 |
| `DB_KEEPALIVES_IDLE` | Keepalive idle time | 600 |
| `DB_KEEPALIVES_INTERVAL` | Keepalive interval | 30 |
| `DB_KEEPALIVES_COUNT` | Keepalive count | 3 |