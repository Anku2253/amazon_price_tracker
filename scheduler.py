#!/usr/bin/env python3
"""
Amazon Price Tracker - Background Scheduler
Handles periodic price monitoring and database updates.
"""

import logging
import time
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore

# Import Flask app components
from app import app, db
from models import Product, PriceHistory
from scraper import AmazonScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class PriceScheduler:
    """
    Handles scheduling and execution of price monitoring tasks.
    """
    
    def __init__(self):
        """Initialize the scheduler with configuration."""
        self.scraper = AmazonScraper()
        
        # Configure scheduler
        job_stores = {
            'default': MemoryJobStore()
        }
        
        executors = {
            'default': ThreadPoolExecutor(max_workers=3)
        }
        
        job_defaults = {
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 300  # 5 minutes
        }
        
        self.scheduler = BlockingScheduler(
            jobstores=job_stores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )
        
    def scrape_all_products(self):
        """
        Scrape prices for all tracked products and update database.
        """
        logger.info("Starting scheduled price scraping...")
        
        try:
            with app.app_context():
                # Get all active products
                products = Product.query.filter_by(is_active=True).all()
                
                if not products:
                    logger.info("No active products to scrape")
                    return
                
                logger.info(f"Found {len(products)} active products to scrape")
                
                successful_scrapes = 0
                failed_scrapes = 0
                
                for product in products:
                    try:
                        self._scrape_single_product(product)
                        successful_scrapes += 1
                        
                        # Add delay between requests to be respectful
                        time.sleep(2)
                        
                    except Exception as e:
                        logger.error(f"Failed to scrape product {product.id}: {str(e)}")
                        failed_scrapes += 1
                        continue
                
                # Commit all changes
                db.session.commit()
                
                logger.info(
                    f"Scraping completed: {successful_scrapes} successful, "
                    f"{failed_scrapes} failed"
                )
                
        except Exception as e:
            logger.error(f"Error in scheduled scraping: {str(e)}")
            db.session.rollback()
    
    def _scrape_single_product(self, product):
        """
        Scrape a single product and update its price history.
        
        Args:
            product (Product): Product object to scrape
        """
        logger.debug(f"Scraping product: {product.name}")
        
        try:
            # Scrape current price
            scraped_data = self.scraper.scrape_product(product.url)
            
            if not scraped_data or 'price' not in scraped_data:
                logger.warning(f"No price data found for product {product.id}")
                return
            
            current_price = scraped_data['price']
            
            # Check if price has changed significantly
            if product.current_price and abs(current_price - product.current_price) < 0.01:
                logger.debug(f"Price unchanged for product {product.id}")
                return
            
            # Update product information
            old_price = product.current_price
            product.current_price = current_price
            product.last_checked = datetime.utcnow()
            
            # Update other fields if available
            if 'name' in scraped_data and scraped_data['name']:
                product.name = scraped_data['name'][:200]  # Limit length
            
            if 'image_url' in scraped_data and scraped_data['image_url']:
                product.image_url = scraped_data['image_url']
            
            # Create price history entry
            price_history = PriceHistory(
                product_id=product.id,
                price=current_price,
                timestamp=datetime.utcnow()
            )
            
            db.session.add(price_history)
            
            # Log price change
            if old_price:
                change = current_price - old_price
                change_percent = (change / old_price) * 100
                
                if change < 0:
                    logger.info(
                        f"Price drop detected for {product.name}: "
                        f"${old_price:.2f} → ${current_price:.2f} "
                        f"({change_percent:.1f}%)"
                    )
                    
                    # Check if price dropped below target
                    if product.target_price and current_price <= product.target_price:
                        logger.info(
                            f"Target price reached for {product.name}! "
                            f"Current: ${current_price:.2f}, Target: ${product.target_price:.2f}"
                        )
                        # Here you could add notification logic (email, webhook, etc.)
                        self._send_price_alert(product, current_price)
                
                elif change > 0:
                    logger.info(
                        f"Price increase for {product.name}: "
                        f"${old_price:.2f} → ${current_price:.2f} "
                        f"({change_percent:.1f}%)"
                    )
            else:
                logger.info(f"Initial price set for {product.name}: ${current_price:.2f}")
            
        except Exception as e:
            logger.error(f"Error scraping product {product.id}: {str(e)}")
            raise
    
    def _send_price_alert(self, product, current_price):
        """
        Send alert when target price is reached.
        
        Args:
            product (Product): Product that reached target price
            current_price (float): Current price of the product
        """
        # Placeholder for notification logic
        # You can implement email, SMS, or webhook notifications here
        logger.info(f"ALERT: {product.name} reached target price of ${product.target_price:.2f}")
        
        # Example: Mark product as alerted to avoid spam
        # product.alert_sent = True
        # product.alert_sent_at = datetime.utcnow()
    
    def cleanup_old_data(self):
        """
        Clean up old price history data to prevent database bloat.
        """
        logger.info("Starting database cleanup...")
        
        try:
            with app.app_context():
                # Keep only last 90 days of price history
                cutoff_date = datetime.utcnow() - timedelta(days=90)
                
                old_records = PriceHistory.query.filter(
                    PriceHistory.timestamp < cutoff_date
                ).count()
                
                if old_records > 0:
                    PriceHistory.query.filter(
                        PriceHistory.timestamp < cutoff_date
                    ).delete()
                    
                    db.session.commit()
                    logger.info(f"Cleaned up {old_records} old price history records")
                else:
                    logger.info("No old records to clean up")
                    
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            db.session.rollback()
    
    def health_check(self):
        """
        Perform health check and log system status.
        """
        logger.info("Performing health check...")
        
        try:
            with app.app_context():
                total_products = Product.query.count()
                active_products = Product.query.filter_by(is_active=True).count()
                recent_history = PriceHistory.query.filter(
                    PriceHistory.timestamp > datetime.utcnow() - timedelta(hours=24)
                ).count()
                
                logger.info(
                    f"Health check - Total products: {total_products}, "
                    f"Active: {active_products}, "
                    f"Price updates (24h): {recent_history}"
                )
                
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
    
    def start(self):
        """
        Start the scheduler with configured jobs.
        """
        logger.info("Starting Price Tracker Scheduler...")
        
        # Main scraping job - every hour
        self.scheduler.add_job(
            func=self.scrape_all_products,
            trigger=IntervalTrigger(hours=1),
            id='price_scraper',
            name='Scrape All Product Prices',
            replace_existing=True
        )
        
        # Cleanup job - daily at 2 AM UTC
        self.scheduler.add_job(
            func=self.cleanup_old_data,
            trigger=CronTrigger(hour=2, minute=0),
            id='cleanup',
            name='Database Cleanup',
            replace_existing=True
        )
        
        # Health check - every 6 hours
        self.scheduler.add_job(
            func=self.health_check,
            trigger=IntervalTrigger(hours=6),
            id='health_check',
            name='System Health Check',
            replace_existing=True
        )
        
        # Log scheduled jobs
        logger.info("Scheduled jobs:")
        for job in self.scheduler.get_jobs():
            logger.info(f"  - {job.name} (ID: {job.id}) - Next run: {job.next_run_time}")
        
        try:
            # Run initial health check
            self.health_check()
            
            # Start the scheduler
            logger.info("Scheduler started successfully")
            self.scheduler.start()
            
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            self.scheduler.shutdown()
            
        except Exception as e:
            logger.error(f"Scheduler error: {str(e)}")
            self.scheduler.shutdown()
            raise


def main():
    """
    Main entry point for the scheduler.
    """
    try:
        scheduler = PriceScheduler()
        scheduler.start()
        
    except KeyboardInterrupt:
        logger.info("Scheduler interrupted by user")
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        raise


if __name__ == "__main__":
    main()