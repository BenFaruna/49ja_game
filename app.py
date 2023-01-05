from threading import Event, Thread

from flask import Flask, render_template, request, redirect, url_for

from models import storage
from helper_functions import decide_number_color
from main import main, e

thread = Thread(target=main)
app = Flask(__name__)

@app.route('/')
def home():
    data = storage.all()
    data = [*data.values()][-1::-1]
    return render_template('index.html', data=data, color=decide_number_color, category="All")


@app.route('/category', strict_slashes=False)
def category():
    data = []
    hours = float(request.args.get('time', 0))
    occurence = int(request.args.get('occurrence', 1))
    if hours:
        temp_data = storage.time_diff(hours)
        if hours < 1:
            category = f'{int(hours * 60)} mins'
        else:
            category = f'{int(hours)} hours'
    else:
        temp_data = storage.all()
        category = 'All'

    temp_data = [*temp_data.values()][-1::-1]

    if occurence:
        for datum in temp_data:
            if (datum.r_count == occurence) or (datum.g_count == occurence) or (datum.b_count == occurence):
                data.append(datum)
    else:
        data = temp_data
    return render_template('index.html', data=data, category=category, color=decide_number_color)


@app.route('/start_scraping')
def start():
    global thread

    if not thread.is_alive():
        thread = Thread(target=main)
        e.clear()
        thread.start()
    return redirect(url_for('home'))


@app.route('/stop_scraping')
def stop():
    e.set()
    return redirect(url_for('home'))



if __name__ == '__main__':
    # thread.start()
    app.run(threaded=True, debug=True)
