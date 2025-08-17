"""
Batch KOL data processor for processing large KOL ID files and extracting data from Supabase.

This script handles:
1. Splitting large KOL ID files into manageable batches
2. Executing batch queries against the database
3. Exporting results to CSV files
4. Concatenating all results into a final CSV
"""

import os
import csv
import logging
import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid
import time
from datetime import datetime

from db_reader import DatabaseReader

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BatchKOLProcessor:
    """Process KOL IDs in batches and extract video data."""
    
    def __init__(self, input_csv_path: str, output_dir: str = "batch_outputs", batch_size: int = 1000):
        """
        Initialize the batch processor.
        
        Args:
            input_csv_path: Path to the filtered KOL ID CSV file
            output_dir: Directory to store batch outputs
            batch_size: Number of KOL IDs per batch (default: 1000)
        """
        self.input_csv_path = input_csv_path
        self.output_dir = Path(output_dir)
        self.batch_size = batch_size
        self.db = DatabaseReader()
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info(f"BatchKOLProcessor initialized:")
        logger.info(f"  Input file: {input_csv_path}")
        logger.info(f"  Output directory: {output_dir}")
        logger.info(f"  Batch size: {batch_size}")
    
    def read_kol_ids(self) -> List[str]:
        """
        Read KOL IDs from the input CSV file.
        
        Returns:
            List of KOL IDs as strings
        """
        try:
            logger.info(f"Reading KOL IDs from {self.input_csv_path}")
            
            # Try different ways to read the CSV in case the format varies
            try:
                # First try: assume it's a simple CSV with KOL IDs
                df = pd.read_csv(self.input_csv_path)
                
                # Try to find the column with KOL IDs
                possible_columns = ['kol_id', 'id', 'KOL_ID', 'ID', 'kolId']
                kol_column = None
                
                for col in possible_columns:
                    if col in df.columns:
                        kol_column = col
                        break
                
                if kol_column:
                    kol_ids = df[kol_column].astype(str).tolist()
                else:
                    # If no specific column found, try the first column
                    kol_ids = df.iloc[:, 0].astype(str).tolist()
                    
            except Exception as e:
                logger.warning(f"Failed to read as DataFrame: {e}. Trying as plain text...")
                # Fallback: read as plain text and split by lines
                with open(self.input_csv_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    # Split by newlines and clean up
                    kol_ids = [line.strip() for line in content.split('\n') if line.strip()]
                    # Remove header if it exists
                    if kol_ids and not self._is_valid_uuid(kol_ids[0]):
                        kol_ids = kol_ids[1:]
            
            # Filter out invalid UUIDs and clean the data
            valid_kol_ids = []
            for kol_id in kol_ids:
                cleaned_id = str(kol_id).strip().replace('"', '').replace("'", '')
                if self._is_valid_uuid(cleaned_id):
                    valid_kol_ids.append(cleaned_id)
                elif cleaned_id and cleaned_id.lower() not in ['kol_id', 'id', 'nan', 'none', 'null']:
                    logger.warning(f"Invalid UUID format: {cleaned_id}")
            
            logger.info(f"Successfully read {len(valid_kol_ids)} valid KOL IDs")
            return valid_kol_ids
            
        except Exception as e:
            logger.error(f"Error reading KOL IDs: {e}")
            raise
    
    def _is_valid_uuid(self, uuid_string: str) -> bool:
        """Check if a string is a valid UUID."""
        try:
            uuid.UUID(uuid_string)
            return True
        except ValueError:
            return False
    
    def split_into_batches(self, kol_ids: List[str]) -> List[List[str]]:
        """
        Split KOL IDs into batches.
        
        Args:
            kol_ids: List of KOL IDs
            
        Returns:
            List of batches, each containing up to batch_size KOL IDs
        """
        batches = []
        for i in range(0, len(kol_ids), self.batch_size):
            batch = kol_ids[i:i + self.batch_size]
            batches.append(batch)
        
        logger.info(f"Split {len(kol_ids)} KOL IDs into {len(batches)} batches")
        return batches
    
    def process_batch(self, batch_kol_ids: List[str], batch_number: int) -> Optional[str]:
        """
        Process a single batch of KOL IDs and export to CSV.
        
        Args:
            batch_kol_ids: List of KOL IDs for this batch
            batch_number: Batch number for file naming
            
        Returns:
            Path to the generated CSV file, or None if failed
        """
        try:
            logger.info(f"Processing batch {batch_number} with {len(batch_kol_ids)} KOL IDs")
            
            # Format KOL IDs for the SQL query - create a comma-separated list with proper quotes
            formatted_ids = "', '".join(batch_kol_ids)
            
            # Use a single compound query that creates temp table, selects data, and drops table
            compound_query = f"""
            CREATE TEMP TABLE batch_{batch_number}_kol_ids AS
            SELECT unnest(ARRAY['{formatted_ids}']::uuid[]) AS kol_id;
            
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
            INNER JOIN batch_{batch_number}_kol_ids t ON iv.kol_id = t.kol_id
            JOIN kols k ON iv.kol_id = k.id AND iv.channel = k.channel
            ORDER BY iv.kol_id, iv.video_id;
            
            DROP TABLE batch_{batch_number}_kol_ids;
            """
            
            # Execute the compound query using the batch method
            start_time = time.time()
            results = self.db.execute_batch_query(compound_query)
            execution_time = time.time() - start_time
            
            logger.info(f"Batch {batch_number}: Query executed in {execution_time:.2f}s, retrieved {len(results)} records")
            
            if results:
                # Export to CSV
                output_file = self.output_dir / f"batch_{batch_number:03d}_kol_data.csv"
                df = pd.DataFrame(results)
                df.to_csv(output_file, index=False)
                
                logger.info(f"Batch {batch_number}: Exported {len(results)} records to {output_file}")
                return str(output_file)
            else:
                logger.warning(f"Batch {batch_number}: No data found for this batch")
                return None
                
        except Exception as e:
            logger.error(f"Error processing batch {batch_number}: {e}")
            # Try to clean up temp table if it exists
            try:
                self.db.execute_query(f"DROP TABLE IF EXISTS batch_{batch_number}_kol_ids")
            except:
                pass
            return None
    
    def concatenate_csv_files(self, csv_files: List[str], final_output_file: str = None) -> str:
        """
        Concatenate all batch CSV files into a single file.
        
        Args:
            csv_files: List of CSV file paths to concatenate
            final_output_file: Output file path (optional)
            
        Returns:
            Path to the final concatenated CSV file
        """
        if final_output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_output_file = self.output_dir / f"final_kol_data_{timestamp}.csv"
        
        try:
            logger.info(f"Concatenating {len(csv_files)} CSV files into {final_output_file}")
            
            # Read and concatenate all CSV files
            all_dataframes = []
            total_records = 0
            
            for csv_file in csv_files:
                if os.path.exists(csv_file):
                    df = pd.read_csv(csv_file)
                    all_dataframes.append(df)
                    total_records += len(df)
                    logger.info(f"  Added {len(df)} records from {os.path.basename(csv_file)}")
                else:
                    logger.warning(f"  File not found: {csv_file}")
            
            if all_dataframes:
                # Concatenate all dataframes
                final_df = pd.concat(all_dataframes, ignore_index=True)
                
                # Remove duplicates if any
                initial_count = len(final_df)
                final_df = final_df.drop_duplicates()
                final_count = len(final_df)
                
                if initial_count != final_count:
                    logger.info(f"Removed {initial_count - final_count} duplicate records")
                
                # Export final CSV
                final_df.to_csv(final_output_file, index=False)
                
                logger.info(f"✅ Final concatenated file created: {final_output_file}")
                logger.info(f"   Total records: {final_count}")
                
                return str(final_output_file)
            else:
                logger.error("No valid CSV files found to concatenate")
                return None
                
        except Exception as e:
            logger.error(f"Error concatenating CSV files: {e}")
            raise
    
    def process_all_batches(self, kol_ids: List[str]) -> str:
        """
        Process all batches and return the final concatenated CSV file path.
        
        Args:
            kol_ids: List of all KOL IDs to process
            
        Returns:
            Path to the final concatenated CSV file
        """
        logger.info("Starting batch processing workflow")
        
        # Split into batches
        batches = self.split_into_batches(kol_ids)
        
        # Process each batch
        successful_csv_files = []
        failed_batches = []
        
        for i, batch in enumerate(batches, 1):
            logger.info(f"Processing batch {i}/{len(batches)}")
            
            csv_file = self.process_batch(batch, i)
            if csv_file:
                successful_csv_files.append(csv_file)
            else:
                failed_batches.append(i)
                
            # Add a small delay between batches to avoid overwhelming the database
            time.sleep(1)
        
        # Report results
        logger.info(f"✅ Successfully processed {len(successful_csv_files)}/{len(batches)} batches")
        if failed_batches:
            logger.warning(f"❌ Failed batches: {failed_batches}")
        
        # Concatenate all successful CSV files
        if successful_csv_files:
            final_file = self.concatenate_csv_files(successful_csv_files)
            logger.info(f"🎉 Workflow completed! Final file: {final_file}")
            return final_file
        else:
            logger.error("❌ No successful batches to concatenate")
            return None
    
    def run(self) -> str:
        """
        Run the complete workflow.
        
        Returns:
            Path to the final concatenated CSV file
        """
        try:
            # Test database connection
            if not self.db.test_connection():
                raise Exception("Database connection failed")
            
            # Read KOL IDs
            kol_ids = self.read_kol_ids()
            if not kol_ids:
                raise Exception("No valid KOL IDs found in input file")
            
            # Process all batches
            final_file = self.process_all_batches(kol_ids)
            
            return final_file
            
        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            raise
        finally:
            # Clean up database connection
            self.db.close()


def main():
    """Main function to run the batch processor."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Process KOL IDs in batches and extract video data')
    parser.add_argument('input_file', help='Path to the filtered KOL ID CSV file')
    parser.add_argument('--output-dir', default='batch_outputs', help='Output directory for batch files')
    parser.add_argument('--batch-size', type=int, default=1000, help='Number of KOL IDs per batch')
    
    args = parser.parse_args()
    
    # Create processor and run
    processor = BatchKOLProcessor(
        input_csv_path=args.input_file,
        output_dir=args.output_dir,
        batch_size=args.batch_size
    )
    
    try:
        final_file = processor.run()
        if final_file:
            print(f"\n🎉 SUCCESS! Final output file: {final_file}")
        else:
            print("\n❌ FAILED! Check logs for details.")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")


if __name__ == "__main__":
    main()
