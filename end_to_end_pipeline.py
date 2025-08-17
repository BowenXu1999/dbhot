#!/usr/bin/env python3
"""
端到端KOL影响力分析流水线
从数据库连接 -> 批处理取数 -> 数据分析 -> 输出结果

Author: GitHub Copilot
Date: 2025-08-07
"""

import os
import sys
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from pathlib import Path

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# 导入自定义模块
from db_reader import DatabaseReader
from batch_kol_processor import BatchKOLProcessor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class KOLAnalysisPipeline:
    """KOL影响力分析完整流水线"""
    
    def __init__(self, kol_csv_path: str, output_dir: str = "pipeline_outputs"):
        """
        初始化流水线
        
        Args:
            kol_csv_path: KOL ID CSV文件路径
            output_dir: 输出目录
        """
        self.kol_csv_path = kol_csv_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 生成时间戳
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 初始化组件
        self.db_reader = None
        self.batch_processor = None
        
        logger.info(f"Pipeline initialized with output directory: {self.output_dir}")
    
    def step1_validate_input(self) -> bool:
        """步骤1：验证输入文件"""
        logger.info("Step 1: Validating input file...")
        
        if not os.path.exists(self.kol_csv_path):
            logger.error(f"KOL CSV file not found: {self.kol_csv_path}")
            return False
        
        try:
            df = pd.read_csv(self.kol_csv_path)
            kol_count = len(df)
            logger.info(f"Found {kol_count} KOL IDs in input file")
            
            if kol_count == 0:
                logger.error("Input file is empty")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Error reading input file: {e}")
            return False
    
    def step2_setup_database_connection(self) -> bool:
        """步骤2：设置数据库连接"""
        logger.info("Step 2: Setting up database connection...")
        
        try:
            self.db_reader = DatabaseReader()
            
            # 测试连接
            if self.db_reader.test_connection():
                logger.info("Database connection established successfully")
                return True
            else:
                logger.error("Database connection test failed")
                return False
                
        except Exception as e:
            logger.error(f"Failed to establish database connection: {e}")
            return False
    
    def step3_batch_process_data(self) -> str:
        """步骤3：批处理提取数据"""
        logger.info("Step 3: Starting batch processing...")
        
        try:
            # 初始化批处理器
            self.batch_processor = BatchKOLProcessor(
                input_csv_path=self.kol_csv_path,
                output_dir=str(self.output_dir / "batch_data"),
                batch_size=1000
            )
            
            # 执行批处理
            # 首先读取KOL IDs
            kol_ids = self.batch_processor.read_kol_ids()
            if not kol_ids:
                logger.error("Failed to read KOL IDs from input file")
                return None
                
            # 然后处理所有批次
            final_csv_path = self.batch_processor.process_all_batches(kol_ids)
            
            if final_csv_path and os.path.exists(final_csv_path):
                logger.info(f"Batch processing completed: {final_csv_path}")
                return final_csv_path
            else:
                logger.error("Batch processing failed - no output file generated")
                return None
                
        except Exception as e:
            logger.error(f"Error during batch processing: {e}")
            return None
    
    def step4_analyze_influence_scores(self, data_csv_path: str) -> str:
        """步骤4：计算影响力评分"""
        logger.info("Step 4: Analyzing influence scores...")
        
        try:
            # 加载数据
            df = pd.read_csv(data_csv_path)
            logger.info(f"Loaded {len(df)} records for analysis")
            
            # 数据预处理
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
            
            numeric_cols = ["play_count", "comment_count", "share_count", "collect_count",
                           "digg_count", "followers_count"]
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            
            # 过滤到每个KOL的最新月份
            latest_month_map = df.groupby("kol_id")["created_at"].max().dt.month.to_dict()
            df["month"] = df["created_at"].dt.month
            df = df[df["kol_id"].map(latest_month_map) == df["month"]]
            
            logger.info(f"After filtering to latest month: {len(df)} records")
            
            # 计算帖子评分
            df["post_score"] = (df["play_count"]
                               + 2 * df["digg_count"]
                               + 4 * df["comment_count"]
                               + 2 * df["collect_count"] 
                               + 4 * df["share_count"])
            
            # 计算互动比率
            df["interaction_ratio"] = np.where(
                df["play_count"] > 0,
                (df["comment_count"] + df["digg_count"] + df["share_count"] + df["collect_count"])
                / df["play_count"],
                np.nan,
            )
            
            # 按KOL和渠道分组聚合
            g = df.groupby(["kol_id", "channel"])
            base = g.agg(
                num_video=("video_id", "nunique"),
                avg_play=("play_count", "mean"),
                max_play=("play_count", "max"),
                min_play=("play_count", "min"),
                std_play=("play_count", lambda x: x.std(ddof=1)),
                followers_count=("followers_count", "max"),
                avg_comment=("comment_count", "mean"),
                avg_share=("share_count", "mean"),
                avg_collect=("collect_count", "mean"),
                avg_post_score=("post_score", "mean"),
                interaction_rate=("interaction_ratio", "mean"),
            ).reset_index()
            
            # 计算播放量波动性
            base["vol_play"] = (base["max_play"] - base["min_play"]) / base["std_play"]
            base.loc[base["std_play"] == 0, "vol_play"] = np.nan
            
            # 过滤粉丝数范围 [1k, 100k]
            base = base[(base["followers_count"] >= 1_000) & 
                       (base["followers_count"] <= 100_000)].copy()
            
            logger.info(f"After follower filtering: {len(base)} KOL-channel combinations")
            
            # Z-score标准化
            for col in ["avg_post_score", "vol_play"]:
                mean = base[col].mean()
                std = base[col].std(ddof=1)
                if std == 0 or np.isnan(std):
                    base[f"z_{col}"] = 0.0
                else:
                    base[f"z_{col}"] = (base[col] - mean) / std
            
            # 计算影响力潜力评分
            base["influence_potential_score"] = (
                0.3 * np.log(base["followers_count"] + 1)
                + 0.4 * base["z_avg_post_score"]
                + 0.2 * base["z_vol_play"]
                + 0.1 * base["interaction_rate"]
            )
            
            # 获取每个KOL的最高评分
            top_kols = base.groupby("kol_id")["influence_potential_score"].max().reset_index()
            top_kols = top_kols.sort_values("influence_potential_score", ascending=False)
            
            # 获取前2000名
            top_2000_kols = top_kols.head(2000).copy()
            top_2000_kols['rank'] = range(1, len(top_2000_kols) + 1)
            
            # 保存结果
            output_file = self.output_dir / f"top_2000_kol_rankings_{self.timestamp}.csv"
            top_2000_kols.to_csv(output_file, index=False)
            
            logger.info(f"Analysis complete - Top 2000 KOLs saved to: {output_file}")
            logger.info(f"Total distinct KOLs analyzed: {len(top_kols)}")
            
            # 显示前10名
            logger.info("Top 10 KOLs by influence score:")
            for i, row in top_2000_kols.head(10).iterrows():
                logger.info(f"  {row['rank']:2d}. {row['kol_id']} (score: {row['influence_potential_score']:.4f})")
            
            return str(output_file)
            
        except Exception as e:
            logger.error(f"Error during influence score analysis: {e}")
            return None
    
    def step5_generate_summary_report(self, rankings_csv_path: str) -> str:
        """步骤5：生成汇总报告"""
        logger.info("Step 5: Generating summary report...")
        
        try:
            # 读取排名数据
            rankings_df = pd.read_csv(rankings_csv_path)
            
            # 生成报告
            report_file = self.output_dir / f"pipeline_summary_report_{self.timestamp}.txt"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("KOL影响力分析流水线 - 执行报告\n")
                f.write("=" * 60 + "\n")
                f.write(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"时间戳: {self.timestamp}\n\n")
                
                f.write("流水线步骤:\n")
                f.write("1. ✅ 输入文件验证\n")
                f.write("2. ✅ 数据库连接建立\n")
                f.write("3. ✅ 批处理数据提取\n")
                f.write("4. ✅ 影响力评分分析\n")
                f.write("5. ✅ 汇总报告生成\n\n")
                
                f.write("分析结果统计:\n")
                f.write(f"- 输入KOL数量: {len(pd.read_csv(self.kol_csv_path))}\n")
                f.write(f"- 输出排名KOL数量: {len(rankings_df)}\n")
                f.write(f"- 最高影响力评分: {rankings_df['influence_potential_score'].max():.4f}\n")
                f.write(f"- 最低影响力评分: {rankings_df['influence_potential_score'].min():.4f}\n")
                f.write(f"- 平均影响力评分: {rankings_df['influence_potential_score'].mean():.4f}\n\n")
                
                f.write("前20名KOL:\n")
                for _, row in rankings_df.head(20).iterrows():
                    f.write(f"{row['rank']:2d}. {row['kol_id']} (评分: {row['influence_potential_score']:.4f})\n")
                
                f.write(f"\n输出文件:\n")
                f.write(f"- 排名文件: {rankings_csv_path}\n")
                f.write(f"- 报告文件: {report_file}\n")
                f.write(f"- 日志文件: pipeline.log\n")
            
            logger.info(f"Summary report generated: {report_file}")
            return str(report_file)
            
        except Exception as e:
            logger.error(f"Error generating summary report: {e}")
            return None
    
    def run_complete_pipeline(self) -> bool:
        """运行完整的分析流水线"""
        logger.info("Starting complete KOL analysis pipeline...")
        
        try:
            # 步骤1：验证输入
            if not self.step1_validate_input():
                return False
            
            # 步骤2：建立数据库连接
            if not self.step2_setup_database_connection():
                return False
            
            # 步骤3：批处理数据
            data_csv_path = self.step3_batch_process_data()
            if not data_csv_path:
                return False
            
            # 步骤4：分析影响力评分
            rankings_csv_path = self.step4_analyze_influence_scores(data_csv_path)
            if not rankings_csv_path:
                return False
            
            # 步骤5：生成汇总报告
            report_path = self.step5_generate_summary_report(rankings_csv_path)
            if not report_path:
                return False
            
            logger.info("=" * 60)
            logger.info("🎉 Pipeline execution completed successfully!")
            logger.info("=" * 60)
            logger.info(f"📊 Rankings file: {rankings_csv_path}")
            logger.info(f"📋 Summary report: {report_path}")
            logger.info(f"📝 Log file: pipeline.log")
            
            return True
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            return False
        
        finally:
            # 清理资源
            if self.db_reader:
                self.db_reader.close()

def main():
    """主函数"""
    # 配置参数
    KOL_CSV_PATH = "filtered_kol_ids.csv"  # 输入KOL ID文件
    OUTPUT_DIR = "pipeline_outputs"  # 输出目录
    
    # 检查输入文件是否存在
    if not os.path.exists(KOL_CSV_PATH):
        print(f"❌ Error: KOL CSV file not found: {KOL_CSV_PATH}")
        print("Please ensure the file exists before running the pipeline.")
        return False
    
    # 创建并运行流水线
    pipeline = KOLAnalysisPipeline(
        kol_csv_path=KOL_CSV_PATH,
        output_dir=OUTPUT_DIR
    )
    
    success = pipeline.run_complete_pipeline()
    
    if success:
        print("\n🎉 Pipeline completed successfully!")
        return True
    else:
        print("\n❌ Pipeline execution failed. Check pipeline.log for details.")
        return False

if __name__ == "__main__":
    main()
