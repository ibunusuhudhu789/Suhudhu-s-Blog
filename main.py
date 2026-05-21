from functools import wraps
from flask import Flask, render_template, redirect, url_for, flash, abort, request
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from forms import CreatePostForm, Login, RegisterForm, CommentForm
import hashlib
from smtplib import SMTP
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRETKEY")
ckeditor = CKEditor(app)
Bootstrap(app)

# CONNECT TO DB
db_url = os.getenv("DATABASE")

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


def gravatar_url(email):
    email = email.strip().lower()
    hash_email = hashlib.md5(
        email.encode()
    ).hexdigest()
    return f"https://www.gravatar.com/avatar/{hash_email}?d=retro&s=100"


app.jinja_env.globals['gravatar_url'] = gravatar_url

# CONNECT THE FLASK_LOGIN
login_manager = LoginManager()
login_manager.init_app(app)

new_or_edit = None


# CONFIGURE TABLES

class Users(UserMixin, db.Model):
    __tablename__ = "Users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    password = db.Column(db.String, unique=True, nullable=False)
    blog_post = relationship("BlogPost", back_populates="user")
    comments = relationship("Comments", back_populates="user")


class BlogPost(db.Model):
    __tablename__ = "BlogPost"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("Users.id"))
    user = relationship("Users", back_populates="blog_post")
    comments = relationship("Comments", back_populates="blog_post")


class Comments(db.Model):
    __tablename__ = "Comments"
    id = db.Column(db.Integer, nullable=False, primary_key=True)
    comment = db.Column(db.String, nullable=False)
    blog_id = db.Column(db.Integer, db.ForeignKey("BlogPost.id"))
    blog_post = relationship("BlogPost", back_populates="comments")
    author_id = db.Column(db.Integer, db.ForeignKey("Users.id"))
    user = relationship("Users", back_populates="comments")


with app.app_context():
    db.create_all()


def admin_only(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user.id == 1:
            return f(*args, **kwargs)
        else:
            return abort(403)

    return wrapper


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Users, user_id)


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        password = form.conform_password.data
        hashed_password = generate_password_hash(password, "pbkdf2:sha256", 30)
        new_user = Users(name=name, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = Login()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user = Users.query.filter_by(email=email).first()
        if user is None:
            flash("Incorrect email address. The user is not registered, try to register first.")
        else:
            if check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for("get_all_posts"))
            else:
                flash("Incorrect Password")
    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)
    comment = form.comments.data
    all_comments = Comments.query.all()
    blog_id = post_id
    if comment is not None:
        new_comment = Comments(comment=comment, blog_id=post_id, author_id=current_user.id)
        db.session.add(new_comment)
        db.session.commit()
        all_comments = Comments.query.all()
        return render_template("post.html", comment=all_comments, post=requested_post, form=form, id=blog_id)
    return render_template("post.html", post=requested_post, form=form, comment=all_comments, id=blog_id)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
@login_required
def contact():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone_no = request.form["num"]
        message = request.form["msg"]
        try:
            with SMTP("smtp.gmail.com", 587) as connection:
                connection.starttls()
                from_address = os.getenv("FROM")
                to_address = os.getenv("TO")
                pass_word = os.getenv("PASSWORD")
                connection.login(
                    user=from_address,
                    password=pass_word
                )
                connection.sendmail(
                    from_addr=from_address,
                    to_addrs=to_address,
                    msg=f"Subject:Need to contact you\n\n"
                        f"The details about the user are given below.\n\n"
                        f"Name: {name}\n"
                        f"Email: {email}\n"
                        f"Contact: {phone_no}\n\n"
                        f"Message:\n{message}\n\n"
                        f"Thank you!"
                )
                return redirect(url_for("get_all_posts"))
        except Exception as e:
            print(e)
            return str(e)

    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    global new_or_edit
    new_or_edit = None
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            date=date.today().strftime("%B %d, %Y"),
            author_id=current_user.id
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, new_or_edit=new_or_edit)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    global new_or_edit
    new_or_edit = "edit"
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, new_or_edit=new_or_edit)


@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
