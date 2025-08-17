#!/usr/bin/env python3
"""
KOL影响力分析流水线演示脚本
使用已有的批处理结果数据进行演示

这个脚本跳过批处理步骤，直接使用现有的数据文件进行分析
"""

import sys
import os
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('demo_pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class KOLAnalysisDemoPipeline:
    """KOL影响力分析演示流水线"""
    
    def __init__(self, existing_data_path: str, output_dir: str = "demo_outputs"):
        """
        初始化演示流水线
        
        Args:
            existing_data_path: 现有数据文件路径
            output_dir: 输出目录
        """
        self.existing_data_path = existing_data_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 生成时间戳
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        logger.info(f"Demo pipeline initialized with output directory: {self.output_dir}")
    
    def step1_validate_data(self) -> bool:
        """步骤1：验证数据文件"""
        logger.info("Step 1: Validating existing data file...")
        
        if not os.path.exists(self.existing_data_path):
            logger.error(f"Data file not found: {self.existing_data_path}")
            return False
        
        try:
            df = pd.read_csv(self.existing_data_path)
            record_count = len(df)
            kol_count = df['kol_id'].nunique()
            
            logger.info(f"Found {record_count} records for {kol_count} unique KOLs")
            
            if record_count == 0:
                logger.error("Data file is empty")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Error reading data file: {e}")
            return False
    
    def step2_analyze_influence_scores(self) -> str:
        """步骤2：计算影响力评分"""
        logger.info("Step 2: Analyzing influence scores...")
        
        try:
            # 加载数据
            df = pd.read_csv(self.existing_data_path)
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
            
            # 获取第2001到2200名（共200个KOL）
            start_rank = 2001
            end_rank = 2200
            target_kols = top_kols.iloc[start_rank-1:end_rank].copy()
            target_kols['rank'] = range(start_rank, start_rank + len(target_kols))
            
            # 保存结果
            output_file = self.output_dir / f"demo_kol_rankings_{start_rank}_to_{end_rank}_{self.timestamp}.csv"
            target_kols.to_csv(output_file, index=False)
            
            # 保存详细分析结果
            detailed_output = self.output_dir / f"demo_detailed_analysis_{self.timestamp}.csv"
            base.to_csv(detailed_output, index=False)
            
            logger.info(f"Analysis complete - KOL rankings {start_rank} to {end_rank} saved to: {output_file}")
            logger.info(f"Detailed analysis saved to: {detailed_output}")
            logger.info(f"Total distinct KOLs analyzed: {len(top_kols)}")
            
            # 显示前10名（在2001-2200范围内）
            logger.info(f"Top 10 KOLs in ranks {start_rank}-{end_rank} by influence score:")
            for i, row in target_kols.head(10).iterrows():
                logger.info(f"  {row['rank']:2d}. {row['kol_id']} (score: {row['influence_potential_score']:.4f})")
            
            return str(output_file)
            
        except Exception as e:
            logger.error(f"Error during influence score analysis: {e}")
            return None
    
    def step3_generate_demo_report(self, rankings_csv_path: str) -> str:
        """步骤3：生成演示报告"""
        logger.info("Step 3: Generating demo report...")
        
        try:
            # 读取排名数据
            rankings_df = pd.read_csv(rankings_csv_path)
            
            # 读取原始数据统计
            original_df = pd.read_csv(self.existing_data_path)
            
            # 生成报告
            report_file = self.output_dir / f"demo_analysis_report_{self.timestamp}.txt"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("KOL影响力分析流水线 - 演示报告\n")
                f.write("=" * 80 + "\n")
                f.write(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"时间戳: {self.timestamp}\n\n")
                
                f.write("演示流水线步骤:\n")
                f.write("1. ✅ 数据文件验证\n")
                f.write("2. ✅ 影响力评分分析\n")
                f.write("3. ✅ 演示报告生成\n\n")
                
                f.write("数据集统计:\n")
                f.write(f"- 原始记录数量: {len(original_df):,}\n")
                f.write(f"- 涉及KOL数量: {original_df['kol_id'].nunique():,}\n")
                f.write(f"- 数据时间范围: {original_df['created_at'].min()} 到 {original_df['created_at'].max()}\n")
                f.write(f"- 平台渠道: {', '.join(original_df['channel'].unique())}\n\n")
                
                f.write("影响力评分算法:\n")
                f.write("influence_potential_score = \n")
                f.write("  0.3 × log(followers_count + 1) +\n")
                f.write("  0.4 × z_avg_post_score +\n")
                f.write("  0.2 × z_vol_play +\n")
                f.write("  0.1 × interaction_rate\n\n")
                
                f.write("筛选条件:\n")
                f.write("- 粉丝数范围: 1,000 - 100,000\n")
                f.write("- 使用每个KOL最新月份的数据\n")
                f.write("- 按KOL取最高评分（跨平台）\n\n")
                
                f.write("分析结果统计:\n")
                f.write(f"- 目标排名范围: 第2001-2200名\n")
                f.write(f"- 本次提取KOL数量: {len(rankings_df):,}\n")
                f.write(f"- 最高影响力评分（范围内）: {rankings_df['influence_potential_score'].max():.4f}\n")
                f.write(f"- 最低影响力评分（范围内）: {rankings_df['influence_potential_score'].min():.4f}\n")
                f.write(f"- 平均影响力评分（范围内）: {rankings_df['influence_potential_score'].mean():.4f}\n")
                f.write(f"- 评分标准差（范围内）: {rankings_df['influence_potential_score'].std():.4f}\n\n")
                
                f.write("评分分布（第2001-2200名）:\n")
                score_percentiles = [10, 25, 50, 75, 90, 95, 99]
                for p in score_percentiles:
                    score = np.percentile(rankings_df['influence_potential_score'], p)
                    f.write(f"- {p}th percentile: {score:.4f}\n")
                f.write("\n")
                
                f.write("第2001-2200名中的前30名KOL:\n")
                f.write("-" * 60 + "\n")
                f.write(f"{'排名':<4} {'KOL ID':<40} {'影响力评分':<12}\n")
                f.write("-" * 60 + "\n")
                for _, row in rankings_df.head(30).iterrows():
                    f.write(f"{row['rank']:<4} {row['kol_id']:<40} {row['influence_potential_score']:<12.4f}\n")
                
                f.write(f"\n输出文件:\n")
                f.write(f"- 排名文件: {rankings_csv_path}\n")
                f.write(f"- 详细分析: demo_detailed_analysis_{self.timestamp}.csv\n")
                f.write(f"- 演示报告: {report_file}\n")
                f.write(f"- 日志文件: demo_pipeline.log\n\n")
                
                f.write("使用建议:\n")
                f.write("1. 查看排名文件获取完整的KOL排序\n")
                f.write("2. 使用详细分析文件深入了解各项指标\n")
                f.write("3. 根据业务需求调整评分算法权重\n")
                f.write("4. 考虑添加更多筛选条件（如内容类别、地域等）\n")
            
            logger.info(f"Demo report generated: {report_file}")
            return str(report_file)
            
        except Exception as e:
            logger.error(f"Error generating demo report: {e}")
            return None
    
    def run_demo_pipeline(self) -> bool:
        """运行演示分析流水线"""
        logger.info("Starting KOL influence analysis demo pipeline...")
        
        try:
            # 步骤1：验证数据
            if not self.step1_validate_data():
                return False
            
            # 步骤2：分析影响力评分
            rankings_csv_path = self.step2_analyze_influence_scores()
            if not rankings_csv_path:
                return False
            
            # 步骤3：生成演示报告
            report_path = self.step3_generate_demo_report(rankings_csv_path)
            if not report_path:
                return False
            
            logger.info("=" * 80)
            logger.info("🎉 Demo pipeline execution completed successfully!")
            logger.info("=" * 80)
            logger.info(f"📊 Rankings file: {rankings_csv_path}")
            logger.info(f"📋 Demo report: {report_path}")
            logger.info(f"📝 Log file: demo_pipeline.log")
            
            return True
            
        except Exception as e:
            logger.error(f"Demo pipeline execution failed: {e}")
            return False

def main():
    """主函数"""
    # 使用现有的大数据集（包含57K+ KOL）
    EXISTING_DATA_PATH = "batch_outputs/final_kol_data_20250807_173628.csv"
    OUTPUT_DIR = "demo_outputs"
    
    # 检查数据文件是否存在
    if not os.path.exists(EXISTING_DATA_PATH):
        print(f"❌ Error: Data file not found: {EXISTING_DATA_PATH}")
        print("Please run the batch processing first to generate the data file.")
        return False
    
    print("🚀 KOL影响力分析演示流水线")
    print("=" * 60)
    print(f"📁 数据文件: {EXISTING_DATA_PATH}")
    print(f"📂 输出目录: {OUTPUT_DIR}")
    print("=" * 60)
    
    # 创建并运行演示流水线
    demo_pipeline = KOLAnalysisDemoPipeline(
        existing_data_path=EXISTING_DATA_PATH,
        output_dir=OUTPUT_DIR
    )
    
    success = demo_pipeline.run_demo_pipeline()
    
    if success:
        print("\n🎉 演示流水线执行成功完成!")
        print("📊 查看 demo_outputs/ 目录获取结果文件")
        return True
    else:
        print("\n❌ 演示流水线执行失败，请查看 demo_pipeline.log 获取详细信息")
        return False

if __name__ == "__main__":
    main()
