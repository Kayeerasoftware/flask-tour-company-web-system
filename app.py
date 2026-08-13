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
    admin = User(name='Admin', email='admin@dehapiz.com',
                 password=generate_password_hash('admin123'), is_admin=True)
    db.session.add(admin)

    sample_tours = [
        Tour(
            title='Bwindi Gorilla Trekking Safari',
            destination='Bwindi Impenetrable Forest, Kigezi',
            description='Embark on a once-in-a-lifetime gorilla trekking experience deep inside Bwindi Impenetrable National Park — a UNESCO World Heritage Site. Trek through ancient montane forest to spend a magical hour with habituated mountain gorilla families. Bwindi is home to nearly half of the world\'s remaining mountain gorillas. The package includes park entry, gorilla permits, an experienced ranger guide, accommodation in a forest lodge, and transfers from Kampala.',
            duration_days=3, price=2500000, max_seats=8,
            image_url='https://images.unsplash.com/photo-1594803294810-c860e5d29e07?w=800'
        ),
        Tour(
            title='Queen Elizabeth Wildlife Safari',
            destination='Queen Elizabeth National Park, Western Uganda',
            description='Discover the incredible biodiversity of Queen Elizabeth National Park — one of Africa\'s most rewarding safari destinations. Enjoy game drives to spot lions, elephants, buffaloes, leopards, and the famous tree-climbing lions of Ishasha. A Kazinga Channel boat cruise brings you face-to-face with hippos, crocodiles, and hundreds of bird species. The park sits on the Equator and offers stunning views of the Rwenzori Mountains.',
            duration_days=4, price=1800000, max_seats=12,
            image_url='https://images.unsplash.com/photo-1516426122078-c23e76319801?w=800'
        ),
        Tour(
            title='Murchison Falls Adventure',
            destination='Murchison Falls National Park, Northern Uganda',
            description='Visit Uganda\'s largest national park and witness the world\'s most powerful waterfall — Murchison Falls, where the entire Nile River is forced through a 7-metre gorge with thunderous force. Enjoy thrilling game drives to see giraffes, elephants, lions, and buffaloes. A Nile boat cruise to the base of the falls is an absolute highlight. The park also offers excellent bird watching with over 450 recorded species.',
            duration_days=3, price=1500000, max_seats=14,
            image_url='https://images.unsplash.com/photo-1504432842672-1a79f78e4084?w=800'
        ),
        Tour(
            title='Rwenzori Mountains Hiking Expedition',
            destination='Rwenzori Mountains, Kasese',
            description='Conquer the legendary Mountains of the Moon — the Rwenzori Range, a UNESCO World Heritage Site and one of Africa\'s most dramatic mountain environments. Trek through afro-montane forests, bamboo zones, heather moorlands, and glacial valleys to reach Margherita Peak (5,109m), the third highest point in Africa. The Rwenzoris are famous for their unique giant flora including giant lobelias, groundsels, and heathers.',
            duration_days=7, price=3200000, max_seats=8,
            image_url='https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=800'
        ),
        Tour(
            title='Lake Bunyonyi & Kigezi Highlands',
            destination='Lake Bunyonyi, Kabale',
            description='Relax and explore the breathtakingly beautiful Lake Bunyonyi — one of Africa\'s deepest lakes, nestled among the terraced hills of Kigezi in southwestern Uganda. Paddle a dugout canoe between the lake\'s 29 islands, visit Punishment Island, and interact with the warm Bakiga community. The surrounding highlands offer spectacular hiking trails with panoramic views of the rolling green hills often called the \'Switzerland of Africa\'.',
            duration_days=3, price=950000, max_seats=16,
            image_url='https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?w=800'
        ),
        Tour(
            title='Kibale Chimpanzee Tracking',
            destination='Kibale National Park, Fort Portal',
            description='Track our closest relatives — chimpanzees — in Kibale National Park, which boasts the highest density of primates in Africa. Spend time with habituated chimpanzee communities as they forage, play, and socialise in the lush tropical rainforest. Kibale is also home to 12 other primate species including red colobus monkeys and L\'Hoest\'s monkeys. The package includes the Bigodi Wetland Sanctuary walk, a community-run ecotourism gem.',
            duration_days=2, price=1200000, max_seats=10,
            image_url='https://images.unsplash.com/photo-1540573133985-87b6da6d54a9?w=800'
        ),
        Tour(
            title='Source of the Nile & Jinja Adventure',
            destination='Jinja, Eastern Uganda',
            description='Visit Jinja — the adventure capital of East Africa — and stand at the legendary Source of the Nile, where the world\'s longest river begins its 6,650 km journey to the Mediterranean. Beyond history, Jinja offers world-class white-water rafting on Grade 5 rapids, bungee jumping, kayaking, quad biking, and horseback riding along the Nile banks. A perfect blend of history, culture, and adrenaline.',
            duration_days=2, price=750000, max_seats=20,
            image_url='https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800'
        ),
        Tour(
            title='Kidepo Valley Wilderness Safari',
            destination='Kidepo Valley National Park, Karamoja',
            description='Venture off the beaten path to Kidepo Valley National Park — consistently rated among Africa\'s top wilderness destinations. Located in the remote Karamoja region of northeastern Uganda, Kidepo offers raw, untouched savannah landscapes and exceptional wildlife including cheetahs, ostriches, bat-eared foxes, and large lion prides. Interact with the proud Karamojong and IK communities for an authentic cultural experience unlike anywhere else.',
            duration_days=4, price=2200000, max_seats=10,
            image_url='https://images.unsplash.com/photo-1547471080-7cc2caa01a7e?w=800'
        ),
        Tour(
            title='Ssese Islands Beach Getaway',
            destination='Ssese Islands, Lake Victoria',
            description='Escape to the tropical paradise of the Ssese Islands — an archipelago of 84 islands scattered across Lake Victoria, the world\'s second largest freshwater lake. Relax on pristine sandy beaches fringed by lush forest, go fishing with local fishermen, explore the islands by bicycle, and enjoy spectacular sunsets over the lake. The islands are accessible by ferry from Entebbe and offer a perfect weekend retreat from the city.',
            duration_days=3, price=850000, max_seats=18,
            image_url='https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800'
        ),
    ]
    db.session.add_all(sample_tours)
    db.session.commit()


with app.app_context():
    db.create_all()
    seed_data()


if __name__ == '__main__':
    app.run(debug=True)
