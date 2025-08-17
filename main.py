"""
Simple database connection and data fetching from kols and influencer_videos tables.
Clean and minimal implementation for Supabase PostgreSQL database.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import pandas as pd
from dotenv import load_dotenv
from db_reader import DatabaseReader

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataFetcher:
    """Simple data fetcher for kols and influencer_videos tables."""
    
    def __init__(self):
        """Initialize with database connection."""
        self.db = DatabaseReader()
        logger.info("DataFetcher initialized with database connection")
    
    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            success = self.db.test_connection()
            if success:
                logger.info("✅ Database connection successful")
            else:
                logger.error("❌ Database connection failed")
            return success
        except Exception as e:
            logger.error(f"❌ Connection test error: {e}")
            return False
    
    def get_kols(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch data from kols table.
        
        Args:
            limit: Optional limit for number of records to fetch
            
        Returns:
            List of dictionaries containing kol data
        """
        try:
            query = "SELECT * FROM kols"
            params = ()
            
            if limit:
                query += " LIMIT %s"
                params = (limit,)
            
            logger.info(f"Fetching kols data{f' (limit: {limit})' if limit else ''}")
            data = self.db.execute_query_dict(query, params)
            logger.info(f"Retrieved {len(data)} kol records")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching kols data: {e}")
            return []
    
    def get_influencer_videos(self, limit: Optional[int] = None, kol_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch data from influencer_videos table.
        
        Args:
            limit: Optional limit for number of records to fetch
            kol_id: Optional filter by specific kol_id
            
        Returns:
            List of dictionaries containing video data
        """
        try:
            query = "SELECT * FROM influencer_videos"
            params = ()
            conditions = []
            
            if kol_id:
                conditions.append("kol_id = %s")
                params = (kol_id,)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY create_time DESC"
            
            if limit:
                query += " LIMIT %s"
                params = params + (limit,) if params else (limit,)
            
            logger.info(f"Fetching influencer_videos data{f' (limit: {limit})' if limit else ''}{f' (kol_id: {kol_id})' if kol_id else ''}")
            data = self.db.execute_query_dict(query, params)
            logger.info(f"Retrieved {len(data)} video records")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching influencer_videos data: {e}")
            return []
    
    def get_videos_with_descriptions(self, limit: Optional[int] = None, min_length: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch influencer videos that have valid descriptions.
        
        Args:
            limit: Optional limit for number of records to fetch
            min_length: Minimum description length to filter by
            
        Returns:
            List of dictionaries containing video data with descriptions
        """
        try:
            query = """
            SELECT 
                id,
                video_id,
                kol_id,
                title,
                generated_description,
                channel,
                sub_channel,
                play_count,
                digg_count,
                comment_count,
                share_count,
                create_time,
                tags
            FROM influencer_videos 
            WHERE generated_description IS NOT NULL
            AND generated_description != ''
            AND LENGTH(generated_description) >= %s
            ORDER BY create_time DESC
            """
            
            params = (min_length,)
            
            if limit:
                query += " LIMIT %s"
                params = params + (limit,)
            
            logger.info(f"Fetching videos with descriptions{f' (limit: {limit})' if limit else ''} (min_length: {min_length})")
            data = self.db.execute_query_dict(query, params)
            logger.info(f"Retrieved {len(data)} video records with descriptions")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching videos with descriptions: {e}")
            return []
    
    def get_kol_video_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for kols and videos.
        
        Returns:
            Dictionary with summary statistics
        """
        try:
            # Count kols
            kols_count_query = "SELECT COUNT(*) as count FROM kols"
            kols_result = self.db.execute_query_one_dict(kols_count_query)
            kols_count = kols_result['count'] if kols_result else 0
            
            # Count total videos
            videos_count_query = "SELECT COUNT(*) as count FROM influencer_videos"
            videos_result = self.db.execute_query_one_dict(videos_count_query)
            videos_count = videos_result['count'] if videos_result else 0
            
            # Count videos with descriptions
            videos_with_desc_query = """
            SELECT COUNT(*) as count FROM influencer_videos 
            WHERE generated_description IS NOT NULL 
            AND generated_description != ''
            limit 100
            """
            videos_with_desc_result = self.db.execute_query_one_dict(videos_with_desc_query)
            videos_with_desc_count = videos_with_desc_result['count'] if videos_with_desc_result else 0
            
            # Get channel distribution
            channel_query = """
            SELECT channel, COUNT(*) as count 
            FROM influencer_videos 
            GROUP BY channel 
            ORDER BY count DESC
            limit 100
            """
            channel_data = self.db.execute_query_dict(channel_query)
            
            summary = {
                'total_kols': kols_count,
                'total_videos': videos_count,
                'videos_with_descriptions': videos_with_desc_count,
                'description_percentage': round((videos_with_desc_count / videos_count * 100), 2) if videos_count > 0 else 0,
                'channel_distribution': {item['channel']: item['count'] for item in channel_data}
            }
            
            logger.info("Generated summary statistics")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {}
    
    def export_to_csv(self, data: List[Dict[str, Any]], filename: str) -> bool:
        """
        Export data to CSV file.
        
        Args:
            data: List of dictionaries to export
            filename: Output filename
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not data:
                logger.warning("No data to export")
                return False
                
            df = pd.DataFrame(data)
            df.to_csv(filename, index=False)
            logger.info(f"Exported {len(data)} records to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return False
    
    def close(self):
        """Close database connection."""
        self.db.close()
        logger.info("Database connection closed")


def main():
    """Main function demonstrating usage."""
    fetcher = DataFetcher()
    
    try:
        # Test connection
        print("Testing database connection...")
        if not fetcher.test_connection():
            print("Failed to connect to database. Please check your environment variables.")
            return
        
        # Get summary statistics
        print("\nGetting summary statistics...")
        summary = fetcher.get_kol_video_summary()
        if summary:
            print(f"📊 Database Summary:")
            print(f"   Total KOLs: {summary['total_kols']:,}")
            print(f"   Total Videos: {summary['total_videos']:,}")
            print(f"   Videos with Descriptions: {summary['videos_with_descriptions']:,} ({summary['description_percentage']}%)")
            print(f"   Channel Distribution:")
            for channel, count in summary['channel_distribution'].items():
                print(f"     {channel}: {count:,}")
        
        # Fetch sample data
        print("\n📥 Fetching sample data...")
        
        # Get 5 kols
        kols = fetcher.get_kols(limit=5)
        if kols:
            print(f"Sample KOLs ({len(kols)} records):")
            for kol in kols:
                print(f"   ID: {kol.get('id')}, Name: {kol.get('name', 'N/A')}")
        
        # Get 10 recent videos
        videos = fetcher.get_influencer_videos(limit=10)
        if videos:
            print(f"\nRecent Videos ({len(videos)} records):")
            for video in videos[:5]:  # Show first 5
                print(f"   ID: {video.get('id')}, Title: {video.get('title', 'N/A')[:50]}...")
        
        # Get videos with descriptions
        videos_with_desc = fetcher.get_videos_with_descriptions(limit=5)
        if videos_with_desc:
            print(f"\nVideos with Descriptions ({len(videos_with_desc)} records):")
            for video in videos_with_desc:
                desc = video.get('generated_description', 'N/A')
                print(f"   ID: {video.get('id')}, Description: {desc[:100]}...")
        
        # Export sample data
        print("\n💾 Exporting sample data...")
        if fetcher.export_to_csv(kols, 'sample_kols.csv'):
            print("   ✅ Exported sample kols to sample_kols.csv")
        if fetcher.export_to_csv(videos_with_desc, 'sample_videos.csv'):
            print("   ✅ Exported sample videos to sample_videos.csv")
        
        print("\n✅ Data fetching completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        print(f"❌ Error: {e}")
    
    finally:
        fetcher.close()


if __name__ == "__main__":
    main()