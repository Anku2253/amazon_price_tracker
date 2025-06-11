from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Product(db.Model):
    """Product model for storing Amazon product information."""
    
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    url = db.Column(db.Text, nullable=False, unique=True)
    current_price = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship with price history
    price_history = db.relationship('PriceHistory', backref='product', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Product {self.title[:50]}...>'
    
    @property
    def short_title(self):
        """Return a shortened version of the title for display."""
        return self.title[:80] + '...' if len(self.title) > 80 else self.title
    
    @property
    def domain(self):
        """Extract domain from URL for display."""
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(self.url)
            return parsed_url.netloc
        except:
            return 'amazon.com'
    
    @property
    def price_trend(self):
        """Calculate price trend (up, down, stable)."""
        if len(self.price_history) < 2:
            return 'stable'
        
        recent_prices = sorted(self.price_history, key=lambda x: x.timestamp, reverse=True)[:2]
        latest_price = recent_prices[0].price
        previous_price = recent_prices[1].price
        
        if latest_price > previous_price:
            return 'up'
        elif latest_price < previous_price:
            return 'down'
        else:
            return 'stable'
    
    @property
    def lowest_price(self):
        """Get the lowest recorded price."""
        if not self.price_history:
            return self.current_price
        return min(entry.price for entry in self.price_history)
    
    @property
    def highest_price(self):
        """Get the highest recorded price."""
        if not self.price_history:
            return self.current_price
        return max(entry.price for entry in self.price_history)

class PriceHistory(db.Model):
    """Price history model for tracking price changes over time."""
    
    __tablename__ = 'price_history'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<PriceHistory ${self.price} at {self.timestamp}>'
    
    @property
    def formatted_price(self):
        """Return formatted price string."""
        return f'${float(self.price):.2f}'
    
    @property
    def formatted_timestamp(self):
        """Return formatted timestamp string."""
        return self.timestamp.strftime('%Y-%m-%d %H:%M:%S')

class ProductScrapeLog(db.Model):
    """Optional model to log scraping attempts and results."""
    
    __tablename__ = 'scrape_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    url = db.Column(db.Text, nullable=False)
    success = db.Column(db.Boolean, nullable=False)
    error_message = db.Column(db.Text, nullable=True)
    response_code = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<ScrapeLog {self.url} - {"Success" if self.success else "Failed"}>'