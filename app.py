from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from models import db, Product, PriceHistory
from scraper import AmazonScraper

def create_app():
    """Application factory pattern for Flask app creation."""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///price_tracker.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db.init_app(app)
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    return app

app = create_app()
scraper = AmazonScraper()

@app.route('/')
def index():
    """Home page with product URL submission form."""
    recent_products = Product.query.order_by(Product.created_at.desc()).limit(5).all()
    return render_template('index.html', recent_products=recent_products)

@app.route('/add_product', methods=['POST'])
def add_product():
    """Add a new product to track."""
    url = request.form.get('url', '').strip()
    
    if not url:
        flash('Please enter a valid Amazon URL', 'error')
        return redirect(url_for('index'))
    
    # Validate Amazon URL
    if 'amazon.' not in url.lower():
        flash('Please enter a valid Amazon product URL', 'error')
        return redirect(url_for('index'))
    
    try:
        # Check if product already exists
        existing_product = Product.query.filter_by(url=url).first()
        if existing_product:
            flash('This product is already being tracked!', 'info')
            return redirect(url_for('track_product', product_id=existing_product.id))
        
        # Scrape product data
        product_data = scraper.scrape_product(url)
        
        if not product_data:
            flash('Failed to scrape product data. Please check the URL and try again.', 'error')
            return redirect(url_for('index'))
        
        # Create new product
        product = Product(
            title=product_data['title'],
            url=url,
            current_price=product_data['price']
        )
        db.session.add(product)
        db.session.flush()  # Get the product ID
        
        # Add initial price history
        price_history = PriceHistory(
            product_id=product.id,
            price=product_data['price']
        )
        db.session.add(price_history)
        db.session.commit()
        
        flash(f'Successfully added "{product_data["title"]}" to tracking!', 'success')
        return redirect(url_for('track_product', product_id=product.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding product: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/product/<int:product_id>')
def track_product(product_id):
    """Product tracking page with price history chart."""
    product = Product.query.get_or_404(product_id)
    price_history = PriceHistory.query.filter_by(product_id=product_id).order_by(PriceHistory.timestamp.asc()).all()
    
    return render_template('track_product.html', product=product, price_history=price_history)

@app.route('/api/product/<int:product_id>/price_data')
def get_price_data(product_id):
    """API endpoint to get price history data for Chart.js."""
    product = Product.query.get_or_404(product_id)
    price_history = PriceHistory.query.filter_by(product_id=product_id).order_by(PriceHistory.timestamp.asc()).all()
    
    data = {
        'labels': [entry.timestamp.strftime('%Y-%m-%d %H:%M') for entry in price_history],
        'prices': [float(entry.price) for entry in price_history]
    }
    
    return jsonify(data)

@app.route('/update_price/<int:product_id>')
def update_price(product_id):
    """Manually update product price."""
    product = Product.query.get_or_404(product_id)
    
    try:
        product_data = scraper.scrape_product(product.url)
        
        if not product_data:
            flash('Failed to update price. Please try again later.', 'error')
            return redirect(url_for('track_product', product_id=product_id))
        
        # Update product price
        old_price = product.current_price
        new_price = product_data['price']
        
        product.current_price = new_price
        product.updated_at = datetime.utcnow()
        
        # Add to price history if price changed
        if old_price != new_price:
            price_history = PriceHistory(
                product_id=product_id,
                price=new_price
            )
            db.session.add(price_history)
            
            price_change = new_price - old_price
            if price_change > 0:
                flash(f'Price updated! Price increased by ${price_change:.2f}', 'warning')
            else:
                flash(f'Price updated! Price decreased by ${abs(price_change):.2f}', 'success')
        else:
            flash('Price updated! No change in price.', 'info')
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating price: {str(e)}', 'error')
    
    return redirect(url_for('track_product', product_id=product_id))

@app.route('/products')
def all_products():
    """View all tracked products."""
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('all_products.html', products=products)

@app.route('/delete_product/<int:product_id>')
def delete_product(product_id):
    """Delete a tracked product."""
    product = Product.query.get_or_404(product_id)
    
    try:
        # Delete associated price history
        PriceHistory.query.filter_by(product_id=product_id).delete()
        
        # Delete product
        db.session.delete(product)
        db.session.commit()
        
        flash('Product deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}', 'error')
    
    return redirect(url_for('all_products'))

@app.route('/favicon.ico')
def favicon():
    """Handle favicon requests."""
    return '', 204  # Return empty response with "No Content" status

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors."""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    db.session.rollback()
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_ENV') == 'development')