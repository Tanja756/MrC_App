from flask import Blueprint, render_template

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def index():
    return render_template('pages/tasks.html', title='Заявки')


@pages_bp.route('/tasks')
def tasks_page():
    return render_template('pages/tasks.html', title='Заявки')


@pages_bp.route('/warehouse')
def warehouse_page():
    return render_template('pages/warehouse.html', title='Склад')


@pages_bp.route('/salary')
def salary_page():
    return render_template('pages/salary.html', title='Зарплата')


@pages_bp.route('/ppr')
def ppr_page():
    return render_template('pages/ppr.html', title='ППР')


@pages_bp.route('/upload')
def upload_page():
    return render_template('pages/upload.html', title='Загрузка')


@pages_bp.route('/route')
def route_page():
    return render_template('pages/route.html', title='Маршрутный лист')