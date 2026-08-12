from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tour-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tours.db'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'


# ── Models ────────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    bookings = db.relationship('Booking', backref='user', lazy=True)


class Tour(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    max_seats = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(300), default='https://placehold.co/800x400?text=Tour')
    is_active = db.Column(db.Boolean, default=True)
    bookings = db.relationship('Booking', backref='tour', lazy=True)

    @property
    def booked_seats(self):
        return sum(b.seats for b in self.bookings if b.status != 'cancelled')

    @property
    def available_seats(self):
        return self.max_seats - self.booked_seats


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tour_id = db.Column(db.Integer, db.ForeignKey('tour.id'), nullable=False)
    seats = db.Column(db.Integer, nullable=False, default=1)
    travel_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='confirmed')  # confirmed / cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def total_price(self):
        return self.seats * self.tour.price


class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ── Helpers ───────────────────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Public Routes ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    featured = Tour.query.filter_by(is_active=True).limit(3).all()
    return render_template('index.html', tours=featured)


@app.route('/tours')
def tours():
    destination = request.args.get('destination', '')
    max_price = request.args.get('max_price', type=float)
    query = Tour.query.filter_by(is_active=True)
    if destination:
        query = query.filter(Tour.destination.ilike(f'%{destination}%'))
    if max_price:
        query = query.filter(Tour.price <= max_price)
    all_tours = query.all()
    return render_template('tours.html', tours=all_tours, destination=destination, max_price=max_price)


@app.route('/tours/<int:tour_id>')
def tour_detail(tour_id):
    tour = db.get_or_404(Tour, tour_id)
    return render_template('tour_detail.html', tour=tour)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        msg = ContactMessage(
            name=request.form['name'],
            email=request.form['email'],
            message=request.form['message']
        )
        db.session.add(msg)
        db.session.commit()
        flash('Your message has been sent! We will get back to you soon.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')


# ── Auth Routes ───────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        if User.query.filter_by(email=request.form['email']).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))
        user = User(
            name=request.form['name'],
            email=request.form['email'],
            password=generate_password_hash(request.form['password'])
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f'Welcome, {user.name}!', 'success')
        return redirect(url_for('index'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            flash(f'Welcome back, {user.name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# ── Booking Routes ────────────────────────────────────────────────────────────

@app.route('/book/<int:tour_id>', methods=['GET', 'POST'])
@login_required
def book_tour(tour_id):
    tour = db.get_or_404(Tour, tour_id)
    if request.method == 'POST':
        seats = int(request.form['seats'])
        travel_date = datetime.strptime(request.form['travel_date'], '%Y-%m-%d').date()
        if seats > tour.available_seats:
            flash(f'Only {tour.available_seats} seats available.', 'danger')
            return redirect(url_for('book_tour', tour_id=tour_id))
        if travel_date < datetime.today().date():
            flash('Travel date must be in the future.', 'danger')
            return redirect(url_for('book_tour', tour_id=tour_id))
        booking = Booking(user_id=current_user.id, tour_id=tour_id, seats=seats, travel_date=travel_date)
        db.session.add(booking)
        db.session.commit()
        flash('Booking confirmed! 🎉', 'success')
        return redirect(url_for('my_bookings'))
    return render_template('booking.html', tour=tour)


@app.route('/my-bookings')
@login_required
def my_bookings():
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).all()
    return render_template('my_bookings.html', bookings=bookings)


@app.route('/cancel-booking/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    booking = db.get_or_404(Booking, booking_id)
    if booking.user_id != current_user.id:
        abort(403)
    booking.status = 'cancelled'
    db.session.commit()
    flash('Booking cancelled.', 'info')
    return redirect(url_for('my_bookings'))


# ── Admin Routes ──────────────────────────────────────────────────────────────

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    stats = {
        'tours': Tour.query.count(),
        'users': User.query.count(),
        'bookings': Booking.query.filter_by(status='confirmed').count(),
        'revenue': db.session.query(db.func.sum(Tour.price * Booking.seats))
                     .join(Booking, Tour.id == Booking.tour_id)
                     .filter(Booking.status == 'confirmed').scalar() or 0
    }
    return render_template('admin/dashboard.html', stats=stats)


@app.route('/admin/tours')
@login_required
@admin_required
def admin_tours():
    all_tours = Tour.query.all()
    return render_template('admin/tours.html', tours=all_tours)


@app.route('/admin/tours/add', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_tour():
    if request.method == 'POST':
        tour = Tour(
            title=request.form['title'],
            destination=request.form['destination'],
            description=request.form['description'],
            duration_days=int(request.form['duration_days']),
            price=float(request.form['price']),
            max_seats=int(request.form['max_seats']),
            image_url=request.form['image_url'] or 'https://placehold.co/800x400?text=Tour'
        )
        db.session.add(tour)
        db.session.commit()
        flash('Tour added!', 'success')
        return redirect(url_for('admin_tours'))
    return render_template('admin/tour_form.html', tour=None)


@app.route('/admin/tours/edit/<int:tour_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_tour(tour_id):
    tour = db.get_or_404(Tour, tour_id)
    if request.method == 'POST':
        tour.title = request.form['title']
        tour.destination = request.form['destination']
        tour.description = request.form['description']
        tour.duration_days = int(request.form['duration_days'])
        tour.price = float(request.form['price'])
        tour.max_seats = int(request.form['max_seats'])
        tour.image_url = request.form['image_url'] or tour.image_url
        tour.is_active = 'is_active' in request.form
        db.session.commit()
        flash('Tour updated!', 'success')
        return redirect(url_for('admin_tours'))
    return render_template('admin/tour_form.html', tour=tour)


@app.route('/admin/tours/delete/<int:tour_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_tour(tour_id):
    tour = db.get_or_404(Tour, tour_id)
    db.session.delete(tour)
    db.session.commit()
    flash('Tour deleted.', 'warning')
    return redirect(url_for('admin_tours'))


@app.route('/admin/bookings')
@login_required
@admin_required
def admin_bookings():
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    return render_template('admin/bookings.html', bookings=bookings)


@app.route('/admin/messages')
@login_required
@admin_required
def admin_messages():
    messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).all()
    return render_template('admin/messages.html', messages=messages)


# ── Seed & Init ───────────────────────────────────────────────────────────────

def seed_data():
    if Tour.query.first():
        return
    admin = User(name='Admin', email='admin@tours.com',
                 password=generate_password_hash('admin123'), is_admin=True)
    db.session.add(admin)

    sample_tours = [
        Tour(title='Pyramids & Nile Adventure', destination='Egypt',
             description='Explore the ancient wonders of Egypt — the Great Pyramids of Giza, the Sphinx, and a relaxing Nile cruise through Luxor and Aswan.',
             duration_days=7, price=1200, max_seats=20,
             image_url='https://images.unsplash.com/photo-1539768942893-daf53e448371?w=800'),
        Tour(title='Safari in the Serengeti', destination='Tanzania',
             description='Witness the Great Migration and spot the Big Five on an unforgettable safari across the Serengeti plains.',
             duration_days=5, price=2500, max_seats=12,
             image_url='https://images.unsplash.com/photo-1516426122078-c23e76319801?w=800'),
        Tour(title='Santorini Sunset Escape', destination='Greece',
             description='Enjoy the iconic blue-domed churches, volcanic beaches, and breathtaking sunsets of Santorini island.',
             duration_days=6, price=1800, max_seats=15,
             image_url='https://images.unsplash.com/photo-1570077188670-e3a8d69ac5ff?w=800'),
        Tour(title='Tokyo & Mount Fuji', destination='Japan',
             description='Discover the perfect blend of ultra-modern Tokyo and the serene beauty of Mount Fuji and traditional Kyoto.',
             duration_days=10, price=3200, max_seats=10,
             image_url='https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=800'),
        Tour(title='Machu Picchu Trek', destination='Peru',
             description='Hike the legendary Inca Trail through cloud forests and mountain passes to reach the mystical citadel of Machu Picchu.',
             duration_days=8, price=2100, max_seats=14,
             image_url='https://images.unsplash.com/photo-1526392060635-9d6019884377?w=800'),
        Tour(title='Northern Lights in Iceland', destination='Iceland',
             description='Chase the Aurora Borealis, soak in geothermal hot springs, and explore dramatic volcanic landscapes.',
             duration_days=5, price=2800, max_seats=16,
             image_url='https://images.unsplash.com/photo-1531366936337-7c912a4589a7?w=800'),
    ]
    db.session.add_all(sample_tours)
    db.session.commit()


with app.app_context():
    db.create_all()
    seed_data()


if __name__ == '__main__':
    app.run(debug=True)
