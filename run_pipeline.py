#!/usr/bin/env python3
"""
KOL影响力分析流水线 - 快速运行脚本

使用方法:
python run_pipeline.py [KOL_CSV_文件路径]

如果不提供文件路径，将使用默认的 filtered_kol_ids.csv
"""

import sys
import os
from pathlib import Path

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

from end_to_end_pipeline import KOLAnalysisPipeline

def main():
    """快速运行流水线"""
    
    # 获取KOL CSV文件路径
    if len(sys.argv) > 1:
        kol_csv_path = sys.argv[1]
    else:
        kol_csv_path = "filtered_kol_ids.csv"
    
    print("🚀 KOL影响力分析流水线")
    print("=" * 50)
    print(f"📁 输入文件: {kol_csv_path}")
    print(f"📂 输出目录: pipeline_outputs")
    print("=" * 50)
    
    # 检查输入文件
    if not os.path.exists(kol_csv_path):
        print(f"❌ 错误: 找不到KOL CSV文件: {kol_csv_path}")
        print("请确保文件存在后再运行流水线。")
        return False
    
    # 创建并运行流水线
    try:
        pipeline = KOLAnalysisPipeline(
            kol_csv_path=kol_csv_path,
            output_dir="pipeline_outputs"
        )
        
        success = pipeline.run_complete_pipeline()
        
        if success:
            print("\n🎉 流水线执行成功完成!")
            print("📊 查看 pipeline_outputs/ 目录获取结果文件")
            return True
        else:
            print("\n❌ 流水线执行失败，请查看 pipeline.log 获取详细信息")
            return False
            
    except KeyboardInterrupt:
        print("\n⏹️  用户中断了流水线执行")
        return False
    except Exception as e:
        print(f"\n💥 流水线执行出现异常: {e}")
        return False

if __name__ == "__main__":
    main()
